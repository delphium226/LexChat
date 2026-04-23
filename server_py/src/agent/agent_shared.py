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


async def run_worker_tool(
    name: str,
    args: dict,
    query: str,
    chunk_fn: Callable,
    summarise_model: str,
    parent_on_chunk: Optional[Callable] = None,
    timing_collector=None,
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
    """
    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}"})

    result = await execute_worker_tool(name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector)

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

    if parent_on_chunk:
        await call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "result": "Done"})

    return result
