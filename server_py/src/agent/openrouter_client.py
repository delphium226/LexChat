import asyncio
import json
import logging
import os
import time
import uuid
from typing import AsyncGenerator, Callable, Optional

import httpx

from ..config import (
    MANAGER_SYSTEM_PROMPT,
    OPENROUTER_MODEL_LIST,
    WORKER_SYSTEM_PROMPT,
    settings,
)
from .learning import format_learning_context, get_relevant_examples
from .summarisation import (
    call_chunk,
    summarise_prompt,
)
from .tools import MANAGER_TOOLS, WORKER_TOOLS
from .agent_shared import run_worker_tool

logger = logging.getLogger("agent")


def _get_cfg() -> dict:
    from .provider_factory import get_request_provider_config
    return get_request_provider_config()


def _base_url() -> str:
    return _get_cfg().get("base_url", settings.openrouter_base_url).rstrip("/")


def _get_proxy() -> Optional[str]:
    return os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None


def _get_headers() -> dict:
    api_key = _get_cfg().get("api_key") or settings.openrouter_api_key
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


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
                "tool_call_id": msg.get("tool_call_id") or f"call_{uuid.uuid4().hex[:8]}",
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
    _turn: int = 0,
    max_turns: int = 20,
) -> dict:
    """Core ReAct loop using OpenRouter's OpenAI-compatible streaming API."""
    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError("Aborted")

    if _turn >= max_turns:
        logger.warning(f"[OpenRouter] Max turns ({max_turns}) reached — halting tool calls")
        return {"role": "assistant", "content": f"[Research halted: exceeded {max_turns} tool-call steps]"}

    openai_messages = _convert_messages_to_openai(messages)
    openai_tools = _convert_tools_to_openai(tools)

    payload = {
        "model": model,
        "messages": openai_messages,
        "stream": True,
        "temperature": _get_cfg().get("temperature", settings.ollama_temperature),
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
        async with httpx.AsyncClient(timeout=None, verify=False, proxy=_get_proxy()) as client:
            async with client.stream(
                "POST",
                f"{_base_url()}/chat/completions",
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
                            await call_chunk(on_chunk, {"type": "token", "content": content})

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
        cost = (usage_stats.get("cost") or 0) if usage_stats else 0
        if cost:
            timing_collector.record_cost(float(cost))

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
            await call_chunk(on_chunk, {"type": "tool_call", "tool_calls": tool_calls})

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

        for (call_id, func_name, tool_result) in tool_results:
            if emit_tool_details and on_chunk:
                await call_chunk(on_chunk, {
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
            _turn=_turn + 1,
            max_turns=max_turns,
        )

    return assistant_message


# -----------------------------------------------------------------------
# Legislation summarisation helper
# -----------------------------------------------------------------------

def _get_summarise_semaphore() -> asyncio.Semaphore:
    from .provider_factory import get_summarise_semaphore
    cfg = _get_cfg()
    provider = cfg.get("_provider", "openrouter")
    concurrency = int(cfg.get("max_summarise_concurrency", 5))
    return get_summarise_semaphore(provider, concurrency)


async def _summarise_chunk(text: str, query: str, model: str, timing_collector=None) -> Optional[str]:
    """Summarise a single chunk via OpenRouter. Returns None on any error."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": summarise_prompt(text, query)}],
        "stream": False,
        "temperature": 0,  # Always 0 for summarisation — deterministic output
    }

    try:
        async with _get_summarise_semaphore():
            async with httpx.AsyncClient(timeout=600.0, verify=False, proxy=_get_proxy()) as client:
                t_send = time.perf_counter()
                resp = await client.post(
                    f"{_base_url()}/chat/completions",
                    json=payload,
                    headers=_get_headers(),
                )
                elapsed_ms = (time.perf_counter() - t_send) * 1000
                resp.raise_for_status()
                resp_json = resp.json()
                content = (
                    resp_json
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
                if timing_collector:
                    timing_collector.record_llm_call(elapsed_ms, elapsed_ms)
                    cost = (resp_json.get("usage") or {}).get("cost") or 0
                    if cost:
                        timing_collector.record_cost(float(cost))
                return content if content else None
    except Exception as e:
        logger.warning(f"[OpenRouter Summarise] Chunk failed ({type(e).__name__}: {e!r})")
        return None



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

    summarise_model = _get_cfg().get("summarisation_model") or model

    messages = [
        {"role": "system", "content": WORKER_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    async def worker_tool_executor(name: str, args: dict) -> str:
        return await run_worker_tool(
            name, args, query, _summarise_chunk, summarise_model,
            parent_on_chunk=parent_on_chunk,
            timing_collector=timing_collector,
        )

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
    if final_messages and final_messages[0].get("role") == "system":
        final_messages[0] = system_message
    else:
        final_messages = [system_message, *final_messages]

    async def manager_tool_executor(name: str, args: dict) -> str:
        if name == "delegate_research":
            if on_chunk:
                await call_chunk(on_chunk, {"type": "tool_start", "tool": "Research Agent"})

            result = await run_worker_agent(
                args["query"], model, cancel_event, num_ctx, on_chunk,
                emit_tool_details=emit_tool_details,
                timing_collector=timing_collector,
            )

            if on_chunk:
                await call_chunk(on_chunk, {"type": "tool_end", "tool": "Research Agent", "result": "Research Complete"})

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

_model_list_cache: dict = {}
_MODEL_LIST_CACHE_TTL = 300  # seconds


def make_list_models(cfg: dict):
    """Return a list_models() coroutine bound to the given provider config."""
    async def list_models() -> list:
        base_url = (cfg.get("base_url") or settings.openrouter_base_url).rstrip("/")
        api_key = cfg.get("api_key") or settings.openrouter_api_key

        cache_key = (base_url, api_key)
        now = time.time()
        cached = _model_list_cache.get(cache_key)
        if cached and now - cached[0] < _MODEL_LIST_CACHE_TTL:
            return cached[1]

        if api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"{base_url}/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                result = sorted(
                    [
                        {
                            "name": m["id"],
                            "context_length": m.get("context_length") or 128000,
                            "provider": "openrouter",
                        }
                        for m in data.get("data", [])
                        if m.get("id")
                    ],
                    key=lambda m: m["name"],
                )
                _model_list_cache[cache_key] = (now, result)
                return result
            except Exception:
                pass  # fall through to static list

        static = [
            {"name": m["name"], "context_length": m["contextLengthKB"] * 1024, "provider": "openrouter"}
            for m in OPENROUTER_MODEL_LIST
        ]
        return static

    return list_models


