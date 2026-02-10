import asyncio
import logging
from typing import Callable, Optional

from ..config import DEEP_RESEARCH_SYSTEM_PROMPT
from .ollama_client import _call_chunk, chat_loop
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
) -> dict:
    """Deep Research entry point.

    Uses worker tools + web search with an iterative research system prompt.
    """
    logger.info("[Deep Research] Starting session...")

    system_message = {"role": "system", "content": DEEP_RESEARCH_SYSTEM_PROMPT}

    final_messages = list(messages)
    if final_messages and final_messages[0].get("role") == "system":
        final_messages[0] = system_message
    else:
        final_messages = [system_message, *final_messages]

    async def deep_research_tool_executor(name: str, args: dict) -> str:
        await _call_chunk(on_status_update, {
            "type": "tool_start",
            "tool": f"Deep Research: {name}",
        })

        result = await _execute_deep_research_tool(name, args)

        await _call_chunk(on_status_update, {
            "type": "tool_end",
            "tool": f"Deep Research: {name}",
            "result": "Done",
        })

        return result

    return await chat_loop(
        final_messages, model, cancel_event, num_ctx,
        DEEP_RESEARCH_TOOLS, deep_research_tool_executor, on_status_update,
    )
