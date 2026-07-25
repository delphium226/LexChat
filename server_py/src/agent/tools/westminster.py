"""Westminster (UK Parliament) research tools.

Backed by the official Hansard JSON API (`hansard-api.parliament.uk`, Open
Parliament Licence v3.0, no auth), plus the Members and Bills APIs.

Deliberately NOT TheyWorkForYou: the parliament bot's original Westminster tools
were TWFY-backed, and `getHansard` orders by recency rather than relevance, has
no working date filter, and is excerpt-only — which made the Worker loop on
search. The Hansard API is relevance-ranked, date-filterable and returns full
contribution text, so none of that failure mode applies here.

Unlike the Scotland tools there is no crawler and no local FTS table: Hansard
searches server-side, so search is an HTTP call rather than a SQL query.
"""

import html as _html
import json
import logging
import re as _re
import time
import uuid
from typing import Callable, Optional

import httpx

from ..provider_factory import get_request_provider_config
from ._util import _emit

logger = logging.getLogger("agent")

_HANSARD_API_BASE = "https://hansard-api.parliament.uk"
_HANSARD_SITE_BASE = "https://hansard.parliament.uk"
_MEMBERS_API_BASE = "https://members-api.parliament.uk/api"
_BILLS_API_BASE = "https://bills-api.parliament.uk/api/v1"

# Westminster Parliament (general-election term) → sitting-date window (inclusive).
# The Holyrood analogue is SP_SESSIONS in parliament.py; keys ascend chronologically
# so the same _sessions_date_window collapse logic applies. Boundaries use the
# polling day / dissolution date so adjacent Parliaments do not overlap. The
# current Parliament has an open upper bound (None).
#
# Westminster's own unit below a Parliament is the *session* (roughly annual,
# bounded by State Opening / prorogation). Sessions are deliberately NOT modelled:
# their boundaries move with the parliamentary timetable, and the date-range filter
# already gives finer slicing than a session picker would.
WM_PARLIAMENTS: dict[int, tuple[str, Optional[str]]] = {
    1: ("2005-05-05", "2010-04-12"),
    2: ("2010-05-06", "2015-03-30"),
    3: ("2015-05-07", "2017-05-03"),
    4: ("2017-06-08", "2019-11-06"),
    5: ("2019-12-12", "2024-05-30"),
    6: ("2024-07-04", None),  # current Parliament — open-ended
}


def _wm_sessions_date_window(sessions) -> tuple[Optional[str], Optional[str]]:
    """Collapse selected Parliament numbers into a single (from, to) window.

    Earliest start and latest end across the selection; an open-ended (current)
    Parliament yields a None upper bound. Unknown numbers are ignored.
    """
    if not sessions:
        return None, None
    starts, ends, open_ended = [], [], False
    for s in sessions:
        rng = WM_PARLIAMENTS.get(s)
        if not rng:
            continue
        starts.append(rng[0])
        if rng[1] is None:
            open_ended = True
        else:
            ends.append(rng[1])
    if not starts:
        return None, None
    return min(starts), (None if open_ended else (max(ends) if ends else None))


# Record type → (contribution type, accepted `Section` values).
# The Hansard API exposes the record taxonomy as the `Section` field on results
# ("Commons Chamber", "Westminster Hall", "Public Bill Committees", …). Its
# `queryParameters.debateType` param is accepted but has no effect (verified
# 2026-07-25: all four taxonomy values returned byte-identical results), so
# record type is enforced by post-filtering on `Section` instead.
_RECORD_TYPES: dict[str, tuple[str, tuple[str, ...]]] = {
    "chamber": ("Spoken", ("Commons Chamber", "Lords Chamber")),
    "westminster_hall": ("Spoken", ("Westminster Hall",)),
    "public_bill_committee": ("Spoken", ("Public Bill Committees",)),
    "written_statements": ("Written", ("Written Statements",)),
    "written_answers": ("Written", ("Written Answers",)),
}

_HOUSES = {"commons": "Commons", "lords": "Lords"}

# Hansard `Value` / `ContributionText` fields intermittently carry text that was
# UTF-8 encoded then decoded as cp1252 ("Â£300,000", "residentsâ€™"). Only convert
# back when the round trip is lossless, so clean text is never mangled.
_MOJIBAKE_MARKERS = ("Â", "â€", "Ã")


def _strip_surrogates(text: str) -> str:
    """Drop lone surrogate code points, which the API emits for some smart quotes.

    They cannot be encoded to UTF-8, so they break json.dumps consumers downstream.
    """
    if not text:
        return ""
    return "".join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)


def _fix_mojibake(text: str) -> str:
    if not text or not any(m in text for m in _MOJIBAKE_MARKERS):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _clean_text(text: str) -> str:
    """Normalise a Hansard text field: drop markup, repair encoding, tidy whitespace.

    Contribution values carry inline HRS markup (`<Question HRSContentId="…">`)
    that is noise to the model and to a quoted citation.
    """
    if not text:
        return ""
    cleaned = _strip_surrogates(text)
    cleaned = _fix_mojibake(cleaned)
    cleaned = _re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = _html.unescape(cleaned)
    return _re.sub(r"\s+", " ", cleaned).strip()


def _title_slug(title: str) -> str:
    """Hansard's CamelCase URL slug for a debate title.

    Cosmetic only — hansard.parliament.uk resolves the debate from the ExtId in
    the path; the slug is a human-readable tail.
    """
    words = _re.findall(r"[A-Za-z0-9]+", title or "")
    return "".join(w[:1].upper() + w[1:] for w in words) or "Debate"


def _debate_url(house: str, sitting_date: str, ext_id: str, title: str) -> str:
    """Public hansard.parliament.uk URL for a debate section (emitted, never fetched)."""
    day = (sitting_date or "")[:10]
    house_seg = house if house in ("Commons", "Lords") else "Commons"
    return f"{_HANSARD_SITE_BASE}/{house_seg}/{day}/debates/{ext_id}/{_title_slug(title)}"


def _slim_contribution_results(resp_json: dict, query: str, sections: tuple[str, ...] = ()) -> dict:
    """Trim a Hansard contribution search response to what the Worker needs.

    Keeps the debate identity (`debate_ext_id` — the Phase 2 handle), the speaker,
    the date, the record location, and a short excerpt. Full contribution text is
    dropped: Phase 2 retrieves the whole debate anyway, and keeping it here would
    push Phase 1 over the summarisation threshold for no benefit (same reasoning
    as _slim_search_results dropping `description` on the legislation bot).
    """
    results = []
    seen: set[str] = set()
    for r in resp_json.get("Results") or []:
        section = r.get("Section") or ""
        if sections and section not in sections:
            continue
        ext_id = r.get("DebateSectionExtId") or ""
        if not ext_id:
            continue
        # One row per debate: several matching contributions in the same debate
        # are a single Phase 2 retrieval, so collapse them here.
        if ext_id in seen:
            continue
        seen.add(ext_id)
        sitting_date = (r.get("SittingDate") or "")[:10]
        title = r.get("DebateSection") or ""
        house = r.get("House") or ""
        results.append({
            "debate_ext_id": ext_id,
            "title": title,
            "house": house,
            "section": section,
            "date": sitting_date,
            "speaker": _clean_text(r.get("AttributedTo") or ""),
            "member_id": r.get("MemberId"),
            "excerpt": _clean_text(r.get("ContributionText") or "")[:400],
            "url": _debate_url(house, sitting_date, ext_id, title),
        })
    return {
        "results": results[:10],
        "total": len(results[:10]),
        "total_matches": resp_json.get("TotalResultCount", 0),
        "query": query,
    }


def _flatten_debate(data: dict) -> dict:
    """Turn a Hansard debate JSON document into a flat contribution list.

    A debate section may nest further child debates (a department's oral questions
    contain one child per question), so walk the tree and keep document order.
    """
    overview = data.get("Overview") or {}
    contributions: list[dict] = []

    def walk(node: dict) -> None:
        for item in node.get("Items") or []:
            if item.get("ItemType") != "Contribution":
                continue
            text = _clean_text(item.get("Value") or "")
            if not text:
                continue
            contributions.append({
                "speaker": _clean_text(item.get("AttributedTo") or ""),
                "member_id": item.get("MemberId"),
                "text": text[:3000],
                "order": item.get("OrderInSection"),
                # Local wall-clock (no timezone suffix) where Hansard populated it;
                # sparse — roughly a third of contributions carry one.
                "timecode": item.get("Timecode"),
            })
        for child in node.get("ChildDebates") or []:
            walk(child)

    walk(data)

    ext_id = overview.get("ExtId") or ""
    title = _clean_text(overview.get("Title") or "")
    house = overview.get("House") or ""
    date = (overview.get("Date") or "")[:10]
    return {
        "debate_ext_id": ext_id,
        "title": title,
        "house": house,
        "location": overview.get("Location") or "",
        "date": date,
        "url": _debate_url(house, date, ext_id, title),
        "contributions": contributions,
        "total_contributions": len(contributions),
    }


def _apply_westminster_filters(name: str, args: dict) -> Optional[str]:
    """Apply the user's Westminster filters (House, record type, date range).

    Mutates `args` in place to inject filter-derived arguments the model omitted.
    Returns a redirect JSON string to short-circuit a call that contradicts an
    active filter, or None to let the call proceed. Mirrors the prompt constraint
    block so filters hold even when the model ignores the instruction.
    """
    cfg = get_request_provider_config()
    house = cfg.get("_wm_house")
    record_type = cfg.get("_wm_record_type")
    date_from = cfg.get("_date_from")
    date_to = cfg.get("_date_to")

    # Parliament filter → date window, intersected with any explicit date range so
    # the tighter bound wins (ISO dates compare lexically == chronologically).
    session_from, session_to = _wm_sessions_date_window(cfg.get("_pt_sessions"))
    if session_from:
        date_from = max(date_from, session_from) if date_from else session_from
    if session_to:
        date_to = min(date_to, session_to) if date_to else session_to

    if name == "search_hansard":
        # The user's House/record-type selection overrides whatever the model chose.
        if house:
            args["house"] = house
        if record_type:
            args["record_type"] = record_type
        if date_from and not args.get("date_from"):
            args["date_from"] = date_from
        if date_to and not args.get("date_to"):
            args["date_to"] = date_to

    # A Lords-only filter cannot be satisfied by a Commons-only record type.
    if house == "lords" and args.get("record_type") in ("westminster_hall", "public_bill_committee"):
        return json.dumps({
            "results": [],
            "note": (
                "The House filter is set to Lords, but Westminster Hall and Public Bill "
                "Committees are Commons-only business. Search the Lords Chamber instead "
                "(record_type='chamber')."
            ),
        })

    return None


async def execute_westminster_tool(
    name: str,
    args: dict,
    on_chunk: Optional[Callable] = None,
    timing_collector=None,
) -> str:
    """Execute a Westminster research tool call and return a JSON string result."""
    logger.info(f"[Westminster Tool Exec] {name} with args: {json.dumps(args)}")

    call_id = str(uuid.uuid4())

    redirect = _apply_westminster_filters(name, args)
    if redirect is not None:
        return redirect

    try:
        # verify=False mirrors the other tool executors: the deployment target sits
        # behind TLS inspection that presents a re-signed certificate.
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:

            if name == "search_hansard":
                record_type = (args.get("record_type") or "").strip().lower()
                contribution_type, sections = _RECORD_TYPES.get(record_type, ("Spoken", ()))
                url = f"{_HANSARD_API_BASE}/search/contributions/{contribution_type}.json"

                params: dict = {
                    "queryParameters.searchTerm": args["query"],
                    # Over-fetch when a Section post-filter is active so the filter
                    # has enough rows to work with (the API's own debateType param
                    # is inert — see _RECORD_TYPES).
                    "queryParameters.take": 100 if sections else 20,
                    "queryParameters.orderBy": "SittingDateDesc",
                }
                house = _HOUSES.get((args.get("house") or "").strip().lower())
                if house:
                    params["queryParameters.house"] = house
                if args.get("date_from"):
                    params["queryParameters.startDate"] = args["date_from"]
                if args.get("date_to"):
                    params["queryParameters.endDate"] = args["date_to"]

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
                await _emit(on_chunk, {
                    "type": "api_call_end", "id": call_id, "url": url,
                    "status": resp.status_code,
                    "response": {"total": resp_json.get("TotalResultCount") if isinstance(resp_json, dict) else None},
                    "elapsed_ms": round(elapsed_ms),
                })
                resp.raise_for_status()
                slimmed = _slim_contribution_results(resp_json, args["query"], sections)
                if not slimmed["results"] and sections:
                    slimmed["note"] = (
                        f"No {record_type.replace('_', ' ')} records matched. The record-type filter "
                        "is active, so chamber debates were excluded from these results."
                    )
                return json.dumps(slimmed)

            elif name == "get_hansard_debate":
                ext_id = str(args["debate_ext_id"]).strip()
                url = f"{_HANSARD_API_BASE}/debates/debate/{ext_id}.json"

                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": {}})
                t0 = time.perf_counter()
                resp = await client.get(url)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                await _emit(on_chunk, {
                    "type": "api_call_end", "id": call_id, "url": url,
                    "status": resp.status_code,
                    "response": {"preview": f"{len(resp.text)} chars"},
                    "elapsed_ms": round(elapsed_ms),
                })
                resp.raise_for_status()
                parsed = _flatten_debate(resp.json())
                if not parsed["contributions"]:
                    parsed["note"] = (
                        "This debate section contains no spoken contributions "
                        "(it may be a heading). Try a different debate_ext_id from the search results."
                    )
                return json.dumps(parsed)

            elif name == "get_member_info":
                url = f"{_MEMBERS_API_BASE}/Members/Search"
                params = {"Name": args["name"], "take": 5}
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
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": {"n": len(resp_json.get("items", []) if isinstance(resp_json, dict) else [])}, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                members = []
                for item in (resp_json.get("items") or [])[:5]:
                    v = item.get("value") or {}
                    membership = v.get("latestHouseMembership") or {}
                    members.append({
                        "member_id": v.get("id"),
                        "name": v.get("nameDisplayAs"),
                        "full_title": v.get("nameFullTitle"),
                        "party": (v.get("latestParty") or {}).get("name"),
                        "constituency": membership.get("membershipFrom"),
                        "house": "Commons" if membership.get("house") == 1 else "Lords",
                        "member_since": (membership.get("membershipStartDate") or "")[:10],
                        "is_current": bool((membership.get("membershipStatus") or {}).get("statusIsActive")),
                        "url": f"https://members.parliament.uk/member/{v.get('id')}/career" if v.get("id") else "",
                    })
                return json.dumps({"results": members, "total": len(members)})

            elif name == "search_bills":
                url = f"{_BILLS_API_BASE}/Bills"
                params = {"SearchTerm": args["query"], "take": 10}
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
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": {"total": resp_json.get("totalResults") if isinstance(resp_json, dict) else None}, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                bills = []
                for b in (resp_json.get("items") or [])[:10]:
                    stage = b.get("currentStage") or {}
                    bills.append({
                        "bill_id": b.get("billId"),
                        "short_title": b.get("shortTitle"),
                        "current_house": b.get("currentHouse"),
                        "current_stage": stage.get("description"),
                        "is_act": b.get("isAct"),
                        "last_update": (b.get("lastUpdate") or "")[:10],
                        "url": f"https://bills.parliament.uk/bills/{b.get('billId')}",
                    })
                return json.dumps({"results": bills, "total": len(bills), "parliament": "westminster"})

            else:
                return f"Error: Tool {name} not found in Westminster toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Westminster Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Westminster Tool Error] {name}: {e}", exc_info=True)
        return f"Error executing tool: {str(e)}"
