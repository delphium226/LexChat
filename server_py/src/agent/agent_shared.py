"""
Shared worker-tool execution logic used by both ollama_client and openrouter_client.

Both provider clients run an identical pipeline when processing Worker tool results:
execute the tool, optionally summarise large results, append a Phase 2 nudge for
search_legislation calls.  This module owns that logic once so future changes only
need to happen here.
"""
import asyncio
import json
import logging
import uuid
from typing import Awaitable, Callable, Optional

from ..utils.audit_trace import get_audit_collector
from ..utils.citation_links import harvest_legislation_urls, provision_url_block
from ..utils.section_outline import subsection_outline
from ..utils.schedule_units import (
    BARE_ABSENT,
    BARE_ONE,
    bare_schedule_action,
    row_unit,
    sole_schedule_reason,
    FROM_LIST,
    FROM_TEXT,
    MATCHED,
    MATCHED_CUTS_MIN_CHARS,
    SUMMARY,
    cut_pieces,
    matched_numbers,
    matched_pieces,
    cut_unit_from_text,
    fetch_failed_line,
    fetched_block,
    instrument_without_text_line,
    named_units,
    pick_provision,
    provision_list_facts,
    schedules_note,
    unit_absent_line,
    unit_in_results,
    unit_without_text_line,
)
from ..utils.instrument_lookup import lookup_args
from ..utils.instrument_lookup import legislation_id as lookup_legislation_id
from .tools.executor import fetch_provision_list, fetch_text_with_schedules
from ..utils.instrument_lookup import LOOKUP_TOOL
from ..utils.made_under import MADE_UNDER_TOOL, made_under_note
from ..utils.search_scope import record_made_under
from ..utils.discovery_budget import (
    legislation_budget_blocks,
    legislation_stop_message,
    section_budget_blocks,
    section_stop_message,
)
from ..utils.search_scope import (
    CASE_LAW_BOTH_ZERO_STOP,
    FCL_ZERO_NOTE_WITH_SCTS,
    SCTS_ZERO_NOTE,
    scottish_search_note,
)
from ..utils.search_scope import (
    amendment_search_note,
    case_law_search_note,
    currency_note,
    enabling_power_note,
    legislation_search_note,
    lookup_enabling_note,
    not_held_note,
    record_budget_stop,
    record_section_budget_stop,
    record_case_law_search,
    record_currency,
    record_enabling_power,
    record_lookup,
    record_not_held,
    record_relations,
    record_search,
    section_search_note,
)
from .provider_factory import get_request_provider_config
from .summarisation import call_chunk, summarise_for_query
from .tools import (
    execute_worker_tool,
    execute_parliament_tool,
    execute_westminster_tool,
    extract_legislation_ids_from_search,
    detect_appellate_decisions,
    _PARLIAMENT_TOOL_NAMES,
)

logger = logging.getLogger("agent")


def describe_agent_error(exc: BaseException) -> str:
    """Human-readable one-liner for a provider/agent failure.

    httpx's timeout exceptions are raised through httpcore's exception mapping
    with an EMPTY message, so `str(exc)` is "" — which surfaced to the lawyer as
    an error banner with no text at all, and logged as "[AI] Chat error:" with
    nothing after the colon. Every caller that shows a failure to a user or the
    model should render it through here rather than str().
    """
    import httpx

    if isinstance(exc, httpx.TimeoutException):
        return (
            "the AI provider did not respond in time — this usually means the "
            "request was too large or the provider is overloaded"
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return f"the AI provider returned HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TransportError):
        return f"could not reach the AI provider ({type(exc).__name__})"
    text = str(exc).strip()
    return text or f"an unexpected {type(exc).__name__}"


def _extract_sources_from_tool(name: str, args: dict, raw_result_str: str, accumulator: list) -> None:
    """Parse a raw tool result JSON string and append structured source dicts to accumulator.

    Called BEFORE summarisation so the full structured response is available.
    Internal bookkeeping keys (prefixed with '_') are stripped before the sources
    are exposed to the frontend.
    """
    try:
        data = json.loads(raw_result_str)
    except Exception:
        return

    if not isinstance(data, dict):
        return

    try:
        _extract_sources_inner(name, args, data, accumulator)
    except Exception as e:
        logger.debug(f"[Sources] Extraction skipped for '{name}': {e}")


def _legislation_kind(legislation_id: str) -> str:
    """Derive a human-readable source kind from the legislation_id path prefix."""
    prefix = legislation_id.split("/")[0].lower()
    if prefix in ("ukpga", "ukla", "ukppa", "ukpba", "nia", "asp", "anaw", "asc", "mwa"):
        return "Act"
    if prefix in ("uksi", "nisi", "wsi", "ssi", "nisr", "ukmo"):
        return "SI"
    if prefix == "ukdsi":
        return "Draft SI"
    return "Statute"


def _extract_sources_inner(name: str, args: dict, data: dict, accumulator: list) -> None:
    if name == "search_legislation":
        for item in data.get("results", []):
            lid = item.get("legislation_id") or ""
            if not lid:
                continue
            if any(s.get("_lid") == lid for s in accumulator):
                continue
            accumulator.append({
                "_lid": lid,
                "kind": _legislation_kind(lid),
                "title": item.get("title") or lid,
                "url": item.get("url") or "",
                # P2.5 renamed the slimmed key to `text_version` (see
                # `_slim_search_results`); `status` is read as a fallback so a
                # cached or replayed pre-P2.5 result still populates the rail.
                "meta": item.get("text_version") or item.get("status") or "",
                "year": item.get("year"),
                "extent": item.get("extent") or [],
                "cite": lid,
            })

    elif name == "search_legislation_sections":
        lid = args.get("legislation_id") or ""
        sections = data.get("sections") or data.get("results") or []
        for sec in sections[:1]:  # enrich with first matching section only
            sec_title = sec.get("title") or sec.get("section_title") or ""
            content = sec.get("content") or sec.get("text") or sec.get("excerpt") or ""
            section_number = sec.get("section_number") or sec.get("number") or ""
            excerpt = content[:300] if content else ""
            existing = next((s for s in accumulator if s.get("_lid") == lid), None)
            if existing:
                if not existing.get("sub") and sec_title:
                    existing["sub"] = sec_title
                if not existing.get("excerpt") and excerpt:
                    existing["excerpt"] = excerpt
                if section_number and existing.get("cite") == lid:
                    existing["cite"] = f"{existing.get('title', lid)}, s.{section_number}"
            else:
                accumulator.append({
                    "_lid": lid,
                    "kind": "Statute",
                    "title": data.get("title") or lid,
                    "sub": sec_title,
                    "excerpt": excerpt,
                    "cite": f"{lid}, s.{section_number}" if section_number else lid,
                    "url": data.get("url") or "",
                })

    elif name == "get_legislation_text":
        lid = args.get("legislation_id") or ""
        content = data.get("content") or data.get("text") or ""
        excerpt = content[:300] if content else ""
        existing = next((s for s in accumulator if s.get("_lid") == lid), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
        else:
            accumulator.append({
                "_lid": lid,
                "kind": "Statute",
                "title": data.get("title") or lid,
                "excerpt": excerpt,
                "cite": lid,
                "url": data.get("url") or "",
            })

    elif name == "get_legislation_changes":
        # P3.5 (B3). The instruments a change record names are the answer to a
        # commencement question, so an answer citing SSI 2025/119 must be able
        # to show it in the References rail.
        #
        # **Deliberately no excerpt, and the subtitle says what was established.**
        # The change record proves that this instrument commenced or amended
        # provisions of the subject; it does NOT mean its text was read.
        # `_source_is_used` keeps a source unconditionally when it carries an
        # excerpt, so giving one here would pin every related instrument into the
        # rail whether or not the answer cited it — overstating what the research
        # did and inflating `sources_kept`. Without one, only the instruments the
        # answer actually names survive the filter.
        for group in (data.get("related") or [])[:10]:
            if not isinstance(group, dict) or group.get("self"):
                continue
            rel_lid = group.get("legislation_id") or ""
            if not rel_lid or any(s.get("_lid") == rel_lid for s in accumulator):
                continue
            effect = group.get("type_of_effect") or "change"
            subject = data.get("legislation_id") or args.get("legislation_id") or ""
            accumulator.append({
                "_lid": rel_lid,
                "kind": "Statute",
                "title": rel_lid,
                "sub": f"recorded as {effect} for provisions of {subject}",
                "cite": rel_lid,
                "url": group.get("url") or "",
            })

    elif name == "search_case_law":
        for case in data.get("results", []):
            url = case.get("url") or case.get("link") or ""
            if url and any(s.get("url") == url for s in accumulator):
                continue
            ncn = case.get("ncn") or case.get("neutral_citation") or ""
            court = case.get("court") or ""
            date = case.get("date") or ""
            meta_parts = [p for p in [court, date] if p]
            accumulator.append({
                "kind": "Case",
                "title": case.get("title") or case.get("name") or "",
                "sub": ncn,
                "meta": ", ".join(meta_parts),
                "cite": ncn,
                "url": url,
            })
        # P3.20: the Scottish list (present only with `scts_caselaw_enabled`).
        # Its date is the date of decision SCTS records, never a citation's year.
        scottish = data.get("scottish_results")
        for case in scottish if isinstance(scottish, list) else []:
            if not isinstance(case, dict):
                continue
            url = case.get("url") or ""
            if url and any(s.get("url") == url for s in accumulator):
                continue
            ncn = case.get("ncn") or ""
            meta_parts = [p for p in [case.get("court") or "", case.get("decision_date") or ""] if p]
            accumulator.append({
                "kind": "Case",
                "title": case.get("title") or "",
                "sub": ncn,
                "meta": ", ".join(meta_parts),
                "cite": ncn,
                "url": url,
            })

    elif name == "get_case_law_text":
        url = data.get("url") or args.get("url") or ""
        text = data.get("text") or ""
        excerpt = text[:300] if text else ""
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
        else:
            ncn = data.get("ncn") or ""
            accumulator.append({
                "kind": "Case",
                "title": data.get("title") or url,
                "sub": ncn,
                "excerpt": excerpt,
                "cite": ncn or url,
                "url": url,
            })

    elif name == "search_scottish_parliament":
        for speech in data.get("results", []):
            url = speech.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            accumulator.append({
                "kind": "Scottish Parliament",
                "title": speech.get("debate", ""),
                "sub": speech.get("speaker", ""),
                "meta": speech.get("hdate", ""),
                "cite": f"{speech.get('speaker', '')}, {speech.get('hdate', '')}",
                "url": url,
            })

    elif name == "search_bills":
        # Holyrood bills come back camelCase, Westminster bills snake_case — the
        # tool name is shared across both bots, so accept either spelling.
        for bill in data.get("results", []):
            url = bill.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            title = bill.get("shortTitle") or bill.get("short_title") or ""
            accumulator.append({
                "kind": "Bill",
                "title": title,
                "sub": bill.get("currentStage") or bill.get("current_stage") or "",
                "meta": bill.get("current_house") or "",
                "cite": title,
                "url": url,
            })

    elif name == "get_member_info":
        for member in data.get("results", []):
            url = member.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            accumulator.append({
                "kind": "Member",
                "title": member.get("name", ""),
                "sub": member.get("party", ""),
                "meta": member.get("constituency", ""),
                "cite": member.get("name", ""),
                "url": url,
            })

    elif name == "search_hansard":
        for item in data.get("results", []):
            url = item.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            title = item.get("title", "")
            date = item.get("date", "")
            section = item.get("section", "")
            accumulator.append({
                "kind": "Hansard",
                "title": title or "Hansard debate",
                "sub": section,
                "meta": date,
                "cite": f"HC Deb, {date}, {title}" if item.get("house") == "Commons" else f"HL Deb, {date}, {title}",
                "url": url,
            })

    elif name == "get_hansard_debate":
        url = data.get("url") or ""
        title = data.get("title") or ""
        date = data.get("date") or ""
        contributions = data.get("contributions") or []
        excerpt = contributions[0].get("text", "")[:300] if contributions else ""
        # Item-level video entry point: the first contribution with a deep link
        # marks where this debate starts on parliamentlive (mirrors the SP branches).
        video = None
        for c in contributions:
            dl = c.get("video_deeplink")
            if dl and dl.get("url"):
                video = {"url": dl["url"], "clip_start": dl.get("clip_start"), "label": dl.get("label")}
                break
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
            if video and not existing.get("video"):
                existing["video"] = video
        else:
            src = {
                "kind": "Hansard",
                "title": title or "Hansard debate",
                "sub": data.get("location") or "",
                "meta": date,
                "excerpt": excerpt,
                "cite": f"HC Deb, {date}, {title}" if data.get("house") == "Commons" else f"HL Deb, {date}, {title}",
                "url": url,
            }
            if video:
                src["video"] = video
            accumulator.append(src)

    elif name == "search_scottish_committee_transcripts":
        for item in data.get("results", []):
            url = item.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            committee = item.get("committee_name", "")
            meeting_date = item.get("meeting_date", "")
            agenda_title = item.get("agenda_item_title", "")
            accumulator.append({
                "kind": "Committee",
                "title": committee,
                "sub": agenda_title,
                "meta": meeting_date,
                "cite": f"{committee}, {meeting_date}",
                "url": url,
            })

    elif name == "get_scottish_committee_transcript":
        url = data.get("url") or args.get("url") or ""
        page_title = data.get("page_title") or data.get("committee_name") or ""
        speeches = data.get("speeches") or []
        excerpt = speeches[0].get("text", "")[:300] if speeches else ""
        # Item-level video entry point: the first speech with a confident deep link
        # marks where this agenda item starts on SP TV (mirrors the plenary branch).
        video = None
        for sp in speeches:
            dl = sp.get("video_deeplink")
            if dl and dl.get("url"):
                video = {"url": dl["url"], "clip_start": dl.get("clip_start")}
                break
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
            if video and not existing.get("video"):
                existing["video"] = video
        else:
            src = {
                "kind": "Transcript",
                "title": page_title or "Scottish Parliament Committee",
                "excerpt": excerpt,
                "cite": page_title or url,
                "url": url,
            }
            if video:
                src["video"] = video
            accumulator.append(src)

    elif name == "search_scottish_plenary":
        for item in data.get("results", []):
            url = item.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            meeting_date = item.get("meeting_date", "")
            agenda_title = item.get("agenda_item_title", "")
            accumulator.append({
                "kind": "Plenary",
                "title": agenda_title or "Meeting of Parliament",
                "sub": "Meeting of Parliament",
                "meta": meeting_date,
                "cite": f"Meeting of Parliament, {meeting_date} — {agenda_title}",
                "url": url,
            })

    elif name == "get_scottish_plenary_debate":
        url = data.get("url") or args.get("url") or ""
        page_title = data.get("page_title") or ""
        speeches = data.get("speeches") or []
        excerpt = speeches[0].get("text", "")[:300] if speeches else ""
        # Item-level video entry point: the first speech with a confident deep link
        # marks where this agenda item starts on SP TV. (Per-moment links are inline
        # in the answer; the panel offers a single "watch from …" for the item.)
        video = None
        for sp in speeches:
            dl = sp.get("video_deeplink")
            if dl and dl.get("url"):
                video = {"url": dl["url"], "clip_start": dl.get("clip_start")}
                break
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
            if video and not existing.get("video"):
                existing["video"] = video
        else:
            src = {
                "kind": "Plenary",
                "title": page_title or "Scottish Parliament Plenary",
                "excerpt": excerpt,
                "cite": page_title or url,
                "url": url,
            }
            if video:
                src["video"] = video
            accumulator.append(src)


def summarised_result_blocks(name: str, raw_result) -> str:
    """What a SUMMARISED tool result gets back, built from the RAW result.

    Two blocks, both restoring what the summariser dropped: P1.6's provision
    URLs (`provision_url_block`, any tool) and P3.11's subsection outline
    (`subsection_outline`, section searches only - a whole-Act retrieval has
    no `results` rows and a change record no provision text). One definition,
    shared with `tools/seam_replay.py --from-raw`, so the seam rebuilds
    exactly the blocks the product appends rather than a copy that drifts.
    Returns "" when there is nothing to hand back.
    """
    blocks = provision_url_block(raw_result)
    if name == "search_legislation_sections":
        blocks += subsection_outline(raw_result)
    return blocks


def _worker_tool_key_arg(args: dict) -> Optional[str]:
    """Identifying argument for redundancy detection (record_worker_tool).

    A transcript's identity is (meeting_id, iob_id) — two different agenda
    items of one meeting are legitimate distinct retrievals, not redundant.
    slug is derivable and must NOT be part of the key.

    **P3.5 adds `direction` to the key for the same reason** (bucket B3).
    `get_legislation_changes` is the first legislation tool that takes a second
    identifying argument: the two directions over one `legislation_id` are
    different questions — what commenced this Act, and what this Act commences —
    and on `asp/2025/2` they return 36 and 143 relations respectively. Keyed on
    the id alone, asking both would be scored a redundant re-fetch and, on the
    legislation profile where `max_redundant_tool_calls` is 0, would write an
    EFFICIENCY breach for correct behaviour.
    """
    key_arg = args.get("legislation_id") or args.get("url") or args.get("gid") or args.get("debate_ext_id")
    if key_arg and args.get("direction"):
        key_arg = f"{key_arg}:{args['direction']}"
    if not key_arg and args.get("meeting_id"):
        key_arg = f"{args['meeting_id']}:{args.get('iob_id', '')}"
    return key_arg


# P3.12: at most this many instruments' provision lists fetched by code in one
# worker run. Each is one call (memoised for the run); a unit named on a
# further instrument is left to the Worker. Batch 9 A (user decision,
# 2026-10-06): its own constant, 8, no longer P3.7's MAX_ROUTED_LOOKUPS (5,
# which P3.7's lookups keep). The bound now holds within a round (see
# `_fetch_once`); at 5 it would have cut a Deep Research step that read six
# lists in one round in Session 40's sweep. No stored worker run reaches 8:
# the most instruments the route fires on in one run is 6.
MAX_PROVISION_FETCHES = 8


def provision_fetch_key(args) -> str:
    """The key `provision_fetches` holds an instrument under: the canonical
    id where the argument parses, else the argument as given. One definition,
    so the route that fills the dict and the cap that reads it agree."""
    ref = lookup_args({"legislation_id": args.get("legislation_id")})
    return lookup_legislation_id(ref) if ref else str(args.get("legislation_id") or "").strip()


async def _fetch_once(holder: dict, key, fetch: Callable[[], Awaitable],
                      bound: Optional[int] = None):
    """`holder[key]`, fetched by `fetch()` once however many calls of one
    round ask for it at the same time; None when `bound` refuses a new key.

    Batch 9 A (P3.12): `chat_loop` runs a round's tool calls as concurrent
    tasks, and the route used to check its per-run bound and memo before the
    fetch's await and write the result after it, so every call of a batched
    round passed the check (one Deep Research step in the Session 40 sweep
    read 6 provision lists against a bound of 5, and one instrument could be
    fetched twice). Here the slot is reserved, and counted against `bound`,
    before the await: while the fetch is in flight `holder[key]` is a
    Future, and every other call for that key waits on it (shielded, so a
    waiter cancelled mid-fetch takes nothing from the others). A Future is
    not a dict, so `provision_list_facts` never reads an in-flight slot as a
    complete list. A value `fetch()` returns, a failed outcome included, is
    recorded in the slot. A fetch that raises (a cancelled round) releases
    the slot, establishing nothing, and the calls waiting on it get None.
    With calls made one at a time nothing differs from before: no call ever
    finds a slot in flight."""
    if key in holder:
        value = holder[key]
        if isinstance(value, asyncio.Future):
            value = await asyncio.shield(value)
        return value
    if bound is not None and len(holder) >= bound:
        return None
    slot = asyncio.get_running_loop().create_future()
    holder[key] = slot
    try:
        value = await fetch()
    except BaseException:
        del holder[key]
        slot.set_result(None)
        raise
    holder[key] = value
    slot.set_result(value)
    return value


def held_provision_list(fetches: Optional[dict], args) -> Optional[dict]:
    """Batch 8 A2: what code's COMPLETE read of this instrument's provision
    list, earlier in the same worker run, established
    (`schedule_units.provision_list_facts`), or None: no dict, no read yet
    (or one still in flight), a list cut short, failed or without text.
    Never raises."""
    try:
        if not fetches or not isinstance(args, dict):
            return None
        return provision_list_facts(fetches.get(provision_fetch_key(args)))
    except Exception:
        return None


async def schedule_route_block(
    name: str,
    args: dict,
    raw_result,
    query: str,
    fetches: Optional[dict],
    chunk_fn: Callable = None,
    summarise_model: str = "",
    parent_on_chunk: Optional[Callable] = None,
    timing_collector=None,
    cancel_event=None,
    pending_chars: int = 0,
    context_budget: Optional[dict] = None,
    retrieved_urls: Optional[set] = None,
) -> str:
    """P3.12: the block for a schedule or annex unit a section search's query
    names and its results left out ("" when there is none).

    Fetches the instrument's provision list once per worker run (`fetches`,
    lid -> outcome, or a Future while that fetch is in flight: `_fetch_once`;
    None disables the route), picks the unit by `uri` and hands
    it over: cut where it cuts cleanly (`schedule_units.cut_pieces`), else
    whole, summarised for the query when it is larger than a result the Worker
    would be handed verbatim (the same threshold, and the same context budget,
    as any tool result). Batch 10 A: a whole schedule over that threshold
    whose query names no paragraph goes first as its paragraph headings and
    the paragraphs whose headings share a distinctive word with the section
    search's query (`schedule_units.matched_pieces`), where they fit; only
    otherwise is it summarised. A unit the complete list does not hold is said in
    code: a true negative, attributed to the index. On a failed list, the
    instrument's whole text with its schedules (P3.27's flag) is cut at the
    unit's heading; failing that, a line says the question is open.
    Exceptions propagate: the caller fails soft.
    """
    if name != "search_legislation_sections" or fetches is None or not isinstance(args, dict):
        return ""
    units = [u for u in named_units(args.get("query"))
             if unit_in_results(raw_result, u) is False]
    if not units:
        return ""
    lid = provision_fetch_key(args)
    if not lid:
        return ""
    # Batch 9 A: the slot is reserved (and counted against the bound) before
    # the await, so the bound and the one-fetch-per-instrument memo hold
    # across a round whose section searches run concurrently.
    outcome = await _fetch_once(
        fetches, lid,
        lambda: fetch_provision_list(lid, on_chunk=parent_on_chunk,
                                     timing_collector=timing_collector),
        bound=MAX_PROVISION_FETCHES)
    if outcome is None:
        return ""

    from .provider_factory import get_summarise_threshold
    threshold = get_summarise_threshold()
    out = []
    for unit in units:
        source, url, text = FROM_LIST, "", None
        sole_reason = ""
        if not unit.label:
            # Decision 1 (user, 2026-10-06): "the Schedule" with no label. Act
            # only on a provision list that holds no schedule or annex (the
            # true negative) or exactly one schedule (handed over whole, cut
            # nothing); with two or more the query does not say which, so
            # nothing is appended. No fallback on a failed list.
            if outcome.get("status") != "ok":
                continue
            action, row = bare_schedule_action(outcome.get("rows"),
                                               bool(outcome.get("complete")))
            if action == BARE_ABSENT:
                out.append(unit_absent_line(lid, unit, outcome.get("rows") or [], True))
                continue
            if action != BARE_ONE:
                continue
            unit = row_unit(row)
            url = str(row.get("uri") or row.get("id") or "")
            text = str(row.get("text") or "")
            if not text.strip():
                out.append(unit_without_text_line(lid, unit))
                continue
            sole_reason = sole_schedule_reason(lid)
        elif outcome.get("status") == "ok":
            row = pick_provision(outcome.get("rows"), unit)
            if row is None:
                out.append(unit_absent_line(lid, unit, outcome.get("rows") or [],
                                            bool(outcome.get("complete"))))
                continue
            url = str(row.get("uri") or row.get("id") or "")
            text = str(row.get("text") or "")
            if not text.strip():
                out.append(unit_without_text_line(lid, unit))
                continue
        elif outcome.get("status") == "no_text":
            out.append(instrument_without_text_line(lid, unit))
            continue
        else:
            # The fallback's whole text is fetched once per instrument too,
            # by the same reservation, however many calls of a round need it.
            whole = await _fetch_once(
                outcome, "text",
                lambda: fetch_text_with_schedules(lid, on_chunk=parent_on_chunk,
                                                  timing_collector=timing_collector))
            text = cut_unit_from_text(whole or "", unit)
            if not text:
                out.append(fetch_failed_line(lid, unit))
                continue
            source = FROM_TEXT
        # Batch 13 B: past the threshold, the named paragraphs that cut are
        # handed over even where another named one does not cut.
        pieces, how, reason = cut_pieces(unit, text, whole_limit=threshold)
        reason = " ".join(r for r in (sole_reason, reason) if r)
        total = sum(len(t) for _, t in pieces)
        over_budget = (context_budget is not None and
                       context_budget["used"] + pending_chars + total > context_budget["limit"])
        # Batch 10 A: a whole schedule over the verbatim threshold, whose query
        # names no paragraph, is handed over as its heading list and the
        # paragraphs whose headings match the section search's query, where
        # they fit the bound and the context budget; otherwise summarised.
        # (`matched_pieces` itself refuses a cut, an annex or a named paragraph.)
        matched = None
        if total > threshold:
            matched = matched_pieces(unit, text, args.get("query"),
                                     max(threshold, MATCHED_CUTS_MIN_CHARS))
            if matched is not None and context_budget is not None:
                size = sum(len(lbl) + len(t) for lbl, t in matched)
                if context_budget["used"] + pending_chars + size > context_budget["limit"]:
                    matched = None
        summary_of = how
        numbers = ()
        if matched is not None:
            pieces, how = matched, MATCHED
            numbers = matched_numbers(unit, text, args.get("query"))
        elif total > threshold or over_budget:
            joined = "\n\n".join((lbl + "\n" if lbl else "") + t for lbl, t in pieces)
            summary, _degraded = await summarise_for_query(
                joined, query, summarise_model, chunk_fn=chunk_fn,
                timing_collector=timing_collector,
                doc_name=f"{unit.display()} of {lid}", cancel_event=cancel_event)
            if len(summary) > threshold:
                summary = summary[:threshold]
            if timing_collector:
                from .summarisation import SUMMARISE_CHUNK_CHARS
                timing_collector.record_summarisation(
                    total, len(summary), max(1, -(-total // SUMMARISE_CHUNK_CHARS)))
            pieces, how = [("", summary)], SUMMARY
        if url and retrieved_urls is not None:
            harvest_legislation_urls(json.dumps({"url": url}), into=retrieved_urls)
        block = fetched_block(lid, unit, url, pieces, how, reason=reason,
                              total_chars=total, source=source, summary_of=summary_of,
                              matched=numbers)
        pending_chars += len(block)
        out.append(block)
    return "".join(out)



def _enabling_subject(name: str, args: dict, raw_result) -> str:
    """The one instrument a text read, section search or lookup was about."""
    if name == LOOKUP_TOOL:
        try:
            return str((json.loads(raw_result) or {}).get("legislation_id") or "")
        except Exception:
            return ""
    return str((args or {}).get("legislation_id") or "")


async def stored_enabling_note(lid: str, search_log: Optional[list]) -> str:
    """P2.3's permitting ENABLING POWER block from the made-under record (P3.31),
    or "". Once per instrument per run; never raises."""
    try:
        from ..utils.search_scope import _enabling_stated_block, _is_secondary
        lid = str(lid or "").strip().strip("/")
        if not lid or not _is_secondary(lid):
            return ""
        if any(e.get("tool") == "enabling_power" and e.get("legislation_id") == lid[:60]
               and e.get("stated") for e in (search_log or [])):
            return ""
        from ..services.made_under_store import recital_for
        recital = await recital_for(lid)
        if not recital:
            return ""
        if search_log is not None:
            search_log.append({"tool": "enabling_power", "legislation_id": lid[:60],
                               "stated": True, "source": "made_under_record"})
        return _enabling_stated_block(
            lid, "... " + recital,
            source=f"the made-under record (the as-made preamble of {lid}, harvested from "
                   "legislation.gov.uk)")
    except Exception:
        return ""


def _has_scottish_list(result) -> bool:
    """P3.20: a `search_case_law` result that carries SCTS's list."""
    try:
        d = json.loads(result) if isinstance(result, str) else result
        return isinstance(d, dict) and isinstance(d.get("scottish"), dict)
    except Exception:
        return False


def _case_law_note_with_scottish(args: dict, result) -> str:
    """P3.20: the notes on a `search_case_law` result with both lists.

    The Find Case Law half is what it always was (its window note, or its
    zero note without the stop rule), then the Scottish list's window note or
    zero note, then ONE stop rule if both lists are empty, or ONE imperative
    naming up to three judgments from each list, last, as P2.2's order puts it.
    Never raises.
    """
    try:
        data = json.loads(result) if isinstance(result, str) else result
        fcl = data.get("results") if isinstance(data.get("results"), list) else []
        scot = (data.get("scottish_results")
                if isinstance(data.get("scottish_results"), list) else [])
        block = data.get("scottish") or {}
        note = ""
        if fcl:
            note += case_law_search_note(args, data)
        elif not data.get("error"):
            note += FCL_ZERO_NOTE_WITH_SCTS
        if block.get("status") == "ok" and not scot:
            note += SCTS_ZERO_NOTE
        else:
            note += scottish_search_note(args, data)
        if not fcl and not scot:
            if not data.get("error") and block.get("status") == "ok":
                note += CASE_LAW_BOTH_ZERO_STOP
            return note
        lines = [f'  - url: "{r["url"]}"  ({r.get("title", "")} {r.get("ncn", "")})'
                 for r in fcl[:3] if isinstance(r, dict) and r.get("url")]
        for r in scot[:3]:
            if not isinstance(r, dict) or not r.get("url"):
                continue
            label = ", ".join(p for p in (
                r.get("title") or "", r.get("ncn") or "", r.get("court") or "",
                f"decided {r['decision_date']}" if r.get("decision_date") else "") if p)
            lines.append(f'  - url: "{r["url"]}"  ({label})')
        url_lines = "\n".join(lines)
        note += (
            f"\n\n[MANDATORY NEXT STEP — DO NOT synthesise yet. "
            f"Call get_case_law_text for the 1–3 most relevant cases below to retrieve the full judgment text "
            f"before composing your answer. Pass the exact url field:\n{url_lines}]"
        )
        appeals = detect_appellate_decisions(fcl)
        if appeals:
            appeal_lines = "\n".join(
                f'  - url: "{r["url"]}"  ({r.get("title", "")} {r.get("ncn", "")})'
                for r in appeals[:3]
            )
            note += (
                f"\n\n[NOTE — APPELLATE DECISION PRESENT: the results include an appeal "
                f"of a case that also appears at a lower court level. You MUST retrieve and "
                f"cite the appellate (higher-court) decision below via get_case_law_text — "
                f"do not rely on the first-instance judgment alone:\n{appeal_lines}]"
            )
        return note
    except Exception:
        logger.warning("[Worker] Case-law note with the Scottish list failed", exc_info=True)
        return ""


async def run_worker_tool(
    name: str,
    args: dict,
    query: str,
    chunk_fn: Callable,
    summarise_model: str,
    parent_on_chunk: Optional[Callable] = None,
    timing_collector=None,
    source_accumulator: Optional[list] = None,
    search_budget: Optional[dict] = None,
    cancel_event=None,
    tool_memo: Optional[dict] = None,
    memo_count_redundant: bool = False,
    context_budget: Optional[dict] = None,
    audit_delegation: Optional[dict] = None,
    retrieved_urls: Optional[set] = None,
    search_log: Optional[list] = None,
    result_suffix: str = "",
    provision_fetches: Optional[dict] = None,
) -> str:
    """Execute a single Worker tool call and return the (possibly summarised) result.

    Args:
        name: Tool function name.
        args: Tool arguments dict.
        query: The original research query, used to focus summarisation.
        chunk_fn: Provider-specific summarisation chunk function.
        summarise_model: Model to use for summarisation (may differ from main model).
        parent_on_chunk: SSE streaming callback for progress events.
        timing_collector: Optional timing collector for metrics.
        source_accumulator: If provided, structured sources are extracted from the
            raw result (before summarisation) and appended here.
        tool_memo: Per-request memo dict keyed
            (tool_name, canonical args JSON) → {"raw", "final"}. Exact-match
            repeats return the cached final result without the API call or
            re-summarisation; the memo dies with the request.
        memo_count_redundant: If True (standard research mode), a memo hit is
            ALSO counted via record_worker_tool so the "model re-fetched the
            same Act" loop-health signal survives — the hit costs nothing but
            still reflects model behaviour. Deep Research leaves this False:
            cross-step reuse there is by design, not misbehaviour.
        context_budget: Per-worker-run {"used": chars, "limit": chars}. Once the
            accumulated tool output would exceed the limit, results are summarised
            regardless of their own size — the per-result threshold alone does not
            bound the sum. None disables the budget.
        audit_delegation: The audit trace's delegation record this tool call
            belongs to (evaluation harnesses only; None on /api/chat). Passed
            explicitly rather than read from a ContextVar so nesting stays
            correct if worker runs are ever parallelised.
        retrieved_urls: Per-request set of every legislation.gov.uk URL any tool
            returned, harvested from the RAW response (P1.6/B14). Feeds the
            provision-link enforcement at the answer seam. None disables both the
            harvest and, downstream, the enforcement — so a caller that does not
            thread it keeps exactly the previous behaviour.
        search_log: Per-WORKER-RUN list of the searches this run issued (P2.2/B5).
            Rendered onto the worker's report by `run_worker_agent`, because the
            agent that writes the negative — the Manager, or the Deep Research
            synthesis — never sees a tool result. Run-scoped, not request-scoped,
            unlike `retrieved_urls`: "what this step searched for" is a statement
            about one step. None disables the record.
        result_suffix: Text the caller appends to this result, last, so the
            memo, the context budget and the audit's `final_result` all see
            exactly what the model receives (P3.25: the quick-lookup Worker's
            recital block from a code lookup). Not applied to a memo hit or a
            refused call, which return what they returned before. "" (the
            default) changes nothing.
        provision_fetches: Per-WORKER-RUN dict, legislation_id -> the outcome
            of code's `/legislation/section/lookup` for it (P3.12). When a
            section search's query names a schedule or annex unit its results
            left out, `schedule_route_block` fetches the instrument's
            provisions once, picks the unit by `uri` and appends it. A slot
            holds a Future while its fetch is in flight, so the calls of one
            round share it (`_fetch_once`). None (the default) disables the
            route.
    """
    activity_id = uuid.uuid4().hex[:8]

    # Audit trace: open a tool record and sniff the on_chunk callback so the
    # external API calls the executor makes land inside THIS tool's record.
    _audit = get_audit_collector()
    _audit_tool = _audit.start_tool(audit_delegation, name, args) if _audit else None
    if _audit_tool is not None:
        parent_on_chunk = _audit.sniff_on_chunk(_audit_tool, parent_on_chunk)

    # P2.7: the legislation discovery budget, checked BEFORE the memo lookup
    # (the parliamentary one below is checked after it, and is unchanged). A
    # step repeating its own search is the loop this budget exists for, so a
    # memo-served search is refused too once the step's search rounds are
    # spent (see utils/discovery_budget.py). A blocked call is not a search:
    # it is kept out of `record_search` and the phase counts, and recorded
    # instead as a stop, which the worker's block and the lawyer's footer
    # both state as a limit.
    #
    # P3.1: the per-instrument section budget, the same way one level down: at
    # most 3 rounds of `search_legislation_sections` on one legislation_id per
    # worker run, also checked before the memo. Its refusals share this path,
    # the audit's `budget_blocked` flag and the `search_budget_blocked`
    # counter; the audit record's tool name tells the two apart.
    refusal = None
    if search_budget is not None:
        if legislation_budget_blocks(search_budget, name):
            record_budget_stop(search_log, name, args, search_budget)
            refusal = (legislation_stop_message(search_budget),
                       "Discovery budget spent", "Search limit reached")
        elif section_budget_blocks(search_budget, name, args):
            # Batch 8 A2: where code has read this instrument's complete
            # provision list in this run, the refusal, the scope record and
            # the footer say what it holds (None: exactly as before).
            held = held_provision_list(provision_fetches, args)
            record_section_budget_stop(search_log, name, args, search_budget, held=held)
            refusal = (section_stop_message(search_budget, args, held=held),
                       "Section budget spent for this instrument",
                       "Section-search limit reached")
    if refusal is not None:
        stop_msg, log_label, ui_label = refusal
        if timing_collector:
            timing_collector.record_search_budget_blocked()
        logger.info(f"[Worker] {log_label} — '{name}' not run")
        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})
            await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": ui_label})
        if _audit:
            _audit.end_tool(
                _audit_tool, raw_result=stop_msg, final_result=stop_msg,
                budget_blocked=True,
            )
        return stop_msg

    # Tool-result memo: exact-arg repeats within one request are served from
    # the per-request memo. In Deep Research, counted only as memo_hits — NOT
    # as a worker tool call / phase call / redundant call (it's a saving, not
    # a loop-health signal); standard mode also counts redundancy (see
    # memo_count_redundant). A hit never consumes the search budget.
    memo_key = None
    if tool_memo is not None:
        try:
            memo_key = (name, json.dumps(args, sort_keys=True))
        except (TypeError, ValueError):
            memo_key = None
        if memo_key is not None and memo_key in tool_memo:
            hit = tool_memo[memo_key]
            logger.info(f"[Worker] Memo hit for '{name}' — returning cached result")
            if timing_collector:
                timing_collector.record_memo_hit()
                if memo_count_redundant:
                    timing_collector.record_worker_tool(name, _worker_tool_key_arg(args))
            # The reusing step must still get this retrieval's sources: re-run
            # extraction on the stored RAW result against this step's accumulator.
            if source_accumulator is not None:
                _extract_sources_from_tool(name, args, hit["raw"], source_accumulator)
            # Same for the retrieved-URL set: the memo saves the fetch, not the
            # provenance. A step reusing a memoised retrieval has still retrieved
            # those provisions and must be allowed to cite them.
            if retrieved_urls is not None:
                harvest_legislation_urls(hit["raw"], into=retrieved_urls)
            # P2.9 (B5): the search itself, which P2.2 did not record on this
            # path. `search_log` is per-WORKER-RUN while the memo is
            # per-REQUEST, so a step served from an earlier step's search had
            # that query missing from its own record — and the block still told
            # the agent writing the negative that it "MUST quote the search
            # terms above", with none above. Measured over the six replay
            # directories that have a scope block (`replay_report scoperecord`):
            # 277 of 1,189 searches (23%) absent, in 86 of 259 worker runs
            # (33%), 11 of which recorded NO search at all; and `issued -
            # recorded == memo hits` exactly, per run, with no exceptions across
            # all six — which is what identifies the memo as the sole cause.
            # Gated on the tool name here because `record_search` does not
            # self-gate: the two call sites on the non-memo path do it, and this
            # is the third.
            if name in ("search_legislation", "search_legislation_sections"):
                record_search(search_log, name, args, hit["raw"])
            # P2.3 (B3b): a memo hit is still a retrieval for this step, and the
            # enabling-power record drives a PERMISSION as well as a prohibition
            # — omitting it here would forbid a claim the material supports.
            record_enabling_power(search_log, name, args, hit["raw"])
            # P3.5 (B3): and the change record, for the same reason — a step
            # reusing a memoised retrieval has still consulted it, and the
            # record drives a PERMISSION (state the relation) as well as a
            # disclosure. Silent here, the worker's report would say the step
            # never looked.
            record_relations(search_log, name, args, hit["raw"])
            # P2.5 (B4): and the currency evidence. Same argument a third time,
            # and it bites hardest here: `_currency_limb` speaks on every step
            # that touched legislation, so a memo hit that did not record its
            # `valid_date` or its `coming into force` count would leave the
            # report block forbidding a currency statement the step's own
            # retrieval supports.
            record_currency(search_log, name, args, hit["raw"])
            # P2.4 (B12): and a case-law search, for the lawyer-facing corpus
            # disclosure. A memo-served search is still a search this step ran;
            # P2.9 is the measured cost of forgetting that on this path.
            # Self-gated on the tool name.
            record_case_law_search(search_log, name, args, hit["raw"])
            # P2.4 (6373): a memoised not-found is still this step's not-found.
            record_not_held(search_log, name, args, hit["raw"])
            # P3.7: and a memoised lookup is still this step's lookup. A model
            # repeating the lookup code ran for it is served from here.
            record_lookup(search_log, name, args, hit["raw"])
            if parent_on_chunk:
                await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})
                await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Done (cached)"})
            # A memo hit costs no API call, but the result still lands in the
            # context a second time — so it still spends context budget.
            if context_budget is not None:
                context_budget["used"] += len(hit["final"])
            if _audit:
                _audit.end_tool(
                    _audit_tool, raw_result=hit["raw"], final_result=hit["final"],
                    memo_hit=True,
                )
            return hit["final"]

    # Parliamentary search budget: after the allowed number of search/listing calls,
    # return a hard-stop so the model proceeds to retrieval instead of looping.
    _PARLIAMENT_SEARCH_TOOLS = {
        "search_scottish_parliament", "search_scottish_committee_transcripts", "search_scottish_plenary",
        "search_hansard",  # Westminster discovery tool — same budget, same stop semantics
    }
    # `"remaining" in` since P2.7: a legislation budget is also a dict now, and
    # a parliamentary tool name hallucinated in a legislation mode must reach
    # the executor's unknown-tool path, not a KeyError here.
    if search_budget is not None and "remaining" in search_budget and name in _PARLIAMENT_SEARCH_TOOLS:
        if search_budget["remaining"] <= 0:
            # The parliament bot's defining constraint: a budget-blocked search
            # means the model looped on discovery instead of retrieving. Count it
            # on its own counter (NOT worker_tool_calls / phase counts).
            if timing_collector:
                timing_collector.record_search_budget_blocked()
            if name == "search_hansard":
                instruction = (
                    "STOP calling search_hansard. You MUST now either: (a) call get_hansard_debate "
                    "with a debate_ext_id from your previous search results to retrieve the full "
                    "verbatim contributions, or (b) if no results were found at all, synthesize your "
                    "answer stating that no relevant records were found."
                )
            else:
                instruction = (
                    "STOP calling search_scottish_plenary, search_scottish_parliament, or "
                    "search_scottish_committee_transcripts. "
                    "You MUST now either: (a) call get_scottish_plenary_debate or "
                    "get_scottish_committee_transcript with the IDs from your previous search results to "
                    "retrieve full text (search_scottish_parliament results are excerpt-only and need no "
                    "retrieval), or (b) if no results were found at all, synthesize your answer stating that "
                    "no relevant records were found."
                )
            stop_msg = json.dumps({
                "notice": "Search limit reached — you have already performed the maximum number of parliamentary searches.",
                "instruction": instruction,
                "results": [],
                "total": 0,
            })
            if parent_on_chunk:
                await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})
                await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Search limit reached"})
            if _audit:
                _audit.end_tool(
                    _audit_tool, raw_result=stop_msg, final_result=stop_msg,
                    budget_blocked=True,
                )
            return stop_msg
        search_budget["remaining"] -= 1

    # Efficiency: count the worker tool call, classify its phase, and flag a
    # repeat fetch of the same resource (same Act sectioned twice, same case
    # fetched twice). key_arg is the identifying argument for redundancy.
    if timing_collector:
        timing_collector.record_worker_tool(name, _worker_tool_key_arg(args))

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})

    # Dispatch by research mode first: get_member_info / search_bills exist in BOTH
    # the Holyrood and Westminster tool sets with the same names but different
    # backing APIs, so name alone cannot pick the executor.
    if get_request_provider_config().get("_research_mode") == "westminster_records":
        result = await execute_westminster_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)
    elif name in _PARLIAMENT_TOOL_NAMES:
        result = await execute_parliament_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)
    else:
        result = await execute_worker_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)

    # Kept for the memo: source extraction on a memo hit re-parses the raw
    # (pre-summarisation) response, not the summarised final string.
    raw_result = result

    # Extract sources from the raw structured response BEFORE summarisation compresses it.
    if source_accumulator is not None:
        _extract_sources_from_tool(name, args, result, source_accumulator)

    # P1.6 (B14): record every legislation.gov.uk URL this retrieval returned,
    # from the RAW response. "Did the research retrieve this provision" and "was
    # the model shown the string" are different questions, and they diverge on
    # the ~70% of section searches that get summarised — the summary keeps the
    # section numbers and drops every URL.
    if retrieved_urls is not None:
        harvest_legislation_urls(raw_result, into=retrieved_urls)

    # For search_case_law: inject a Phase 2 nudge to call get_case_law_text for
    # the most relevant results, or a stop note on zero results.
    case_law_note = ""
    # P2.4 (B12): recorded before the parse below, so an errored search (which
    # is not always JSON) is still recorded, as not ok. It feeds the code-emitted
    # corpus disclosure on the answer, which fires on any turn that searched
    # case law, not only on the empty result this note handles.
    record_case_law_search(search_log, name, args, result)
    if name == "search_case_law" and _has_scottish_list(result):
        # P3.20: the result carries SCTS's list beside Find Case Law's (the
        # setting on). Its own composition, so a result without one goes
        # through the branch below exactly as before.
        case_law_note = _case_law_note_with_scottish(args, result)
    elif name == "search_case_law":
        try:
            raw_data = json.loads(result)
            # P3.23: keyed on the SHOWN count, never on `total`. `total` is
            # now the matching total read from the feed's `last` link (an
            # estimate, and for a full page an upper bound), so it need not be
            # 0 when nothing was shown; P1.3 kept `returned` apart from
            # `total_matched` for legislation for the same reason.
            _cl_results = raw_data.get("results")
            n = len(_cl_results) if isinstance(_cl_results, list) else 0
            if n == 0 and not raw_data.get("error"):
                # P2.4 (B12): "does not comprehensively index" was false; the
                # gap is total (TNA rejects `court=csoh` with a 400). The UKSC
                # half matters as much: Scottish appeals ARE indexed.
                case_law_note = (
                    "\n\n[This search returned 0 results. The National Archives Find Case Law database "
                    "holds no decisions of the Court of Session, the Sheriff Appeal Court, the Sheriff "
                    "Courts or the High Court of Justiciary; Scottish appeals decided by the UK Supreme "
                    "Court are included. "
                    "If you have already tried 2–3 different queries without results, stop searching "
                    "and compose your answer noting that no directly relevant case law was found in this database.]"
                )
            elif n > 0:
                results = raw_data.get("results", [])
                url_lines = "\n".join(
                    f'  - url: "{r["url"]}"  ({r.get("title", "")} {r.get("ncn", "")})'
                    for r in results[:3]
                    if r.get("url")
                )
                # P3.23: the window first, so the imperative stays last (P2.2's
                # order for the legislation scope block).
                case_law_note = case_law_search_note(args, raw_data) + (
                    f"\n\n[MANDATORY NEXT STEP — DO NOT synthesise yet. "
                    f"Call get_case_law_text for the 1–3 most relevant cases below to retrieve the full judgment text "
                    f"before composing your answer. Pass the exact url field:\n{url_lines}]"
                )
                # Appeals nudge: when both a first-instance judgment and its appeal
                # appear in the results, cite the higher court, not only the lower one.
                appeals = detect_appellate_decisions(results)
                if appeals:
                    logger.info(
                        "[Worker] A2 appellate nudge fired: flagged %d appellate decision(s) — %s",
                        len(appeals),
                        ", ".join(r.get("url", "") for r in appeals[:3]),
                    )
                    appeal_lines = "\n".join(
                        f'  - url: "{r["url"]}"  ({r.get("title", "")} {r.get("ncn", "")})'
                        for r in appeals[:3]
                    )
                    case_law_note += (
                        f"\n\n[NOTE — APPELLATE DECISION PRESENT: the results include an appeal "
                        f"of a case that also appears at a lower court level. You MUST retrieve and "
                        f"cite the appellate (higher-court) decision below via get_case_law_text — "
                        f"do not rely on the first-instance judgment alone:\n{appeal_lines}]"
                    )
        except Exception:
            pass

    # For search_scottish_parliament: the results are excerpt-only (TheyWorkForYou
    # exposes no full-text retrieval endpoint for Holyrood plenary content), so nudge
    # the model to synthesise from the excerpts rather than re-searching or trying to
    # fetch full text.
    sp_phase2_note = ""
    if name == "search_scottish_parliament":
        try:
            raw_data = json.loads(result)
            results = raw_data.get("results", [])
            if results:
                sp_phase2_note = (
                    "\n\n[These Scottish Parliament plenary results are EXCERPT-ONLY — there is no full-text "
                    "retrieval tool for them. DO NOT call search_scottish_parliament again (unless you received "
                    "ZERO results). Compose your answer from the excerpts above, citing the speaker, date, and URL "
                    "of each. If the question concerns committee activity, call search_scottish_committee_transcripts.]"
                )
            else:
                sp_phase2_note = (
                    "\n\n[This search returned 0 results. You may retry search_scottish_parliament with "
                    "different or broader keywords. If after 2 searches you still have 0 results, "
                    "state that no relevant Scottish Parliament records were found and compose your answer.]"
                )
        except Exception:
            pass

    sp_committee_phase2_note = ""
    if name == "search_scottish_committee_transcripts":
        try:
            raw_data = json.loads(result)
            items = raw_data.get("results", [])
            note = raw_data.get("note", "")
            if note and not items:
                sp_committee_phase2_note = f"\n\n[{note}]"
            elif items:
                item_lines = [
                    f'  - meeting_id: "{r["meeting_id"]}"  slug: "{r["slug"]}"  iob_id: "{r["iob_id"]}"'
                    f'  ({r.get("committee_name", "")}, {r.get("meeting_date", "")} — {r.get("agenda_item_title", "")})'
                    for r in items[:8]
                    if r.get("meeting_id") and r.get("iob_id")
                ]
                if item_lines:
                    sp_committee_phase2_note = (
                        f"\n\n[MANDATORY NEXT STEP — Call get_scottish_committee_transcript for the most "
                        f"relevant result(s) below to retrieve full speech text before composing your answer. "
                        f"Pass meeting_id, slug, and iob_id exactly as shown:\n"
                        + "\n".join(item_lines)
                        + "]"
                    )
            else:
                sp_committee_phase2_note = (
                    "\n\n[No committee transcript results found. "
                    "Try search_scottish_committee_transcripts with different or broader keywords, "
                    "or use search_scottish_parliament for plenary debates.]"
                )
        except Exception:
            pass

    sp_plenary_phase2_note = ""
    if name == "search_scottish_plenary":
        try:
            raw_data = json.loads(result)
            items = raw_data.get("results", [])
            note = raw_data.get("note", "")
            if note and not items:
                sp_plenary_phase2_note = f"\n\n[{note}]"
            elif items:
                item_lines = [
                    f'  - meeting_id: "{r["meeting_id"]}"  slug: "{r["slug"]}"  iob_id: "{r["iob_id"]}"'
                    f'  ({r.get("meeting_date", "")} — {r.get("agenda_item_title", "")})'
                    for r in items[:8]
                    if r.get("meeting_id") and r.get("iob_id")
                ]
                if item_lines:
                    sp_plenary_phase2_note = (
                        f"\n\n[MANDATORY NEXT STEP — Call get_scottish_plenary_debate for the most "
                        f"relevant result(s) below to retrieve the full verbatim speeches before composing "
                        f"your answer. Pass meeting_id, slug, and iob_id exactly as shown:\n"
                        + "\n".join(item_lines)
                        + "]"
                    )
            else:
                sp_plenary_phase2_note = (
                    "\n\n[No plenary debate results found. "
                    "Try search_scottish_plenary with different or broader keywords, "
                    "or use search_scottish_parliament for excerpt-only plenary content.]"
                )
        except Exception:
            pass

    hansard_phase2_note = ""
    if name == "search_hansard":
        try:
            raw_data = json.loads(result)
            items = raw_data.get("results", [])
            note = raw_data.get("note", "")
            if items:
                item_lines = [
                    f'  - debate_ext_id: "{r["debate_ext_id"]}"'
                    f'  ({r.get("house", "")} {r.get("section", "")}, {r.get("date", "")} — {r.get("title", "")})'
                    for r in items[:8]
                    if r.get("debate_ext_id")
                ]
                if item_lines:
                    hansard_phase2_note = (
                        "\n\n[MANDATORY NEXT STEP — Call get_hansard_debate for the most relevant "
                        "result(s) below to retrieve the full verbatim contributions before composing "
                        "your answer. Pass debate_ext_id exactly as shown:\n"
                        + "\n".join(item_lines)
                        + "]"
                    )
            elif note:
                hansard_phase2_note = f"\n\n[{note}]"
            else:
                hansard_phase2_note = (
                    "\n\n[This search returned 0 results. You may retry search_hansard once with "
                    "different or broader keywords. If you still have 0 results, state that no "
                    "relevant Hansard records were found and compose your answer.]"
                )
        except Exception:
            pass

    # For search_legislation: capture legislation_ids from the raw response before
    # any summarisation strips them, so we can inject a Phase 2 instruction into
    # the final result the model actually sees.
    #
    # P2.2 (B5) adds the scope block alongside. The row was written against the
    # missing `else:` on `if id_pairs:` — the only search tool with no
    # zero-result nudge — but that branch fires on 4 of 790 searches post-Wave-1,
    # while **783 of 783** are windowed (5 rows of a median 141 matches) and all
    # 17 measured bare negatives came from a NON-empty result. So the block is
    # attached on both branches, and the non-empty one is the one that matters.
    phase2_note = ""
    scope_note = ""
    if name == "search_legislation":
        try:
            raw_data = json.loads(result)
            id_pairs = extract_legislation_ids_from_search(raw_data)
            if timing_collector:
                timing_collector.record_legislation_ids_seen(lid for lid, _ in id_pairs)
            scope_note = legislation_search_note(
                args, raw_data, get_request_provider_config()
            )
            record_search(search_log, name, args, raw_data)
            # P2.5 (B4): the repeal/revocation marker legislation.gov.uk puts in
            # the title itself — the only currency signal a search result
            # carries, on 1.7% of rows, and the one a lawyer must not miss.
            scope_note += currency_note(args, raw_data)
            record_currency(search_log, name, args, raw_data)
            if id_pairs:
                id_lines = "\n".join(
                    f'  - legislation_id: "{lid}"  ({title})'
                    for lid, title in id_pairs[:5]
                )
                phase2_note = (
                    f"\n\n[NEXT STEP: Call search_legislation_sections with the relevant "
                    f"legislation_id(s) below to retrieve the actual legal text before "
                    f"composing your answer:\n{id_lines}]"
                )
        except Exception:
            phase2_note = (
                "\n\n[NEXT STEP: Call search_legislation_sections with the legislation_id "
                "from this result to retrieve the actual legal text.]"
            )

    # P2.2 (B5), second source of bare negatives: a provision absent from the
    # ranked ten is not absent from the Act. 6335 turn 7 reported that a targeted
    # search "returned no results" when it had returned results, and then
    # invented a cause for it. This tool had no note of any kind before now.
    if name == "search_legislation_sections":
        try:
            _sec_data = json.loads(result)
            scope_note = section_search_note(args, _sec_data)
            record_search(search_log, name, args, _sec_data)
        except Exception:
            scope_note = ""

    # P2.3 (B3b): *made under* is the one B3 relation no endpoint returns, so the
    # only evidence of it is an instrument's own preamble — which arrives in
    # `legislation.description` on this response and nowhere else. Computed from
    # the RAW result for the same reason `provision_url_block` is: a large
    # instrument gets summarised and the summariser drops the preamble, so by
    # the time the model reads the text the evidence has gone.
    enabling_note = ""
    # P3.27: which schedules and annexes this whole text carries, or that the
    # index holds none for the instrument. From the RAW result (the executor
    # stamped where the schedule text starts), appended after summarisation:
    # a summary of a 1.2M-character Act keeps neither the boundary nor the
    # headings, and the Worker must know what the text it read contains.
    schedules_line = ""
    if name == "get_legislation_text":
        enabling_note = enabling_power_note(args, raw_result)
        schedules_line = schedules_note(args, raw_result)
    elif name == LOOKUP_TOOL:
        # P3.25: the lookup record carries the same `description`, where most
        # recitals sit. Only the permitting block, and only where it has one.
        enabling_note = lookup_enabling_note(raw_result)
    elif name == MADE_UNDER_TOOL:
        # P3.31: the reverse question, answered from the made-under record.
        enabling_note = made_under_note(raw_result)
        record_made_under(search_log, raw_result)
    # P3.31, the forward question: where the record read here carries no
    # recital (0 of 28 SSIs at `/legislation/text`, P2.3), the made-under
    # record may hold the instrument's as-made preamble. Only the permitting
    # block is ever built from it, once per instrument per run, and it
    # replaces P2.3's forbidding block for that instrument only.
    if name in ("get_legislation_text", "search_legislation_sections", LOOKUP_TOOL)             and "DOES state what" not in enabling_note:
        stored = await stored_enabling_note(_enabling_subject(name, args, raw_result), search_log)
        if stored:
            enabling_note = stored
    record_enabling_power(search_log, name, args, raw_result)

    # P3.5 (B3): the other four relations of the bucket, which ARE retrievable.
    # Computed from the RAW result for the same reason as everything else at
    # this seam — a large change record is summarised, and a summary of a
    # relation list keeps the prose and drops the counts the block is about.
    relations_note = ""
    if name == "get_legislation_changes":
        relations_note = amendment_search_note(args, raw_result)
    record_relations(search_log, name, args, raw_result)

    # P2.5 (B4): the change record's currency-bearing counts, and `valid_date`
    # off a `/legislation/text` response. From the RAW result for the reason
    # every other recorder at this seam is — a summarised change record keeps
    # the prose and drops the counts, and a summarised instrument drops the
    # metadata block `valid_date` lives in.
    #
    # **Name-gated here rather than left to `record_currency`'s own dispatch.**
    # `record_currency` also handles `search_legislation`, and that call is made
    # further up next to `currency_note`, which needs the same parsed page. At
    # this point `raw_result` is still the executor's own output — summarisation
    # is below — so the two calls would see identical data and record the page
    # twice. One seam per tool.
    # P3.25: and `valid_date` off a lookup record, the route that replaces the
    # whole text for the quick-lookup Worker.
    if name in ("get_legislation_changes", "get_legislation_text", LOOKUP_TOOL):
        record_currency(search_log, name, args, raw_result)

    # P2.4 (6373): a retrieval by id that the index answered with not-found.
    # The Worker read that as proof the lawyer's citation was wrong in all three
    # reps of the pre-measurement. Stated at the result, and carried to the
    # Manager in the worker's block. Keyed on the API's own not-found detail,
    # never on the model's prose.
    not_held = not_held_note(args, raw_result)
    record_not_held(search_log, name, args, raw_result)
    # P3.7: the lookup's definite outcome, for the worker's block and the
    # lawyer's footer. Self-gated on the tool name.
    record_lookup(search_log, name, args, raw_result)

    from .provider_factory import get_summarise_threshold
    # Two independent triggers: this result is large on its own, OR the run has
    # accumulated enough context that even a modest addition is no longer free.
    # The second is what stops several under-threshold retrievals stacking into a
    # prefill the provider cannot start streaming inside the read timeout.
    _over_budget = (
        context_budget is not None
        and context_budget["used"] + len(result) > context_budget["limit"]
    )
    # Audit flags — what happened to the raw result on its way to the model.
    _audit_summarised = False
    _audit_local_hit = False
    _audit_truncated = False
    # P3.31: the made-under list is bounded by construction (`MAX_LISTED`,
    # compact rows), and a summary that dropped instruments from it would
    # undo the tool, so it always reaches the Worker whole.
    if (len(result) > get_summarise_threshold() or _over_budget) and name != MADE_UNDER_TOOL:
        if _over_budget and len(result) <= get_summarise_threshold():
            logger.info(
                f"[Worker] Context budget reached "
                f"({context_budget['used']}/{context_budget['limit']} chars) — "
                f"summarising {len(result)}-char result from '{name}' that would "
                f"otherwise pass through raw"
            )
        else:
            logger.info(
                f"[Worker] Result from '{name}' is {len(result)} chars — summarising "
                f"with model '{summarise_model}'"
            )

        doc_name = name
        try:
            result_data = json.loads(result)
            doc_name = (
                result_data.get("title")
                or result_data.get("name")
                or args.get("legislation_id")
                or name
            )
        except Exception:
            doc_name = args.get("legislation_id") or name

        summarise_id = uuid.uuid4().hex[:8]

        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {
                "type": "tool_start",
                "tool": "Extracting the relevant sections from a large document",
                "id": summarise_id,
            })

        # Local prompt cache (D7): cross-user/cross-provider summary reuse,
        # exact (content_hash, canonicalised-query) match only. Flag-gated;
        # every cache operation is fail-soft (a DB error is just a miss).
        _req_cfg = get_request_provider_config()
        _local_cache_on = _req_cfg.get("_local_prompt_cache_enabled", True)
        # Cache-key query (D8 Phase 5): standard mode keys on the raw user
        # question (deterministic across models/runs) rather than the Manager's
        # paraphrased delegation brief. Deep Research leaves _cache_key_query
        # unset/empty, so each step's plan text keys as before.
        _cache_key_query = _req_cfg.get("_cache_key_query") or query
        _content_hash = None
        _cached = None
        if _local_cache_on:
            from ..services import local_prompt_cache as _local_cache
            # Cross-user safety invariant: only allowlisted (public-source)
            # tools may enter the shared cache — see local_prompt_cache docstring.
            if name not in _local_cache.CACHEABLE_TOOLS:
                _local_cache_on = False
            else:
                _content_hash = _local_cache.content_hash(result)
                _cached = await _local_cache.lookup(_content_hash, _cache_key_query)

        if _cached is not None:
            logger.info(
                f"[Worker] Local cache hit for '{name}' ({len(result)} chars) — "
                f"skipping summarisation"
            )
            # A hit is a saving, not a summarisation: no record_summarisation.
            if timing_collector:
                timing_collector.record_local_cache_hit(_cached["chars_in"] or len(result))
            result = _cached["summary"]
            _audit_summarised = True
            _audit_local_hit = True
        else:
            async def _emit_progress(msg: str) -> None:
                if parent_on_chunk:
                    await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": msg})

            _chars_in = len(result)
            result, _degraded = await summarise_for_query(
                result, query, summarise_model,
                chunk_fn=chunk_fn,
                on_progress=_emit_progress,
                timing_collector=timing_collector,
                doc_name=doc_name,
                cancel_event=cancel_event,
            )
            logger.info(f"[Worker] Summarised to {len(result)} chars")

            if timing_collector:
                from .summarisation import SUMMARISE_CHUNK_CHARS
                _chunks = max(1, -(-_chars_in // SUMMARISE_CHUNK_CHARS))  # ceil division
                timing_collector.record_summarisation(_chars_in, len(result), _chunks)

            _audit_summarised = True

            # Enforce the size cap here, BEFORE the phase nudges are appended, so a
            # summary that still exceeds the threshold is trimmed without losing the
            # nudges (the chat loop's own truncation would chop them off the tail).
            threshold = get_summarise_threshold()
            _truncated = False
            if len(result) > threshold:
                logger.warning(
                    f"[Worker] Summarised result from '{name}' still exceeds threshold "
                    f"({len(result)} -> {threshold} chars)"
                )
                if timing_collector:
                    timing_collector.record_truncation()
                _truncated = True
                _audit_truncated = True
                result = (
                    result[:threshold]
                    + "\n\n[Content truncated — summary exceeded context limit]"
                )

            # Store post-cap, pre-nudge (nudges are request-contextual). Fail-soft.
            # Never store degraded (summariser fell back to raw/partial text) or
            # truncated output — it would poison the key cross-user permanently.
            if _local_cache_on and _content_hash is not None:
                if _degraded or _truncated:
                    logger.info(
                        f"[LocalCache] Not storing degraded/truncated summary for '{doc_name}'"
                    )
                else:
                    await _local_cache.store(
                        _content_hash, _cache_key_query, result,
                        summarise_model=summarise_model,
                        doc_name=str(doc_name) if doc_name else None,
                        chars_in=_chars_in,
                    )

        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {
                "type": "tool_end",
                "tool": "Extracting the relevant sections from a large document",
                "id": summarise_id,
                "result": result,
            })

    # P1.6 (B14): hand the provision URLs back after summarisation. A 32K
    # section retrieval summarises to ~3.5K of prose that names the sections and
    # carries no URLs at all, so the model — forbidden from inventing one and
    # holding none — rebuilds it from the Act's base URI. Appended here for the
    # same reason the nudges are: the summariser cannot discard what it never
    # saw. Only on the summarised path; an unsummarised result already carries
    # its own `url` per row, and restating them would be noise.
    #
    # P3.11 (B10 residual): and the subsection outline, for the same reason
    # and on the same path. Measured over every stored 6348 run: the section
    # search returns s.36 with both subsections, and the summariser keeps the
    # second in 1 of 11 summaries - the Worker then describes the first alone.
    # Both blocks are appended OUTSIDE the local-cache summary, so a cache hit
    # gets them too. `summarised_result_blocks` is the one definition.
    if _audit_summarised:
        result += summarised_result_blocks(name, raw_result)

    # P3.12: a schedule or annex unit the query named and the results left
    # out, fetched by code from the instrument's provision list. After the
    # result's own summarisation, so the unit is never folded into that
    # summary; fail-soft (Invariant 5), so a failure here leaves the search
    # result exactly as it was.
    fetched_note = ""
    try:
        fetched_note = await schedule_route_block(
            name, args, raw_result, query, provision_fetches,
            chunk_fn=chunk_fn, summarise_model=summarise_model,
            parent_on_chunk=parent_on_chunk, timing_collector=timing_collector,
            cancel_event=cancel_event, pending_chars=len(result),
            context_budget=context_budget, retrieved_urls=retrieved_urls)
    except Exception:
        logger.warning("[Worker] Schedule route after a section search failed", exc_info=True)
        fetched_note = ""

    # Append phase nudges after summarisation so they are not discarded
    # by the summariser and remain visible in the message the model receives.
    # P2.2's scope block goes on before the Phase-2 nudge, so the imperative
    # ("call search_legislation_sections with these ids") stays the last thing
    # the model reads on a productive search.
    result += scope_note
    result += not_held
    result += enabling_note
    result += schedules_line
    result += relations_note
    result += fetched_note
    result += phase2_note
    result += sp_phase2_note
    result += sp_committee_phase2_note
    result += sp_plenary_phase2_note
    result += hansard_phase2_note
    result += case_law_note
    result += result_suffix

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Done"})

    if tool_memo is not None and memo_key is not None:
        tool_memo[memo_key] = {"raw": raw_result, "final": result}

    # Charged after the nudges are appended: what is counted is exactly what the
    # model receives, so the budget tracks the real context growth.
    if context_budget is not None:
        context_budget["used"] += len(result)

    if _audit:
        _audit.end_tool(
            _audit_tool,
            raw_result=raw_result,
            final_result=result,
            summarised=_audit_summarised,
            local_cache_hit=_audit_local_hit,
            truncated=_audit_truncated,
        )

    return result
