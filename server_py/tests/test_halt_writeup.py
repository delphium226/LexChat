"""FIX_PLAN P3.8 — the halted worker's lost findings.

Before this, a worker that hit the 20-round step cap discarded everything it
had retrieved: `chat_loop` returned the halt marker as its content and
`halt_worker_report` replaced that with a statement that no findings were
written. 6335's worker had five provisions of the Insolvency Act 1986 in its
context and the lawyer got "could you narrow this down?"; 16 sources reached
the rail behind 6340's empty halted turn.

Now, at the cap, `chat_loop` (both providers) makes ONE more call with NO tools
and the write-up instruction appended, and returns its content with the halt
still attached (`halted.written_up`). Everything P2.1 built is unchanged: the
worker's report carries the agent-addressed header (now saying the findings
are partial), the lawyer's notice is still prepended by code, and
`research_incomplete` still rides on the result.

The chat-loop tests run the REAL loops against a mocked transport (the
harness from `test_stream_retry.py`), because the write-up is a control-flow
change inside them and a stubbed loop would test nothing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx
import pytest

import tools.replay_report as rr
from src.agent import ollama_client, openrouter_client
from src.agent.agent_core import process_user_request, run_deep_research, run_worker_agent
from src.agent.provider_factory import set_request_provider_config
from src.utils.audit_trace import AuditCollector, set_audit_collector
from src.utils.research_halt import (
    halt_marker_text,
    halt_notice,
    halt_worker_report,
    halt_writeup_instruction,
)
from src.utils.search_scope import incomplete_steps_note

HALT = {"reason": "step_cap", "limit": 20, "steps": 20}
RAW = halt_marker_text(20)
# Link-free on purpose: P1.6 (B14) rewrites any provision URL no tool returned,
# and these tests run no tools, so a linked fixture would be altered by a fix
# that is not this row's before it reached the assertion.
FINDINGS = (
    "1. **Summary Answer (BLUF):**\nSection A16(3) of the Insolvency Act 1986 ends a "
    "Part A1 moratorium when the company enters administration under Schedule B1.\n\n"
    "4. **References:**\n* Insolvency Act 1986, s. A16"
)
_TOOLS = [{"type": "function", "function": {
    "name": "search_legislation", "description": "d",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
}}]


@pytest.fixture
def _cfg():
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False,
    })
    yield
    set_request_provider_config({})


# --- harness (the real loops, mocked transport) -----------------------------

def _sse(*chunks: str) -> str:
    return "".join(f"data: {c}\n\n" for c in chunks) + "data: [DONE]\n\n"


def _or_text(text: str) -> str:
    return _sse(json.dumps({"choices": [{"delta": {"content": text}}]}))


def _or_tool_call(name: str, args: dict) -> str:
    return _sse(json.dumps({"choices": [{"delta": {"tool_calls": [{
        "index": 0, "id": "call_1",
        "function": {"name": name, "arguments": json.dumps(args)},
    }]}}]}))


_OR_EMPTY = _sse(json.dumps({"choices": [{"delta": {}}]}))


def _ollama_text(text: str) -> str:
    return json.dumps({"message": {"role": "assistant", "content": text}, "done": True}) + "\n"


def _ollama_tool_call(name: str, args: dict) -> str:
    return json.dumps({"message": {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": name, "arguments": args}},
    ]}, "done": True}) + "\n"


@pytest.fixture
def _no_sleep(monkeypatch):
    delays = []

    async def fake_sleep(d):
        delays.append(d)

    monkeypatch.setattr(openrouter_client.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(ollama_client.asyncio, "sleep", fake_sleep)
    return delays


@pytest.fixture
def _mock_http(monkeypatch):
    """Route both clients through a MockTransport; return the request payloads seen."""
    real = httpx.AsyncClient

    def install(handler):
        seen: list = []

        def wrapped(request):
            try:
                seen.append(json.loads(request.content))
            except Exception:
                seen.append(None)
            return handler(request)

        def factory(*args, **kwargs):
            kwargs.pop("verify", None)
            kwargs.pop("proxy", None)
            return real(transport=httpx.MockTransport(wrapped), **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", factory)
        return seen

    return install


def _sequence_handler(responses):
    state = {"i": 0}

    def handler(request):
        i = min(state["i"], len(responses) - 1)
        state["i"] += 1
        item = responses[i]
        return item(request) if callable(item) else item

    return handler


def _recording_executor():
    calls = []

    async def executor(name, args):
        calls.append(name)
        return '{"results": []}'

    return executor, calls


async def _or_loop(executor, cancel_event=None, max_turns=1):
    return await openrouter_client.chat_loop(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}],
        "test/model", cancel_event, 0, _TOOLS, executor, None, max_turns=max_turns,
    )


async def _ollama_loop(executor, max_turns=1):
    return await ollama_client.chat_loop(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}],
        "test-model", None, 0, _TOOLS, executor, None, max_turns=max_turns,
    )


# --- the write-up round, in the real loops ---------------------------------

@pytest.mark.asyncio
async def test_or_the_cap_makes_one_tool_free_call_and_keeps_the_halt(_mock_http):
    """Round 0 calls a tool; the cap is 1; the loop then makes exactly one
    more request with no tools, the retrievals in front of the instruction,
    and returns what came back — still marked halted."""
    seen = _mock_http(_sequence_handler([
        httpx.Response(200, text=_or_tool_call("search_legislation", {"query": "shop"})),
        httpx.Response(200, text=_or_text(FINDINGS)),
    ]))
    executor, calls = _recording_executor()
    result = await _or_loop(executor)

    assert calls == ["search_legislation"]            # the real tool ran once, in round 0
    assert len(seen) == 2
    first, writeup = seen
    assert first.get("tools")                          # round 0 had the tool schemas
    assert "tools" not in writeup                      # the write-up round has none
    assert "tool_choice" not in writeup
    last = writeup["messages"][-1]
    assert last["role"] == "user"
    assert last["content"] == halt_writeup_instruction(1)
    assert any(m.get("role") == "tool" for m in writeup["messages"])   # retrievals kept
    assert result["content"] == FINDINGS
    assert result["halted"] == {"reason": "step_cap", "limit": 1, "steps": 1, "written_up": True}


@pytest.mark.asyncio
async def test_ollama_the_cap_makes_one_tool_free_call_and_keeps_the_halt(_mock_http):
    seen = _mock_http(_sequence_handler([
        httpx.Response(200, text=_ollama_tool_call("search_legislation", {"query": "shop"})),
        httpx.Response(200, text=_ollama_text(FINDINGS)),
    ]))
    executor, calls = _recording_executor()
    result = await _ollama_loop(executor)

    assert calls == ["search_legislation"]
    assert len(seen) == 2
    first, writeup = seen
    assert first["tools"] == _TOOLS
    assert writeup["tools"] == []
    assert writeup["messages"][-1] == {"role": "user", "content": halt_writeup_instruction(1)}
    assert result["content"] == FINDINGS
    assert result["halted"] == {"reason": "step_cap", "limit": 1, "steps": 1, "written_up": True}


@pytest.mark.asyncio
async def test_or_the_write_up_never_writes_up_its_own_halt(_mock_http):
    """A model that calls a tool in the tool-free round gets one dead round
    and then the plain halt — never a second write-up, never the real tool."""
    seen = _mock_http(_sequence_handler([
        httpx.Response(200, text=_or_tool_call("search_legislation", {"query": "shop"})),
    ]))  # every request answers with a tool call, the write-up included
    executor, calls = _recording_executor()
    result = await _or_loop(executor)

    assert calls == ["search_legislation"]            # the real executor ran ONCE
    assert len(seen) == 2                              # round 0 + the write-up; nothing after
    assert result["content"] == halt_marker_text(1)
    assert result["halted"] == {"reason": "step_cap", "limit": 1, "steps": 1, "written_up": False}


@pytest.mark.asyncio
async def test_ollama_the_write_up_never_writes_up_its_own_halt(_mock_http):
    seen = _mock_http(_sequence_handler([
        httpx.Response(200, text=_ollama_tool_call("search_legislation", {"query": "shop"})),
    ]))
    executor, calls = _recording_executor()
    result = await _ollama_loop(executor)

    assert calls == ["search_legislation"]
    assert len(seen) == 2
    assert result["content"] == halt_marker_text(1)
    assert result["halted"]["written_up"] is False


@pytest.mark.asyncio
async def test_or_an_empty_write_up_falls_back_to_the_plain_halt(_mock_http, _no_sleep):
    """P4.2's empty-completion retry runs inside the write-up call too; if the
    provider returns nothing three times, the halt is exactly what it was."""
    seen = _mock_http(_sequence_handler([
        httpx.Response(200, text=_or_tool_call("search_legislation", {"query": "shop"})),
        httpx.Response(200, text=_OR_EMPTY),
    ]))
    executor, _ = _recording_executor()
    result = await _or_loop(executor)

    assert len(seen) == 1 + openrouter_client._MAX_STREAM_ATTEMPTS
    assert result["content"] == halt_marker_text(1)
    assert result["halted"]["written_up"] is False


@pytest.mark.asyncio
async def test_or_a_failed_write_up_call_falls_back_to_the_plain_halt(_mock_http):
    """Fail-soft: an HTTP error on the extra call must not turn a halt into an
    exception — the worker had a valid (if empty) outcome before this existed."""
    seen = _mock_http(_sequence_handler([
        httpx.Response(200, text=_or_tool_call("search_legislation", {"query": "shop"})),
        httpx.Response(500, text="upstream error"),
    ]))
    executor, _ = _recording_executor()
    result = await _or_loop(executor)

    assert len(seen) == 2
    assert result["content"] == halt_marker_text(1)
    assert result["halted"]["written_up"] is False


@pytest.mark.asyncio
async def test_or_a_cancel_during_the_write_up_still_propagates(_mock_http):
    """A user abort is a BaseException and the fail-soft catch must not eat it."""
    cancel = asyncio.Event()

    def cancel_then_answer(request):
        cancel.set()
        return httpx.Response(200, text=_or_text(FINDINGS))

    _mock_http(_sequence_handler([
        httpx.Response(200, text=_or_tool_call("search_legislation", {"query": "shop"})),
        cancel_then_answer,
    ]))
    executor, _ = _recording_executor()
    with pytest.raises(asyncio.CancelledError):
        await _or_loop(executor, cancel_event=cancel)


@pytest.mark.asyncio
async def test_or_a_marker_echoed_in_the_write_up_is_stripped(_mock_http):
    seen = _mock_http(_sequence_handler([
        httpx.Response(200, text=_or_tool_call("search_legislation", {"query": "shop"})),
        httpx.Response(200, text=_or_text(f"{FINDINGS}\n\n{halt_marker_text(1)}")),
    ]))
    executor, _ = _recording_executor()
    result = await _or_loop(executor)
    assert len(seen) == 2
    assert result["content"] == FINDINGS
    assert result["halted"]["written_up"] is True


@pytest.mark.asyncio
async def test_a_loop_that_never_hits_the_cap_makes_no_extra_call(_mock_http):
    """Silence: the write-up exists only at the cap."""
    seen = _mock_http(_sequence_handler([httpx.Response(200, text=_or_text("done"))]))
    executor, calls = _recording_executor()
    result = await _or_loop(executor, max_turns=20)
    assert len(seen) == 1 and calls == []
    assert result["content"] == "done" and "halted" not in result


# --- the instruction and the header -----------------------------------------

def test_the_instruction_says_no_tools_and_names_the_stop_correctly():
    text = halt_writeup_instruction(20)
    assert "20 tool-call rounds" in text
    assert "No further tool call" in text
    assert "Do not call any tool" in text
    assert "not retrieved because this step's limit was reached" in text
    for bad in ("no relevant records", "no results were found", "synthesize your answer"):
        assert bad not in text.lower()            # not the parliamentary stop's bare negative


@pytest.mark.parametrize("text", [
    halt_writeup_instruction(20),
    halt_worker_report({**HALT, "written_up": True}, 5, writeup="findings"),
    halt_worker_report({**HALT, "written_up": True}, 0, writeup="findings"),
])
def test_the_new_text_names_no_timeout_and_carries_no_raw_marker(text):
    """Both are agent-facing, so only the two detectors a model echo could
    turn into a lawyer-facing falsehood are asserted: 6340's "timed out", and
    the raw marker. (`NEG_ASSERTED` matches P2.1's own "could not be found"
    prohibition and always has; the header never reaches a lawyer.)"""
    assert not rr.HALT_AS_TIMEOUT.search(text), text
    assert not rr.HALT_LITERAL.search(text), text


def test_the_worker_report_without_a_write_up_is_what_p21_shipped():
    assert halt_worker_report(HALT, 3) == halt_worker_report(HALT, 3, writeup="")
    assert "no findings were written from them" in halt_worker_report(HALT, 3)
    assert "PARTIAL" not in halt_worker_report(HALT, 3)


def test_the_worker_report_with_a_write_up_keeps_the_findings_under_the_header():
    report = halt_worker_report({**HALT, "written_up": True}, 5, writeup=FINDINGS)
    assert report.startswith("[Research Incomplete — step limit reached; PARTIAL findings below]")
    assert "5 source(s) had been retrieved when it stopped" in report
    assert "They are PARTIAL" in report
    assert "NOT a timeout" in report and "NOT evidence that the material does not exist" in report
    assert "Do NOT call delegate_research again" in report
    assert report.endswith(FINDINGS)
    assert report.index("PARTIAL FINDINGS") < report.index(FINDINGS)


def test_the_lawyer_notice_is_unchanged_by_a_write_up():
    """The lawyer-facing disclosure was validated at P2.1 and is not this row's
    to reword: a written-up halt reads the same notice."""
    assert halt_notice([{**HALT, "written_up": True, "scope": "delegation"}]) == \
        halt_notice([{**HALT, "written_up": False, "scope": "delegation"}])


# --- the worker seam ----------------------------------------------------------

def _loop_returning(content, written_up=True):
    state = {"calls": 0}

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        state["calls"] += 1
        return {"role": "assistant", "content": content,
                "halted": {**HALT, "written_up": written_up}}

    chat_loop.state = state
    return chat_loop


@pytest.mark.asyncio
async def test_a_written_up_halt_keeps_its_findings_under_the_header(_cfg):
    loop = _loop_returning(FINDINGS)
    result = await run_worker_agent(loop, lambda *a, **k: None, "q", "test-model", None, 0)
    assert result["halted"] == {**HALT, "written_up": True}
    assert result["content"].startswith("[Research Incomplete — step limit reached; PARTIAL")
    assert FINDINGS in result["content"]
    assert "no findings were written" not in result["content"]
    assert loop.state["calls"] == 1                    # no A4 reformat call (P2.6)


@pytest.mark.asyncio
async def test_a_halt_that_was_not_written_up_reads_as_before(_cfg):
    result = await run_worker_agent(
        _loop_returning(RAW, written_up=False), lambda *a, **k: None, "q", "test-model", None, 0,
    )
    assert result["halted"] == {**HALT, "written_up": False}
    assert "No sources had been retrieved when it stopped." in result["content"]
    assert "[Research halted" not in result["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "   ", RAW, f"\n{RAW}\n"])
async def test_a_blank_or_marker_only_write_up_counts_as_not_written_up(_cfg, content):
    """`written_up` is what the worker VERIFIED, not what the loop claimed."""
    result = await run_worker_agent(
        _loop_returning(content, written_up=True), lambda *a, **k: None, "q", "test-model", None, 0,
    )
    assert result["halted"]["written_up"] is False
    assert "No sources had been retrieved when it stopped." in result["content"]
    assert "PARTIAL" not in result["content"]


@pytest.mark.asyncio
async def test_the_trace_carries_written_up(_cfg):
    """Audit schema v4."""
    audit = AuditCollector("req1")
    set_audit_collector(audit)
    try:
        await run_worker_agent(
            _loop_returning(FINDINGS), lambda *a, **k: None, "q", "test-model", None, 0,
        )
    finally:
        set_audit_collector(None)
    dg = audit.delegations[0]
    assert dg["halted"] == {**HALT, "written_up": True}
    assert FINDINGS in dg["report"]


# --- the two routes to the lawyer ----------------------------------------------

@pytest.mark.asyncio
async def test_the_manager_route_carries_the_findings_and_still_discloses(_cfg):
    seen = {}
    halt = {**HALT, "written_up": True}

    async def written_up_worker(*a, **kw):
        return {"content": halt_worker_report(halt, 5, writeup=FINDINGS),
                "sources": [], "halted": dict(halt)}

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        seen["tool_result"] = await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": f"Here is what I found.\n\n{FINDINGS}"}

    final = await process_user_request(
        manager, written_up_worker, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert "PARTIAL findings below" in seen["tool_result"]
    assert FINDINGS in seen["tool_result"]
    assert final["research_incomplete"]["halts"][0]["written_up"] is True
    assert "This answer is incomplete" in final["content"]     # P2.1's notice, unchanged
    assert FINDINGS in final["content"]
    assert "[Research halted" not in final["content"]


def _plan(n):
    return {"scope_note": "scope",
            "steps": [{"id": i, "title": f"Step {i} title", "detail": "d"}
                      for i in range(1, n + 1)]}


@pytest.mark.asyncio
async def test_a_written_up_step_reaches_the_synthesis_as_partial_findings(_cfg):
    payload = {}

    async def synthesis(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk, emit_tool_details=False, timing_collector=None):
        payload["user"] = messages[1]["content"]
        return {"content": "INTEGRATED REPORT."}

    halt = {**HALT, "written_up": True}

    async def worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        if "Step 2" in query:
            return {"content": halt_worker_report(halt, 5, writeup=FINDINGS),
                    "sources": [], "halted": dict(halt)}
        return {"content": "findings", "sources": []}

    final = await run_deep_research(
        synthesis, worker, _plan(3), [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert FINDINGS in payload["user"]                          # the step's findings arrived
    assert "are PARTIAL" in payload["user"]                      # and were called partial
    assert "are missing because the work stopped" not in payload["user"]
    assert final["research_incomplete"]["halts"][0]["written_up"] is True
    assert "step 2 (Step 2 title)" in final["content"]


def test_the_synthesis_note_says_partial_only_when_a_step_wrote_up():
    plain = incomplete_steps_note([{"step": 2, "scope": "step", **HALT}], 3)
    wrote = incomplete_steps_note([{"step": 2, "scope": "step", **HALT, "written_up": True}], 3)
    assert "are missing because the work stopped" in plain and "PARTIAL" not in plain
    assert "are PARTIAL" in wrote and "are missing because the work stopped" not in wrote
    for note in (plain, wrote):
        assert "NOT because the material was searched for and not found" in note
        assert "MUST NOT write" in note


# --- the instruments ----------------------------------------------------------

def test_the_seam_tool_replays_a_halted_delegation_with_the_products_instruction():
    """`seam_replay worker` on a halted fixture IS the write-up round, for the
    price of one call: its closing message must be the product's own
    instruction, and `--without-fix` must keep the generic line for the A/B."""
    from tools.seam_replay import worker_messages

    doc = {"session_id": "6335", "filters": {"research_mode": "legislation_only"}}
    dg = {"brief": "b", "halted": dict(HALT), "tools": [
        {"name": "search_legislation", "args": {"query": "q"}, "final_result": "{}"},
    ]}
    turn = {"turn": 7, "chat_mode": "research", "audit": {"delegations": [dg]}}
    fixed = worker_messages(doc, turn)
    assert fixed[-1] == {"role": "user", "content": halt_writeup_instruction(20)}
    generic = worker_messages(doc, turn, without_fix=True)
    assert generic[-1]["content"] == "Compose your report now from the results above."
    dg["halted"] = None                                   # a completed delegation
    assert worker_messages(doc, turn)[-1]["content"] == generic[-1]["content"]


def test_halts_prints_the_written_up_count(tmp_path: Path, capsys):
    """`replay_report halts` is P2.1's grader; it now also counts the write-ups."""
    run = {
        "session_id": "6335", "rep": 1,
        "turns": [{
            "turn": 7,
            "answer": halt_notice([{**HALT, "scope": "delegation"}]) + "\n\n" + FINDINGS,
            "timing": {"max_turns_halted": 1},
            "audit": {"delegations": [
                {"halted": {**HALT, "written_up": True}, "report": "r", "tools": []},
                {"halted": {**HALT, "written_up": False}, "report": "r", "tools": []},
            ]},
        }],
    }
    (tmp_path / "6335_rep1.json").write_text(json.dumps(run), encoding="utf-8")
    rc = rr.cmd_halts(argparse.Namespace(dir=str(tmp_path), answers=False, chars=0))
    out = capsys.readouterr().out
    assert rc == 0
    assert "1/2" in out
    assert "2 halted worker run(s); 1 wrote up partial findings" in out
