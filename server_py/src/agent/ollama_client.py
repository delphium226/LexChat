import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Callable, Optional

import httpx

from ..config import (
    MODEL_LIST,
    WORKER_SYSTEM_PROMPT,
    get_manager_system_prompt,
    get_worker_system_prompt,
    settings,
)
from .learning import format_learning_context, get_relevant_examples
from .summarisation import (
    call_chunk,
    summarise_prompt,
)
from .tools import get_manager_tools, get_worker_tools
from .agent_shared import run_worker_tool
from .federation_client import (
    build_peer_descriptions,
    consult_peer,
    load_peer_registry,
)

logger = logging.getLogger("agent")


def _get_cfg() -> dict:
    """Return the current request's provider config (set by provider_factory)."""
    from .provider_factory import get_request_provider_config
    return get_request_provider_config()


def _base_url() -> str:
    return _get_cfg().get("base_url", settings.ollama_base_url).rstrip("/")


def _get_headers() -> dict:
    api_key = _get_cfg().get("api_key") or settings.ollama_api_key
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


# -----------------------------------------------------------------------
# Generic Chat Loop (ReAct pattern — used by Manager and Worker)
# -----------------------------------------------------------------------

async def chat_loop(
    messages: list,
    model: str,
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    tools: list,
    tool_executor: Callable,
    on_chunk: Optional[Callable] = None,
    emit_tool_details: bool = False,
    timing_collector=None,
    _turn: int = 0,
    max_turns: int = 20,
) -> dict:
    """Core ReAct loop: stream from Ollama, handle tool calls, recurse.

    Args:
        messages: Conversation history.
        model: Ollama model name.
        cancel_event: If set, abort processing.
        num_ctx: Context window size.
        tools: Tool schemas for Ollama.
        tool_executor: async (name, args) -> str.
        on_chunk: Optional callback for SSE events.
        emit_tool_details: Whether to emit detailed tool call/result events.

    Returns:
        Final assistant message dict {role, content}.
    """
    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError("Aborted")

    if _turn >= max_turns:
        logger.warning(f"[ChatLoop] Max turns ({max_turns}) reached — halting tool calls")
        return {"role": "assistant", "content": f"[Research halted: exceeded {max_turns} tool-call steps]"}

    # Determine context size from model config
    configured = next((m for m in MODEL_LIST if m["name"] == model), None)
    default_ctx = (
        configured["contextLengthKB"] * 1024
        if configured
        else settings.ollama_default_context
    )

    temperature = _get_cfg().get("temperature", settings.ollama_temperature)

    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": True,
        "options": {
            "num_ctx": num_ctx or default_ctx,
            "temperature": temperature,
        },
    }

    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    logger.info(
        f"[ChatLoop] Sending request to Ollama (Tools: {len(tools)}, "
        f"msgs: {len(messages)}, ~{total_chars} chars, num_ctx: {num_ctx or default_ctx})..."
    )

    full_content = ""
    tool_calls = []
    final_stats = {}

    t_send = time.perf_counter()
    first_content_time: Optional[float] = None

    try:
        async with httpx.AsyncClient(timeout=None, verify=False) as client:
            async with client.stream(
                "POST",
                f"{_base_url()}/api/chat",
                json=payload,
                headers=_get_headers(),
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if cancel_event and cancel_event.is_set():
                        raise asyncio.CancelledError("Aborted")

                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = data.get("message", {})
                    content = msg.get("content", "")

                    if content:
                        if first_content_time is None:
                            first_content_time = time.perf_counter()
                        full_content += content
                        if on_chunk:
                            await call_chunk(on_chunk, {"type": "token", "content": content})

                    if msg.get("tool_calls"):
                        tool_calls.extend(msg["tool_calls"])

                    if data.get("done"):
                        final_stats = {
                            "prompt_eval_count": data.get("prompt_eval_count", 0),
                            "eval_count": data.get("eval_count", 0),
                            "total_duration": data.get("total_duration", 0),
                            "load_duration": data.get("load_duration", 0),
                        }

    except httpx.ConnectError:
        raise ConnectionError(
            "Agent Service (Ollama) is not reachable. "
            "Please ensure it is running on your machine."
        )
    except httpx.HTTPStatusError as e:
        try:
            await e.response.aread()
            body = e.response.text[:500]
        except Exception:
            body = "(body unreadable)"
        logger.error(f"[ChatLoop] Ollama HTTP {e.response.status_code}: {body}")
        raise

    # Record LLM call timing (ttft = time to first content token)
    if timing_collector:
        t_done = time.perf_counter()
        ttft_ms = ((first_content_time or t_done) - t_send) * 1000
        total_stream_ms = (t_done - t_send) * 1000
        timing_collector.record_llm_call(ttft_ms, total_stream_ms)

    # Build assistant message
    message = {"role": "assistant", "content": full_content}
    if final_stats:
        message["stats"] = final_stats
    if tool_calls:
        message["tool_calls"] = tool_calls

    # If tool calls, execute and recurse
    if tool_calls:
        logger.info(f"[ChatLoop] Tool calls: {len(tool_calls)}")
        
        # Emit detailed tool call event if requested
        if emit_tool_details and on_chunk:
            await call_chunk(on_chunk, {
                "type": "tool_call", 
                "tool_calls": tool_calls
            })

        next_messages = [*messages, message]

        # Cap each tool result at the summarisation threshold — results above this
        # are summarised by run_worker_tool before reaching here, so truncation only
        # fires as a last-resort safety net (e.g. model not in config list).
        from .provider_factory import get_summarise_threshold
        MAX_TOOL_RESULT_CHARS = get_summarise_threshold()

        # Execute all tool calls concurrently — they are independent of each
        # other so there is no reason to serialise them.  Results are reordered
        # back to the original sequence before appending to the message history.
        async def _run_tool(tc):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError("Aborted")
            func_name = tc["function"]["name"]
            func_args = tc["function"]["arguments"]
            result = await tool_executor(func_name, func_args)
            if len(result) > MAX_TOOL_RESULT_CHARS:
                logger.warning(
                    f"[ChatLoop] Tool result from '{func_name}' truncated "
                    f"({len(result)} -> {MAX_TOOL_RESULT_CHARS} chars)"
                )
                result = (
                    result[:MAX_TOOL_RESULT_CHARS]
                    + "\n\n[Content truncated — result exceeded context limit]"
                )
            return func_name, result

        tool_tasks = [asyncio.create_task(_run_tool(tc)) for tc in tool_calls]
        try:
            tool_results = await asyncio.gather(*tool_tasks)
        except BaseException:
            for t in tool_tasks:
                if not t.done():
                    t.cancel()
            raise
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Aborted")

        for (func_name, tool_result) in tool_results:
            # Emit detailed tool result event if requested
            if emit_tool_details and on_chunk:
                await call_chunk(on_chunk, {
                    "type": "tool_result",
                    "tool": func_name,
                    "result": tool_result
                })

            next_messages.append({
                "role": "tool",
                "content": tool_result,
                "name": func_name,
            })

        # Recurse
        return await chat_loop(
            next_messages, model, cancel_event, num_ctx,
            tools, tool_executor, on_chunk,
            emit_tool_details=emit_tool_details,
            timing_collector=timing_collector,
            _turn=_turn + 1,
            max_turns=max_turns,
        )

    return message


# -----------------------------------------------------------------------
# Legislation summarisation helper
# -----------------------------------------------------------------------

# Serialise summarisation calls so concurrent requests don't overwhelm the
# cloud Ollama endpoint with multiple large-context inference jobs at once.
def _get_summarise_semaphore() -> asyncio.Semaphore:
    from .provider_factory import get_summarise_semaphore
    cfg = _get_cfg()
    provider = cfg.get("_provider", "ollama")
    concurrency = int(cfg.get("max_summarise_concurrency", 1))
    return get_summarise_semaphore(provider, concurrency)


async def _summarise_chunk(text: str, query: str, model: str, timing_collector=None) -> Optional[str]:
    """Summarise a single chunk via Ollama. Returns None on any error."""
    configured = next((m for m in MODEL_LIST if m["name"] == model), None)
    ctx = configured["contextLengthKB"] * 1024 if configured else 131072

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": summarise_prompt(text, query)}],
        "stream": False,
        "options": {
            "num_ctx": ctx,
            "temperature": 0,
        },
    }

    try:
        async with _get_summarise_semaphore():
            async with httpx.AsyncClient(timeout=600.0, verify=False) as client:
                t_send = time.perf_counter()
                resp = await client.post(
                    f"{_base_url()}/api/chat",
                    json=payload,
                    headers=_get_headers(),
                )
                elapsed_ms = (time.perf_counter() - t_send) * 1000
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content")
                if timing_collector:
                    timing_collector.record_llm_call(elapsed_ms, elapsed_ms)
                return content if content else None
    except Exception as e:
        logger.warning(f"[Summarise] Chunk failed ({type(e).__name__}: {e!r})")
        return None



# -----------------------------------------------------------------------
# Worker Agent (Legal Research Specialist)
# -----------------------------------------------------------------------

async def run_worker_agent(
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
    # Limit Hansard searches so the model proceeds to Phase 2 instead of looping.
    search_budget = {"remaining": 2} if research_mode == "parliamentary_records" else None

    async def worker_tool_executor(name: str, args: dict) -> str:
        return await run_worker_tool(
            name, args, query, _summarise_chunk, summarise_model,
            parent_on_chunk=parent_on_chunk,
            timing_collector=timing_collector,
            source_accumulator=source_accumulator,
            search_budget=search_budget,
        )

    result = await chat_loop(
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

            result = await run_worker_agent(
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

    final = await chat_loop(
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


# -----------------------------------------------------------------------
# Model Listing
# -----------------------------------------------------------------------

async def list_models() -> list:
    """Return the configured model list with context lengths."""
    return [
        {"name": m["name"], "context_length": m["contextLengthKB"] * 1024, "provider": "ollama"}
        for m in MODEL_LIST
    ]


# -----------------------------------------------------------------------
# Simple streaming (kept for basic fallback without agent loop)
# -----------------------------------------------------------------------

async def stream_chat(messages: list, model: str) -> AsyncGenerator[str, None]:
    """Basic streaming chat without tool calling (fallback)."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": settings.ollama_temperature},
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            async with client.stream(
                "POST",
                f"{_base_url()}/api/chat",
                json=payload,
                headers=_get_headers(),
            ) as response:
                response.raise_for_status()
                accumulated = ""

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            accumulated += content
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                    except json.JSONDecodeError:
                        continue

                yield f"data: {json.dumps({'type': 'result', 'message': accumulated})}\n\n"

    except httpx.ConnectError:
        yield f"data: {json.dumps({'type': 'error', 'error': 'Agent Service (Ollama) is not reachable.'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


