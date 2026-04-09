import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Callable, Optional

import httpx

from ..config import (
    MANAGER_SYSTEM_PROMPT,
    MODEL_LIST,
    WORKER_SYSTEM_PROMPT,
    settings,
)
from .learning import format_learning_context, get_relevant_examples
from .tools import MANAGER_TOOLS, WORKER_TOOLS, execute_worker_tool

logger = logging.getLogger("agent")

OLLAMA_BASE_URL = settings.ollama_base_url.rstrip("/")


def _get_headers() -> dict:
    headers = {}
    if settings.ollama_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
    return headers


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

    # Determine context size from model config
    configured = next((m for m in MODEL_LIST if m["name"] == model), None)
    default_ctx = (
        configured["contextLengthKB"] * 1024
        if configured
        else settings.ollama_default_context
    )

    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": True,
        "options": {
            "num_ctx": num_ctx or default_ctx,
            "temperature": settings.ollama_temperature,
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
                f"{OLLAMA_BASE_URL}/api/chat",
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
                            await _call_chunk(on_chunk, {"type": "token", "content": content})

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
        logger.info(f"Tool calls: {len(tool_calls)}")
        
        # Emit detailed tool call event if requested
        if emit_tool_details and on_chunk:
            await _call_chunk(on_chunk, {
                "type": "tool_call", 
                "tool_calls": tool_calls
            })

        next_messages = [*messages, message]

        # Cap each tool result to avoid blowing the context window.
        # Chunked summaries of large acts land at 15K-45K chars; 40 000 chars ≈ 10 000 tokens.
        MAX_TOOL_RESULT_CHARS = 40_000

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

        tool_results = await asyncio.gather(*[_run_tool(tc) for tc in tool_calls])

        for (func_name, tool_result) in tool_results:
            # Emit detailed tool result event if requested
            if emit_tool_details and on_chunk:
                await _call_chunk(on_chunk, {
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
        )

    return message


# -----------------------------------------------------------------------
# Legislation summarisation helper
# -----------------------------------------------------------------------

# Results larger than this are summarised before being fed back to the model.
# Below this threshold the raw text is used as-is.
_SUMMARISE_THRESHOLD_CHARS = 8_000

# Maximum chars sent to Ollama in a single summarisation call.
# At ~4 chars/token this is ~37K tokens — well within the 256K context and
# avoids ReadTimeout / HTTP 500 on the cloud-routed endpoint for large acts.
_SUMMARISE_CHUNK_CHARS = 150_000

# Fallback: if a chunk summarisation fails, include only this many chars of the
# raw chunk so the Worker still gets some content without blowing the context.
_SUMMARISE_CHUNK_FALLBACK_CHARS = 5_000

# Serialise summarisation calls so concurrent requests don't overwhelm the
# cloud Ollama endpoint with multiple large-context inference jobs at once.
_summarise_semaphore: Optional[asyncio.Semaphore] = None


def _get_summarise_semaphore() -> asyncio.Semaphore:
    global _summarise_semaphore
    if _summarise_semaphore is None:
        _summarise_semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
    return _summarise_semaphore


def _summarise_prompt(text: str, query: str) -> str:
    return (
        f"You are summarising a piece of UK legislation to assist with a legal research question.\n\n"
        f"Research question: {query}\n\n"
        f"Summarise the legislation text below. Retain only the sections, provisions, "
        f"definitions, and legal thresholds directly relevant to the research question. "
        f"Preserve exact section numbers, citations, and statutory references. "
        f"Discard preamble, unrelated schedules, and provisions that do not bear on the question.\n\n"
        f"Legislation text:\n{text}\n\nSummary:"
    )


async def _summarise_chunk(text: str, query: str, model: str) -> Optional[str]:
    """Summarise a single chunk via Ollama. Returns None on any error."""
    configured = next((m for m in MODEL_LIST if m["name"] == model), None)
    ctx = configured["contextLengthKB"] * 1024 if configured else 131072

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _summarise_prompt(text, query)}],
        "stream": False,
        "options": {
            "num_ctx": ctx,
            "temperature": 0,
        },
    }

    try:
        async with _get_summarise_semaphore():
            async with httpx.AsyncClient(timeout=600.0, verify=False) as client:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                    headers=_get_headers(),
                )
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content")
                return content if content else None
    except Exception as e:
        logger.warning(f"[Summarise] Chunk failed ({type(e).__name__}: {e!r})")
        return None


async def _summarise_for_query(
    text: str,
    query: str,
    model: str,
    on_progress: Optional[Callable] = None,
) -> str:
    """Produce a query-focused summary of a legislation text.

    Texts larger than _SUMMARISE_CHUNK_CHARS are split into chunks, each
    summarised independently, then the partial summaries are combined and
    optionally consolidated in a final pass.  Falls back gracefully when
    individual chunk calls fail.

    on_progress(msg) is called before each chunk so the UI can show progress.
    """
    if len(text) <= _SUMMARISE_CHUNK_CHARS:
        result = await _summarise_chunk(text, query, model)
        if result is None:
            logger.warning("[Summarise] Single-chunk summarisation failed, returning original text")
            return text
        return result

    # Split into chunks and summarise each.
    chunks = [
        text[i : i + _SUMMARISE_CHUNK_CHARS]
        for i in range(0, len(text), _SUMMARISE_CHUNK_CHARS)
    ]
    n = len(chunks)
    logger.info(
        f"[Summarise] {len(text)} chars exceeds chunk limit — splitting into {n} chunks"
    )

    partial_summaries: list[str] = []
    for i, chunk in enumerate(chunks):
        if on_progress:
            await on_progress(
                f"Extracting relevant sections from a large document (part {i + 1} of {n})"
            )
        logger.info(f"[Summarise] Chunk {i + 1}/{n} ({len(chunk)} chars)...")
        summary = await _summarise_chunk(chunk, query, model)
        if summary is None:
            logger.warning(
                f"[Summarise] Chunk {i + 1}/{n} failed — using first "
                f"{_SUMMARISE_CHUNK_FALLBACK_CHARS} chars of chunk"
            )
            summary = chunk[:_SUMMARISE_CHUNK_FALLBACK_CHARS]
        partial_summaries.append(summary)

    combined = "\n\n---\n\n".join(partial_summaries)
    logger.info(
        f"[Summarise] Combined {n} partial summaries into {len(combined)} chars"
    )

    # If the combined summaries are still large, do one final consolidation pass.
    if len(combined) > _SUMMARISE_CHUNK_CHARS:
        if on_progress:
            await on_progress("Consolidating extracted sections")
        logger.info("[Summarise] Running final consolidation pass")
        final = await _summarise_chunk(combined, query, model)
        if final is None:
            logger.warning("[Summarise] Final consolidation failed — returning combined partials")
            return combined
        logger.info(f"[Summarise] Consolidated to {len(final)} chars")
        return final

    return combined


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

    messages = [
        {"role": "system", "content": WORKER_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    async def worker_tool_executor(name: str, args: dict) -> str:
        if parent_on_chunk:
            await _call_chunk(parent_on_chunk, {"type": "tool_start", "tool": f"Worker: {name}"})

        result = await execute_worker_tool(
            name, args, on_chunk=parent_on_chunk, timing_collector=timing_collector
        )

        if len(result) > _SUMMARISE_THRESHOLD_CHARS:
            logger.info(
                f"[Worker] Result from '{name}' is {len(result)} chars — summarising for query focus"
            )
            if parent_on_chunk:
                await _call_chunk(parent_on_chunk, {"type": "tool_start", "tool": "Extracting the relevant sections from a large document"})

            async def _emit_progress(msg: str) -> None:
                if parent_on_chunk:
                    await _call_chunk(parent_on_chunk, {"type": "tool_start", "tool": msg})

            result = await _summarise_for_query(result, query, model, on_progress=_emit_progress)
            logger.info(f"[Worker] Summarised to {len(result)} chars")
            if parent_on_chunk:
                await _call_chunk(parent_on_chunk, {"type": "tool_end", "tool": "Extracting the relevant sections from a large document", "result": "Done"})

        if parent_on_chunk:
            await _call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "result": "Done"})
        return result

    return await chat_loop(
        messages, model, cancel_event, num_ctx,
        WORKER_TOOLS, worker_tool_executor, None,  # on_chunk=None for worker to avoid mixing tokens
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )


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
) -> dict:
    """Main entry point: Manager agent with learning injection.

    Args:
        messages: User conversation history.
        model: Model name.
        on_chunk: SSE streaming callback.
        cancel_event: Cancellation signal.
        num_ctx: Context window.
        db_session: Optional async DB session for learning retrieval.
        emit_tool_details: Whether to emit detailed tool events.
    """
    system_content = MANAGER_SYSTEM_PROMPT

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
    if not final_messages or final_messages[0].get("role") != "system":
        final_messages = [system_message, *final_messages]

    async def manager_tool_executor(name: str, args: dict) -> str:
        if name == "delegate_research":
            if on_chunk:
                await _call_chunk(on_chunk, {"type": "tool_start", "tool": "Research Agent"})

            result = await run_worker_agent(
                args["query"], model, cancel_event, num_ctx, on_chunk,
                emit_tool_details=emit_tool_details,
                timing_collector=timing_collector,
            )

            if on_chunk:
                await _call_chunk(on_chunk, {"type": "tool_end", "tool": "Research Agent", "result": "Research Complete"})

            return f"[Research Agent Result]\n{result['content']}"

        return f"Error: Unknown manager tool {name}"

    return await chat_loop(
        final_messages, model, cancel_event, num_ctx,
        MANAGER_TOOLS, manager_tool_executor, on_chunk,
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )


# -----------------------------------------------------------------------
# Model Listing
# -----------------------------------------------------------------------

async def list_models() -> list:
    """Return the configured model list with context lengths."""
    return [
        {"name": m["name"], "context_length": m["contextLengthKB"] * 1024}
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
                f"{OLLAMA_BASE_URL}/api/chat",
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


# -----------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------

async def _call_chunk(on_chunk: Callable, data: dict):
    """Call on_chunk callback, handling both sync and async callables."""
    result = on_chunk(data)
    if asyncio.iscoroutine(result):
        await result
