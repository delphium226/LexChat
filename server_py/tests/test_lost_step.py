"""P4.5 — a worker whose final reply is lost must be reported as lost.

`chat_loop` retries an empty completion (P4.2) and, when every attempt comes
back empty, returns `content: ""` with no flag. Before this row the Manager or
the Deep Research synthesis then received the scope block alone ("Searched the
legislation index 2 time(s) for: ..."), which reads as a search that found
nothing (6409 r3 t11, 6373 r1 t3), or "" for a case-law step, which one
synthesis reported to a lawyer as "Step 1 found no results" (6375 r3 t2).

The acceptance is deterministic (FIX_PLAN P4.5, booked in 637a882): a test at
each seam — the worker in research and conversational mode, the Manager path
(the P4.2 fallback exclusion and the redone rule), the Deep Research note,
both lawyer notices, the progress events and the audit field.

Measured over 49 replay directories (`replay_report lost --all-dirs`): 16
unrecovered calls in 929 schema-v3 turns; 11 landed in a research worker and 2
in a Deep Research step. After 15 of 18 lost worker reports the Manager
re-delegated and a later worker returned findings, which is why the label does
not forbid re-delegation and the Manager-path notice is kept for a lost step
nothing made good.
"""

import json
import sys
from pathlib import Path

import pytest

from src.agent.agent_core import (
    build_synthesis_messages,
    process_user_request,
    run_deep_research,
    run_worker_agent,
)
from src.agent.provider_factory import set_request_provider_config
from src.utils.audit_trace import AuditCollector, set_audit_collector
from src.utils.empty_completion import LOST_ANSWER_NOTICE
from src.utils.research_halt import (
    LOST_REPORT_TAG,
    apply_lost_disclosure,
    halt_marker_text,
    halt_worker_report,
    lost_notice,
    lost_worker_report,
    progress_result,
    strip_lost_blocks,
)
from src.utils.search_scope import incomplete_steps_note

HALT = {"reason": "step_cap", "limit": 20, "steps": 20}
LOST = {"reason": "empty_completion", "sources_retrieved": 0}
SCOPE_OPEN = "[SEARCH SCOPE"


@pytest.fixture(autouse=True)
def _cfg():
    set_request_provider_config({
        "_provider": "openrouter", "_chat_mode": "research",
        "_research_mode": "legislation_only", "model": "test-model",
        "_tool_memo_enabled": False,
    })
    yield
    set_request_provider_config({})
    set_audit_collector(None)


def _set_cfg(**kw):
    set_request_provider_config({
        "_provider": "openrouter", "_chat_mode": "research",
        "_research_mode": "legislation_only", "model": "test-model",
        "_tool_memo_enabled": False, **kw,
    })


async def _noop_summarise(*a, **kw):
    return ""


def _worker_loop(tool_calls, final_content, calls=None):
    """A worker chat_loop that runs `tool_calls`, then returns `final_content`
    (what `chat_loop` returns after three empty attempts is "")."""
    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        if calls is not None:
            calls.append(tools)
        for name, args in tool_calls:
            await executor(name, args)
        return {"role": "assistant", "content": final_content}
    return chat_loop


@pytest.fixture
def _fake_tools(monkeypatch):
    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return json.dumps({"results": []})
    monkeypatch.setattr("src.agent.agent_shared.execute_worker_tool", fake_execute)


# ---------------------------------------------------------------------------
# The wording
# ---------------------------------------------------------------------------

def test_the_report_says_the_answer_was_lost_and_is_not_a_negative():
    r = lost_worker_report(3)
    assert r.startswith(LOST_REPORT_TAG)
    assert "came back empty on every attempt" in r
    assert "NOT evidence that the material does not exist" in r
    assert "record of work, not findings" in r
    assert "3 source(s)" in r
    assert "No sources had been retrieved" in lost_worker_report(0)


def test_the_report_does_not_borrow_the_halts_false_cause():
    """Invariant 1: the disclosure must be TRUE. `halt_notice` names a limit
    of 20 tool-call rounds; no limit was reached here. And 6409's failed
    attempts ended "Upstream idle timeout exceeded", so the report must not
    deny a timeout either."""
    for text in (lost_worker_report(2), lost_notice([LOST]),
                 incomplete_steps_note([], 3, [{**LOST, "step": 1}])):
        assert "tool-call rounds" not in text
        assert "timeout" not in text.lower() and "timed out" not in text.lower()


def test_the_report_permits_one_more_delegation_where_the_halt_forbids_it():
    """After 15 of 18 stored lost worker reports the Manager re-delegated and
    the later worker returned findings. The halt's "Do NOT call
    delegate_research again" would forbid the recovery that works."""
    assert "Do NOT call delegate_research again" in halt_worker_report(HALT)
    r = lost_worker_report(0)
    assert "Do NOT call delegate_research" not in r
    assert "may call it once more" in r


def test_the_block_is_stripped_whole_and_so_is_a_stray_marker():
    r = lost_worker_report(1)
    out, n = strip_lost_blocks("Intro.\n\n" + r + "\n\nOutro.")
    assert n == 1 and out == "Intro.\n\nOutro."
    out, n = strip_lost_blocks(f"{LOST_REPORT_TAG} Answer.")
    assert n == 1 and LOST_REPORT_TAG not in out


def test_the_notice_names_plan_steps_and_agrees_in_number():
    one = lost_notice([{**LOST, "step": 1, "title": "Common law"}])
    assert one.startswith("> **⚠ This answer is incomplete.**")
    assert "Research step 1 (Common law) did not return its findings" in one
    assert "not** the step limit" in one
    assert "not** a finding that the material does not exist" in one
    two = lost_notice([{**LOST, "step": 3, "title": "B"}, {**LOST, "step": 1, "title": "A"}])
    assert "step 1 (A) and step 3 (B) did not return their findings" in two
    assert "One research step did not return its findings" in lost_notice([LOST])


def test_the_notice_says_when_no_research_stands_behind_the_answer():
    assert "Treat the coverage below as partial" in lost_notice([LOST], True)
    assert "No completed research stands behind" in lost_notice([LOST], False)


def test_the_disclosure_is_prepended_idempotent_and_silent_when_nothing_was_lost():
    once, disclosed = apply_lost_disclosure("Body.", [LOST])
    assert disclosed and once.startswith("> **⚠") and once.endswith("Body.")
    assert apply_lost_disclosure(once, [LOST])[0] == once
    assert apply_lost_disclosure("Body.", []) == ("Body.", False)


def test_the_progress_result_names_the_outcome():
    assert progress_result({}, step=True) == "Step complete"
    assert progress_result({}, step=False) == "Research Complete"
    assert progress_result({"lost": LOST}, step=True) == "Step incomplete: no reply returned"
    assert progress_result({"lost": LOST}, step=False) == "Research incomplete: no reply returned"
    assert progress_result({"halted": {**HALT, "written_up": False}}, step=True) == \
        "Step incomplete: stopped at the step limit"
    assert progress_result({"halted": {**HALT, "written_up": True}}, step=False) == \
        "Research incomplete: stopped at the step limit (partial findings)"


def test_the_synthesis_note_names_a_lost_step_in_its_own_words():
    note = incomplete_steps_note([], 3, [{**LOST, "step": 1, "title": "Case law"}])
    assert "LOST STEPS" in note
    assert "step 1 (Case law) did not return findings (1 of 3 steps)" in note
    assert "NOT because the material was searched for and not found" in note
    assert "MUST NOT write" in note
    assert "INCOMPLETE STEPS" not in note  # the halt's paragraph is not used
    assert incomplete_steps_note([], 3, []) == ""
    assert incomplete_steps_note([], 3) == ""


# ---------------------------------------------------------------------------
# The worker seam
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_lost_worker_is_labelled_ahead_of_its_scope_block(_fake_tools):
    """6409 r3 t11's shape: two searches ran, the reply was lost, and the
    report was the scope block alone."""
    calls = []
    result = await run_worker_agent(
        _worker_loop([("search_legislation", {"query": "a"})], "", calls),
        _noop_summarise, "brief", "test-model", None, 0,
    )
    content = result["content"]
    assert result["lost"] == {"reason": "empty_completion", "sources_retrieved": 0}
    assert not result.get("halted")
    assert content.startswith(LOST_REPORT_TAG)
    assert SCOPE_OPEN in content
    assert content.index(LOST_REPORT_TAG) < content.index(SCOPE_OPEN)
    assert len(calls) == 1  # no A4 reformat call on a lost report


@pytest.mark.asyncio
async def test_a_lost_case_law_step_is_labelled_not_empty():
    """6375 r3 t2: a case-law step has no scope block, so the report was ""."""
    _set_cfg(_research_mode="case_law_only")
    result = await run_worker_agent(
        _worker_loop([], ""), _noop_summarise, "brief", "test-model", None, 0,
    )
    assert result["content"] == lost_worker_report(0)


@pytest.mark.asyncio
async def test_the_conversational_quick_lookup_worker_is_labelled_too(_fake_tools):
    """wave3_p313 rep 2 t1: handed a scope block alone, the conversational
    Manager wrote a research-report heading into its answer."""
    _set_cfg(_chat_mode="conversational")
    result = await run_worker_agent(
        _worker_loop([("search_legislation", {"query": "a"})], "  \n "),
        _noop_summarise, "brief", "test-model", None, 0,
    )
    assert result["lost"]["reason"] == "empty_completion"
    assert result["content"].startswith(LOST_REPORT_TAG)


@pytest.mark.asyncio
async def test_a_worker_that_answered_is_untouched(_fake_tools):
    result = await run_worker_agent(
        _worker_loop([("search_legislation", {"query": "a"})],
                     "1. **Summary Answer (BLUF):** An answer.\n2. **References:** None found."),
        _noop_summarise, "brief", "test-model", None, 0,
    )
    assert "lost" not in result
    assert LOST_REPORT_TAG not in result["content"]


@pytest.mark.asyncio
async def test_a_halt_stays_a_halt():
    async def chat_loop(*a, **kw):
        return {"role": "assistant", "content": halt_marker_text(20), "halted": dict(HALT)}
    result = await run_worker_agent(chat_loop, _noop_summarise, "q", "test-model", None, 0)
    assert result["halted"] and "lost" not in result
    assert LOST_REPORT_TAG not in result["content"]


@pytest.mark.asyncio
async def test_the_trace_carries_lost_as_a_field(_fake_tools):
    audit = AuditCollector("req1")
    set_audit_collector(audit)
    await run_worker_agent(
        _worker_loop([("search_legislation", {"query": "a"})], ""),
        _noop_summarise, "brief", "test-model", None, 0,
    )
    dg = audit.delegations[0]
    assert dg["lost"] == {"reason": "empty_completion", "sources_retrieved": 0}
    assert dg["halted"] is None
    assert dg["report"].startswith(LOST_REPORT_TAG)


# ---------------------------------------------------------------------------
# The Manager path
# ---------------------------------------------------------------------------

def _worker_seq(outcomes):
    """A run_worker_agent stand-in returning one outcome per call."""
    state = {"i": 0}

    async def worker(*a, **kw):
        kind = outcomes[state["i"]]
        state["i"] += 1
        if kind == "lost":
            return {"content": lost_worker_report(0), "sources": [], "lost": dict(LOST)}
        if kind == "halted":
            return {"content": halt_worker_report(HALT), "sources": [],
                    "halted": {**HALT, "written_up": False}}
        return {"content": "1. **Summary Answer (BLUF):** Found it.", "sources": []}
    return worker


def _manager(n_delegations, answer, seen=None):
    async def manager(messages, model, cancel_event, num_ctx, tools, executor,
                      on_chunk=None, **kw):
        for _ in range(n_delegations):
            out = await executor("delegate_research", {"query": "q"})
            if seen is not None:
                seen.append(out)
        return {"role": "assistant", "content": answer}
    return manager


@pytest.mark.asyncio
async def test_the_manager_is_told_the_answer_was_lost_not_that_nothing_was_found():
    seen = []
    await process_user_request(
        _manager(1, "No provision was found.", seen), _worker_seq(["lost"]),
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert seen[0].startswith("[Research Agent Result]\n" + LOST_REPORT_TAG)


@pytest.mark.asyncio
async def test_a_lost_step_nothing_made_good_is_disclosed_to_the_lawyer():
    """6373 r1 t3's shape: one delegation, lost, no re-delegation. The
    Manager restated a negative; the code tells the lawyer the truth."""
    final = await process_user_request(
        _manager(1, "No provision was found."), _worker_seq(["lost"]),
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert final["content"].startswith("> **⚠ This answer is incomplete.**")
    assert "One research step did not return its findings" in final["content"]
    assert "No completed research stands behind" in final["content"]
    assert final["research_lost"]["disclosed"] is True
    assert final["research_lost"]["not_made_good"] == 1
    assert final["research_lost"]["lost"][0]["scope"] == "delegation"


@pytest.mark.asyncio
async def test_a_lost_step_the_manager_redid_gets_no_notice():
    """6409 r3 t11's shape: lost, then re-delegated, then findings. The answer
    rests on completed research like any other, so no notice; the trace and
    the result still record the loss."""
    final = await process_user_request(
        _manager(2, "Here is the answer."), _worker_seq(["lost", "complete"]),
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert "This answer is incomplete" not in final["content"]
    assert final["research_lost"]["not_made_good"] == 0
    assert final["research_lost"]["disclosed"] is False


@pytest.mark.asyncio
async def test_a_completed_step_before_the_lost_one_does_not_make_it_good():
    final = await process_user_request(
        _manager(2, "Partial answer."), _worker_seq(["complete", "lost"]),
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert "One research step did not return its findings" in final["content"]
    assert "Treat the coverage below as partial" in final["content"]


@pytest.mark.asyncio
async def test_a_manager_that_copies_the_block_never_shows_it():
    final = await process_user_request(
        _manager(1, lost_worker_report(0) + "\n\nMy answer."), _worker_seq(["lost"]),
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert LOST_REPORT_TAG not in final["content"]
    assert "REQUIRED" not in final["content"]
    assert "My answer." in final["content"]


@pytest.mark.asyncio
async def test_p42s_fallback_does_not_reproduce_a_lost_report():
    """The Manager's own completion lost too (wave2_p24_final/6385 r2 t3 had
    both). P4.2's fallback reproduces worker reports; a lost report is a label
    addressed to an agent, not findings, so the fallback is the bare notice."""
    final = await process_user_request(
        _manager(1, ""), _worker_seq(["lost"]),
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert LOST_ANSWER_NOTICE in final["content"]
    assert LOST_REPORT_TAG not in final["content"]
    assert "One research step did not return its findings" in final["content"]


@pytest.mark.asyncio
async def test_the_managers_progress_event_names_each_outcome():
    events = []
    await process_user_request(
        _manager(3, "Answer."), _worker_seq(["lost", "halted", "complete"]),
        [{"role": "user", "content": "q"}], "test-model", events.append, None, 0,
    )
    ends = [e["result"] for e in events if e.get("type") == "tool_end"]
    assert ends == ["Research incomplete: no reply returned",
                    "Research incomplete: stopped at the step limit",
                    "Research Complete"]


# ---------------------------------------------------------------------------
# Deep Research
# ---------------------------------------------------------------------------

def _plan(n):
    return {"scope_note": "scope",
            "steps": [{"id": i, "title": f"Step {i} title", "detail": "d"}
                      for i in range(1, n + 1)]}


def _step_worker(lost_steps):
    async def worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        n = int(query.split("RESEARCH TASK: Step ")[1].split(" ")[0])
        if n in lost_steps:
            return {"content": lost_worker_report(0), "sources": [], "lost": dict(LOST)}
        return {"content": f"findings of step {n}", "sources": []}
    return worker


def _synthesis(capture, content="INTEGRATED REPORT."):
    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk, emit_tool_details=False, timing_collector=None):
        capture.append(messages)
        return {"content": content}
    return chat_loop


@pytest.mark.asyncio
async def test_a_lost_plan_step_reaches_the_synthesis_note_and_the_lawyer():
    """6375 r3 t2: step 1 lost, and the synthesis said "Step 1 found no
    results". It is now handed a named lost step, and the lawyer is told."""
    seen, events = [], []
    final = await run_deep_research(
        _synthesis(seen), _step_worker({1}), _plan(3),
        [{"role": "user", "content": "q"}], "test-model", events.append, None, 0,
    )
    payload = seen[0][1]["content"]
    assert "LOST STEPS" in payload
    assert "step 1 (Step 1 title) did not return findings (1 of 3 steps)" in payload
    assert LOST_REPORT_TAG in payload  # the step's own findings block says so
    assert final["content"].startswith("> **⚠ This answer is incomplete.**")
    assert "Research step 1 (Step 1 title) did not return its findings" in final["content"]
    assert "INTEGRATED REPORT." in final["content"]
    assert final["research_lost"]["steps_total"] == 3
    assert final["research_lost"]["lost"][0]["step"] == 1
    ends = [e["result"] for e in events if e.get("type") == "tool_end"]
    assert ends == ["Step incomplete: no reply returned", "Step complete", "Step complete"]


@pytest.mark.asyncio
async def test_a_synthesis_that_copies_the_block_never_shows_it():
    seen = []
    final = await run_deep_research(
        _synthesis(seen, lost_worker_report(0) + "\n\nREPORT."), _step_worker({2}),
        _plan(2), [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert LOST_REPORT_TAG not in final["content"]
    assert "REPORT." in final["content"]


@pytest.mark.asyncio
async def test_the_synthesis_fallback_does_not_reproduce_a_lost_step():
    seen = []
    final = await run_deep_research(
        _synthesis(seen, ""), _step_worker({1}), _plan(2),
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert LOST_REPORT_TAG not in final["content"]
    assert "findings of step 2" in final["content"]
    assert "Research step 1 (Step 1 title) did not return its findings" in final["content"]


@pytest.mark.asyncio
async def test_a_plan_with_no_lost_step_is_untouched():
    seen = []
    final = await run_deep_research(
        _synthesis(seen), _step_worker(set()), _plan(2),
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert "research_lost" not in final
    assert "LOST STEPS" not in seen[0][1]["content"]
    assert "incomplete" not in final["content"]


def test_the_synthesis_builder_takes_lost_as_an_optional_argument():
    """Additive: a caller that passes no `lost` (the seam tool at an older
    revision, say) builds exactly what it built before."""
    findings = [{"title": "A", "detail": "d", "content": "x"}]
    before = build_synthesis_messages("q", {"scope_note": ""}, findings, [], 1)
    assert "LOST STEPS" not in before[1]["content"]
    after = build_synthesis_messages("q", {"scope_note": ""}, findings, [], 1,
                                     lost=[{**LOST, "step": 1, "title": "A"}])
    assert after[1]["content"].startswith(before[1]["content"])
    assert "LOST STEPS" in after[1]["content"]


# ---------------------------------------------------------------------------
# The replay instrument agrees with the product
# ---------------------------------------------------------------------------

def test_the_instrument_reads_the_products_label():
    """`replay_report lost --require-label` passes on the builder's own output
    (the other half of the acceptance: it exits 1 on the stored directories)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import replay_report as rr

    assert rr._lost_report_label() == LOST_REPORT_TAG
    turn = {"answer": "An answer.", "chat_mode": "research",
            "timing": {"total_cost_usd": 0.1},
            "audit": {"delegations": [{"kind": "delegation", "halted": None,
                                        "error": None,
                                        "report": lost_worker_report(2)}],
                      "empty_completions": []}}
    assert rr.lost_sites(turn, rr._lost_report_label())[0]["shape"] == "labelled"
