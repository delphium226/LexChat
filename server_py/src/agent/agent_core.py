"""Provider-agnostic agent core: Worker and Manager orchestration.

Both provider clients (ollama_client, openrouter_client) previously carried
byte-identical copies of run_worker_agent and process_user_request. The logic
lives here once, parameterised by the provider's chat_loop and summarise-chunk
functions (the only genuinely provider-specific parts — wire format, streaming
parse, and per-provider options).
"""

import asyncio
import logging
import uuid
from typing import Callable, Optional

from ..prompts import get_manager_system_prompt, get_worker_system_prompt
from .agent_shared import run_worker_tool
from .federation_client import (
    build_peer_descriptions,
    consult_peer,
    load_peer_registry,
)
from .learning import format_learning_context, get_relevant_examples
from .summarisation import call_chunk
from .tools import get_manager_tools, get_worker_tools

logger = logging.getLogger("agent")


def _get_cfg() -> dict:
    """Return the current request's provider config (set by provider_factory)."""
    from .provider_factory import get_request_provider_config
    return get_request_provider_config()


# -----------------------------------------------------------------------
# Worker Agent (Legal Research Specialist)
# -----------------------------------------------------------------------

async def run_worker_agent(
    chat_loop_fn: Callable,
    summarise_chunk_fn: Callable,
    query: str,
    model: str,
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    parent_on_chunk: Optional[Callable] = None,
    emit_tool_details: bool = False,
    timing_collector=None,
) -> dict:
    """Run the Worker agent with a fresh context for legal research."""
    logger.info(f"[Worker] Starting research on: {query}")

    cfg = _get_cfg()
    research_mode = cfg.get("_research_mode", "legislation_only")
    summarise_model = cfg.get("summarisation_model") or model

    messages = [
        {"role": "system", "content": get_worker_system_prompt(research_mode, cfg)},
        {"role": "user", "content": query},
    ]

    worker_tools = get_worker_tools(research_mode)
    source_accumulator: list = []
    # Limit parliamentary searches so the model proceeds to Phase 2 instead of looping.
    # Budget covers search_hansard, search_scottish_parliament, and search_scottish_committee_transcripts.
    search_budget = {"remaining": 3} if research_mode == "parliamentary_records" else None

    async def worker_tool_executor(name: str, args: dict) -> str:
        return await run_worker_tool(
            name, args, query, summarise_chunk_fn, summarise_model,
            parent_on_chunk=parent_on_chunk,
            timing_collector=timing_collector,
            source_accumulator=source_accumulator,
            search_budget=search_budget,
        )

    result = await chat_loop_fn(
        messages, model, cancel_event, num_ctx,
        worker_tools, worker_tool_executor, None,  # on_chunk=None for worker to avoid mixing tokens
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )

    if source_accumulator:
        result["sources"] = [
            {**{k: v for k, v in src.items() if not k.startswith("_")}, "n": i + 1}
            for i, src in enumerate(source_accumulator)
        ]

    return result


# -----------------------------------------------------------------------
# Manager Agent (Main Chat Interface)
# -----------------------------------------------------------------------

async def process_user_request(
    chat_loop_fn: Callable,
    run_worker_agent_fn: Callable,
    messages: list,
    model: str,
    on_chunk: Optional[Callable],
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    db_session=None,
    emit_tool_details: bool = False,
    timing_collector=None,
    depth: int = 0,
) -> dict:
    """Main entry point: Manager agent with learning injection."""
    _cfg = _get_cfg()
    research_mode = _cfg.get("_research_mode", "legislation_only")
    system_content = get_manager_system_prompt(research_mode, _cfg)

    doc_context = _cfg.get("_doc_context", "")
    if doc_context:
        system_content += f"\n\n{doc_context}"

    matter_context = _cfg.get("_matter_context", "")
    if matter_context:
        system_content += f"\n\n{matter_context}"

    # Learning mechanism injection
    if db_session:
        try:
            last_msg = messages[-1] if messages else None
            if last_msg and last_msg.get("role") == "user":
                learning_data = await get_relevant_examples(
                    last_msg["content"], db_session, timing_collector=timing_collector
                )
                context_injection = format_learning_context(learning_data)
                if context_injection:
                    logger.info("[Learning] Injecting feedback context into System Prompt.")
                    system_content += f"\n\n{context_injection}"
        except Exception as e:
            logger.error(f"[Learning] Failed to inject context: {e}")

    system_message = {"role": "system", "content": system_content}

    final_messages = list(messages)
    if final_messages and final_messages[0].get("role") == "system":
        final_messages[0] = system_message
    else:
        final_messages = [system_message, *final_messages]

    # Load peer registry and build dynamic tool list
    peers = []
    if db_session:
        try:
            peers = await load_peer_registry(db_session)
        except Exception as e:
            logger.warning(f"[Federation] Could not load peer registry: {e}")
    peer_descriptions = build_peer_descriptions(peers)
    manager_tools = get_manager_tools(peer_descriptions)

    accumulated_sources: list = []

    async def manager_tool_executor(name: str, args: dict) -> str:
        if name == "delegate_research":
            research_id = uuid.uuid4().hex[:8]
            if on_chunk:
                await call_chunk(on_chunk, {"type": "tool_start", "tool": "Research Agent", "id": research_id})

            result = await run_worker_agent_fn(
                args["query"], model, cancel_event, num_ctx, on_chunk,
                emit_tool_details=emit_tool_details,
                timing_collector=timing_collector,
            )

            if on_chunk:
                await call_chunk(on_chunk, {"type": "tool_end", "tool": "Research Agent", "id": research_id, "result": "Research Complete"})

            accumulated_sources.extend(result.get("sources", []))
            return f"[Research Agent Result]\n{result['content']}"

        if name == "consult_peer":
            peer_id = args.get("peer_id", "")
            question = args.get("question", "")
            peer = next((p for p in peers if p.peer_id == peer_id), None)
            if not peer:
                return f"Error: Unknown peer '{peer_id}'"
            try:
                consult_id = uuid.uuid4().hex[:8]
                if on_chunk:
                    await call_chunk(on_chunk, {"type": "tool_start", "tool": f"Peer: {peer.name}", "id": consult_id})
                answer = await consult_peer(peer, question, depth=depth + 1)
                if on_chunk:
                    await call_chunk(on_chunk, {"type": "tool_end", "tool": f"Peer: {peer.name}", "id": consult_id, "result": "Peer consult complete"})
                return f"[Peer Bot: {peer.name}]\n{answer}"
            except Exception as e:
                return f"Error consulting peer '{peer_id}': {e}"

        return f"Error: Unknown manager tool {name}"

    final = await chat_loop_fn(
        final_messages, model, cancel_event, num_ctx,
        manager_tools, manager_tool_executor, on_chunk,
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )

    if accumulated_sources:
        final["sources"] = [
            {**{k: v for k, v in s.items() if k != "n"}, "n": i + 1}
            for i, s in enumerate(accumulated_sources)
        ]

    return final
