"""P4.12 — a lost Manager reply: no retry after a heavy empty, one after an
idle timeout, and the Worker's output cap, while a worker report is in hand.

Measured over 63 replay directories (batch 10 D, `notes/batch10_D.md`
section 2): 10 Manager calls came back empty, 8 unrecovered. The retry after
a Manager heavy empty answered 0 of 3; after two idle timeouts the third
attempt answered 0 of 11 at every site; every one of the 10 came after a
delegation, so all 8 unrecovered calls got P4.2's fallback with the worker
reports, 6 to 18 minutes later than one attempt would have given it.

The fix, by user decision (FIX_PLAN P4.12, 2026-10-08): on a Manager call,
L1 no retry after a heavy empty, L2' at most one retry after an idle timeout,
L3 the 32,000-token cap (OpenRouter only); L1 and L2' gated on a usable
worker report being in hand (the list P4.2's fallback reads), so a reply lost
before any research keeps every retry. The planner, the Deep Research
synthesis and the Worker are unchanged. These tests are the acceptance, one
per seam. Synthetic text only.

`asyncio.sleep` is stubbed, so no retry waits.
"""
import asyncio
import json
import logging

import httpx
import pytest

from src.agent import ollama_client, openrouter_client
from src.agent.agent_core import (
    draft_research_plan,
    process_user_request,
    run_deep_research,
    run_worker_agent,
)
from src.agent.provider_factory import set_request_provider_config
from src.utils import empty_completion as ec

from .test_idle_timeout import _OLLAMA_IDLE, _OR_RATE
from .test_lost_cost import (  # noqa: F401  (fixtures are used by name)
    _OLLAMA_CONTENT,
    _OLLAMA_EMPTY,
    _OLLAMA_HEAVY,
    _OR_BARE,
    _OR_CONTENT,
    _OR_HEAVY,
    _OR_IDLE,
    _audit,
    _recording,
    _recording_loop,
    _worker_cfg,
)
from .test_lost_step import _plan, _step_worker
from .test_stream_retry import _mock_http, _no_sleep, _sse  # noqa: F401

_REPORT = "1. **Summary Answer (BLUF):** The Widget Order 1901 applies (ssi/1901/3)."

_OR_DELEGATE = _sse(
    '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"d1",'
    '"function":{"name":"delegate_research","arguments":"{\\"query\\": \\"q\\"}"}}]}}]}'
)
_OR_TOOL_CALL = _sse(
    '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
    '"function":{"name":"delegate_research","arguments":"{}"}}]}}]}'
)
_OR_CUT = _sse(
    '{"choices":[{"delta":{"content":"an answer that was still going"},'
    '"finish_reason":"length","native_finish_reason":"MAX_TOKENS"}]}',
)

HEAVY = {"completion_tokens": 62914, "reasoning_chars": 98000}
IDLE = {"stream_error": "Upstream idle timeout exceeded", "completion_tokens": 170}
BARE = {"completion_tokens": None, "finish_reason": "stop"}
RATE = {"stream_error": "google/gemini-3.1-pro-preview is temporarily rate-limited "
                        "upstream. Please retry shortly", "completion_tokens": 0}


def _retry(probe, attempt, *, report=True, earlier=0, manager=True, attempts_max=3):
    return ec.should_retry_empty(
        probe, attempt=attempt, attempts_max=attempts_max, worker_call=False,
        manager_call=manager, report_in_hand=report, earlier_idle_timeouts=earlier)


# --- the retry decision, per mechanism ------------------------------------------

def test_a_managers_heavy_empty_with_a_report_in_hand_is_not_retried():  # (a), L1
    assert not _retry(HEAVY, 0)
    assert not _retry(HEAVY, 1)
    # gated: with no report in hand it is retried as before
    assert _retry(HEAVY, 0, report=False)
    assert _retry(HEAVY, 1, report=False)
    # and off the Manager, as before
    assert _retry(HEAVY, 0, manager=False)


def test_heavy_means_the_instruments_threshold_on_the_manager_too():
    """The same `is_heavy_empty` as P4.10: a light token count is not heavy."""
    assert _retry({"completion_tokens": ec.HEAVY_EMPTY_TOKENS - 1}, 0)
    assert not _retry({"completion_tokens": ec.HEAVY_EMPTY_TOKENS}, 0)
    assert not _retry({"reasoning_chars": ec.HEAVY_EMPTY_REASONING_CHARS}, 0)


def test_a_managers_first_idle_timeout_keeps_its_one_retry():  # (b) attempt 1, L2'
    assert _retry(IDLE, 0, earlier=0)
    assert _retry(IDLE, 0, earlier=0, report=False)


def test_a_managers_second_idle_timeout_is_not_retried():  # (b) attempt 2, L2'
    assert not _retry(IDLE, 1, earlier=1)
    # gated: with no report in hand the third attempt is kept
    assert _retry(IDLE, 1, earlier=1, report=False)
    # off the Manager, as before
    assert _retry(IDLE, 1, earlier=1, manager=False)


def test_the_count_is_of_idle_timeouts_not_of_attempts():
    """A first idle timeout on a later attempt (after a rate limit, say) still
    gets its one retry; a second one never does, whatever came between."""
    assert _retry(IDLE, 1, earlier=0)
    assert not _retry(IDLE, 2, earlier=1, attempts_max=4)
    assert ec.MANAGER_IDLE_TIMEOUT_RETRIES == 1


def test_a_managers_clean_stop_and_rate_limit_are_retried_as_before():  # (c), (d)
    for probe in (BARE, RATE):
        assert _retry(probe, 0) and _retry(probe, 1)
        assert _retry(probe, 1, earlier=1)  # an earlier idle timeout changes nothing


def test_the_last_attempt_is_never_retried_as_before():
    for probe in (HEAVY, IDLE, BARE, RATE):
        assert not _retry(probe, 2, report=False)
        assert not _retry(probe, 2, manager=False)


def test_the_workers_rules_are_unchanged():
    kw = {"attempts_max": 3}
    assert not ec.should_retry_empty(HEAVY, attempt=0, worker_call=True, **kw)
    assert not ec.should_retry_empty(IDLE, attempt=0, worker_call=True, **kw)
    assert ec.should_retry_empty(RATE, attempt=0, worker_call=True, **kw)
    assert ec.should_retry_empty(BARE, attempt=0, worker_call=True, **kw)


def test_report_in_hand_now_is_fail_soft():
    assert ec.report_in_hand_now(lambda: True) is True
    assert ec.report_in_hand_now(lambda: ["x"]) is True
    assert ec.report_in_hand_now(lambda: []) is False
    assert ec.report_in_hand_now(None) is False
    assert ec.report_in_hand_now(True) is False  # not a callable: no report

    def boom():
        raise RuntimeError("x")

    assert ec.report_in_hand_now(boom) is False  # fails to "keep the retries"


# --- both clients' chat_loop on a Manager call ----------------------------------

async def _mgr(in_hand, **kw):
    """The OpenRouter loop as the Manager calls it. `in_hand` is the gate's
    value (a callable, or a bool turned into one)."""
    gate = in_hand if callable(in_hand) or in_hand is None else (lambda: in_hand)
    return await openrouter_client.chat_loop(
        messages=[{"role": "user", "content": "q"}], model="test/model",
        cancel_event=None, num_ctx=0, tools=kw.pop("tools", []),
        tool_executor=kw.pop("tool_executor", None),
        manager_call=kw.pop("manager_call", True), manager_report_in_hand=gate, **kw)


def _serve(mock_http, *bodies):
    h = _recording([httpx.Response(200, text=b) for b in bodies])
    mock_http(h)
    return h


@pytest.mark.asyncio
async def test_a_manager_call_carries_the_cap_with_or_without_a_report(_no_sleep, _mock_http):
    h = _serve(_mock_http, _OR_CONTENT)
    await _mgr(True)
    await _mgr(False)
    await _mgr(None)
    assert [b.get("max_tokens") for b in h.seen] == [32_000] * 3
    assert ec.WORKER_MAX_OUTPUT_TOKENS == 32_000


@pytest.mark.asyncio
async def test_the_cap_is_on_the_manager_payload_only(_no_sleep, _mock_http):
    """A plain call (the planner, the synthesis, the reformat) is unchanged."""
    h = _serve(_mock_http, _OR_CONTENT)
    await _mgr(True, manager_call=False)
    assert set(h.seen[0]) == {"model", "messages", "stream", "temperature"}


@pytest.mark.asyncio
async def test_or_manager_heavy_empty_with_a_report_is_not_retried(_no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OR_HEAVY, _OR_CONTENT)
    result = await _mgr(True)
    assert result["content"] == "" and len(h.seen) == 1 and _no_sleep == []
    (probe,) = _audit.empty_completions
    assert probe["attempt"] == 1 and probe["retried"] is False


@pytest.mark.asyncio
async def test_or_manager_heavy_empty_without_a_report_is_retried(_no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OR_HEAVY, _OR_CONTENT)
    result = await _mgr(False)
    assert result["content"] == "hello" and len(h.seen) == 2
    assert _audit.empty_completions[0]["retried"] is True


@pytest.mark.asyncio
async def test_or_manager_idle_timeouts_with_a_report_stop_at_two(_no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OR_IDLE, _OR_IDLE, _OR_CONTENT)
    result = await _mgr(True)
    assert result["content"] == "" and len(h.seen) == 2
    assert [(p["attempt"], p["retried"]) for p in _audit.empty_completions] == [
        (1, True), (2, False)]


@pytest.mark.asyncio
async def test_or_manager_idle_timeout_then_an_answer_is_kept(_no_sleep, _mock_http, _audit):
    """All three stored (b) recoveries came on the second attempt."""
    h = _serve(_mock_http, _OR_IDLE, _OR_CONTENT)
    result = await _mgr(True)
    assert result["content"] == "hello" and len(h.seen) == 2


@pytest.mark.asyncio
async def test_or_manager_idle_timeouts_without_a_report_keep_three(_no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OR_IDLE, _OR_IDLE, _OR_CONTENT)
    result = await _mgr(False)
    assert result["content"] == "hello" and len(h.seen) == 3


@pytest.mark.asyncio
async def test_or_manager_rate_limit_then_idle_timeout_still_gets_the_retry(
        _no_sleep, _mock_http, _audit):
    """The count is of idle timeouts, not attempts: the (b) on attempt 2 is the
    call's first and keeps its one retry."""
    h = _serve(_mock_http, _OR_RATE, _OR_IDLE, _OR_CONTENT)
    result = await _mgr(True)
    assert result["content"] == "hello" and len(h.seen) == 3


@pytest.mark.asyncio
async def test_or_manager_clean_stop_with_a_report_is_retried(_no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OR_BARE, _OR_BARE, _OR_CONTENT)
    result = await _mgr(True)
    assert result["content"] == "hello" and len(h.seen) == 3


@pytest.mark.asyncio
async def test_or_the_gate_is_read_when_the_empty_arrives(_no_sleep, _mock_http, _audit):
    """The report arrives during round 0's tool call; round 1's heavy empty sees
    it, and the cap reaches every round of the loop."""
    reports = []

    async def executor(name, args):
        reports.append("a report")
        return "tool output"

    h = _serve(_mock_http, _OR_TOOL_CALL, _OR_HEAVY, _OR_CONTENT)
    result = await _mgr(lambda: bool(reports), tool_executor=executor)
    assert result["content"] == "" and len(h.seen) == 2
    assert [b.get("max_tokens") for b in h.seen] == [32_000, 32_000]


@pytest.mark.asyncio
async def test_or_a_heavy_empty_before_any_report_is_retried(_no_sleep, _mock_http, _audit):
    reports = []
    h = _serve(_mock_http, _OR_HEAVY, _OR_CONTENT)
    result = await _mgr(lambda: bool(reports))
    assert result["content"] == "hello" and len(h.seen) == 2


@pytest.mark.asyncio
async def test_or_a_gate_that_raises_keeps_the_retries(_no_sleep, _mock_http, _audit):
    def boom():
        raise RuntimeError("x")

    h = _serve(_mock_http, _OR_HEAVY, _OR_CONTENT)
    result = await _mgr(boom)
    assert result["content"] == "hello" and len(h.seen) == 2


@pytest.mark.asyncio
async def test_or_the_flags_reach_the_step_cap_write_up(_no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OR_HEAVY, _OR_CONTENT)
    result = await _mgr(True, max_turns=0)
    # the write-up round is capped, and its heavy empty is not retried
    assert h.seen[0]["max_tokens"] == 32_000 and len(h.seen) == 1
    assert result["halted"]["written_up"] is False


@pytest.mark.asyncio
async def test_or_a_capped_manager_answer_is_logged(_no_sleep, _mock_http, caplog):
    _serve(_mock_http, _OR_CUT)
    with caplog.at_level(logging.WARNING, logger="agent"):
        result = await _mgr(True)
    assert result["content"] == "an answer that was still going"
    msgs = [r.getMessage() for r in caplog.records]
    assert any("Manager call reached" in m and "answer may be cut" in m for m in msgs)


@pytest.mark.asyncio
async def test_or_a_plain_calls_cut_answer_is_not_logged(_no_sleep, _mock_http, caplog):
    _serve(_mock_http, _OR_CUT)
    with caplog.at_level(logging.WARNING, logger="agent"):
        await _mgr(True, manager_call=False)
    assert not any("output cap" in r.getMessage() for r in caplog.records)


async def _ollama_mgr(in_hand):
    return await ollama_client.chat_loop(
        messages=[{"role": "user", "content": "q"}], model="m", cancel_event=None,
        num_ctx=0, tools=[], tool_executor=None, manager_call=True,
        manager_report_in_hand=lambda: in_hand)


@pytest.mark.asyncio
async def test_ollama_manager_heavy_empty_follows_the_gate(_no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OLLAMA_HEAVY, _OLLAMA_CONTENT)
    assert (await _ollama_mgr(True))["content"] == "" and len(h.seen) == 1
    h2 = _serve(_mock_http, _OLLAMA_HEAVY, _OLLAMA_CONTENT)
    assert (await _ollama_mgr(False))["content"] == "hello" and len(h2.seen) == 2


@pytest.mark.asyncio
async def test_ollama_manager_idle_timeouts_follow_the_gate(_no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OLLAMA_IDLE, _OLLAMA_IDLE, _OLLAMA_CONTENT)
    assert (await _ollama_mgr(True))["content"] == "" and len(h.seen) == 2
    h2 = _serve(_mock_http, _OLLAMA_IDLE, _OLLAMA_IDLE, _OLLAMA_CONTENT)
    assert (await _ollama_mgr(False))["content"] == "hello" and len(h2.seen) == 3
    h3 = _serve(_mock_http, _OLLAMA_EMPTY, _OLLAMA_EMPTY, _OLLAMA_CONTENT)
    assert (await _ollama_mgr(True))["content"] == "hello" and len(h3.seen) == 3


@pytest.mark.asyncio
async def test_ollama_manager_call_takes_no_cap(_no_sleep, _mock_http):
    h = _serve(_mock_http, _OLLAMA_CONTENT)
    await _ollama_mgr(True)
    assert set(h.seen[0]["options"]) == {"num_ctx", "temperature"}
    assert "max_tokens" not in h.seen[0]


# --- who passes it, and what the gate reads -----------------------------------

def _worker_returning(*results):
    calls = []

    async def worker(*a, **kw):
        calls.append(a)
        return results[min(len(calls), len(results)) - 1]

    return worker


def _gate_probe_loop(n_delegations):
    """A Manager stub that reads the gate before and after each delegation."""
    seen = {"kw": None, "gate": []}

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, **kw):
        seen["kw"] = kw
        gate = kw.get("manager_report_in_hand")
        seen["gate"].append(gate())
        for _ in range(n_delegations):
            await executor("delegate_research", {"query": "q"})
            seen["gate"].append(gate())
        return {"role": "assistant", "content": "An answer."}

    chat_loop.seen = seen
    return chat_loop


def test_the_manager_passes_the_flag_and_a_live_gate(_worker_cfg):
    loop = _gate_probe_loop(1)
    worker = _worker_returning({"content": _REPORT, "sources": []})
    asyncio.run(process_user_request(loop, worker, [{"role": "user", "content": "q"}],
                                     "test-model", None, None, 0))
    assert loop.seen["kw"]["manager_call"] is True
    assert not loop.seen["kw"].get("worker_call")
    assert loop.seen["gate"] == [False, True]  # no report, then one in hand


def test_a_lost_or_empty_report_does_not_open_the_gate(_worker_cfg):
    """The gate reads exactly what P4.2's fallback would show: a lost report's
    label and an empty report are not research."""
    loop = _gate_probe_loop(3)
    worker = _worker_returning(
        {"content": "[Research Incomplete — answer lost] label", "sources": [],
         "lost": {"reason": "empty_completion", "sources_retrieved": 0}},
        {"content": "   ", "sources": []},
        {"content": _REPORT, "sources": []},
    )
    asyncio.run(process_user_request(loop, worker, [{"role": "user", "content": "q"}],
                                     "test-model", None, None, 0))
    assert loop.seen["gate"] == [False, False, False, True]


def test_the_planner_does_not_pass_it(_worker_cfg):
    loop = _recording_loop("prose")
    asyncio.run(draft_research_plan(loop, [{"role": "user", "content": "q"}],
                                    "test-model", None, 0))
    assert loop.calls and not any(c.get("manager_call") for c in loop.calls)


def test_the_deep_research_synthesis_does_not_pass_it(_worker_cfg):
    loop = _recording_loop("INTEGRATED REPORT.")
    asyncio.run(run_deep_research(loop, _step_worker(set()), _plan(2),
                                  [{"role": "user", "content": "q"}], "test-model",
                                  None, None, 0))
    assert len(loop.calls) == 1 and not loop.calls[0].get("manager_call")


def test_the_worker_and_its_reformat_do_not_pass_it(_worker_cfg):
    flat = "An answer with no report structure at all, long enough to be checked."
    fixed = "1. **Summary Answer (BLUF):** Answer.\n2. **References:** None found."
    loop = _recording_loop(flat, fixed)
    asyncio.run(run_worker_agent(loop, lambda *a, **k: None, "q", "test-model", None, 0))
    assert len(loop.calls) == 2 and not any(c.get("manager_call") for c in loop.calls)


# --- end to end: the real loop under process_user_request ------------------------

@pytest.fixture
def _mgr_cfg():
    set_request_provider_config({
        "_provider": "openrouter", "_chat_mode": "conversational",
        "_research_mode": "legislation_only", "model": "test-model",
        "_tool_memo_enabled": False,
    })
    yield
    set_request_provider_config({})


def test_a_heavy_empty_reaches_the_fallback_after_one_attempt(
        _mgr_cfg, _no_sleep, _mock_http, _audit):
    """The stored Manager heavy empties' shape (P4.12's row): a delegation,
    then a heavy empty. Before this row
    the provider was asked three times (~$2.35 and ~17 minutes over the slot)
    before P4.2's fallback; now once, and the fallback is the same."""
    h = _serve(_mock_http, _OR_DELEGATE, _OR_HEAVY, _OR_CONTENT)
    worker = _worker_returning({"content": _REPORT, "sources": [], "searches": []})
    final = asyncio.run(process_user_request(
        openrouter_client.chat_loop, worker, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0))
    assert len(h.seen) == 2  # round 0, then one attempt at round 1
    assert all(b.get("max_tokens") == 32_000 for b in h.seen)
    assert final["answer_failed"] is True
    assert "not a composed answer" in final["content"]
    assert "Widget Order 1901" in final["content"]
    (probe,) = _audit.empty_completions
    assert probe["react_turn"] == 1 and probe["retried"] is False


def test_two_idle_timeouts_reach_the_fallback_after_two_attempts(
        _mgr_cfg, _no_sleep, _mock_http, _audit):
    h = _serve(_mock_http, _OR_DELEGATE, _OR_IDLE, _OR_IDLE, _OR_CONTENT)
    worker = _worker_returning({"content": _REPORT, "sources": [], "searches": []})
    final = asyncio.run(process_user_request(
        openrouter_client.chat_loop, worker, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0))
    assert len(h.seen) == 3
    assert final["answer_failed"] is True and "Widget Order 1901" in final["content"]


def test_a_reply_lost_before_any_research_keeps_all_three_attempts(
        _mgr_cfg, _no_sleep, _mock_http, _audit):
    """The gate: no report in hand, so the bare notice comes only after every
    attempt it came after before this row."""
    async def never_called_worker(*a, **kw):  # pragma: no cover
        raise AssertionError("no delegation in this scenario")

    h = _serve(_mock_http, _OR_HEAVY, _OR_HEAVY, _OR_HEAVY, _OR_CONTENT)
    final = asyncio.run(process_user_request(
        openrouter_client.chat_loop, never_called_worker,
        [{"role": "user", "content": "q"}], "test-model", None, None, 0))
    assert len(h.seen) == 3
    assert final["content"].startswith(ec.LOST_ANSWER_NOTICE[:40])
    assert [p["retried"] for p in _audit.empty_completions] == [True, True, False]


def test_a_heavy_empty_before_any_research_can_still_recover(
        _mgr_cfg, _no_sleep, _mock_http, _audit):
    async def never_called_worker(*a, **kw):  # pragma: no cover
        raise AssertionError("no delegation in this scenario")

    h = _serve(_mock_http, _OR_HEAVY, _OR_CONTENT)
    final = asyncio.run(process_user_request(
        openrouter_client.chat_loop, never_called_worker,
        [{"role": "user", "content": "q"}], "test-model", None, None, 0))
    assert len(h.seen) == 2 and "answer_failed" not in final
    assert final["content"].startswith("hello")


def test_the_request_bodies_are_json(_mgr_cfg, _no_sleep, _mock_http):
    """Sanity for the fixtures above: the delegation body parses as a tool call."""
    body = json.loads(_OR_DELEGATE.split("data: ")[1].strip())
    call = body["choices"][0]["delta"]["tool_calls"][0]["function"]
    assert call["name"] == "delegate_research" and json.loads(call["arguments"]) == {"query": "q"}
