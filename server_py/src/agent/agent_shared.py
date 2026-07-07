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
        existing = next((s for s in accumulator if s.get("url") == url), None)
        if existing:
            if not existing.get("excerpt") and excerpt:
                existing["excerpt"] = excerpt
        else:
            accumulator.append({
                "kind": "Transcript",
                "title": page_title or "Scottish Parliament Committee",
                "excerpt": excerpt,
                "cite": page_title or url,
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
    cancel_event=None,
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

    # Parliamentary search budget: after the allowed number of search/listing calls,
    # return a hard-stop so the model proceeds to retrieval instead of looping.
    _PARLIAMENT_SEARCH_TOOLS = {"search_hansard", "search_scottish_parliament", "search_scottish_committee_transcripts"}
    if search_budget is not None and name in _PARLIAMENT_SEARCH_TOOLS:
        if search_budget["remaining"] <= 0:
            stop_msg = json.dumps({
                "notice": "Search limit reached — you have already performed the maximum number of parliamentary searches.",
                "instruction": (
                    "STOP calling search_hansard, search_scottish_parliament, or search_scottish_committee_transcripts. "
                    "You MUST now either: (a) call get_hansard_debate or get_scottish_committee_transcript with IDs "
                    "from your previous results to retrieve full text, or (b) if no results were found at all, "
                    "synthesize your answer stating that no relevant records were found."
                ),
                "results": [],
                "total": 0,
            })
            if parent_on_chunk:
                await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})
                await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Search limit reached"})
            return stop_msg
        search_budget["remaining"] -= 1

    # Efficiency: count the worker tool call, classify its phase, and flag a
    # repeat fetch of the same resource (same Act sectioned twice, same case
    # fetched twice). key_arg is the identifying argument for redundancy.
    if timing_collector:
        key_arg = (
            args.get("legislation_id") or args.get("url")
            or args.get("gid") or args.get("meeting_id")
        )
        timing_collector.record_worker_tool(name, key_arg)

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}", "id": activity_id})

    if name in _PARLIAMENT_TOOL_NAMES:
        result = await execute_parliament_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)
    else:
        result = await execute_worker_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)

    # Extract sources from the raw structured response BEFORE summarisation compresses it.
    if source_accumulator is not None:
        _extract_sources_from_tool(name, args, result, source_accumulator)

    # For search_case_law: inject a Phase 2 nudge to call get_case_law_text for
    # the most relevant results, or a stop note on zero results.
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
                url_lines = "\n".join(
                    f'  - url: "{r["url"]}"  ({r.get("title", "")} {r.get("ncn", "")})'
                    for r in raw_data.get("results", [])[:3]
                    if r.get("url")
                )
                case_law_note = (
                    f"\n\n[MANDATORY NEXT STEP — DO NOT synthesise yet. "
                    f"Call get_case_law_text for the 1–3 most relevant cases below to retrieve the full judgment text "
                    f"before composing your answer. Pass the exact url field:\n{url_lines}]"
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

    # For search_legislation: capture legislation_ids from the raw response before
    # any summarisation strips them, so we can inject a Phase 2 instruction into
    # the final result the model actually sees.
    phase2_note = ""
    if name == "search_legislation":
        try:
            raw_data = json.loads(result)
            id_pairs = extract_legislation_ids_from_search(raw_data)
            if timing_collector:
                timing_collector.record_legislation_ids_seen(lid for lid, _ in id_pairs)
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

        _chars_in = len(result)
        result = await summarise_for_query(
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

        # Enforce the size cap here, BEFORE the phase nudges are appended, so a
        # summary that still exceeds the threshold is trimmed without losing the
        # nudges (the chat loop's own truncation would chop them off the tail).
        threshold = get_summarise_threshold()
        if len(result) > threshold:
            logger.warning(
                f"[Worker] Summarised result from '{name}' still exceeds threshold "
                f"({len(result)} -> {threshold} chars)"
            )
            if timing_collector:
                timing_collector.record_truncation()
            result = (
                result[:threshold]
                + "\n\n[Content truncated — summary exceeded context limit]"
            )

        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {
                "type": "tool_end",
                "tool": "Extracting the relevant sections from a large document",
                "id": summarise_id,
                "result": result,
            })

    # Append phase nudges after summarisation so they are not discarded
    # by the summariser and remain visible in the message the model receives.
    result += phase2_note
    result += hansard_phase2_note
    result += sp_phase2_note
    result += sp_committee_phase2_note
    result += case_law_note

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "id": activity_id, "result": "Done"})

    return result
