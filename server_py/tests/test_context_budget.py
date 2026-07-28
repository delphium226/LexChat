"""Unit tests for the Worker accumulated-context budget and graceful failure.

get_summarise_threshold() caps each tool result individually but scales with the
model's context window, so several under-threshold retrievals could stack into a
prefill large enough to trip the stream read timeout. WORKER_CONTEXT_BUDGET_CHARS
bounds the sum. These drive run_worker_tool directly with the tool execution and
summariser stubbed, so no network, DB or LLM is involved.
"""
import json

import httpx
import pytest

from src.agent import agent_shared
from src.agent.agent_shared import describe_agent_error, run_worker_tool

_THRESHOLD = 10_000


@pytest.fixture
def _stub_pipeline(monkeypatch):
    """Stub the tool executor, threshold and summariser around run_worker_tool.

    Returns a dict recording which results were summarised, so a test can assert
    on the *decision* rather than on summary text.
    """
    state = {"summarised": [], "payload": ""}

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return state["payload"]

    async def fake_summarise(text, query, model, **kw):
        state["summarised"].append(len(text))
        return f"[summary of {len(text)} chars]", False

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_execute)
    monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)
    monkeypatch.setattr(
        "src.agent.provider_factory.get_summarise_threshold", lambda: _THRESHOLD
    )
    # Keep the shared cross-user cache out of it — it needs a DB.
    monkeypatch.setattr(
        "src.agent.provider_factory.get_request_provider_config",
        lambda: {"_local_prompt_cache_enabled": False},
    )
    return state


async def _run(payload: str, budget=None, state=None):
    state["payload"] = payload
    return await run_worker_tool(
        "get_case_law_text", {"url": "http://example/case"}, "q",
        chunk_fn=None, summarise_model="m",
        context_budget=budget,
    )


# --- the budget bounds the sum, not just each result ----------------------------

@pytest.mark.asyncio
async def test_under_threshold_and_under_budget_passes_through_raw(_stub_pipeline):
    budget = {"used": 0, "limit": 100_000}
    out = await _run("x" * 5_000, budget, _stub_pipeline)
    assert out == "x" * 5_000
    assert _stub_pipeline["summarised"] == []
    assert budget["used"] == 5_000


@pytest.mark.asyncio
async def test_result_over_budget_is_summarised_despite_being_under_threshold(_stub_pipeline):
    """The case that caused the outage: individually legal, collectively fatal."""
    budget = {"used": 98_000, "limit": 100_000}
    payload = "x" * 5_000  # well under _THRESHOLD
    out = await _run(payload, budget, _stub_pipeline)
    assert _stub_pipeline["summarised"] == [5_000]
    assert out.startswith("[summary of 5000 chars]")


@pytest.mark.asyncio
async def test_budget_accumulates_across_calls_until_it_trips(_stub_pipeline):
    budget = {"used": 0, "limit": 25_000}
    for _ in range(4):
        await _run("x" * 8_000, budget, _stub_pipeline)
    # First three fit (8k/16k/24k); the fourth would exceed 25k, so it is summarised.
    assert len(_stub_pipeline["summarised"]) == 1


@pytest.mark.asyncio
async def test_no_budget_leaves_behaviour_unchanged(_stub_pipeline):
    """context_budget=None must reproduce the pre-existing threshold-only rule."""
    out = await _run("x" * 9_000, None, _stub_pipeline)
    assert out == "x" * 9_000
    assert _stub_pipeline["summarised"] == []


@pytest.mark.asyncio
async def test_oversized_result_still_summarised_on_threshold_alone(_stub_pipeline):
    budget = {"used": 0, "limit": 1_000_000}
    await _run("x" * (_THRESHOLD + 1), budget, _stub_pipeline)
    assert _stub_pipeline["summarised"] == [_THRESHOLD + 1]


@pytest.mark.asyncio
async def test_memo_hit_still_spends_budget(_stub_pipeline):
    """A cached repeat costs no API call but still occupies context."""
    budget = {"used": 0, "limit": 100_000}
    memo = {}
    args = {"url": "http://example/case"}
    _stub_pipeline["payload"] = json.dumps({"text": "y" * 100})
    for _ in range(2):
        await run_worker_tool(
            "get_case_law_text", args, "q", chunk_fn=None, summarise_model="m",
            tool_memo=memo, context_budget=budget,
        )
    assert len(memo) == 1  # second call was a memo hit
    assert budget["used"] == 2 * len(_stub_pipeline["payload"])  # charged twice


# --- describe_agent_error -------------------------------------------------------

def test_describe_timeout_is_not_empty():
    """The bug this exists for: httpx timeouts stringify to ''."""
    exc = httpx.ReadTimeout("")
    assert str(exc) == ""
    assert "did not respond in time" in describe_agent_error(exc)


def test_describe_http_status_includes_code():
    resp = httpx.Response(503, request=httpx.Request("GET", "http://x"))
    exc = httpx.HTTPStatusError("boom", request=resp.request, response=resp)
    assert "503" in describe_agent_error(exc)


def test_describe_falls_back_to_message_then_type():
    assert describe_agent_error(ValueError("something specific")) == "something specific"
    assert "ValueError" in describe_agent_error(ValueError())


# --- worker failure is contained, not fatal -------------------------------------

@pytest.mark.asyncio
async def test_worker_timeout_becomes_a_tool_result_not_a_dead_request(monkeypatch):
    """A worker that dies must not take the whole request down.

    Before this, the exception propagated worker -> manager -> queue -> SSE and
    the lawyer got a dead stream. Now the Manager receives an error string and
    can still compose a reply.
    """
    from src.agent.agent_core import process_user_request
    from src.agent.provider_factory import set_request_provider_config

    set_request_provider_config({
        "_provider": "ollama", "_research_mode": "legislation_only",
        "model": "test-model",
    })
    seen = {}

    async def dying_worker(*a, **kw):
        raise httpx.ReadTimeout("")

    async def fake_chat_loop(messages, model, cancel_event, num_ctx, tools,
                             tool_executor, on_chunk, **kw):
        seen["tool_result"] = await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "I could not complete the research."}

    try:
        final = await process_user_request(
            fake_chat_loop, dying_worker,
            [{"role": "user", "content": "q"}], "test-model",
            None, None, 0,
        )
    finally:
        set_request_provider_config({})

    assert final["content"]  # the request completed instead of raising
    assert "[Research Agent Error]" in seen["tool_result"]
    assert "did not respond in time" in seen["tool_result"]
    # The Manager must be steered away from a retry loop and away from inventing.
    assert "Do NOT call delegate_research again" in seen["tool_result"]
    assert "Do NOT invent findings" in seen["tool_result"]


@pytest.mark.asyncio
async def test_connection_error_still_propagates(monkeypatch):
    """ConnectionError has a dedicated handler upstream — don't swallow it."""
    from src.agent.agent_core import process_user_request
    from src.agent.provider_factory import set_request_provider_config

    set_request_provider_config({
        "_provider": "ollama", "_research_mode": "legislation_only",
        "model": "test-model",
    })

    async def unreachable(*a, **kw):
        raise ConnectionError("provider down")

    async def fake_chat_loop(messages, model, cancel_event, num_ctx, tools,
                             tool_executor, on_chunk, **kw):
        return await tool_executor("delegate_research", {"query": "q"})

    try:
        with pytest.raises(ConnectionError):
            await process_user_request(
                fake_chat_loop, unreachable,
                [{"role": "user", "content": "q"}], "test-model",
                None, None, 0,
            )
    finally:
        set_request_provider_config({})
