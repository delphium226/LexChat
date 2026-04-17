import asyncio
import json
import logging
from typing import Callable, Optional

from ..config import DEEP_RESEARCH_SYSTEM_PROMPT
from .provider_factory import (
    call_chunk,
    get_active_chat_loop,
    get_active_summarise_for_query,
)
from .summarisation import SUMMARISE_THRESHOLD_CHARS
from .tools import WORKER_TOOLS, execute_worker_tool
from .web_search import search_web

logger = logging.getLogger("agent")

# Deep research tools = worker tools + web search
DEEP_RESEARCH_TOOLS = [
    *WORKER_TOOLS,
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the public web for information. "
                "Use this for broad context, news, or general knowledge "
                "not in the legal database."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


async def _execute_deep_research_tool(name: str, args: dict) -> str:
    """Execute a deep research tool (worker tools + web search)."""
    if name == "search_web":
        return await search_web(args["query"])
    return await execute_worker_tool(name, args)


async def chat_with_deep_research(
    messages: list,
    model: str,
    on_status_update: Callable,
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    timing_collector=None,
) -> dict:
    """Deep Research entry point.

    Uses worker tools + web search with an iterative research system prompt.
    Large tool results are summarised via the active provider before being
    fed back to the model (same pipeline as the Worker agent).
    """
    logger.info("[Deep Research] Starting session...")

    system_message = {"role": "system", "content": DEEP_RESEARCH_SYSTEM_PROMPT}

    final_messages = list(messages)
    if final_messages and final_messages[0].get("role") == "system":
        final_messages[0] = system_message
    else:
        final_messages = [system_message, *final_messages]

    # Extract the user's query for summarisation focus
    user_query = next(
        (m["content"] for m in reversed(final_messages) if m.get("role") == "user"),
        "",
    )

    async def deep_research_tool_executor(name: str, args: dict) -> str:
        await call_chunk(on_status_update, {
            "type": "tool_start",
            "tool": f"Deep Research: {name}",
        })

        result = await _execute_deep_research_tool(name, args)

        # Summarise large results — same threshold/pipeline as the Worker agent
        if len(result) > SUMMARISE_THRESHOLD_CHARS:
            logger.info(
                f"[Deep Research] Result from '{name}' is {len(result)} chars — summarising"
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

            await call_chunk(on_status_update, {
                "type": "tool_start",
                "tool": "Extracting the relevant sections from a large document",
            })

            async def _emit_progress(msg: str) -> None:
                await call_chunk(on_status_update, {"type": "tool_start", "tool": msg})

            summarise_for_query = get_active_summarise_for_query()
            result = await summarise_for_query(
                result,
                user_query,
                model,
                on_progress=_emit_progress,
                timing_collector=timing_collector,
                doc_name=doc_name,
            )
            logger.info(f"[Deep Research] Summarised to {len(result)} chars")

            await call_chunk(on_status_update, {
                "type": "tool_end",
                "tool": "Extracting the relevant sections from a large document",
                "result": "Done",
            })

        await call_chunk(on_status_update, {
            "type": "tool_end",
            "tool": f"Deep Research: {name}",
            "result": "Done",
        })

        return result

    chat_loop = get_active_chat_loop()
    return await chat_loop(
        final_messages, model, cancel_event, num_ctx,
        DEEP_RESEARCH_TOOLS, deep_research_tool_executor, on_status_update,
        timing_collector=timing_collector,
    )
