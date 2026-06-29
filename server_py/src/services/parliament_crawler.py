"""
Background crawler for Scottish Parliament committee meeting transcripts.

Populates sp_committee_items with agenda items + full speech text,
enabling FTS-backed search_scottish_committee_transcripts.

Two modes:
  crawl_sp_new_meetings  — rolling, runs daily, fetches recent listing page
  backfill_session7      — one-shot, fetches date-windowed listing pages
                           back to Session 7 start (2026-05-06)
"""
import asyncio
import json
import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import text

from ..database import async_session_maker
from ..agent.tools import (
    _parse_sp_listing_meetings,
    _parse_sp_meeting_page,
    _parse_sp_transcript_page,
    _SP_OR_BASE,
)

logger = logging.getLogger("crawler")

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_REQ_DELAY = 1.2          # seconds between HTTP requests
_BACKFILL_DELAY = 1.5     # slightly slower during backfill
_SESSION7_START = date(2026, 5, 6)  # Holyrood reassembly after May 2026 election


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str):
    """Parse YYYY-MM-DD string to date; return None on failure."""
    try:
        return date.fromisoformat(date_str)
    except Exception:
        return None


async def _url_exists(session, url: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM sp_committee_items WHERE url = :url LIMIT 1"),
        {"url": url},
    )
    return result.scalar() is not None


async def _meeting_iob_exists(session, meeting_id: str, iob_id: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM sp_committee_items WHERE meeting_id = :m AND iob_id = :i LIMIT 1"),
        {"m": meeting_id, "i": iob_id},
    )
    return result.scalar() is not None


async def _insert_item(session, row: dict) -> None:
    await session.execute(
        text(
            "INSERT INTO sp_committee_items "
            "(meeting_id, slug, iob_id, committee_code, committee_name, meeting_date, "
            " agenda_item_title, url, speeches, full_text, fetched_at) "
            "VALUES (:meeting_id, :slug, :iob_id, :committee_code, :committee_name, :meeting_date, "
            "        :agenda_item_title, :url, CAST(:speeches AS jsonb), :full_text, :fetched_at) "
            "ON CONFLICT ON CONSTRAINT uq_sp_meeting_iob DO NOTHING"
        ),
        row,
    )


def _build_full_text(committee_name: str, agenda_title: str, speeches: list) -> str:
    parts = []
    if committee_name:
        parts.append(committee_name)
    if agenda_title:
        parts.append(agenda_title)
    for s in speeches:
        speaker = s.get("speaker", "")
        text_body = s.get("text", "")
        if speaker:
            parts.append(f"{speaker}: {text_body}")
        elif text_body:
            parts.append(text_body)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Core: fetch one meeting's transcript items and store them
# ---------------------------------------------------------------------------

async def _process_meeting(client: httpx.AsyncClient, meeting: dict) -> int:
    """Fetch a meeting page, then each unseen transcript item. Returns rows inserted."""
    slug = meeting["slug"]
    meeting_id = meeting["meeting_id"]
    meeting_date = _parse_date(meeting.get("date", ""))

    # Fetch meeting page to get agenda items + committee name
    meeting_url = meeting.get("url") or f"{_SP_OR_BASE}/{slug}?meeting={meeting_id}"
    try:
        resp = await client.get(meeting_url, headers=_HEADERS, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning(f"[Crawler] Failed to fetch meeting page {meeting_url}: {exc}")
        return 0

    detail = _parse_sp_meeting_page(resp.text, slug, meeting_id)
    committee_name = detail.get("committee_name") or meeting.get("committee_code", "")
    committee_code = meeting.get("committee_code", "")
    agenda_items = detail.get("agenda_items") or []

    if not agenda_items:
        logger.debug(f"[Crawler] No agenda items for meeting {meeting_id}/{slug}")
        return 0

    inserted = 0
    async with async_session_maker() as session:
        for item in agenda_items:
            iob_id = item["iob_id"]
            transcript_url = item["url"]

            if await _meeting_iob_exists(session, meeting_id, iob_id):
                continue

            await asyncio.sleep(_REQ_DELAY)
            try:
                tr = await client.get(transcript_url, headers=_HEADERS, follow_redirects=True, timeout=20.0)
                tr.raise_for_status()
            except Exception as exc:
                logger.warning(f"[Crawler] Failed to fetch transcript {transcript_url}: {exc}")
                continue

            parsed = _parse_sp_transcript_page(tr.text, transcript_url)
            speeches = parsed.get("speeches") or []
            agenda_title = item.get("title", "")
            full_text = _build_full_text(committee_name, agenda_title, speeches)

            row = {
                "meeting_id": meeting_id,
                "slug": slug,
                "iob_id": iob_id,
                "committee_code": committee_code or None,
                "committee_name": committee_name or None,
                "meeting_date": meeting_date,
                "agenda_item_title": agenda_title[:512] if agenda_title else None,
                "url": transcript_url,
                "speeches": json.dumps(speeches),
                "full_text": full_text or None,
                "fetched_at": datetime.utcnow(),
            }
            await _insert_item(session, row)
            await session.commit()
            inserted += 1
            logger.info(
                f"[Crawler] Stored {committee_name} | {agenda_title[:60]} "
                f"(meeting={meeting_id} iob={iob_id})"
            )

    return inserted


# ---------------------------------------------------------------------------
# Rolling crawl: fetch listing page, process new meetings
# ---------------------------------------------------------------------------

async def crawl_sp_new_meetings() -> int:
    """Fetch the current SP OR listing page and store any unseen committee meetings."""
    logger.info("[Crawler] Rolling crawl starting...")
    total = 0
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(_SP_OR_BASE, headers=_HEADERS, follow_redirects=True)
            resp.raise_for_status()
            meetings = _parse_sp_listing_meetings(resp.text)
            logger.info(f"[Crawler] Listing page returned {len(meetings)} committee meetings")

            # Filter out meetings already fully stored (check by meeting_id presence)
            async with async_session_maker() as session:
                new_meetings = []
                for m in meetings:
                    result = await session.execute(
                        text("SELECT COUNT(*) FROM sp_committee_items WHERE meeting_id = :m"),
                        {"m": m["meeting_id"]},
                    )
                    if (result.scalar() or 0) == 0:
                        new_meetings.append(m)

            logger.info(f"[Crawler] {len(new_meetings)} meetings not yet in DB")
            for meeting in new_meetings:
                await asyncio.sleep(_REQ_DELAY)
                n = await _process_meeting(client, meeting)
                total += n

    except Exception as exc:
        logger.error(f"[Crawler] Rolling crawl error: {exc}")

    logger.info(f"[Crawler] Rolling crawl complete — {total} items stored")
    return total


# ---------------------------------------------------------------------------
# Backfill: date-windowed listing pages from Session 7 start
# ---------------------------------------------------------------------------

async def backfill_session7() -> int:
    """Backfill all Session 7 committee meetings via date-windowed listing pages.

    Iterates two-week windows from SESSION7_START to today, fetching the listing
    page with showCommittee=true&dtDateFrom=X&dtDateTo=Y for each window.
    Known-to-work approach for the SP Official Report listing.
    """
    logger.info("[Crawler] Session 7 backfill starting...")
    total = 0
    today = date.today()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            window_start = _SESSION7_START
            while window_start < today:
                window_end = min(window_start + timedelta(days=13), today)
                date_from = window_start.strftime("%Y-%m-%d")
                date_to = window_end.strftime("%Y-%m-%d")

                params = {
                    "showCommittee": "true",
                    "dtDateFrom": date_from,
                    "dtDateTo": date_to,
                }
                url = _SP_OR_BASE
                try:
                    await asyncio.sleep(_BACKFILL_DELAY)
                    resp = await client.get(url, params=params, headers=_HEADERS, follow_redirects=True)
                    resp.raise_for_status()
                    meetings = _parse_sp_listing_meetings(resp.text)
                    logger.info(
                        f"[Crawler] Backfill {date_from}→{date_to}: {len(meetings)} meetings found"
                    )

                    async with async_session_maker() as session:
                        new_meetings = []
                        for m in meetings:
                            result = await session.execute(
                                text("SELECT COUNT(*) FROM sp_committee_items WHERE meeting_id = :m"),
                                {"m": m["meeting_id"]},
                            )
                            if (result.scalar() or 0) == 0:
                                new_meetings.append(m)

                    for meeting in new_meetings:
                        await asyncio.sleep(_BACKFILL_DELAY)
                        n = await _process_meeting(client, meeting)
                        total += n

                except Exception as exc:
                    logger.warning(f"[Crawler] Backfill window {date_from}→{date_to} error: {exc}")

                window_start = window_end + timedelta(days=1)

    except Exception as exc:
        logger.error(f"[Crawler] Backfill error: {exc}")

    logger.info(f"[Crawler] Session 7 backfill complete — {total} items stored")
    return total


# ---------------------------------------------------------------------------
# Background loop
# ---------------------------------------------------------------------------

async def background_crawl_loop(interval_seconds: int = 86400) -> None:
    """Run rolling crawl daily. Designed to be launched as an asyncio task."""
    while True:
        try:
            await crawl_sp_new_meetings()
        except Exception as exc:
            logger.error(f"[Crawler] Unhandled error in crawl loop: {exc}")
        await asyncio.sleep(interval_seconds)
