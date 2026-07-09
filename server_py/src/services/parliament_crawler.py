"""
Background crawler for Scottish Parliament committee meeting transcripts.

Populates sp_committee_items with agenda items + full speech text,
enabling FTS-backed search_scottish_committee_transcripts.

Two modes:
  crawl_sp_new_meetings  — rolling, runs daily, fetches recent listing page
  backfill_sessions      — one-shot, fetches date-windowed listing pages
                           back to Session 6 start (2021-05-13), covering
                           Session 6 and Session 7
"""
import asyncio
import json
import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import text

from ..config import settings
from ..database import async_session_maker
from . import sptv_client as _sptv
from ..agent.tools import (
    _fetch_sp_page_with_retry,
    _parse_sp_listing_meetings,
    _parse_sp_meeting_page,
    _parse_sp_plenary_meetings,
    _parse_sp_plenary_transcript,
    _parse_sp_transcript_page,
    _SP_OR_BASE,
)

logger = logging.getLogger("crawler")

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_REQ_DELAY = 1.2          # seconds between HTTP requests
_BACKFILL_DELAY = 1.5     # slightly slower during backfill
_SESSION6_START = date(2021, 5, 13)  # Holyrood first met after May 2021 election
_SESSION7_START = date(2026, 5, 6)   # Holyrood reassembly after May 2026 election
_BACKFILL_START = _SESSION6_START    # earliest session to backfill


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

async def backfill_sessions() -> int:
    """Backfill all committee meetings via date-windowed listing pages.

    Iterates two-week windows from _BACKFILL_START (Session 6 start) to today,
    fetching the listing page with showCommittee=true&dtDateFrom=X&dtDateTo=Y
    for each window. Covers Session 6 and Session 7; the inter-session
    dissolution gap simply returns empty windows.
    Known-to-work approach for the SP Official Report listing.
    """
    logger.info("[Crawler] Session backfill starting...")
    total = 0
    today = date.today()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            window_start = _BACKFILL_START
            while window_start < today:
                window_end = min(window_start + timedelta(days=13), today)
                date_from = window_start.strftime("%Y-%m-%d")
                date_to = window_end.strftime("%Y-%m-%d")

                params = {
                    "showCommittee": "true",
                    # Without dateSelect=custom the SP Official Report search defaults
                    # to the current session and silently ignores dtDateFrom/dtDateTo
                    # outside it — so older sessions (e.g. Session 6) return nothing.
                    "dateSelect": "custom",
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

    logger.info(f"[Crawler] Session backfill complete — {total} items stored")
    return total


# ---------------------------------------------------------------------------
# Plenary (chamber) crawl — mirrors the committee pipeline into sp_plenary_items
# ---------------------------------------------------------------------------

async def _plenary_meeting_iob_exists(session, meeting_id: str, iob_id: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM sp_plenary_items WHERE meeting_id = :m AND iob_id = :i LIMIT 1"),
        {"m": meeting_id, "i": iob_id},
    )
    return result.scalar() is not None


async def _insert_plenary_item(session, row: dict) -> None:
    await session.execute(
        text(
            "INSERT INTO sp_plenary_items "
            "(meeting_id, slug, iob_id, committee_code, committee_name, meeting_date, "
            " agenda_item_title, url, speeches, full_text, fetched_at) "
            "VALUES (:meeting_id, :slug, :iob_id, :committee_code, :committee_name, :meeting_date, "
            "        :agenda_item_title, :url, CAST(:speeches AS jsonb), :full_text, :fetched_at) "
            "ON CONFLICT ON CONSTRAINT uq_sp_plenary_meeting_iob DO NOTHING"
        ),
        row,
    )


async def _process_plenary_meeting(client: httpx.AsyncClient, meeting: dict) -> int:
    """Fetch a plenary meeting page, then each unseen agenda item. Returns rows inserted.

    Reuses _parse_sp_meeting_page (works for plenary as-is) for agenda items, and the
    dedicated _parse_sp_plenary_transcript for the item pages. Transcript fetches use
    retry-with-backoff and reject undersized (Cloudflare 524) error pages.
    """
    slug = meeting["slug"]
    meeting_id = meeting["meeting_id"]
    meeting_date = _parse_date(meeting.get("date", ""))

    meeting_url = meeting.get("url") or f"{_SP_OR_BASE}/{slug}?meeting={meeting_id}"
    try:
        resp = await client.get(meeting_url, headers=_HEADERS, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning(f"[Crawler] Failed to fetch plenary meeting page {meeting_url}: {exc}")
        return 0

    detail = _parse_sp_meeting_page(resp.text, slug, meeting_id)
    # Plenary sittings have no committee; use the listing label as the display name.
    committee_name = meeting.get("committee_name") or detail.get("committee_name") or "Meeting of Parliament"
    committee_code = meeting.get("committee_code", "MOP")
    agenda_items = detail.get("agenda_items") or []

    if not agenda_items:
        logger.debug(f"[Crawler] No agenda items for plenary meeting {meeting_id}/{slug}")
        return 0

    inserted = 0
    async with async_session_maker() as session:
        for item in agenda_items:
            iob_id = item["iob_id"]
            transcript_url = item["url"]

            if await _plenary_meeting_iob_exists(session, meeting_id, iob_id):
                continue

            await asyncio.sleep(_REQ_DELAY)
            try:
                # Retry/backoff; rejects <20 KB (524) error pages.
                page_html = await _fetch_sp_page_with_retry(client, transcript_url)
            except Exception as exc:
                logger.warning(f"[Crawler] Failed to fetch plenary transcript {transcript_url}: {exc}")
                continue

            agenda_title = item.get("title", "")
            parsed = _parse_sp_plenary_transcript(page_html, transcript_url, agenda_title or None)
            speeches = parsed.get("speeches") or []
            if not speeches:
                logger.debug(f"[Crawler] No speeches parsed for plenary {transcript_url}; skipping")
                continue
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
            await _insert_plenary_item(session, row)
            await session.commit()
            inserted += 1
            logger.info(
                f"[Crawler] Stored plenary | {agenda_title[:60]} "
                f"(meeting={meeting_id} iob={iob_id}, {len(speeches)} speeches)"
            )

    # After the meeting's agenda items are stored, cache its SP TV captions once.
    if inserted and settings.enable_video_deeplinks:
        await asyncio.sleep(_REQ_DELAY)
        await _capture_meeting_captions(client, meeting_id, meeting_date)

    return inserted


async def crawl_sp_new_plenary() -> int:
    """Fetch the current SP OR listing page and store any unseen plenary sittings."""
    logger.info("[Crawler] Rolling plenary crawl starting...")
    total = 0
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {"showPlenary": "true"}
            resp = await client.get(_SP_OR_BASE, params=params, headers=_HEADERS, follow_redirects=True)
            resp.raise_for_status()
            meetings = _parse_sp_plenary_meetings(resp.text)
            logger.info(f"[Crawler] Listing page returned {len(meetings)} plenary sittings")

            async with async_session_maker() as session:
                new_meetings = []
                for m in meetings:
                    result = await session.execute(
                        text("SELECT COUNT(*) FROM sp_plenary_items WHERE meeting_id = :m"),
                        {"m": m["meeting_id"]},
                    )
                    if (result.scalar() or 0) == 0:
                        new_meetings.append(m)

            logger.info(f"[Crawler] {len(new_meetings)} plenary sittings not yet in DB")
            for meeting in new_meetings:
                await asyncio.sleep(_REQ_DELAY)
                total += await _process_plenary_meeting(client, meeting)

    except Exception as exc:
        logger.error(f"[Crawler] Rolling plenary crawl error: {exc}")

    logger.info(f"[Crawler] Rolling plenary crawl complete — {total} items stored")
    return total


async def backfill_plenary() -> int:
    """Backfill all plenary (chamber) sittings via date-windowed listing pages.

    Near-copy of backfill_sessions() using showPlenary=true. dateSelect=custom is
    mandatory or the endpoint silently returns only the current session.
    """
    logger.info("[Crawler] Plenary backfill starting...")
    total = 0
    today = date.today()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            window_start = _BACKFILL_START
            while window_start < today:
                window_end = min(window_start + timedelta(days=13), today)
                date_from = window_start.strftime("%Y-%m-%d")
                date_to = window_end.strftime("%Y-%m-%d")

                params = {
                    "showPlenary": "true",
                    # dateSelect=custom is mandatory — without it the SP Official Report
                    # search defaults to the current session and ignores dtDateFrom/dtDateTo.
                    "dateSelect": "custom",
                    "dtDateFrom": date_from,
                    "dtDateTo": date_to,
                }
                try:
                    await asyncio.sleep(_BACKFILL_DELAY)
                    resp = await client.get(_SP_OR_BASE, params=params, headers=_HEADERS, follow_redirects=True)
                    resp.raise_for_status()
                    meetings = _parse_sp_plenary_meetings(resp.text)
                    logger.info(
                        f"[Crawler] Plenary backfill {date_from}→{date_to}: {len(meetings)} sittings found"
                    )

                    async with async_session_maker() as session:
                        new_meetings = []
                        for m in meetings:
                            result = await session.execute(
                                text("SELECT COUNT(*) FROM sp_plenary_items WHERE meeting_id = :m"),
                                {"m": m["meeting_id"]},
                            )
                            if (result.scalar() or 0) == 0:
                                new_meetings.append(m)

                    for meeting in new_meetings:
                        await asyncio.sleep(_BACKFILL_DELAY)
                        total += await _process_plenary_meeting(client, meeting)

                except Exception as exc:
                    logger.warning(f"[Crawler] Plenary backfill window {date_from}→{date_to} error: {exc}")

                window_start = window_end + timedelta(days=1)

    except Exception as exc:
        logger.error(f"[Crawler] Plenary backfill error: {exc}")

    logger.info(f"[Crawler] Plenary backfill complete — {total} items stored")
    return total


# ---------------------------------------------------------------------------
# SP TV video captions — resolve plenary meeting → cache caption transcript
# (gated behind ENABLE_VIDEO_DEEPLINKS; see bots/parliament/VIDEO_DEEPLINK_PLAN.md)
# ---------------------------------------------------------------------------

async def _video_caption_exists(session, meeting_id: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM sp_video_captions WHERE meeting_id = :m LIMIT 1"),
        {"m": meeting_id},
    )
    return result.scalar() is not None


async def _capture_meeting_captions(
    client: httpx.AsyncClient, meeting_id: str, meeting_date, slug: str | None = None
) -> bool:
    """Resolve a plenary meeting's SP TV event, cache its captions. Idempotent.

    Stores one row per event (ON CONFLICT event_id DO NOTHING). Records a
    caption_ok=False row when an event resolves but has no subtitle track, so it
    isn't retried. Meetings with no resolvable event are simply skipped (retried
    on the next backfill). Fail-soft — never raises.
    """
    if not meeting_date:
        return False
    try:
        async with async_session_maker() as session:
            if await _video_caption_exists(session, meeting_id):
                return False

        resolved = await _sptv.resolve_event(client, meeting_date, slug)
        if not resolved:
            return False
        event_id, sptv_slug = resolved

        pm = await _sptv.get_playback_model(client, event_id)
        if not pm:
            return False

        cap = await _sptv.fetch_caption_transcript(client, pm)
        start_utc = cap.start_time_utc.replace(tzinfo=None) if cap.start_time_utc else None

        async with async_session_maker() as session:
            await session.execute(
                text(
                    "INSERT INTO sp_video_captions "
                    "(meeting_id, event_id, slug, meeting_date, start_time_utc, is_youtube, "
                    " youtube_url, transcript, offset_index, caption_ok, fetched_at) "
                    "VALUES (:meeting_id, :event_id, :slug, :meeting_date, :start_time_utc, "
                    "        :is_youtube, :youtube_url, :transcript, CAST(:offset_index AS jsonb), "
                    "        :caption_ok, :fetched_at) "
                    "ON CONFLICT (event_id) DO NOTHING"
                ),
                {
                    "meeting_id": meeting_id,
                    "event_id": event_id,
                    "slug": sptv_slug,
                    "meeting_date": meeting_date,
                    "start_time_utc": start_utc,
                    "is_youtube": pm.is_youtube,
                    "youtube_url": pm.youtube_url or None,
                    "transcript": cap.transcript or None,
                    "offset_index": json.dumps(cap.offset_index) if cap.offset_index else None,
                    "caption_ok": cap.caption_ok,
                    "fetched_at": datetime.utcnow(),
                },
            )
            await session.commit()
        logger.info(
            f"[Crawler] Cached SP TV captions for meeting {meeting_id} "
            f"(event {event_id}, caption_ok={cap.caption_ok})"
        )
        return cap.caption_ok
    except Exception as exc:  # noqa: BLE001 — video is best-effort
        logger.warning(f"[Crawler] Caption capture failed for meeting {meeting_id}: {exc}")
        return False


async def backfill_captions() -> int:
    """One-shot: cache SP TV captions for every plenary meeting already crawled.

    Iterates distinct (meeting_id, meeting_date) in sp_plenary_items not yet in
    sp_video_captions. Rate-limited like the other backfills; runs after
    backfill_plenary() so it doesn't hit the SP origin concurrently. No-op unless
    ENABLE_VIDEO_DEEPLINKS is set.
    """
    if not settings.enable_video_deeplinks:
        logger.info("[Crawler] Caption backfill skipped (ENABLE_VIDEO_DEEPLINKS off)")
        return 0

    logger.info("[Crawler] Caption backfill starting...")
    captured = 0
    try:
        async with async_session_maker() as session:
            rows = await session.execute(text(
                "SELECT DISTINCT p.meeting_id, p.meeting_date, p.slug "
                "FROM sp_plenary_items p "
                "LEFT JOIN sp_video_captions v ON v.meeting_id = p.meeting_id "
                "WHERE v.meeting_id IS NULL AND p.meeting_date IS NOT NULL "
                "ORDER BY p.meeting_date"
            ))
            meetings = [(r[0], r[1]) for r in rows.all()]

        logger.info(f"[Crawler] Caption backfill: {len(meetings)} plenary meetings to resolve")
        async with httpx.AsyncClient(timeout=60.0) as client:
            for meeting_id, meeting_date in meetings:
                await asyncio.sleep(_BACKFILL_DELAY)
                # slug is derived from date inside _capture_meeting_captions;
                # the sp_plenary_items slug is the Official Report slug, not SP TV's.
                if await _capture_meeting_captions(client, str(meeting_id), meeting_date):
                    captured += 1
    except Exception as exc:
        logger.error(f"[Crawler] Caption backfill error: {exc}")

    logger.info(f"[Crawler] Caption backfill complete — {captured} meetings with captions cached")
    return captured


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


async def background_plenary_crawl_loop(interval_seconds: int = 86400) -> None:
    """Run rolling plenary crawl daily. Designed to be launched as an asyncio task.

    Offset from the committee loop so the two do not hit the origin concurrently.
    """
    # Stagger the first run so plenary and committee crawls don't overlap on startup.
    await asyncio.sleep(300)
    while True:
        try:
            await crawl_sp_new_plenary()
        except Exception as exc:
            logger.error(f"[Crawler] Unhandled error in plenary crawl loop: {exc}")
        await asyncio.sleep(interval_seconds)
