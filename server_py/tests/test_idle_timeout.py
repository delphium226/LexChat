"""P4.11 — an upstream idle timeout, on a Worker call.

Mechanism (b): the stream ends `finish_reason=error`, "Upstream idle timeout
exceeded", after ~130-310 tokens and ~125-190 s. It costs ~$0 but a retry
costs the same wait again, and the retry resends identical bytes. Redrawn as
sent at the recorded head and date (BASELINE.md, "The latency of an upstream
idle timeout"): the next draw of a (b) payload was (b) again 11 times in 11,
and the recorded Worker retries after a (b) answered 1 time in 14. The same
payloads also ran away, and one changed line cured both.

The fix, by user decision (FIX_PLAN P4.11, booked in d34c48e): on a Worker
call an idle-timeout empty is not retried but falls into P4.5's lost-report
label, and the Manager re-delegates with new bytes. A rate limit (also a
stream error; its retry answered 13 of 14) and every non-Worker call keep the
retry. These tests are the acceptance, one per seam.

`asyncio.sleep` is stubbed, so no retry waits.
"""
import asyncio

import httpx
import pytest

from src.agent import ollama_client, openrouter_client
from src.agent.agent_core import run_worker_agent
from src.utils import empty_completion as ec
from src.utils.research_halt import LOST_REPORT_TAG

from .test_lost_cost import (  # noqa: F401  (fixtures are used by name)
    _OLLAMA_CONTENT,
    _OR_CONTENT,
    _OR_HEAVY,
    _OR_IDLE,
    _audit,
    _or,
    _recording,
    _worker_cfg,
)
from .test_stream_retry import _mock_http, _no_sleep, _sse  # noqa: F401

# (d) wave2_p24/6385 r2 t3, attempt 3: a rate limit, also a stream error.
_OR_RATE = _sse(
    '{"error":{"message":"google/gemini-3.1-pro-preview is temporarily '
    'rate-limited upstream. Please retry shortly"},'
    '"choices":[{"delta":{},"finish_reason":"error"}]}',
)
_OR_OTHER_ERROR = _sse(
    '{"error":{"message":"Internal server error"},'
    '"choices":[{"delta":{},"finish_reason":"error"}]}',
)
_OLLAMA_IDLE = '{"error":"upstream idle timeout exceeded","done":true}\n'


# --- the predicate ------------------------------------------------------------

def test_the_recorded_error_text_is_an_idle_timeout():
    assert ec.is_idle_timeout({"stream_error": "Upstream idle timeout exceeded"})
    assert ec.is_idle_timeout({"stream_error": "UPSTREAM IDLE TIMEOUT"})
    assert not ec.is_idle_timeout({"stream_error": "google/gemini-3.1-pro-preview is "
                                                   "temporarily rate-limited upstream."})
    assert not ec.is_idle_timeout({"stream_error": None})
    assert not ec.is_idle_timeout({})
    assert not ec.is_idle_timeout({"stream_error": {"message": "idle timeout"}})
    assert not ec.is_idle_timeout(None)  # never raises


def test_only_a_workers_idle_timeout_loses_its_retry():
    idle = {"stream_error": "Upstream idle timeout exceeded", "completion_tokens": 170}
    rate = {"stream_error": "temporarily rate-limited upstream", "completion_tokens": 0}
    bare = {"completion_tokens": None}
    other = {"stream_error": "Internal server error", "completion_tokens": 12}
    kw = {"attempts_max": 3}
    assert not ec.should_retry_empty(idle, attempt=0, worker_call=True, **kw)
    assert ec.should_retry_empty(idle, attempt=0, worker_call=False, **kw)
    for probe in (rate, bare, other):
        assert ec.should_retry_empty(probe, attempt=0, worker_call=True, **kw)
    # P4.10's rule is unchanged
    assert not ec.should_retry_empty({"completion_tokens": 62912}, attempt=0,
                                     worker_call=True, **kw)
    assert ec.should_retry_empty({"completion_tokens": 62912}, attempt=0,
                                 worker_call=False, **kw)


# --- the retry, both clients ----------------------------------------------------

@pytest.mark.asyncio
async def test_a_workers_idle_timeout_is_not_retried(_no_sleep, _mock_http, _audit):
    h = _recording([httpx.Response(200, text=_OR_IDLE),
                    httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = await _or(True)
    assert result["content"] == ""
    assert len(h.seen) == 1 and _no_sleep == []
    (probe,) = _audit.empty_completions
    assert probe["stream_error"] == "Upstream idle timeout exceeded"
    assert probe["attempt"] == 1 and probe["retried"] is False


@pytest.mark.asyncio
async def test_the_same_idle_timeout_off_a_worker_is_retried_as_before(
        _no_sleep, _mock_http, _audit):
    """The Manager keeps its retry: an unrecovered Manager call has no
    re-delegation behind it, only P4.2's fallback."""
    h = _recording([httpx.Response(200, text=_OR_IDLE),
                    httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = await _or(False)
    assert result["content"] == "hello" and len(h.seen) == 2
    assert _audit.empty_completions[0]["retried"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [_OR_RATE, _OR_OTHER_ERROR], ids=["d_rate", "other_error"])
async def test_a_workers_other_stream_errors_are_still_retried(
        body, _no_sleep, _mock_http, _audit):
    h = _recording([httpx.Response(200, text=body), httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = await _or(True)
    assert result["content"] == "hello" and len(h.seen) == 2
    assert _audit.empty_completions[0]["retried"] is True


@pytest.mark.asyncio
async def test_ollama_does_not_retry_a_workers_idle_timeout(_no_sleep, _mock_http, _audit):
    async def call(worker_call):
        return await ollama_client.chat_loop(
            messages=[{"role": "user", "content": "q"}], model="m", cancel_event=None,
            num_ctx=0, tools=[], tool_executor=None, worker_call=worker_call)

    h = _recording([httpx.Response(200, text=_OLLAMA_IDLE),
                    httpx.Response(200, text=_OLLAMA_CONTENT)])
    _mock_http(h)
    result = await call(True)
    assert result["content"] == "" and len(h.seen) == 1
    # and off a worker it still is
    h2 = _recording([httpx.Response(200, text=_OLLAMA_IDLE),
                     httpx.Response(200, text=_OLLAMA_CONTENT)])
    _mock_http(h2)
    result = await call(False)
    assert result["content"] == "hello" and len(h2.seen) == 2


@pytest.mark.asyncio
async def test_an_idle_timeout_then_a_runaway_ends_at_the_first(_no_sleep, _mock_http, _audit):
    """wave2_p28/6409 r3 t11 went b, a, b. After P4.10 the (a) ended the call
    at two attempts; now the (b) ends it at one."""
    h = _recording([httpx.Response(200, text=_OR_IDLE),
                    httpx.Response(200, text=_OR_HEAVY),
                    httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    await _or(True)
    assert len(h.seen) == 1


# --- end to end: one attempt, then P4.5's label ---------------------------------

def test_a_workers_idle_timeout_is_labelled_lost_after_one_attempt(
        _worker_cfg, _no_sleep, _mock_http):
    """The whole seam: the real OpenRouter loop under run_worker_agent. Before
    this row the provider was asked three times (~6-9 minutes on the stored
    episodes) before the label; now once."""
    h = _recording([httpx.Response(200, text=_OR_IDLE),
                    httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = asyncio.run(run_worker_agent(
        openrouter_client.chat_loop, lambda *a, **k: None, "q", "test-model", None, 0))
    assert len(h.seen) == 1
    assert result["lost"]["reason"] == "empty_completion"
    assert result["content"].startswith(LOST_REPORT_TAG)
