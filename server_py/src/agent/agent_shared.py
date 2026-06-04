"""
Shared worker-tool execution logic used by both ollama_client and openrouter_client.

Both provider clients run an identical pipeline when processing Worker tool results:
execute the tool, optionally summarise large results, append a Phase 2 nudge for
search_legislation calls.  This module owns that logic once so future changes only
need to happen here.
"""
import json
import logging
import uuid
from typing import Callable, Optional

from .summarisation import call_chunk, summarise_for_query
from .tools import (
    execute_worker_tool,
    execute_parliament_tool,
    extract_legislation_ids_from_search,
    _PARLIAMENT_TOOL_NAMES,
)

logger = logging.getLogger("agent")


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
                "meta": item.get("status") or "",
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

    elif name in ("search_hansard", "search_scottish_parliament"):
        for speech in data.get("results", []):
            url = speech.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            accumulator.append({
                "kind": "Hansard",
                "title": speech.get("debate", ""),
                "sub": speech.get("speaker", ""),
                "meta": speech.get("hdate", ""),
                "cite": f"{speech.get('speaker', '')}, {speech.get('hdate', '')}",
                "url": url,
            })

    elif name == "search_bills":
        for bill in data.get("results", []):
            url = bill.get("url", "")
            if url and any(s.get("url") == url for s in accumulator):
                continue
            accumulator.append({
                "kind": "Bill",
                "title": bill.get("shortTitle", ""),
                "sub": bill.get("currentStage", ""),
                "meta": bill.get("currentHouse", ""),
                "cite": bill.get("shortTitle", ""),
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
    """
    activity_id = uuid.uuid4().hex[:8]

    # Parliamentary search budget: after the allowed number of search_hansard /
    # search_scottish_parliament calls, return a hard-stop message so the model
    # proceeds to get_hansard_debate instead of looping indefinitely.
    _PARLIAMENT_SEARCH_TOOLS = {"search_hansard", "search_scottish_parliament"}
    if search_budget is not None and name in _PARLIAMENT_SEARCH_TOOLS:
        if search_budget["remaining"] <= 0:
            stop_msg = json.dumps({
                "notice": "Search limit reached — you have already performed the maximum number of Hansard searches.",
                "instruction": (
                    "STOP calling search_hansard or search_scottish_parliament. "
                    "You MUST now either: (a) call get_hansard_debate with gid(s) from your previous "
                    "search results to retrieve full text, or (b) if no results were found at all, "
                    "synthesize your answer stating that no relevant Hansard records were found."
                ),
                "results": [],
                "total": 0,
            })
            if parent_on_chunk:
                await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})
                await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Search limit reached"})
            return stop_msg
        search_budget["remaining"] -= 1

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})

    if name in _PARLIAMENT_TOOL_NAMES:
        result = await execute_parliament_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)
    else:
        result = await execute_worker_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)

    # Extract sources from the raw structured response BEFORE summarisation compresses it.
    if source_accumulator is not None:
        _extract_sources_from_tool(name, args, result, source_accumulator)

    # For search_case_law: inject a stop-or-continue nudge so the model knows
    # when to give up on empty searches rather than looping indefinitely.
    case_law_note = ""
    if name == "search_case_law":
        try:
            raw_data = json.loads(result)
            n = raw_data.get("total", 0)
            if n == 0 and not raw_data.get("error"):
                case_law_note = (
                    "\n\n[This search returned 0 results. The National Archives Find Case Law database "
                    "does not comprehensively index Scottish Court of Session cases. "
                    "If you have already tried 2–3 different queries without results, stop searching "
                    "and compose your answer noting that no directly relevant case law was found in this database.]"
                )
            elif n > 0:
                case_law_note = (
                    f"\n\n[Found {n} result(s) above. If these adequately cover the question, "
                    f"proceed to SYNTHESISE your answer now. Only search further if important "
                    f"aspects of the question are not yet covered.]"
                )
        except Exception:
            pass

    # For search_hansard / search_scottish_parliament: inject a mandatory Phase 2 nudge.
    # The model must call get_hansard_debate before composing its answer. Without this
    # nudge weaker models re-search instead of retrieving full text.
    hansard_phase2_note = ""
    if name == "search_hansard":
        try:
            raw_data = json.loads(result)
            results = raw_data.get("results", [])
            if results:
                gid_lines = "\n".join(
                    f'  - gid: "{r["gid"]}"  debate_type: "{r.get("debate_type","debates")}"  ({r.get("speaker", "Unknown")}, {r.get("hdate", "")} — {r.get("debate", "Unknown debate")})'
                    for r in results[:5]
                    if r.get("gid")
                )
                hansard_phase2_note = (
                    f"\n\n[MANDATORY NEXT STEP — DO NOT call search_hansard again. "
                    f"Call get_hansard_debate NOW for the 1-3 most relevant results below to retrieve full speech text. "
                    f"Only call search_hansard again if you received ZERO results. "
                    f"Pass the debate_type field alongside gid so the correct endpoint is used:\n{gid_lines}]"
                )
            else:
                hansard_phase2_note = (
                    "\n\n[This search returned 0 results. You may retry search_hansard with "
                    "different or broader keywords. If after 2 searches you still have 0 results, "
                    "state that no relevant Hansard records were found and compose your answer.]"
                )
        except Exception:
            pass

    sp_phase2_note = ""
    if name == "search_scottish_parliament":
        try:
            raw_data = json.loads(result)
            results = raw_data.get("results", [])
            if results:
                gid_lines = "\n".join(
                    f'  - gid: "{r["gid"]}"  debate_type: "{r.get("debate_type","sp")}"  ({r.get("speaker", "Unknown")}, {r.get("hdate", "")} — {r.get("debate", "Unknown debate")})'
                    for r in results[:5]
                    if r.get("gid")
                )
                sp_phase2_note = (
                    f"\n\n[MANDATORY NEXT STEP — DO NOT call search_scottish_parliament again. "
                    f"Call get_hansard_debate NOW for the 1-3 most relevant results below to retrieve full speech text. "
                    f"Only call search_scottish_parliament again if you received ZERO results. "
                    f"Pass the debate_type field alongside gid so the correct endpoint is used:\n{gid_lines}]"
                )
            else:
                sp_phase2_note = (
                    "\n\n[This search returned 0 results. You may retry search_scottish_parliament with "
                    "different or broader keywords. If after 2 searches you still have 0 results, "
                    "state that no relevant Scottish Parliament records were found and compose your answer.]"
                )
        except Exception:
            pass

    # For search_legislation: capture legislation_ids from the raw response before
    # any summarisation strips them, so we can inject a Phase 2 instruction into
    # the final result the model actually sees.
    phase2_note = ""
    if name == "search_legislation":
        try:
            raw_data = json.loads(result)
            id_pairs = extract_legislation_ids_from_search(raw_data)
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

    from .provider_factory import get_summarise_threshold
    if len(result) > get_summarise_threshold():
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

        async def _emit_progress(msg: str) -> None:
            if parent_on_chunk:
                await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": msg})

        result = await summarise_for_query(
            result, query, summarise_model,
            chunk_fn=chunk_fn,
            on_progress=_emit_progress,
            timing_collector=timing_collector,
            doc_name=doc_name,
        )
        logger.info(f"[Worker] Summarised to {len(result)} chars")

        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {
                "type": "tool_end",
                "tool": "Extracting the relevant sections from a large document",
                "id": summarise_id,
                "result": "Done",
            })

    # Append phase nudges after summarisation so they are not discarded
    # by the summariser and remain visible in the message the model receives.
    result += phase2_note
    result += hansard_phase2_note
    result += sp_phase2_note
    result += case_law_note

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Done"})

    return result
