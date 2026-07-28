"""Parliamentary research tools: TWFY/Hansard, UK Parliament APIs, Scottish Parliament
Official Report parsers, and the SP committee transcript DB search."""

import json
import logging
import time
import uuid
from typing import Callable, Optional

import httpx

from ...config import settings
from ..provider_factory import get_request_provider_config
from ._util import _emit

logger = logging.getLogger("agent")

import re as _re

_TWFY_API_BASE = "https://www.theyworkforyou.com/api"
_SP_OR_BASE = "https://www.parliament.scot/chamber-and-committees/official-report/search-what-was-said-in-parliament"

# Scottish Parliament (Holyrood) session → meeting-date window (inclusive).
# Each session spans one parliamentary term between elections; boundaries use the
# election / dissolution dates so adjacent sessions don't overlap. The current
# session has an open upper bound (None). Used to translate the frontend session
# filter into date_from/date_to on the date-capable SP search tools.
SP_SESSIONS: dict[int, tuple[str, Optional[str]]] = {
    1: ("1999-05-06", "2003-05-06"),
    2: ("2003-05-07", "2007-05-02"),
    3: ("2007-05-03", "2011-05-04"),
    4: ("2011-05-05", "2016-05-04"),
    5: ("2016-05-05", "2021-05-05"),
    6: ("2021-05-06", "2026-05-05"),
    7: ("2026-05-06", None),  # current term — open-ended
}


def _sessions_date_window(sessions) -> tuple[Optional[str], Optional[str]]:
    """Collapse a list of selected session numbers into a single (from, to) window.

    Returns the earliest start and latest end across the selected sessions. If any
    selected session is open-ended (the current term), the upper bound is None.
    Unknown session numbers are ignored; an empty/invalid selection yields (None, None).
    """
    if not sessions:
        return None, None
    starts, ends, open_ended = [], [], False
    for s in sessions:
        rng = SP_SESSIONS.get(s)
        if not rng:
            continue
        starts.append(rng[0])
        if rng[1] is None:
            open_ended = True
        else:
            ends.append(rng[1])
    if not starts:
        return None, None
    date_from = min(starts)
    date_to = None if open_ended else (max(ends) if ends else None)
    return date_from, date_to


def _strip_html(text: str) -> str:
    import html as _html
    clean = _re.sub(r"<[^>]+>", " ", text or "")
    return _html.unescape(clean).strip()


def _parse_sp_listing_meetings(html: str) -> list[dict]:
    """Extract committee meeting links from the SP Official Report listing page.

    Finds href attributes pointing to individual meeting pages (slug?meeting=ID)
    and returns committee meetings only — plenary (meeting-of-parliament-*) are excluded.
    """
    pattern = _re.compile(
        r'href="[^"]*?official-report/search-what-was-said-in-parliament/([^"?/\s]+)\?meeting=(\d+)"',
        _re.IGNORECASE,
    )
    seen: dict[tuple, dict] = {}
    for slug, meeting_id in pattern.findall(html):
        if "meeting-of-parliament" in slug.lower():
            continue
        key = (slug, meeting_id)
        if key in seen:
            continue
        parts = slug.split("-")
        if len(parts) >= 4:
            day, month, year = parts[-3], parts[-2], parts[-1]
            committee_code = "-".join(parts[:-3])
            date_str = f"{year}-{month}-{day}"
        else:
            committee_code = slug
            date_str = ""
        seen[key] = {
            "slug": slug,
            "meeting_id": meeting_id,
            "committee_code": committee_code,
            "date": date_str,
            "url": f"{_SP_OR_BASE}/{slug}?meeting={meeting_id}",
        }
    return sorted(seen.values(), key=lambda x: x.get("date", ""), reverse=True)


def _parse_sp_plenary_meetings(html: str) -> list[dict]:
    """Extract plenary (chamber) meeting links from the SP Official Report listing page.

    The committee listing parser (`_parse_sp_listing_meetings`) explicitly *excludes*
    plenary sittings (slugs of the form `meeting-of-parliament-DD-MM-YYYY`). This variant
    INCLUDES only those, for the plenary crawl pipeline.
    """
    pattern = _re.compile(
        r'href="[^"]*?official-report/search-what-was-said-in-parliament/([^"?/\s]+)\?meeting=(\d+)"',
        _re.IGNORECASE,
    )
    seen: dict[tuple, dict] = {}
    for slug, meeting_id in pattern.findall(html):
        if "meeting-of-parliament" not in slug.lower():
            continue
        key = (slug, meeting_id)
        if key in seen:
            continue
        parts = slug.split("-")
        if len(parts) >= 4:
            day, month, year = parts[-3], parts[-2], parts[-1]
            date_str = f"{year}-{month}-{day}"
        else:
            date_str = ""
        seen[key] = {
            "slug": slug,
            "meeting_id": meeting_id,
            # Plenary sittings have no committee; use a stable label for the DB column.
            "committee_code": "MOP",
            "committee_name": "Meeting of Parliament",
            "date": date_str,
            "url": f"{_SP_OR_BASE}/{slug}?meeting={meeting_id}",
        }
    return sorted(seen.values(), key=lambda x: x.get("date", ""), reverse=True)


def _parse_sp_meeting_page(html: str, slug: str, meeting_id: str) -> dict:
    """Extract committee name and agenda items (with iob_ids) from a SP meeting page."""
    h1_match = _re.search(r"<h1[^>]*>(.*?)</h1>", html, _re.IGNORECASE | _re.DOTALL)
    committee_name = _strip_html(h1_match.group(1)).strip() if h1_match else ""
    committee_name = _re.sub(r"\s*\[Draft\]", "", committee_name, flags=_re.IGNORECASE)
    committee_name = _re.sub(r",?\s*Meeting date:.*", "", committee_name, flags=_re.IGNORECASE).strip()
    if not committee_name:
        title_match = _re.search(r"<title[^>]*>([^<]+)</title>", html, _re.IGNORECASE)
        if title_match:
            committee_name = _strip_html(title_match.group(1)).split("|")[0].strip()

    # Find all <a> elements whose href contains ?meeting=ID&iob=IOBID
    link_pattern = _re.compile(
        r'<a\s[^>]*href="[^"]*meeting='
        + _re.escape(meeting_id)
        + r'(?:&amp;|&)iob=(\d+)[^"]*"[^>]*>(.*?)</a>',
        _re.DOTALL | _re.IGNORECASE,
    )
    agenda_items = []
    seen_iobs: set[str] = set()
    for iob_id, link_html in link_pattern.findall(html):
        if iob_id in seen_iobs:
            continue
        seen_iobs.add(iob_id)
        item_title = _strip_html(link_html).strip() or f"Item {iob_id}"
        agenda_items.append({
            "iob_id": iob_id,
            "title": item_title[:200],
            "url": f"{_SP_OR_BASE}/{slug}?meeting={meeting_id}&iob={iob_id}",
        })
    return {"committee_name": committee_name, "agenda_items": agenda_items}


def _parse_sp_plenary_transcript(html: str, url: str, agenda_title: str | None = None) -> dict:
    """Parse a Scottish Parliament plenary Official Report page into attributed speeches.

    Plenary markup differs from committee pages: each contribution is a
    <p id="orscontributions_..."> element whose speaker is the first /msps/ anchor.
    """
    m = _re.search(r"<main[^>]*>(.*?)</main>", html, _re.S | _re.I)
    main = m.group(1) if m else html

    title_match = _re.search(r"<title[^>]*>([^<]+)</title>", html, _re.I)
    page_title = _strip_html(title_match.group(1)).split("|")[0].strip() if title_match else ""

    # Scope to the requested agenda item: from its <h2 class="h3"> to the next one
    if agenda_title:
        hm = _re.search(r'<h2[^>]*class="h3[^"]*"[^>]*>\s*' + _re.escape(agenda_title), main, _re.I)
        if hm:
            rest = main[hm.end():]
            nxt = _re.search(r'<h2[^>]*class="h3', rest, _re.I)
            main = rest[: nxt.start()] if nxt else rest

    parts = _re.split(r'<p\s+id="orscontributions_[^"]*"[^>]*>', main)
    speeches: list[dict] = []
    for block in parts[1:]:  # parts[0] is preamble before the first contribution
        spk = _re.search(r'<a\s[^>]*href="/msps/[^"]*"[^>]*>(.*?)</a>', block, _re.S | _re.I)
        speaker = _strip_html(spk.group(1)) if spk else ""
        body = block[spk.end():] if spk else block
        body = _re.sub(r'<div class="share-float-right">.*?</div>\s*</div>\s*</div>\s*</div>',
                       ' ', body, flags=_re.S | _re.I)
        texts = []
        for p in _re.findall(r'<p[^>]*>(.*?)</p>', body, _re.S | _re.I):
            t = _strip_html(p)
            if not t or _re.fullmatch(r'\d{1,2}:\d{2}', t):
                continue
            texts.append(t)
        text = " ".join(texts).strip()
        if text:
            speeches.append({"speaker": speaker, "text": text[:3000]})

    return {
        "page_title": page_title,
        "url": url,
        "speeches": speeches,
        "total_speeches": len(speeches),
    }


# Cap on the speeches a *retrieval tool* hands back to the Worker. An agenda item
# can run to several hundred contributions of up to 3000 chars each, and if the
# stored agenda title is missing the parser falls back to the whole meeting page —
# a single result then approaches the (context-scaled) summarisation threshold
# without tripping it, and four of them stack into a prefill large enough to stall
# the provider past the stream read timeout.
#
# Deliberately NOT applied inside _parse_sp_plenary_transcript: the crawler parses
# the same pages to build the FTS `full_text`, which must stay complete.
_MAX_RETURNED_SPEECHES = 150


def _cap_speeches(parsed: dict) -> dict:
    """Trim a parsed transcript's speech list to _MAX_RETURNED_SPEECHES, in place.

    `total_speeches` keeps the true count so the model can see what it is missing,
    and a note tells it how to narrow the request.
    """
    speeches = parsed.get("speeches") or []
    if len(speeches) <= _MAX_RETURNED_SPEECHES:
        return parsed
    logger.info(
        f"[Parliament] Capping transcript result: {len(speeches)} -> "
        f"{_MAX_RETURNED_SPEECHES} speeches ({parsed.get('url', '')})"
    )
    parsed["speeches"] = speeches[:_MAX_RETURNED_SPEECHES]
    parsed["truncated"] = True
    parsed["note"] = (
        f"Showing the first {_MAX_RETURNED_SPEECHES} of {len(speeches)} contributions. "
        "If the passage you need is not here, retrieve a more specific agenda item "
        "(iob_id) rather than re-requesting this one."
    )
    return parsed


_MIN_TRANSCRIPT_BYTES = 20_000  # reject undersized Cloudflare 524 error pages


async def _fetch_sp_page_with_retry(
    client: httpx.AsyncClient,
    url: str,
    attempts: int = 4,
    min_bytes: int = _MIN_TRANSCRIPT_BYTES,
) -> str:
    """Fetch an SP Official Report page, retrying on failure or undersized responses.

    Large plenary item pages (200–700 KB) intermittently return an ~8 KB Cloudflare
    524 error page. Retry with exponential backoff and reject any response smaller
    than min_bytes so an error page is never treated as a real transcript.
    Charset: honour the response's declared encoding but fall back to UTF-8 to avoid
    replacement chars from origin mislabelling.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = await client.get(
                url, headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True, timeout=30.0,
            )
            resp.raise_for_status()
            if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "latin-1", "ascii"):
                resp.encoding = "utf-8"
            body = resp.text
            if len(body.encode("utf-8", "ignore")) >= min_bytes:
                return body
            logger.warning(
                f"[Parliament] Undersized response ({len(body)} chars) for {url} "
                f"(attempt {attempt + 1}/{attempts}) — likely a 524 error page, retrying"
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                f"[Parliament] Fetch failed for {url} "
                f"(attempt {attempt + 1}/{attempts}): {exc}"
            )
        if attempt < attempts - 1:
            import asyncio as _asyncio
            await _asyncio.sleep(2 * (attempt + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to fetch a full-size page for {url} after {attempts} attempts")


async def _lookup_video_captions(meeting_id: str):
    """Return the cached SpVideoCaption row for a plenary meeting, or None.

    Only consulted when ENABLE_VIDEO_DEEPLINKS is on. Returns a lightweight dict
    (caption_ok, transcript, offset_index, slug, is_youtube, youtube_url,
    start_time_utc) suitable for caption_match. Fail-soft: any error → None.
    """
    from sqlalchemy import text as sa_text
    from ...database import async_session_maker

    try:
        async with async_session_maker() as session:
            row = await session.execute(
                sa_text(
                    "SELECT caption_ok, transcript, offset_index, slug, is_youtube, "
                    "       youtube_url, start_time_utc "
                    "FROM sp_video_captions WHERE meeting_id = :m AND caption_ok = TRUE LIMIT 1"
                ),
                {"m": meeting_id},
            )
            r = row.mappings().first()
            return dict(r) if r else None
    except Exception:
        return None


async def _lookup_plenary_agenda_title(meeting_id: str, iob_id: str) -> Optional[str]:
    """Fetch the stored agenda-item title for a plenary (meeting_id, iob_id), if crawled."""
    from sqlalchemy import text as sa_text
    from ...database import async_session_maker

    try:
        async with async_session_maker() as session:
            row = await session.execute(
                sa_text(
                    "SELECT agenda_item_title FROM sp_plenary_items "
                    "WHERE meeting_id = :m AND iob_id = :i LIMIT 1"
                ),
                {"m": meeting_id, "i": iob_id},
            )
            title = row.scalar()
            return title or None
    except Exception:
        return None


async def _lookup_committee_agenda_title(meeting_id: str, iob_id: str) -> Optional[str]:
    """Fetch the stored agenda-item title for a committee (meeting_id, iob_id), if crawled."""
    from sqlalchemy import text as sa_text
    from ...database import async_session_maker

    try:
        async with async_session_maker() as session:
            row = await session.execute(
                sa_text(
                    "SELECT agenda_item_title FROM sp_committee_items "
                    "WHERE meeting_id = :m AND iob_id = :i LIMIT 1"
                ),
                {"m": meeting_id, "i": iob_id},
            )
            title = row.scalar()
            return title or None
    except Exception:
        return None


# Stopword set for the OR-fallback tsquery (mirrors orq.py in the FTS eval harness).
_OR_TSQUERY_STOP = frozenset(
    "the a an of for in on to and or is are with about said has what which people use".split()
)


def _or_tsquery(query: str) -> str:
    """Build an OR-combined to_tsquery string from a free-text query.

    Lowercases, tokenises on [a-z0-9]+, drops tokens <=2 chars and a small stopword
    set, dedups (order-preserving), and joins with ' | '. Returns '' when nothing
    survives — callers MUST skip the fallback in that case (never call
    to_tsquery('english', '')).
    """
    seen: list[str] = []
    for tok in _re.findall(r"[a-z0-9]+", query.lower()):
        if len(tok) <= 2 or tok in _OR_TSQUERY_STOP:
            continue
        if tok not in seen:
            seen.append(tok)
    return " | ".join(seen)


async def _search_plenary_db(
    query: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Run PostgreSQL FTS against sp_plenary_items and return slim results.

    Mirrors `_search_committee_transcripts_db` but for plenary (chamber) sittings;
    plenary has no committee filter.
    """
    from sqlalchemy import text as sa_text
    from ...database import async_session_maker

    async with async_session_maker() as session:
        count_row = await session.execute(sa_text("SELECT COUNT(*) FROM sp_plenary_items"))
        total_rows = count_row.scalar() or 0

        if total_rows == 0:
            return {
                "results": [],
                "total": 0,
                "note": (
                    "SP plenary transcript database is still being populated. "
                    "Try again later or use search_scottish_parliament for excerpt-only plenary content."
                ),
            }

        where_parts = [
            "to_tsvector('english', coalesce(full_text,'')) @@ plainto_tsquery('english', :query)"
        ]
        params: dict = {"query": query}

        if date_from:
            from datetime import date as _date
            try:
                params["date_from"] = _date.fromisoformat(date_from)
            except ValueError:
                params["date_from"] = date_from
            where_parts.append("meeting_date >= :date_from")
        if date_to:
            from datetime import date as _date
            try:
                params["date_to"] = _date.fromisoformat(date_to)
            except ValueError:
                params["date_to"] = date_to
            where_parts.append("meeting_date <= :date_to")

        where_sql = " AND ".join(where_parts)
        sql = sa_text(f"""
            SELECT meeting_id, slug, iob_id, meeting_date, agenda_item_title, url,
                   ts_rank(to_tsvector('english', coalesce(full_text,'')),
                           plainto_tsquery('english', :query)) AS rank,
                   left(full_text, 300) AS excerpt
            FROM sp_plenary_items
            WHERE {where_sql}
            ORDER BY rank DESC, meeting_date DESC
            LIMIT 10
        """)

        rows = (await session.execute(sql, params)).fetchall()

        fallback_note = None
        if not rows:
            orquery = _or_tsquery(query)
            if orquery:
                # plainto ANDs all terms, so one absent term (e.g. "unhoused" when
                # the corpus says "homeless") returns 0 rows. Re-run the SAME query
                # (same filters, same ranking) with an OR-combined to_tsquery. Fired
                # ONLY on an empty exact result, so precision on working queries is
                # untouched.
                or_where_sql = " AND ".join(
                    ["to_tsvector('english', coalesce(full_text,'')) @@ to_tsquery('english', :orquery)"]
                    + where_parts[1:]
                )
                or_sql = sa_text(f"""
                    SELECT meeting_id, slug, iob_id, meeting_date, agenda_item_title, url,
                           ts_rank(to_tsvector('english', coalesce(full_text,'')),
                                   to_tsquery('english', :orquery)) AS rank,
                           left(full_text, 300) AS excerpt
                    FROM sp_plenary_items
                    WHERE {or_where_sql}
                    ORDER BY rank DESC, meeting_date DESC
                    LIMIT 10
                """)
                or_params = dict(params)
                or_params["orquery"] = orquery
                rows = (await session.execute(or_sql, or_params)).fetchall()
                if rows:
                    fallback_note = "No exact (all-terms) match; broadened to any-term search."

    results = [
        {
            "meeting_id": r.meeting_id,
            "slug": r.slug,
            "iob_id": r.iob_id,
            "meeting_date": str(r.meeting_date) if r.meeting_date else "",
            "agenda_item_title": r.agenda_item_title or "",
            "url": r.url or "",
            "excerpt": r.excerpt or "",
        }
        for r in rows
    ]
    out = {"results": results, "total": len(results), "query": query}
    if fallback_note:
        out["note"] = fallback_note
    return out


def _slim_hansard_results(resp, query: str) -> dict:
    """Slim a TheyWorkForYou getHansard response (Scottish Parliament plenary) to
    the fields the model needs.

    TWFY type=sp is broken (returns Westminster debates regardless), so the caller
    fetches without a type filter and we post-filter here to SP-specific listurls.
    """
    if isinstance(resp, dict) and "error" in resp:
        return {"error": resp["error"], "results": [], "total": 0, "query": query}
    rows = resp if isinstance(resp, list) else resp.get("rows", [])

    rows = [
        r for r in rows
        if "/sp/" in (r.get("listurl", "")).lower()
        or "/spwrans/" in (r.get("listurl", "")).lower()
    ]

    slimmed = []
    for speech in rows[:10]:
        body_clean = _strip_html(speech.get("body", ""))
        speaker = speech.get("speaker") or {}
        speaker_name = (
            speaker.get("name", "") if isinstance(speaker, dict) else ""
        ) or speech.get("hname", "")

        # Debate title: TWFY API puts this in parent.body, not debate.name
        parent = speech.get("parent") or {}
        parent_body = parent.get("body", "") if isinstance(parent, dict) else ""
        debate_name = _strip_html(parent_body) if parent_body else ""

        listurl = speech.get("listurl", "")
        # SP written answers use spwrans; all other SP content uses sp
        debate_type_hint = "spwrans" if "wrans" in listurl.lower() else "sp"

        gid = speech.get("gid", "")
        speech_url = f"https://www.theyworkforyou.com/sp/?id={gid}"
        slimmed.append({
            "gid": gid,
            "hdate": speech.get("hdate", ""),
            "speaker": speaker_name,
            "debate": debate_name,
            "debate_type": debate_type_hint,
            "excerpt": body_clean[:400],
            "url": speech_url,
        })
    return {"results": slimmed, "total": len(slimmed), "query": query}


async def _search_committee_transcripts_db(
    query: str,
    committee: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Run PostgreSQL FTS against sp_committee_items and return slim results."""
    from sqlalchemy import text as sa_text
    from ...database import async_session_maker

    async with async_session_maker() as session:
        count_row = await session.execute(sa_text("SELECT COUNT(*) FROM sp_committee_items"))
        total_rows = count_row.scalar() or 0

        if total_rows == 0:
            return {
                "results": [],
                "total": 0,
                "note": (
                    "SP committee transcript database is still being populated. "
                    "Try again later or use search_scottish_parliament for plenary content."
                ),
            }

        where_parts = [
            "to_tsvector('english', coalesce(full_text,'')) @@ plainto_tsquery('english', :query)"
        ]
        params: dict = {"query": query}

        if committee:
            where_parts.append(
                "(committee_name ILIKE :committee OR committee_code ILIKE :committee)"
            )
            params["committee"] = f"%{committee}%"
        if date_from:
            from datetime import date as _date
            try:
                params["date_from"] = _date.fromisoformat(date_from)
            except ValueError:
                params["date_from"] = date_from
            where_parts.append("meeting_date >= :date_from")
        if date_to:
            from datetime import date as _date
            try:
                params["date_to"] = _date.fromisoformat(date_to)
            except ValueError:
                params["date_to"] = date_to
            where_parts.append("meeting_date <= :date_to")

        where_sql = " AND ".join(where_parts)
        sql = sa_text(f"""
            SELECT meeting_id, slug, iob_id, committee_code, committee_name,
                   meeting_date, agenda_item_title, url,
                   ts_rank(to_tsvector('english', coalesce(full_text,'')),
                           plainto_tsquery('english', :query)) AS rank,
                   left(full_text, 300) AS excerpt
            FROM sp_committee_items
            WHERE {where_sql}
            ORDER BY rank DESC, meeting_date DESC
            LIMIT 10
        """)

        rows = (await session.execute(sql, params)).fetchall()

        fallback_note = None
        if not rows:
            orquery = _or_tsquery(query)
            if orquery:
                # See _search_plenary_db: OR-fallback to escape plainto's AND-cliff.
                # Fired only on an empty exact result; committee/date filters preserved.
                or_where_sql = " AND ".join(
                    ["to_tsvector('english', coalesce(full_text,'')) @@ to_tsquery('english', :orquery)"]
                    + where_parts[1:]
                )
                or_sql = sa_text(f"""
                    SELECT meeting_id, slug, iob_id, committee_code, committee_name,
                           meeting_date, agenda_item_title, url,
                           ts_rank(to_tsvector('english', coalesce(full_text,'')),
                                   to_tsquery('english', :orquery)) AS rank,
                           left(full_text, 300) AS excerpt
                    FROM sp_committee_items
                    WHERE {or_where_sql}
                    ORDER BY rank DESC, meeting_date DESC
                    LIMIT 10
                """)
                or_params = dict(params)
                or_params["orquery"] = orquery
                rows = (await session.execute(or_sql, or_params)).fetchall()
                if rows:
                    fallback_note = "No exact (all-terms) match; broadened to any-term search."

    results = [
        {
            "meeting_id": r.meeting_id,
            "slug": r.slug,
            "iob_id": r.iob_id,
            "committee_name": r.committee_name or "",
            "meeting_date": str(r.meeting_date) if r.meeting_date else "",
            "agenda_item_title": r.agenda_item_title or "",
            "url": r.url or "",
            "excerpt": r.excerpt or "",
        }
        for r in rows
    ]
    out = {"results": results, "total": len(results), "query": query}
    if fallback_note:
        out["note"] = fallback_note
    return out


def _apply_parliament_filters(name: str, args: dict) -> Optional[str]:
    """Apply the user's parliamentary filters (record type, date range).

    Mutates `args` in place to inject filter-derived arguments (debate_type, date
    range) that the model omitted. Returns a redirect JSON string to short-circuit a
    tool call that contradicts the active record-type filter, or None to let the call
    proceed. Mirrors the prompt constraint block so the filter is honoured even when
    the model does not follow the instruction.
    """
    cfg = get_request_provider_config()
    record_type = cfg.get("_pt_record_type")
    date_from = cfg.get("_date_from")
    date_to = cfg.get("_date_to")

    # Session filter → date window. Intersect with any explicit date range so the
    # tighter of the two bounds wins (both are ISO "YYYY-MM-DD", so lexical compare
    # == chronological). The merged window is applied to the date-capable tools below.
    session_from, session_to = _sessions_date_window(cfg.get("_pt_sessions"))
    if session_from:
        date_from = max(date_from, session_from) if date_from else session_from
    if session_to:
        date_to = min(date_to, session_to) if date_to else session_to

    # Record type — set the debate_type the model omitted; redirect where the
    # record type is unavailable for the requested tool.
    if record_type and name == "search_scottish_parliament" and not args.get("debate_type"):
        if record_type == "written_answers":
            args["debate_type"] = "written_answers"
        elif record_type == "committee":
            return json.dumps({"results": [], "note": "Record type is set to committee transcripts. Use search_scottish_committee_transcripts."})
        elif record_type == "debates":
            # Plenary debates now have a full-text DB pipeline — prefer it over the
            # excerpt-only TWFY search. search_scottish_parliament remains available
            # as a breadth/older-session fallback but is not the primary route.
            return json.dumps({"results": [], "note": "Record type is set to plenary debates. Use search_scottish_plenary for full-text plenary chamber debates (search_scottish_parliament is excerpt-only and covers older sessions as a fallback)."})

    # A committee-record filter should not be satisfied by a plenary search.
    if record_type == "committee" and name == "search_scottish_plenary":
        return json.dumps({"results": [], "note": "Record type is set to committee transcripts. Use search_scottish_committee_transcripts, not search_scottish_plenary."})

    # Date range — merge into the date-capable search tools (the SP committee DB,
    # SP plenary DB, and SP plenary/TWFY search honour date_from/date_to).
    if name in ("search_scottish_committee_transcripts", "search_scottish_parliament", "search_scottish_plenary"):
        if date_from and not args.get("date_from"):
            args["date_from"] = date_from
        if date_to and not args.get("date_to"):
            args["date_to"] = date_to

    return None


async def execute_parliament_tool(
    name: str,
    args: dict,
    on_chunk: Optional[Callable] = None,
    timing_collector=None,
) -> str:
    """Execute a parliament research tool call and return JSON string result."""
    logger.info(f"[Parliament Tool Exec] {name} with args: {json.dumps(args)}")

    call_id = str(uuid.uuid4())
    twfy_key = settings.twfy_api_key or ""

    redirect = _apply_parliament_filters(name, args)
    if redirect is not None:
        return redirect

    if not twfy_key and name in {"search_scottish_parliament"}:
        return json.dumps({
            "error": (
                "TWFY_API_KEY is not configured. "
                "Register for a free key at https://www.theyworkforyou.com/api/key "
                "and add TWFY_API_KEY to your environment."
            ),
            "results": [],
        })

    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:

            if name == "get_member_info":
                # getMSPInfo was removed from TWFY; getMSPs with search= is the replacement
                url = f"{_TWFY_API_BASE}/getMSPs"
                params = {"key": twfy_key, "output": "js", "search": args["name"]}
                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                t0 = time.perf_counter()
                resp = await client.get(url, params=params)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"text": resp.text}
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                return json.dumps(resp_json)

            elif name == "search_bills":
                url = "https://data.parliament.scot/api/bills"
                params = {}
                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                t0 = time.perf_counter()
                resp = await client.get(url, params=params)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"text": resp.text}
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                # Filter Scottish bills by query keyword (no server-side search param)
                query_lower = args["query"].lower()
                bills = resp_json if isinstance(resp_json, list) else resp_json.get("items", [])
                filtered = [
                    b for b in bills
                    if query_lower in (b.get("ShortTitle") or b.get("title") or "").lower()
                    or query_lower in (b.get("LongTitle") or "").lower()
                ][:10]
                slimmed = [{
                    "billId": b.get("BillId") or b.get("id"),
                    "shortTitle": b.get("ShortTitle") or b.get("title", ""),
                    "currentStage": b.get("CurrentStage") or b.get("stage", ""),
                    "url": f"https://www.parliament.scot/bills-and-laws/bills/{b.get('BillId') or b.get('id')}",
                } for b in filtered]
                return json.dumps({"results": slimmed, "total": len(slimmed), "parliament": "scotland"})

            elif name == "search_scottish_parliament":
                url = f"{_TWFY_API_BASE}/getHansard"
                debate_type = args.get("debate_type")
                params = {
                    "key": twfy_key,
                    "output": "js",
                    "search": args["query"],
                    # Fetch more rows because Westminster results will be filtered out
                    "num": 20,
                }
                # type=sp is broken in TWFY — it returns Westminster content regardless.
                # Only type=spwrans appears to function correctly. SP plenary content
                # is post-filtered in _slim_hansard_results by listurl pattern (/sp/).
                if debate_type == "written_answers":
                    params["type"] = "spwrans"
                # date_from/date_to not supported by TWFY getHansard — ignored.

                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                t0 = time.perf_counter()
                resp = await client.get(url, params=params)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"text": resp.text}
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                return json.dumps(_slim_hansard_results(resp_json, args["query"]))

            elif name == "search_scottish_committee_transcripts":
                t0 = time.perf_counter()
                await _emit(on_chunk, {
                    "type": "api_call_start", "id": call_id,
                    "url": "db:sp_committee_items", "method": "FTS",
                    "payload": {k: v for k, v in args.items() if v},
                })
                result_data = await _search_committee_transcripts_db(
                    query=args.get("query", ""),
                    committee=args.get("committee") or None,
                    date_from=args.get("date_from") or None,
                    date_to=args.get("date_to") or None,
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                await _emit(on_chunk, {
                    "type": "api_call_end", "id": call_id,
                    "url": "db:sp_committee_items", "status": 200,
                    "response": {"total": result_data.get("total", 0)},
                    "elapsed_ms": round(elapsed_ms),
                })
                return json.dumps(result_data)

            elif name == "get_scottish_committee_transcript":
                meeting_id = str(args["meeting_id"])
                slug = str(args["slug"])
                iob_id = str(args["iob_id"])
                transcript_url = f"{_SP_OR_BASE}/{slug}?meeting={meeting_id}&iob={iob_id}"

                # Scope the parser to the requested agenda item using the stored title.
                agenda_title = await _lookup_committee_agenda_title(meeting_id, iob_id)

                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": transcript_url, "method": "GET", "payload": {}})
                t0 = time.perf_counter()
                resp = await client.get(transcript_url, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=20.0)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": transcript_url, "status": resp.status_code, "response": {"preview": f"{len(resp.text)} chars"}, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                # Committee item pages use the same <p id="orscontributions_..."> markup as
                # plenary; the plenary parser attributes speakers correctly where the older
                # _parse_sp_transcript_page returns a single unnamed blob.
                parsed = _cap_speeches(
                    _parse_sp_plenary_transcript(resp.text, transcript_url, agenda_title)
                )

                # Optional enrichment: attach SP TV video deep links to matched speeches.
                # Additive and fail-soft — never blocks or errors the citation.
                if settings.enable_video_deeplinks:
                    try:
                        caption_row = await _lookup_video_captions(meeting_id)
                        if caption_row:
                            from ...services.caption_match import annotate_speeches
                            n = annotate_speeches(caption_row, parsed.get("speeches") or [])
                            if n:
                                logger.info(f"[Parliament] Attached {n} video deep link(s) for committee meeting {meeting_id}")
                    except Exception as exc:
                        logger.warning(f"[Parliament] Video deep-link enrichment failed for committee {meeting_id}: {exc}", exc_info=True)

                return json.dumps(parsed)

            elif name == "search_scottish_plenary":
                t0 = time.perf_counter()
                await _emit(on_chunk, {
                    "type": "api_call_start", "id": call_id,
                    "url": "db:sp_plenary_items", "method": "FTS",
                    "payload": {k: v for k, v in args.items() if v},
                })
                result_data = await _search_plenary_db(
                    query=args.get("query", ""),
                    date_from=args.get("date_from") or None,
                    date_to=args.get("date_to") or None,
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                await _emit(on_chunk, {
                    "type": "api_call_end", "id": call_id,
                    "url": "db:sp_plenary_items", "status": 200,
                    "response": {"total": result_data.get("total", 0)},
                    "elapsed_ms": round(elapsed_ms),
                })
                return json.dumps(result_data)

            elif name == "get_scottish_plenary_debate":
                meeting_id = str(args["meeting_id"])
                slug = str(args["slug"])
                iob_id = str(args["iob_id"])
                transcript_url = f"{_SP_OR_BASE}/{slug}?meeting={meeting_id}&iob={iob_id}"

                # Scope the parser to the requested agenda item using the stored title.
                agenda_title = await _lookup_plenary_agenda_title(meeting_id, iob_id)

                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": transcript_url, "method": "GET", "payload": {}})
                t0 = time.perf_counter()
                # Plenary item pages are large (200–700 KB) and the origin intermittently
                # serves an ~8 KB Cloudflare 524 error page — retry with backoff.
                resp_text = await _fetch_sp_page_with_retry(client, transcript_url)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": transcript_url, "status": 200, "response": {"preview": f"{len(resp_text)} chars"}, "elapsed_ms": round(elapsed_ms)})
                parsed = _cap_speeches(
                    _parse_sp_plenary_transcript(resp_text, transcript_url, agenda_title)
                )

                # Optional enrichment: attach SP TV video deep links to matched speeches.
                # Additive and fail-soft — never blocks or errors the citation.
                if settings.enable_video_deeplinks:
                    try:
                        caption_row = await _lookup_video_captions(meeting_id)
                        if caption_row:
                            from ...services.caption_match import annotate_speeches
                            n = annotate_speeches(caption_row, parsed.get("speeches") or [])
                            if n:
                                logger.info(f"[Parliament] Attached {n} video deep link(s) for meeting {meeting_id}")
                    except Exception as exc:
                        logger.warning(f"[Parliament] Video deep-link enrichment failed for {meeting_id}: {exc}", exc_info=True)

                return json.dumps(parsed)

            else:
                return f"Error: Tool {name} not found in parliament toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Parliament Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Parliament Tool Error] {name}: {e}", exc_info=True)
        return f"Error executing tool: {str(e)}"

