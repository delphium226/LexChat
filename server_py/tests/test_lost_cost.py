"""P4.10 — what a lost completion costs, on a Worker call.

On the pinned model a Worker call sometimes reasons until it has spent about
96% of its output budget and then emits nothing (~62,900 reasoning tokens,
~$0.76 and ~6 minutes an attempt), and P4.2's retry paid that up to three
times. Measured over 50 replay directories (`replay_report lostcost
--all-dirs`): 8 such calls, every one in a research Worker, cost $12.38 and
7,073 s over their slots' medians; the retry after one answered 2 times in 12;
the Manager's re-delegation made good 6 of 6. On the seam a `max_tokens` cap
ended the same failure at 96% of the cap.

The fix, by user decision (FIX_PLAN P4.10, booked in 484f32f): a Worker call
carries `max_tokens` (32,000), and its heavy empty is not retried but falls
into P4.5's lost-report label. Every other call is unchanged. These tests are
the deterministic half of the acceptance, one per seam.

`asyncio.sleep` is stubbed, so no retry waits.
"""
import asyncio
import json
import logging

import httpx
import pytest

from src.agent import ollama_client, openrouter_client
from src.agent.agent_core import process_user_request, run_deep_research, run_worker_agent
from src.agent.provider_factory import set_request_provider_config
from src.utils import empty_completion as ec
from src.utils.audit_trace import AuditCollector, set_audit_collector
from src.utils.research_halt import LOST_REPORT_TAG

from .test_lost_step import _plan, _step_worker
from .test_stream_retry import (  # noqa: F401  (fixtures are used by name)
    _mock_http,
    _no_sleep,
    _sse,
)

# --- bodies: the stored mechanisms --------------------------------------------

# (a) wave3_p313/6348 r2 t1: stop, ~62,900 tokens, reasoning, no content.
_OR_HEAVY = _sse(
    '{"choices":[{"delta":{"reasoning":"' + "x" * 200 + '"},"finish_reason":"stop",'
    '"native_finish_reason":"STOP"}]}',
    '{"usage":{"completion_tokens":62912,"cost":0.76}}',
)
# (b) wave2_p24/6373 r1 t3: a mid-stream upstream idle timeout, ~170 tokens.
_OR_IDLE = _sse(
    '{"error":{"message":"Upstream idle timeout exceeded"},'
    '"choices":[{"delta":{},"finish_reason":"error"}]}',
    '{"usage":{"completion_tokens":170,"cost":0.0}}',
)
# (c) wave2_p24_pre/6375 r3 t2: a clean stop with nothing and no token count.
_OR_BARE = _sse('{"choices":[{"delta":{},"finish_reason":"stop"}]}')
_OR_CONTENT = _sse('{"choices":[{"delta":{"content":"hello"}}]}')
_OR_TOOL_CALL = _sse(
    '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
    '"function":{"name":"search_legislation","arguments":"{}"}}]}}]}'
)
_OR_CUT = _sse(
    '{"choices":[{"delta":{"content":"a report that was still going"},'
    '"finish_reason":"length","native_finish_reason":"MAX_TOKENS"}]}',
)

_OLLAMA_HEAVY = ('{"message":{"thinking":"' + "t" * 25_000 + '"},"done":true,'
                 '"done_reason":"stop","eval_count":62912}\n')
_OLLAMA_EMPTY = '{"message":{},"done":true,"done_reason":"stop"}\n'
_OLLAMA_CONTENT = '{"message":{"content":"hello"},"done":true}\n'


def _recording(responses):
    """A handler that serves `responses` in order (repeating the last) and
    records each request's JSON body."""
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return responses[min(len(seen) - 1, len(responses) - 1)]

    handler.seen = seen
    return handler


@pytest.fixture
def _audit():
    collector = AuditCollector("req-p410")
    set_audit_collector(collector)
    yield collector
    set_audit_collector(None)


async def _or(worker_call, **kw):
    return await openrouter_client.chat_loop(
        messages=[{"role": "user", "content": "q"}], model="test/model",
        cancel_event=None, num_ctx=0, tools=kw.pop("tools", []),
        tool_executor=kw.pop("tool_executor", None), worker_call=worker_call, **kw)


# --- the predicate ------------------------------------------------------------

def test_heavy_empty_is_the_instruments_own_threshold():
    assert ec.is_heavy_empty({"completion_tokens": 62912, "reasoning_chars": 98394})
    assert ec.is_heavy_empty({"completion_tokens": 65556})  # the MAX_TOKENS attempt
    assert ec.is_heavy_empty({"completion_tokens": None, "reasoning_chars": 25_000})
    assert not ec.is_heavy_empty({"completion_tokens": 170, "reasoning_chars": 700})
    assert not ec.is_heavy_empty({"completion_tokens": None, "reasoning_chars": 0})
    assert not ec.is_heavy_empty({"completion_tokens": "junk"})  # never raises


def test_only_a_workers_heavy_empty_loses_its_retry():
    heavy, light = {"completion_tokens": 62912}, {"completion_tokens": 170}
    kw = {"attempts_max": 3}
    assert not ec.should_retry_empty(heavy, attempt=0, worker_call=True, **kw)
    assert ec.should_retry_empty(heavy, attempt=0, worker_call=False, **kw)
    assert ec.should_retry_empty(light, attempt=0, worker_call=True, **kw)
    # the last attempt is never retried, as before
    assert not ec.should_retry_empty(light, attempt=2, worker_call=False, **kw)


# --- the payload --------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_worker_call_carries_the_cap_and_no_other_call_does(_no_sleep, _mock_http):
    h = _recording([httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    await _or(True)
    await _or(False)
    assert h.seen[0]["max_tokens"] == ec.WORKER_MAX_OUTPUT_TOKENS == 32_000
    # every other payload is exactly what it was before this row
    assert set(h.seen[1]) == {"model", "messages", "stream", "temperature"}


@pytest.mark.asyncio
async def test_ollama_takes_the_flag_but_not_the_cap(_no_sleep, _mock_http):
    """`num_predict` on an Ollama cloud model's reasoning is unmeasured."""
    h = _recording([httpx.Response(200, text=_OLLAMA_CONTENT)])
    _mock_http(h)
    await ollama_client.chat_loop(
        messages=[{"role": "user", "content": "q"}], model="m", cancel_event=None,
        num_ctx=0, tools=[], tool_executor=None, worker_call=True)
    assert set(h.seen[0]["options"]) == {"num_ctx", "temperature"}


# --- the retry ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_workers_heavy_empty_is_not_retried(_no_sleep, _mock_http, _audit):
    h = _recording([httpx.Response(200, text=_OR_HEAVY),
                    httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = await _or(True)
    assert result["content"] == ""
    assert len(h.seen) == 1 and _no_sleep == []
    (probe,) = _audit.empty_completions
    assert probe["completion_tokens"] == 62912 and probe["retried"] is False


@pytest.mark.asyncio
async def test_the_same_heavy_empty_off_a_worker_is_retried_as_before(
        _no_sleep, _mock_http, _audit):
    h = _recording([httpx.Response(200, text=_OR_HEAVY),
                    httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = await _or(False)
    assert result["content"] == "hello" and len(h.seen) == 2


@pytest.mark.asyncio
# P4.11 reversed the (b) case, a Worker's upstream idle timeout, which is no
# longer retried: see test_idle_timeout.py. (d) is retried there.
@pytest.mark.parametrize("body", [_OR_BARE], ids=["c_bare"])
async def test_a_workers_light_empty_is_still_retried(body, _no_sleep, _mock_http, _audit):
    h = _recording([httpx.Response(200, text=body), httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = await _or(True)
    assert result["content"] == "hello" and len(h.seen) == 2
    assert _audit.empty_completions[0]["retried"] is True


@pytest.mark.asyncio
async def test_ollama_does_not_retry_a_workers_heavy_empty(_no_sleep, _mock_http, _audit):
    h = _recording([httpx.Response(200, text=_OLLAMA_HEAVY),
                    httpx.Response(200, text=_OLLAMA_CONTENT)])
    _mock_http(h)
    result = await ollama_client.chat_loop(
        messages=[{"role": "user", "content": "q"}], model="m", cancel_event=None,
        num_ctx=0, tools=[], tool_executor=None, worker_call=True)
    assert result["content"] == "" and len(h.seen) == 1
    # and a light one still is
    h2 = _recording([httpx.Response(200, text=_OLLAMA_EMPTY),
                     httpx.Response(200, text=_OLLAMA_CONTENT)])
    _mock_http(h2)
    result = await ollama_client.chat_loop(
        messages=[{"role": "user", "content": "q"}], model="m", cancel_event=None,
        num_ctx=0, tools=[], tool_executor=None, worker_call=True)
    assert result["content"] == "hello" and len(h2.seen) == 2


# --- forwarding -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_flag_reaches_every_round_of_the_react_loop(_no_sleep, _mock_http, _audit):
    """The stored (a) calls were all at a worker's third to seventh round."""
    async def executor(name, args):
        return "tool output"

    h = _recording([httpx.Response(200, text=_OR_TOOL_CALL),
                    httpx.Response(200, text=_OR_HEAVY),
                    httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = await _or(True, tool_executor=executor)
    assert [b.get("max_tokens") for b in h.seen] == [32_000, 32_000]
    assert result["content"] == ""  # the round-2 heavy empty was not retried


@pytest.mark.asyncio
async def test_the_flag_reaches_the_step_cap_write_up(_no_sleep, _mock_http):
    h = _recording([httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = await _or(True, max_turns=0)
    assert result["halted"]["written_up"] is True
    assert h.seen[0]["max_tokens"] == 32_000


@pytest.mark.asyncio
async def test_a_capped_call_that_was_still_writing_is_logged(_no_sleep, _mock_http, caplog):
    _mock_http(_recording([httpx.Response(200, text=_OR_CUT)]))
    with caplog.at_level(logging.WARNING, logger="app"):
        result = await _or(True)
    assert result["content"] == "a report that was still going"
    assert any("output cap" in r.getMessage() for r in caplog.records)


# --- who passes it --------------------------------------------------------------

@pytest.fixture
def _worker_cfg():
    set_request_provider_config({
        "_provider": "openrouter", "_chat_mode": "research",
        "_research_mode": "case_law_only", "model": "test-model",
        "_tool_memo_enabled": False,
    })
    yield
    set_request_provider_config({})


def _recording_loop(*contents):
    calls = []

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, **kw):
        calls.append(kw)
        return {"role": "assistant", "content": contents[min(len(calls), len(contents)) - 1]}

    chat_loop.calls = calls
    return chat_loop


def test_the_worker_passes_it_and_its_a4_reformat_does_not(_worker_cfg):
    flat = "An answer with no report structure at all, long enough to be checked."
    fixed = "1. **Summary Answer (BLUF):** Answer.\n2. **References:** None found."
    loop = _recording_loop(flat, fixed)
    asyncio.run(run_worker_agent(loop, lambda *a, **k: None, "q", "test-model", None, 0))
    assert loop.calls[0].get("worker_call") is True
    assert len(loop.calls) == 2 and not loop.calls[1].get("worker_call")


def test_the_manager_does_not_pass_it(_worker_cfg):
    async def worker(*a, **kw):
        return {"content": "1. **Summary Answer (BLUF):** Found.", "sources": []}

    loop = _recording_loop("An answer.")
    asyncio.run(process_user_request(loop, worker, [{"role": "user", "content": "q"}],
                                     "test-model", None, None, 0))
    assert loop.calls and not any(c.get("worker_call") for c in loop.calls)


def test_the_deep_research_synthesis_does_not_pass_it(_worker_cfg):
    loop = _recording_loop("INTEGRATED REPORT.")
    asyncio.run(run_deep_research(loop, _step_worker(set()), _plan(2),
                                  [{"role": "user", "content": "q"}], "test-model",
                                  None, None, 0))
    assert len(loop.calls) == 1 and not loop.calls[0].get("worker_call")


# --- end to end: one attempt, then P4.5's label ---------------------------------

def test_a_workers_heavy_empty_is_labelled_lost_after_one_attempt(
        _worker_cfg, _no_sleep, _mock_http):
    """The whole seam: the real OpenRouter loop under run_worker_agent. Before
    this row the provider was asked three times (~$2.30 and ~18 minutes on
    the stored episodes) before the label; now once."""
    h = _recording([httpx.Response(200, text=_OR_HEAVY),
                    httpx.Response(200, text=_OR_CONTENT)])
    _mock_http(h)
    result = asyncio.run(run_worker_agent(
        openrouter_client.chat_loop, lambda *a, **k: None, "q", "test-model", None, 0))
    assert len(h.seen) == 1 and h.seen[0]["max_tokens"] == 32_000
    assert result["lost"]["reason"] == "empty_completion"
    assert result["content"].startswith(LOST_REPORT_TAG)
