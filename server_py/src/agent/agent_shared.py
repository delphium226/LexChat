"""
Shared worker-tool execution logic used by both ollama_client and openrouter_client.

Both provider clients run an identical pipeline when processing Worker tool results:
execute the tool, optionally summarise large results, append a Phase 2 nudge for
search_legislation calls.  This module owns that logic once so future changes only
need to happen here.
"""
import json
import logging
from typing import Callable, Optional

from .summarisation import call_chunk, summarise_for_query
from .tools import execute_worker_tool, extract_legislation_ids_from_search

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
                "kind": "Statute",
                "title": item.get("title") or lid,
                "url": item.get("url") or "",
                "meta": item.get("status") or "",
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
                "cite": ncn or case.get("title") or "",
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
    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}"})

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

        if parent_on_chunk:
            await call_chunk(parent_on_chunk, {
                "type": "tool_start",
                "tool": "Extracting the relevant sections from a large document",
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
                "result": "Done",
            })

    # Append Phase 2 instruction after summarisation so it is not discarded
    # by the summariser and is visible in the message the model receives.
    result += phase2_note
    result += case_law_note

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "result": "Done"})

    return result
