"""Parliamentary research tools: TWFY/Hansard, UK Parliament APIs, Scottish Parliament
Official Report parsers, and the SP committee transcript DB search."""

import json
import logging
import time
import uuid
from typing import Callable, Optional

import httpx

from ...config import settings
from ._util import _emit

logger = logging.getLogger("agent")

import re as _re

_TWFY_API_BASE = "https://www.theyworkforyou.com/api"
_SP_OR_BASE = "https://www.parliament.scot/chamber-and-committees/official-report/search-what-was-said-in-parliament"


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


def _parse_sp_transcript_page(html: str, url: str) -> dict:
    """Extract speech content from a SP Official Report transcript page."""
    title_match = _re.search(r"<title[^>]*>([^<]+)</title>", html, _re.IGNORECASE)
    page_title = _strip_html(title_match.group(1)).strip() if title_match else ""
    if "|" in page_title:
        page_title = page_title.split("|")[0].strip()

    h1_match = _re.search(r"<h1[^>]*>(.*?)</h1>", html, _re.IGNORECASE | _re.DOTALL)
    committee_name = _strip_html(h1_match.group(1)).strip() if h1_match else ""
    committee_name = _re.sub(r",?\s*Meeting date:.*", "", committee_name, flags=_re.IGNORECASE).strip()

    main_match = _re.search(r"<main[^>]*>(.*?)</main>", html, _re.DOTALL | _re.IGNORECASE)
    content_html = main_match.group(1) if main_match else html

    speeches: list[dict] = []

    # Try structured contribution/speech divs first
    contrib_pattern = _re.compile(
        r'<(?:div|article|section)[^>]*class="[^"]*(?:contribution|or-contribution|member-speech|speech-contribution)[^"]*"[^>]*>(.*?)</(?:div|article|section)>',
        _re.DOTALL | _re.IGNORECASE,
    )
    blocks = contrib_pattern.findall(content_html)
    if blocks:
        for block in blocks:
            spk_match = _re.search(
                r'<(?:strong|h[2-4]|span[^>]*class="[^"]*speaker[^"]*")[^>]*>(.*?)</(?:strong|h[2-4]|span)>',
                block, _re.IGNORECASE | _re.DOTALL,
            )
            speaker = _strip_html(spk_match.group(1)).strip() if spk_match else ""
            text = _strip_html(block).strip()
            if speaker and text.startswith(speaker):
                text = text[len(speaker):].lstrip(":").strip()
            if text and len(text) > 15:
                speeches.append({"speaker": speaker, "text": text[:3000]})

    # Fallback: speaker-colon pattern in paragraph text
    if not speeches:
        para_pattern = _re.compile(r"<p[^>]*>(.*?)</p>", _re.DOTALL | _re.IGNORECASE)
        current_speaker = ""
        current_parts: list[str] = []
        for m in para_pattern.finditer(content_html):
            text = _strip_html(m.group(1)).strip()
            if not text:
                continue
            spk_match = _re.match(
                r"^([A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+){0,4}(?:\s*\([^)]{0,40}\))*)\s*:\s*(.*)",
                text, _re.DOTALL,
            )
            if spk_match:
                if current_parts:
                    speeches.append({"speaker": current_speaker, "text": " ".join(current_parts)[:3000]})
                current_speaker = spk_match.group(1).strip()
                rest = spk_match.group(2).strip()
                current_parts = [rest] if rest else []
            else:
                current_parts.append(text)
        if current_parts:
            speeches.append({"speaker": current_speaker, "text": " ".join(current_parts)[:3000]})

    # Last resort: all paragraph text as a single block
    if not speeches:
        para_pattern = _re.compile(r"<p[^>]*>(.*?)</p>", _re.DOTALL | _re.IGNORECASE)
        all_paras = [
            _strip_html(m.group(1)).strip()
            for m in para_pattern.finditer(content_html)
            if len(_strip_html(m.group(1)).strip()) > 20
        ]
        if all_paras:
            speeches.append({"speaker": "", "text": "\n\n".join(all_paras)[:8000]})

    return {
        "page_title": page_title,
        "committee_name": committee_name,
        "url": url,
        "speeches": speeches[:30],
        "total_speeches": len(speeches),
    }


def _slim_hansard_results(resp, query: str, source_type: str = "hansard") -> dict:
    """Slim a TheyWorkForYou getHansard response to the fields the model needs.

    source_type: "hansard" for UK Parliament results, "scottish_parliament" for SP results.
    Passed explicitly because SP listurls don't match the UK listurl patterns and would
    otherwise fall back to debate_type "debates" (the UK Commons endpoint), causing
    get_hansard_debate to call the wrong TWFY endpoint.
    """
    if isinstance(resp, dict) and "error" in resp:
        return {"error": resp["error"], "results": [], "total": 0, "query": query}
    rows = resp if isinstance(resp, list) else resp.get("rows", [])

    # For Scottish Parliament queries, filter out Westminster content.
    # TWFY type=sp is broken (returns Westminster debates regardless), so we
    # fetch without a type filter and post-filter here to SP-specific listurls.
    if source_type == "scottish_parliament":
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
        if source_type == "scottish_parliament":
            # SP written answers use spwrans; all other SP content uses getSP
            debate_type_hint = "spwrans" if "wrans" in listurl.lower() else "sp"
        elif "/lords/" in listurl:
            debate_type_hint = "lords"
        elif "/wrans/" in listurl:
            debate_type_hint = "wrans"
        elif "/wms/" in listurl:
            debate_type_hint = "wms"
        else:
            debate_type_hint = "debates"

        gid = speech.get("gid", "")
        if source_type == "scottish_parliament":
            speech_url = f"https://www.theyworkforyou.com/sp/?id={gid}"
        else:
            speech_url = f"https://www.theyworkforyou.com/debate/?id={gid}"
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


def _slim_members_results(resp: dict) -> dict:
    """Slim a UK Parliament Members API response."""
    items = resp.get("items", [])
    slimmed = []
    for item in items[:5]:
        v = item.get("value", {})
        membership = v.get("latestHouseMembership", {}) or {}
        slimmed.append({
            "id": v.get("id"),
            "name": v.get("nameDisplayAs", ""),
            "party": (v.get("latestParty") or {}).get("name", ""),
            "constituency": membership.get("membershipFrom", ""),
            "house": membership.get("house", ""),
            "url": f"https://members.parliament.uk/member/{v.get('id')}/contact",
        })
    return {"results": slimmed, "total": resp.get("totalResults", len(slimmed))}


def _slim_bills_results(resp: dict) -> dict:
    """Slim a UK Parliament Bills API response."""
    items = resp.get("items", [])
    slimmed = []
    for item in items[:10]:
        stage = item.get("currentStage") or {}
        slimmed.append({
            "billId": item.get("billId"),
            "shortTitle": item.get("shortTitle", ""),
            "currentStage": stage.get("description", "") if isinstance(stage, dict) else str(stage),
            "currentHouse": item.get("currentHouse", ""),
            "lastUpdate": item.get("lastUpdate", ""),
            "url": f"https://bills.parliament.uk/bills/{item.get('billId')}",
        })
    return {"results": slimmed, "total": resp.get("totalResults", len(slimmed))}


async def _search_committee_transcripts_db(
    query: str,
    committee: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Run PostgreSQL FTS against sp_committee_items and return slim results."""
    from sqlalchemy import text as sa_text
    from ..database import async_session_maker

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
    return {"results": results, "total": len(results), "query": query}


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

    if not twfy_key and name in {"search_hansard", "get_hansard_debate", "search_scottish_parliament"}:
        return json.dumps({
            "error": (
                "TWFY_API_KEY is not configured. "
                "Register for a free key at https://www.theyworkforyou.com/api/key "
                "and add TWFY_API_KEY to your environment."
            ),
            "results": [],
        })

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:

            if name == "search_hansard":
                url = f"{_TWFY_API_BASE}/getHansard"
                params: dict = {
                    "key": twfy_key,
                    "output": "js",
                    "search": args["query"],
                    "num": 10,
                }
                if args.get("debate_type"):
                    params["type"] = args["debate_type"]
                if args.get("speaker"):
                    params["person"] = args["speaker"]
                # Note: TWFY getHansard does not support date range filtering.
                # date_from/date_to are accepted by the tool schema for intent
                # but are not forwarded to the API — results are ordered by date
                # (most recent first) regardless of any date constraints.

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

            elif name == "get_hansard_debate":
                gid = args["gid"]
                debate_type = args.get("debate_type", "debates")
                gid_lower = gid.lower()

                # TWFY API notes (verified 2026-06):
                # - getDebates requires type= and uses gid= (not id=); type=commons works
                # - getLords is a member-list endpoint, not debate retrieval; Lords full text unavailable via TWFY
                # - getWrans requires date=, not gid=; per-gid wrans retrieval unavailable via TWFY
                # - getSP was removed; SP full text unavailable via TWFY
                # For the broken cases we return a message so the model can fall back to the search excerpt.
                if "wrans" in gid_lower or debate_type == "wrans":
                    return json.dumps({"error": "TWFY no longer supports written answer retrieval by gid. Use the excerpt from search_hansard."})
                elif debate_type in ("sp", "spwrans"):
                    return json.dumps({"error": "TWFY getSP endpoint has been removed. Use the excerpt from search_hansard."})
                elif "lords" in gid_lower or debate_type == "lords":
                    return json.dumps({"error": "TWFY getLords does not support debate retrieval by gid. Use the excerpt from search_hansard."})
                else:
                    endpoint = "getDebates"

                url = f"{_TWFY_API_BASE}/{endpoint}"
                params = {"key": twfy_key, "output": "js", "type": "commons", "gid": gid}

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
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": {"preview": str(resp_json)[:300]}, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                return json.dumps(resp_json)

            elif name == "get_member_info":
                parliament = args.get("parliament", "commons")

                if parliament == "scotland":
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

                else:
                    house = 2 if parliament == "lords" else 1
                    url = "https://members-api.parliament.uk/api/Members/Search"
                    params = {"Name": args["name"], "House": house, "IsCurrentMember": "false", "Skip": 0, "Take": 5}
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
                    return json.dumps(_slim_members_results(resp_json))

            elif name == "search_bills":
                parliament = args.get("parliament", "uk")

                if parliament == "scotland":
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

                else:
                    url = "https://bills-api.parliament.uk/api/v1/Bills"
                    params = {"SearchTerm": args["query"], "SortOrder": "DateUpdatedDescending", "Take": 10, "Skip": 0}
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
                    return json.dumps(_slim_bills_results(resp_json))

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
                return json.dumps(_slim_hansard_results(resp_json, args["query"], source_type="scottish_parliament"))

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

                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": transcript_url, "method": "GET", "payload": {}})
                t0 = time.perf_counter()
                resp = await client.get(transcript_url, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=20.0)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": transcript_url, "status": resp.status_code, "response": {"preview": f"{len(resp.text)} chars"}, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                return json.dumps(_parse_sp_transcript_page(resp.text, transcript_url))

            else:
                return f"Error: Tool {name} not found in parliament toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Parliament Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Parliament Tool Error] {name}: {e}")
        return f"Error executing tool: {str(e)}"

