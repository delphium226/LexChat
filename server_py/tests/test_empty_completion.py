"""P4.2 (bucket B13) — a provider completion that carries nothing.

**The defect.** A streaming completion can return 200, emit no content and no
tool-call deltas, and finish normally. `chat_loop` then returned
`{"role": "assistant", "content": ""}` as the answer: `status: ok`, no error,
full billing, and a blank reply on screen. Measured over the ten replay
directories at `docs/prepilot-fixes/evidence/replay/`: **8 billed blank turns in
616**, across six sessions and three chat modes.

**The acceptance this file is.** The ledger row's acceptance is an invariant, not
a session-turn pair — "non-empty body whenever recorded cost > 0" — because the
turn that blanks moves between runs (6370 blanked at pre-pilot turn 8 and at
replay turns 2 and 3; 6383 blanked where four earlier runs produced 6,503-9,190
chars). These tests pin the invariant at each of the three seams that can now
break it, plus the diagnostic that says which of the four mechanisms fired.
`test_replay_tooling.py` asserts the same invariant over the stored run files
(`replay_report blanks`).

`asyncio.sleep` is stubbed throughout, so the retries cost no wall-clock time.
"""
import httpx
import pytest

from src.agent import ollama_client, openrouter_client
from src.utils import empty_completion as ec
from src.utils.audit_trace import AuditCollector, set_audit_collector

from .test_stream_retry import (  # noqa: F401  (fixtures are used by name)
    _mock_http,
    _no_sleep,
    _ollama_chat_loop,
    _or_chat_loop,
    _sequence_handler,
    _sse,
)


# --- bodies ---------------------------------------------------------------------

# A clean 200 that streams nothing at all: no content, no tool calls, finishing
# normally. This is the shape the eight billed blanks had.
_OR_EMPTY = _sse('{"choices":[{"delta":{},"finish_reason":"stop"}]}')
_OR_CONTENT = _sse('{"choices":[{"delta":{"content":"hello"}}]}')
# Reasoning tokens but no content — mechanism (2). Billed, and indistinguishable
# from a lost answer without the counter.
_OR_REASONING_ONLY = _sse(
    '{"choices":[{"delta":{"reasoning":"thinking hard"},"finish_reason":"stop"}]}',
    '{"usage":{"completion_tokens":420,"cost":0.02}}',
)
# A mid-stream failure arriving as an `error` payload the parser used to ignore —
# mechanism (3).
_OR_STREAM_ERROR = _sse(
    '{"error":{"message":"upstream exploded"},'
    '"choices":[{"delta":{},"finish_reason":"error",'
    '"native_finish_reason":"MALFORMED_FUNCTION_CALL"}]}'
)
# Empty content WITH a tool call: legitimate, and must never be retried.
_OR_TOOL_CALL = _sse(
    '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
    '"function":{"name":"search_legislation","arguments":"{}"}}]}}]}'
)
_OR_EMPTY_BILLED = _sse(
    '{"choices":[{"delta":{},"finish_reason":"stop"}]}',
    '{"usage":{"completion_tokens":0,"cost":0.05}}',
)
_OR_CONTENT_BILLED = _sse(
    '{"choices":[{"delta":{"content":"hello"}}]}',
    '{"usage":{"completion_tokens":9,"cost":0.01}}',
)

_OLLAMA_EMPTY = '{"message":{},"done":true,"done_reason":"stop"}\n'
_OLLAMA_CONTENT = '{"message":{"content":"hello"},"done":true}\n'


@pytest.fixture
def _audit():
    collector = AuditCollector("req-p42")
    set_audit_collector(collector)
    yield collector
    set_audit_collector(None)


# --- the predicate --------------------------------------------------------------

def test_empty_means_nothing_to_act_on():
    assert ec.is_empty_completion("", None)
    assert ec.is_empty_completion("", [])
    assert ec.is_empty_completion(None, None)
    # Whitespace reaches the user as a blank reply just the same, and the replay
    # tooling's `_without_footer` grades it that way.
    assert ec.is_empty_completion("   \n\n  ", None)


def test_content_or_tool_calls_is_not_empty():
    assert not ec.is_empty_completion("an answer", None)
    # A tool-call-only assistant message is the normal ReAct shape. Retrying it
    # would re-run the whole turn's research.
    assert not ec.is_empty_completion("", [{"id": "c1"}])
    assert not ec.is_empty_completion("", {0: {"id": "c1"}})


# --- the diagnostic -------------------------------------------------------------

def test_probe_captures_the_four_mechanisms():
    probe = ec.build_probe(
        provider="OpenRouter", model="m", attempt=0, attempts_max=3,
        finish_reason="error", native_finish_reason="MALFORMED_FUNCTION_CALL",
        reasoning_chars=1200, stream_error={"message": "upstream exploded"},
        usage={"completion_tokens": 420, "cost": 0.02}, sent_chars=21421, turn=4,
    )
    assert probe["finish_reason"] == "error"
    assert probe["native_finish_reason"] == "MALFORMED_FUNCTION_CALL"
    assert probe["reasoning_chars"] == 1200
    assert probe["completion_tokens"] == 420
    assert probe["stream_error"] == "upstream exploded"
    assert probe["attempt"] == 1 and probe["attempts_max"] == 3
    assert probe["sent_chars"] == 21421 and probe["react_turn"] == 4


def test_probe_reads_ollamas_field_name_for_output_tokens():
    probe = ec.build_probe(
        provider="Ollama", model="m", attempt=0, attempts_max=3,
        usage={"eval_count": 17},
    )
    assert probe["completion_tokens"] == 17


def test_probe_never_raises_on_junk():
    """Invariant 5: a diagnostic must never fail a research run."""
    probe = ec.build_probe(
        provider="X", model="m", attempt=0, attempts_max=3,
        reasoning_chars="not-a-number", usage="not-a-dict", stream_error=object(),
    )
    assert isinstance(probe, dict) and probe["provider"] == "X"


def test_report_without_a_collector_is_silent():
    set_audit_collector(None)
    ec.report_empty_completion(
        ec.build_probe(provider="X", model="m", attempt=0, attempts_max=3),
        retrying=True,
    )  # must not raise


def test_report_lands_on_the_audit_trace(_audit):
    ec.report_empty_completion(
        ec.build_probe(provider="OpenRouter", model="m", attempt=1, attempts_max=3),
        retrying=False,
    )
    event = _audit.to_event(config={})
    assert len(event["empty_completions"]) == 1
    assert event["empty_completions"][0]["retried"] is False
    assert event["empty_completions"][0]["attempt"] == 2


# --- the retry, OpenRouter ------------------------------------------------------

@pytest.mark.asyncio
async def test_or_retries_an_empty_completion(_no_sleep, _mock_http, _audit):
    """The core fix. A clean 200 carrying nothing raises no exception, so the
    pre-existing guard could not see it and returned the blank as the answer."""
    _mock_http(_sequence_handler([
        httpx.Response(200, text=_OR_EMPTY),
        httpx.Response(200, text=_OR_CONTENT),
    ]))
    result = await _or_chat_loop()
    assert result["content"] == "hello"
    assert _no_sleep == [openrouter_client._STREAM_RETRY_BASE_S]
    # Recorded even though the retry recovered: the rate is the thing to watch.
    assert len(_audit.empty_completions) == 1
    assert _audit.empty_completions[0]["retried"] is True


@pytest.mark.asyncio
async def test_or_empty_backoff_is_exponential(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([
        httpx.Response(200, text=_OR_EMPTY),
        httpx.Response(200, text=_OR_EMPTY),
        httpx.Response(200, text=_OR_CONTENT),
    ]))
    result = await _or_chat_loop()
    assert result["content"] == "hello"
    base = openrouter_client._STREAM_RETRY_BASE_S
    assert _no_sleep == [base, base * 2]


@pytest.mark.asyncio
async def test_or_persistent_empty_returns_empty_and_does_not_raise(
    _no_sleep, _mock_http, _audit
):
    """Fail-soft. Three empty completions is the provider's answer, not a crash —
    the callers above turn it into a labelled fallback, and raising here would
    discard the research they still hold."""
    _mock_http(_sequence_handler([httpx.Response(200, text=_OR_EMPTY)]))
    result = await _or_chat_loop()
    assert result["content"] == ""
    assert len(_no_sleep) == openrouter_client._MAX_STREAM_ATTEMPTS - 1
    assert len(_audit.empty_completions) == openrouter_client._MAX_STREAM_ATTEMPTS
    assert _audit.empty_completions[-1]["retried"] is False


@pytest.mark.asyncio
async def test_or_does_not_retry_a_tool_call_only_message(_no_sleep, _mock_http, _audit):
    """The ReAct loop's normal shape: no content, one tool call. Retrying it
    would re-run the turn's research and double its cost."""
    calls = []

    async def executor(name, args):
        calls.append(name)
        return "tool output"

    _mock_http(_sequence_handler([
        httpx.Response(200, text=_OR_TOOL_CALL),
        httpx.Response(200, text=_OR_CONTENT),
    ]))
    result = await openrouter_client.chat_loop(
        messages=[{"role": "user", "content": "q"}], model="test/model",
        cancel_event=None, num_ctx=0, tools=[], tool_executor=executor,
    )
    assert result["content"] == "hello"
    assert calls == ["search_legislation"]
    assert _no_sleep == []
    assert _audit.empty_completions == []


@pytest.mark.asyncio
async def test_or_content_first_try_is_untouched(_no_sleep, _mock_http, _audit):
    _mock_http(_sequence_handler([httpx.Response(200, text=_OR_CONTENT)]))
    result = await _or_chat_loop()
    assert result["content"] == "hello"
    assert _no_sleep == []
    assert _audit.empty_completions == []


@pytest.mark.asyncio
async def test_or_reasoning_only_completion_is_distinguishable(
    _no_sleep, _mock_http, _audit
):
    """Mechanism (2): the model spent the completion on thinking tokens. Billed,
    zero content — and only `reasoning_chars` separates it from a lost answer."""
    _mock_http(_sequence_handler([
        httpx.Response(200, text=_OR_REASONING_ONLY),
        httpx.Response(200, text=_OR_CONTENT),
    ]))
    result = await _or_chat_loop()
    assert result["content"] == "hello"
    probe = _audit.empty_completions[0]
    assert probe["reasoning_chars"] == len("thinking hard")
    assert probe["completion_tokens"] == 420
    assert probe["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_or_mid_stream_error_payload_is_captured(_no_sleep, _mock_http, _audit):
    """Mechanism (3): OpenRouter reports a mid-stream failure as an `error`
    payload on the SSE stream. Nothing read it, so such a stream ended as an
    ordinary empty completion with `status: ok`."""
    _mock_http(_sequence_handler([
        httpx.Response(200, text=_OR_STREAM_ERROR),
        httpx.Response(200, text=_OR_CONTENT),
    ]))
    await _or_chat_loop()
    probe = _audit.empty_completions[0]
    assert probe["stream_error"] == "upstream exploded"
    assert probe["finish_reason"] == "error"
    assert probe["native_finish_reason"] == "MALFORMED_FUNCTION_CALL"


class _Timings:
    """Just the recorder methods chat_loop calls."""

    def __init__(self):
        self.cost = 0.0
        self.calls = 0

    def record_llm_call(self, ttft_ms, total_ms):
        self.calls += 1

    def record_cost(self, usd):
        self.cost += usd

    def record_react_turn(self, turn):
        pass

    def record_cached_tokens(self, cached, discount):
        pass


@pytest.mark.asyncio
async def test_or_discarded_attempt_is_still_billed(_no_sleep, _mock_http):
    """The abandoned attempt was charged for. Under-reporting it here would hide
    the very spend that makes a blank turn a defect rather than a slow turn."""
    timings = _Timings()
    _mock_http(_sequence_handler([
        httpx.Response(200, text=_OR_EMPTY_BILLED),
        httpx.Response(200, text=_OR_CONTENT_BILLED),
    ]))
    result = await _or_chat_loop(timing_collector=timings)
    assert result["content"] == "hello"
    assert timings.cost == pytest.approx(0.06)  # 0.05 discarded + 0.01 kept


# --- the retry, Ollama ----------------------------------------------------------

@pytest.mark.asyncio
async def test_ollama_retries_an_empty_completion(_no_sleep, _mock_http, _audit):
    _mock_http(_sequence_handler([
        httpx.Response(200, text=_OLLAMA_EMPTY),
        httpx.Response(200, text=_OLLAMA_CONTENT),
    ]))
    result = await _ollama_chat_loop()
    assert result["content"] == "hello"
    assert _no_sleep == [ollama_client._STREAM_RETRY_BASE_S]
    assert _audit.empty_completions[0]["finish_reason"] == "stop"
    assert _audit.empty_completions[0]["provider"] == "Ollama"


@pytest.mark.asyncio
async def test_ollama_persistent_empty_returns_empty(_no_sleep, _mock_http):
    _mock_http(_sequence_handler([httpx.Response(200, text=_OLLAMA_EMPTY)]))
    result = await _ollama_chat_loop()
    assert result["content"] == ""
    assert len(_no_sleep) == ollama_client._MAX_STREAM_ATTEMPTS - 1


@pytest.mark.asyncio
async def test_ollama_content_is_untouched(_no_sleep, _mock_http, _audit):
    _mock_http(_sequence_handler([httpx.Response(200, text=_OLLAMA_CONTENT)]))
    result = await _ollama_chat_loop()
    assert result["content"] == "hello"
    assert _no_sleep == []
    assert _audit.empty_completions == []


# --- the fallbacks --------------------------------------------------------------

def test_fallback_is_labelled_as_a_fallback():
    """Invariant 1. Research the answering step never used is not an answer, and
    must not read like one — the whole complaint in this bucket is that the
    lawyer could not tell a lost answer from a finished one."""
    out = ec.fallback_from_reports(
        [{"title": "Step 1: Commencement",
          "content": "s. 95 was commenced by SSI 2018/2."}],
        kind="synthesis",
    )
    assert "returned no text" in out
    assert "not an integrated answer" in out
    assert "**not** been synthesised" in out
    assert "s. 95 was commenced by SSI 2018/2." in out
    assert "## Step 1: Commencement" in out


def test_manager_fallback_names_its_own_failure():
    out = ec.fallback_from_reports(
        [{"title": "Research step 1", "content": "The Act is in force."}],
        kind="manager",
    )
    assert "returned no text" in out
    assert "not a composed answer" in out
    assert "The Act is in force." in out


def test_fallback_drops_empty_reports_and_falls_through_to_the_notice():
    assert ec.fallback_from_reports([], kind="manager") == ec.LOST_ANSWER_NOTICE
    assert ec.fallback_from_reports(
        [{"title": "t", "content": "   "}], kind="manager"
    ) == ec.LOST_ANSWER_NOTICE
    assert ec.fallback_from_reports(None, kind="synthesis") == ec.LOST_ANSWER_NOTICE


def test_notice_promises_nothing_it_did_not_do():
    """The bare notice is what a lawyer sees when there is nothing to show. It
    must not imply an answer was attempted from memory."""
    assert "from memory" in ec.LOST_ANSWER_NOTICE
    assert "send the question again" in ec.LOST_ANSWER_NOTICE.lower()


def test_fallback_survives_junk_entries():
    out = ec.fallback_from_reports(
        ["not a dict", {"content": "kept"}, {"no_content_key": 1}], kind="manager"
    )
    assert "kept" in out
    assert "## Research output 1" in out


# --- the seams, wired -----------------------------------------------------------

@pytest.fixture
def _request_cfg():
    from src.agent.provider_factory import set_request_provider_config
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False,
    })
    yield
    set_request_provider_config({})


@pytest.mark.asyncio
async def test_deep_research_falls_back_to_the_step_findings(_request_cfg):
    """6383 rep 1 of P2.5's acceptance sweep, pinned. 30 tool calls, 219
    commencement relations and three intact step reports — and a report whose
    body was empty, footered and returned as though it were an answer, because
    nothing between the synthesis call and the return checked it."""
    from src.agent.agent_core import run_deep_research
    from .test_deep_research import (
        APPROVED_PLAN, _make_synthesis_chat_loop, _make_worker_stub,
    )

    worker = _make_worker_stub([
        {"content": "s. 95 was commenced by SSI 2018/2.", "sources": []},
        {"content": "Compensation is assessed under s. 12.", "sources": []},
    ])
    result = await run_deep_research(
        _make_synthesis_chat_loop(content=""), worker, APPROVED_PLAN,
        [{"role": "user", "content": "Explain CPOs"}],
        "test-model", None, None, 0,
    )
    body = result["content"]
    assert result["synthesis_failed"] is True
    # The research survives...
    assert "s. 95 was commenced by SSI 2018/2." in body
    assert "Compensation is assessed under s. 12." in body
    assert "## Step 1: Procedure" in body
    # ...and is labelled as what it is, not passed off as a synthesis.
    assert "not an integrated answer" in body


@pytest.mark.asyncio
async def test_deep_research_with_content_sets_no_failure_flag(_request_cfg):
    from src.agent.agent_core import run_deep_research
    from .test_deep_research import (
        APPROVED_PLAN, _make_synthesis_chat_loop, _make_worker_stub,
    )

    worker = _make_worker_stub([
        {"content": "f1", "sources": []}, {"content": "f2", "sources": []},
    ])
    result = await run_deep_research(
        _make_synthesis_chat_loop(content="Integrated report."), worker,
        APPROVED_PLAN, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert "synthesis_failed" not in result
    assert result["content"].startswith("Integrated report.")


@pytest.mark.asyncio
async def test_manager_falls_back_to_the_worker_report(_request_cfg):
    """Eight of the nine measured blanks are this path: research ran, the final
    Manager completion came back empty, and every strip below the seam is a
    no-op on an empty body — so the lawyer was shown a scope footer with
    nothing above it."""
    from src.agent.agent_core import process_user_request

    async def worker(*a, **kw):
        return {"content": "SSI 2017/114 applies.", "sources": [], "searches": []}

    async def empty_manager(messages, model, cancel_event, num_ctx, tools,
                            tool_executor, on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": ""}

    final = await process_user_request(
        empty_manager, worker, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert final["answer_failed"] is True
    assert "SSI 2017/114 applies." in final["content"]
    assert "not a composed answer" in final["content"]


@pytest.mark.asyncio
async def test_manager_with_no_research_gets_the_bare_notice(_request_cfg):
    """A conversational turn that blanked: nothing was retrieved, so there is
    nothing to show instead. 6374 rep 3 turn 3 is the measured case — 0
    delegations, 0 tools, $0 — and it is the one blank the cost>0 invariant
    deliberately excludes."""
    from src.agent.agent_core import process_user_request

    async def never_called_worker(*a, **kw):  # pragma: no cover
        raise AssertionError("no delegation expected")

    async def empty_manager(messages, model, cancel_event, num_ctx, tools,
                            tool_executor, on_chunk=None, **kw):
        return {"role": "assistant", "content": ""}

    final = await process_user_request(
        empty_manager, never_called_worker, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert final["answer_failed"] is True
    assert final["content"].startswith(ec.LOST_ANSWER_NOTICE[:40])


@pytest.mark.asyncio
async def test_manager_with_content_sets_no_failure_flag(_request_cfg):
    from src.agent.agent_core import process_user_request

    async def worker(*a, **kw):  # pragma: no cover
        raise AssertionError("no delegation expected")

    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        return {"role": "assistant", "content": "Here is what I found."}

    final = await process_user_request(
        manager, worker, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert "answer_failed" not in final
    assert final["content"].startswith("Here is what I found.")
