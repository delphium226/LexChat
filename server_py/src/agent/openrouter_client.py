import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Callable, Optional

import httpx

from ..config import (
    MANAGER_SYSTEM_PROMPT,
    OPENROUTER_MODEL_LIST,
    WORKER_SYSTEM_PROMPT,
    settings,
)
from .learning import format_learning_context, get_relevant_examples
from .tools import MANAGER_TOOLS, WORKER_TOOLS, execute_worker_tool

logger = logging.getLogger("agent")


def _get_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.openrouter_api_key:
        headers["Authorization"] = f"Bearer {settings.openrouter_api_key}"
    return headers


def _get_base_url() -> str:
    return settings.openrouter_base_url.rstrip("/")


def _convert_tools_to_openai(tools: list) -> list:
    """Convert Ollama-style tool schemas to OpenAI tool format (they are identical)."""
    return tools


def _convert_messages_to_openai(messages: list) -> list:
    """Convert Ollama-style messages to OpenAI format.

    Key difference: Ollama tool results use {"role":"tool","content":"...","name":"func"}
    OpenAI tool results use {"role":"tool","content":"...","tool_call_id":"call_xxx"}

    We carry tool_call_ids in messages that have them already; for legacy messages
    without tool_call_id we fall back to a placeholder so the API still accepts them.
    """
    converted = []
    for msg in messages:
        if msg.get("role") == "tool":
            converted.append({
                "role": "tool",
                "content": msg.get("content", ""),
                "tool_call_id": msg.get("tool_call_id", "call_unknown"),
            })
        elif msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Keep tool_calls in OpenAI format; strip Ollama-only fields
            converted.append({
                "role": "assistant",
                "content": msg.get("content") or None,
                "tool_calls": msg["tool_calls"],
            })
        else:
            converted.append({k: v for k, v in msg.items() if k not in ("stats",)})
    return converted


# -----------------------------------------------------------------------
# Generic Chat Loop (ReAct pattern — OpenAI/OpenRouter format)
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
    """Core ReAct loop using OpenRouter's OpenAI-compatible streaming API."""
    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError("Aborted")

    openai_messages = _convert_messages_to_openai(messages)
    openai_tools = _convert_tools_to_openai(tools)

    payload = {
        "model": model,
        "messages": openai_messages,
        "stream": True,
        "temperature": settings.ollama_temperature,
    }
    if openai_tools:
        payload["tools"] = openai_tools
        payload["tool_choice"] = "auto"

    total_chars = sum(len(str(m.get("content", "") or "")) for m in messages)
    logger.info(
        f"[OpenRouter] Sending request (model={model}, tools={len(tools)}, "
        f"msgs={len(messages)}, ~{total_chars} chars)..."
    )

    full_content = ""
    # tool_calls_map: index -> {"id", "type", "function": {"name", "arguments"}}
    tool_calls_map: dict[int, dict] = {}
    usage_stats: dict = {}

    t_send = time.perf_counter()
    first_content_time: Optional[float] = None

    try:
        async with httpx.AsyncClient(timeout=None, verify=False) as client:
            async with client.stream(
                "POST",
                f"{_get_base_url()}/chat/completions",
                json=payload,
                headers=_get_headers(),
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if cancel_event and cancel_event.is_set():
                        raise asyncio.CancelledError("Aborted")

                    if not line.startswith("data: "):
                        continue

                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break

                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    # Capture usage if present (OpenRouter sends it in the last chunk)
                    if data.get("usage"):
                        usage_stats = data["usage"]

                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    # Accumulate content tokens
                    content = delta.get("content") or ""
                    if content:
                        if first_content_time is None:
                            first_content_time = time.perf_counter()
                        full_content += content
                        if on_chunk:
                            await _call_chunk(on_chunk, {"type": "token", "content": content})

                    # Accumulate tool call deltas
                    for tc_delta in delta.get("tool_calls", []):
                        idx = tc_delta.get("index", 0)
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {
                                "id": tc_delta.get("id", ""),
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_calls_map[idx]
                        if tc_delta.get("id"):
                            entry["id"] = tc_delta["id"]
                        func = tc_delta.get("function", {})
                        if func.get("name"):
                            entry["function"]["name"] += func["name"]
                        if func.get("arguments"):
                            entry["function"]["arguments"] += func["arguments"]

    except httpx.ConnectError:
        raise ConnectionError(
            "OpenRouter is not reachable. "
            "Check your internet connection and OPENROUTER_API_KEY."
        )
    except httpx.HTTPStatusError as e:
        try:
            await e.response.aread()
            body = e.response.text[:500]
        except Exception:
            body = "(body unreadable)"
        logger.error(f"[OpenRouter] HTTP {e.response.status_code}: {body}")
        raise

    # Record timing
    if timing_collector:
        t_done = time.perf_counter()
        ttft_ms = ((first_content_time or t_done) - t_send) * 1000
        total_stream_ms = (t_done - t_send) * 1000
        timing_collector.record_llm_call(ttft_ms, total_stream_ms)

    # Convert accumulated tool calls to a list in index order
    tool_calls = [tool_calls_map[i] for i in sorted(tool_calls_map.keys())]

    # Build assistant message (OpenAI format, carried forward)
    assistant_message: dict = {"role": "assistant", "content": full_content}
    if usage_stats:
        # Map to Ollama-compatible stats field so the UI context bar still works
        assistant_message["stats"] = {
            "prompt_eval_count": usage_stats.get("prompt_tokens", 0),
            "eval_count": usage_stats.get("completion_tokens", 0),
        }
    if tool_calls:
        assistant_message["tool_calls"] = tool_calls

    # If tool calls — execute and recurse
    if tool_calls:
        logger.info(f"[OpenRouter] Tool calls: {len(tool_calls)}")

        if emit_tool_details and on_chunk:
            await _call_chunk(on_chunk, {"type": "tool_call", "tool_calls": tool_calls})

        next_messages = [*messages, assistant_message]

        MAX_TOOL_RESULT_CHARS = 40_000

        async def _run_tool(tc):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError("Aborted")
            func_name = tc["function"]["name"]
            # OpenAI format: arguments is a JSON string
            raw_args = tc["function"]["arguments"]
            try:
                func_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                func_args = {}
            result = await tool_executor(func_name, func_args)
            if len(result) > MAX_TOOL_RESULT_CHARS:
                logger.warning(
                    f"[OpenRouter] Tool result from '{func_name}' truncated "
                    f"({len(result)} -> {MAX_TOOL_RESULT_CHARS} chars)"
                )
                result = (
                    result[:MAX_TOOL_RESULT_CHARS]
                    + "\n\n[Content truncated — result exceeded context limit]"
                )
            return tc["id"], func_name, result

        tool_results = await asyncio.gather(*[_run_tool(tc) for tc in tool_calls])

        for (call_id, func_name, tool_result) in tool_results:
            if emit_tool_details and on_chunk:
                await _call_chunk(on_chunk, {
                    "type": "tool_result",
                    "tool": func_name,
                    "result": tool_result,
                })
            next_messages.append({
                "role": "tool",
                "content": tool_result,
                "tool_call_id": call_id,
                "name": func_name,
            })

        return await chat_loop(
            next_messages, model, cancel_event, num_ctx,
            tools, tool_executor, on_chunk,
            emit_tool_details=emit_tool_details,
            timing_collector=timing_collector,
        )

    return assistant_message


# -----------------------------------------------------------------------
# Legislation summarisation helper
# -----------------------------------------------------------------------

_SUMMARISE_THRESHOLD_CHARS = 8_000
_SUMMARISE_CHUNK_CHARS = 150_000
_SUMMARISE_CHUNK_FALLBACK_CHARS = 5_000
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


async def _summarise_chunk(text: str, query: str, model: str, timing_collector=None) -> Optional[str]:
    """Summarise a single chunk via OpenRouter. Returns None on any error."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _summarise_prompt(text, query)}],
        "stream": False,
        "temperature": 0,
    }

    try:
        async with _get_summarise_semaphore():
            async with httpx.AsyncClient(timeout=600.0, verify=False) as client:
                t_send = time.perf_counter()
                resp = await client.post(
                    f"{_get_base_url()}/chat/completions",
                    json=payload,
                    headers=_get_headers(),
                )
                elapsed_ms = (time.perf_counter() - t_send) * 1000
                resp.raise_for_status()
                content = (
                    resp.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
                if timing_collector:
                    timing_collector.record_llm_call(elapsed_ms, elapsed_ms)
                return content if content else None
    except Exception as e:
        logger.warning(f"[OpenRouter Summarise] Chunk failed ({type(e).__name__}: {e!r})")
        return None


async def _summarise_for_query(
    text: str,
    query: str,
    model: str,
    on_progress: Optional[Callable] = None,
    timing_collector=None,
    doc_name: str = "document",
) -> str:
    if len(text) <= _SUMMARISE_CHUNK_CHARS:
        result = await _summarise_chunk(text, query, model, timing_collector=timing_collector)
        if result is None:
            return text
        return result

    chunks = [
        text[i: i + _SUMMARISE_CHUNK_CHARS]
        for i in range(0, len(text), _SUMMARISE_CHUNK_CHARS)
    ]
    n = len(chunks)

    partial_summaries: list[str] = []
    for i, chunk in enumerate(chunks):
        if on_progress:
            await on_progress(f"Searching through large document ({doc_name}) - part {i + 1} of {n}")
        summary = await _summarise_chunk(chunk, query, model, timing_collector=timing_collector)
        if summary is None:
            summary = chunk[:_SUMMARISE_CHUNK_FALLBACK_CHARS]
        partial_summaries.append(summary)

    combined = "\n\n---\n\n".join(partial_summaries)

    if len(combined) > _SUMMARISE_CHUNK_CHARS:
        if on_progress:
            await on_progress("Consolidating extracted sections")
        final = await _summarise_chunk(combined, query, model, timing_collector=timing_collector)
        if final is None:
            return combined
        return final

    return combined


# -----------------------------------------------------------------------
# Worker Agent
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
    logger.info(f"[OpenRouter Worker] Starting research on: {query}")

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
            logger.info(f"[OpenRouter Worker] Result from '{name}' is {len(result)} chars — summarising")

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
                await _call_chunk(parent_on_chunk, {"type": "tool_start", "tool": "Extracting the relevant sections from a large document"})

            async def _emit_progress(msg: str) -> None:
                if parent_on_chunk:
                    await _call_chunk(parent_on_chunk, {"type": "tool_start", "tool": msg})

            result = await _summarise_for_query(result, query, model, on_progress=_emit_progress, timing_collector=timing_collector, doc_name=doc_name)
            if parent_on_chunk:
                await _call_chunk(parent_on_chunk, {"type": "tool_end", "tool": "Extracting the relevant sections from a large document", "result": "Done"})

        if parent_on_chunk:
            await _call_chunk(parent_on_chunk, {"type": "tool_end", "tool": f"Worker: {name}", "result": "Done"})
        return result

    return await chat_loop(
        messages, model, cancel_event, num_ctx,
        WORKER_TOOLS, worker_tool_executor, None,
        emit_tool_details=emit_tool_details,
        timing_collector=timing_collector,
    )


# -----------------------------------------------------------------------
# Manager Agent
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
    system_content = MANAGER_SYSTEM_PROMPT

    if db_session:
        try:
            last_msg = messages[-1] if messages else None
            if last_msg and last_msg.get("role") == "user":
                learning_data = await get_relevant_examples(
                    last_msg["content"], db_session, timing_collector=timing_collector
                )
                context_injection = format_learning_context(learning_data)
                if context_injection:
                    logger.info("[OpenRouter Learning] Injecting feedback context.")
                    system_content += f"\n\n{context_injection}"
        except Exception as e:
            logger.error(f"[OpenRouter Learning] Failed to inject context: {e}")

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
    return [
        {"name": m["name"], "context_length": m["contextLengthKB"] * 1024, "provider": "openrouter"}
        for m in OPENROUTER_MODEL_LIST
    ]


# -----------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------

async def _call_chunk(on_chunk: Callable, data: dict):
    result = on_chunk(data)
    if asyncio.iscoroutine(result):
        await result
