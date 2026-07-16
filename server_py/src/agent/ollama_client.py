import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Callable, Optional

import httpx

from ..config import MODEL_LIST, settings
from . import agent_core
from .summarisation import call_chunk, summarise_prompt

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

    if timing_collector:
        timing_collector.record_react_turn(_turn)

    if _turn >= max_turns:
        logger.warning(f"[ChatLoop] Max turns ({max_turns}) reached — halting tool calls")
        if timing_collector:
            timing_collector.record_max_turns_halt()
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

    # No overall timeout (a long research answer can legitimately stream for
    # minutes) but a per-read timeout so a provider that hangs mid-stream — no
    # bytes for 180s — raises ReadTimeout instead of holding the request forever.
    stream_timeout = httpx.Timeout(None, connect=30.0, read=180.0)
    try:
        async with httpx.AsyncClient(timeout=stream_timeout, verify=False) as client:
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

        # Last-resort safety net: results above the summarisation threshold are
        # summarised (and capped) by run_worker_tool before reaching here.  The
        # +4K headroom leaves room for the phase nudges appended after
        # summarisation so they are never truncated off the tail.
        from .provider_factory import get_summarise_threshold
        MAX_TOOL_RESULT_CHARS = get_summarise_threshold() + 4_000

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
                if timing_collector:
                    timing_collector.record_truncation()
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
# Worker + Manager agents (shared logic in agent_core, bound to this
# provider's chat_loop and _summarise_chunk)
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
    return await agent_core.run_worker_agent(
        chat_loop, _summarise_chunk,
        query, model, cancel_event, num_ctx,
        parent_on_chunk=parent_on_chunk,
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )


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
    return await agent_core.process_user_request(
        chat_loop, run_worker_agent,
        messages, model, on_chunk, cancel_event, num_ctx,
        db_session=db_session,
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
        depth=depth,
    )


async def draft_research_plan(
    messages: list,
    model: str,
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    timing_collector=None,
) -> dict:
    return await agent_core.draft_research_plan(
        chat_loop,
        messages, model, cancel_event, num_ctx,
        timing_collector=timing_collector,
    )


async def run_deep_research(
    approved_plan: dict,
    messages: list,
    model: str,
    on_chunk: Optional[Callable],
    cancel_event: Optional[asyncio.Event],
    num_ctx: int,
    db_session=None,
    emit_tool_details: bool = False,
    timing_collector=None,
) -> dict:
    return await agent_core.run_deep_research(
        chat_loop, run_worker_agent,
        approved_plan, messages, model, on_chunk, cancel_event, num_ctx,
        db_session=db_session,
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )


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


