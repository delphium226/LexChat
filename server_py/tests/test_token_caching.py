"""Unit tests for D5 token-cost caching.

Part 1: Anthropic prompt-cache breakpoints on the OpenRouter payload path.
Part 2: per-request tool-result memo for Deep Research.
No LLM or network — everything is stubbed.
"""
import json

import pytest

from src.agent.openrouter_client import _apply_anthropic_cache_control
from src.utils.stopwatch import TimingCollector


# ---------------------------------------------------------------------------
# _apply_anthropic_cache_control
# ---------------------------------------------------------------------------

def _sample_messages():
    return [
        {"role": "system", "content": "You are a legal research assistant."},
        {"role": "user", "content": "Explain CPOs"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1"}]},
        {"role": "tool", "content": '{"results": []}', "tool_call_id": "call_1"},
    ]


def test_non_anthropic_payload_untouched():
    """OpenAI/Gemini models cache automatically — payload must be byte-identical."""
    messages = _sample_messages()
    for model in ("google/gemini-2.0-flash", "openai/gpt-4o", "mistralai/mistral-large"):
        result = _apply_anthropic_cache_control(messages, model)
        assert result is messages  # same object, no copy, no mutation
        assert all(isinstance(m.get("content"), (str, type(None))) for m in result)


def test_anthropic_marks_system_and_last_text_message():
    messages = _sample_messages()
    result = _apply_anthropic_cache_control(messages, "anthropic/claude-sonnet-4.5")

    # Input list not mutated
    assert isinstance(messages[0]["content"], str)

    # System prompt marked
    sys_content = result[0]["content"]
    assert isinstance(sys_content, list)
    assert sys_content[0]["cache_control"] == {"type": "ephemeral"}
    assert sys_content[0]["text"] == "You are a legal research assistant."

    # Last text-bearing message (the tool result) marked; the None-content
    # assistant message is skipped and untouched.
    tool_content = result[3]["content"]
    assert isinstance(tool_content, list)
    assert tool_content[0]["cache_control"] == {"type": "ephemeral"}
    assert result[2]["content"] is None
    # tool_call_id preserved alongside the converted content
    assert result[3]["tool_call_id"] == "call_1"

    # Middle user message untouched (only two breakpoints)
    assert result[1]["content"] == "Explain CPOs"


def test_anthropic_system_only_conversation_single_breakpoint():
    messages = [{"role": "system", "content": "sys"}]
    result = _apply_anthropic_cache_control(messages, "anthropic/claude-opus-4.1")
    assert isinstance(result[0]["content"], list)
    assert len(result) == 1


def test_prompt_caching_flag_off_disables_breakpoints():
    """With prompt_caching_enabled=False in the request config, anthropic/*
    payloads come back unchanged — the admin kill-switch for cache_control."""
    from src.agent.provider_factory import set_request_provider_config
    messages = _sample_messages()
    set_request_provider_config({"_prompt_caching_enabled": False})
    try:
        result = _apply_anthropic_cache_control(messages, "anthropic/claude-sonnet-4.5")
        assert result is messages
        assert all(isinstance(m.get("content"), (str, type(None))) for m in result)
    finally:
        set_request_provider_config({})

    # Flag back on (and when the key is absent) → breakpoints applied again
    marked = _apply_anthropic_cache_control(messages, "anthropic/claude-sonnet-4.5")
    assert isinstance(marked[0]["content"], list)


def test_anthropic_skips_empty_contents():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": ""},
    ]
    result = _apply_anthropic_cache_control(messages, "anthropic/claude-sonnet-4.5")
    assert result[2]["content"] == ""            # empty tail skipped
    assert isinstance(result[1]["content"], list)  # breakpoint lands on the user msg


# ---------------------------------------------------------------------------
# TimingCollector: cached-token + memo metrics
# ---------------------------------------------------------------------------

def test_timing_collector_cached_tokens_and_discount():
    t = TimingCollector("req1")
    t.record_cached_tokens(1500, -0.0042)  # OpenRouter reports discount as negative
    t.record_cached_tokens(500, 0)
    d = t.to_dict()
    assert d["cached_prompt_tokens"] == 2000
    assert d["cache_discount_usd"] == pytest.approx(0.0042)


def test_timing_collector_memo_hits():
    t = TimingCollector("req1")
    t.record_memo_hit()
    t.record_memo_hit()
    d = t.to_dict()
    assert d["memo_hits"] == 2
    # Memo hits are a saving, not loop-health noise
    assert d["worker_tool_calls"] == 0
    assert d["redundant_tool_calls"] == 0


# ---------------------------------------------------------------------------
# run_worker_tool: per-request tool-result memo (Deep Research)
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, patch  # noqa: E402

from src.agent.agent_shared import run_worker_tool  # noqa: E402

RAW_SECTIONS_RESULT = json.dumps({
    "title": "Acquisition of Land Act 1981",
    "url": "http://leg/ukpga/1981/67",
    "sections": [{
        "title": "Confirmation of order",
        "section_number": "13",
        "content": "The confirming authority may confirm the order...",
    }],
})

TOOL_ARGS = {"legislation_id": "ukpga/1981/67", "query": "confirmation procedure"}


async def _noop_chunk(*a, **k):
    return None


def _call(tool_memo, timing, source_accumulator, args=TOOL_ARGS, memo_count_redundant=False):
    return run_worker_tool(
        "search_legislation_sections", dict(args), "confirmation procedure",
        _noop_chunk, "test-model",
        timing_collector=timing,
        source_accumulator=source_accumulator,
        tool_memo=tool_memo,
        memo_count_redundant=memo_count_redundant,
    )


@pytest.mark.asyncio
async def test_memo_hit_skips_execution_and_reuses_sources():
    memo = {}
    timing = TimingCollector("req1")
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=RAW_SECTIONS_RESULT),
    ) as mock_exec:
        sources_step1 = []
        first = await _call(memo, timing, sources_step1)

        sources_step2 = []
        second = await _call(memo, timing, sources_step2)

    # Second call served from the memo: no API call, identical result
    assert mock_exec.await_count == 1
    assert second == first

    # A memoised retrieval still contributes its sources to the reusing step
    assert sources_step2 == sources_step1
    assert sources_step2[0]["_lid"] == "ukpga/1981/67"
    assert sources_step2[0]["excerpt"].startswith("The confirming authority")

    # Counted as a memo hit only — NOT a worker/phase call, NOT redundant
    assert timing.memo_hits == 1
    assert timing.worker_tool_calls == 1
    assert timing.phase2_retrieval_calls == 1
    assert timing.redundant_tool_calls == 0


@pytest.mark.asyncio
async def test_memo_requires_exact_arg_match():
    memo = {}
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=RAW_SECTIONS_RESULT),
    ) as mock_exec:
        await _call(memo, None, None)
        await _call(memo, None, None, args={**TOOL_ARGS, "query": "compensation"})
    assert mock_exec.await_count == 2  # different args → no fuzzy matching
    assert len(memo) == 2


@pytest.mark.asyncio
async def test_no_memo_preserves_existing_redundancy_counting():
    """Standard/conversational modes (tool_memo=None) behave exactly as before:
    the repeat executes again and IS counted as redundant."""
    timing = TimingCollector("req1")
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=RAW_SECTIONS_RESULT),
    ) as mock_exec:
        await _call(None, timing, None)
        await _call(None, timing, None)
    assert mock_exec.await_count == 2
    assert timing.worker_tool_calls == 2
    assert timing.redundant_tool_calls == 1
    assert timing.memo_hits == 0


# ---------------------------------------------------------------------------
# Standard-mode memo (D8 Phase 4): hit is free but still counted redundant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standard_mode_memo_hit_counts_redundancy():
    """With memo_count_redundant=True (standard research mode), a repeat is
    served from the memo (one API call) but STILL flagged redundant so the
    Efficiency tab's loop-health signal survives."""
    memo = {}
    timing = TimingCollector("req1")
    with patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=RAW_SECTIONS_RESULT),
    ) as mock_exec:
        first = await _call(memo, timing, None, memo_count_redundant=True)
        second = await _call(memo, timing, None, memo_count_redundant=True)

    assert mock_exec.await_count == 1  # served from memo
    assert second == first
    assert timing.memo_hits == 1
    # Unlike Deep Research, the hit is also a counted (redundant) tool call.
    assert timing.worker_tool_calls == 2
    assert timing.redundant_tool_calls == 1


async def _run_manager_with_two_delegations():
    """Drive process_user_request with a chat loop that delegates twice;
    return the kwargs each run_worker_agent_fn call received."""
    from src.agent import agent_core

    captured = []

    async def fake_worker(query, model, cancel_event, num_ctx, on_chunk, **kwargs):
        captured.append(kwargs)
        return {"content": "findings", "sources": []}

    async def fake_chat_loop(messages, model, cancel_event, num_ctx,
                             tools, tool_executor, on_chunk, **kwargs):
        await tool_executor("delegate_research", {"query": "first aspect"})
        await tool_executor("delegate_research", {"query": "second aspect"})
        return {"content": "final answer"}

    await agent_core.process_user_request(
        fake_chat_loop, fake_worker,
        [{"role": "user", "content": "the question"}],
        "test-model", None, None, 4096,
    )
    return captured


@pytest.mark.asyncio
async def test_standard_manager_creates_shared_memo():
    """process_user_request creates ONE memo per request and passes it to
    every delegation with memo_count_redundant=True."""
    from src.agent.provider_factory import set_request_provider_config
    set_request_provider_config({})
    try:
        captured = await _run_manager_with_two_delegations()
    finally:
        set_request_provider_config({})

    assert len(captured) == 2
    assert captured[0]["memo_count_redundant"] is True
    assert captured[0]["tool_memo"] == {}
    # Same dict object shared across both delegations
    assert captured[0]["tool_memo"] is captured[1]["tool_memo"]


@pytest.mark.asyncio
async def test_standard_manager_memo_flag_off():
    """tool_memo_enabled=False → the manager passes tool_memo=None (disabled)."""
    from src.agent.provider_factory import set_request_provider_config
    set_request_provider_config({"_tool_memo_enabled": False})
    try:
        captured = await _run_manager_with_two_delegations()
    finally:
        set_request_provider_config({})

    assert captured[0]["tool_memo"] is None
