"""P2.1 (bucket B1) — the research step cap must stop being a legal finding.

The rewritten acceptance (FIX_PLAN, 2026-09-15) asserts five things about every
turn whose worker halted. Four of them are deterministic once the disclosure is
emitted by code rather than requested in a prompt, and that is what this file
pins:

1. `halts_undisclosed == 0` — the answer *does* tell the lawyer it is incomplete;
2. no raw `[Research halted` string anywhere in the answer;
3. the stated reason is **true** — a step cap, not "timed out";
4. no invented cause;
5. the halt is present as structured metadata on the step/worker result.

**Why the old acceptance was not merely weak but harmful, since the temptation to
restore it will recur.** It read "produce no halt text", which is satisfied by
saying nothing — and 5 turns in the Wave 1 sweep already halt *silently*: a
worker stops, a normal-looking report comes back, and the lawyer gets no signal.
Under Invariant 1 that is worse than the raw string leaking. So the assertions
below are the other way round: the answer **must** say so.
`test_a_silent_halt_is_disclosed_anyway` is the one that matters.

Three escape routes, all covered, because a fix at one of them leaves the others
open — which is what the row means by "a fix at the `run_deep_research` site
alone leaves the Manager path open":

  * a Manager `delegate_research` result (6340),
  * a Deep Research plan step (6406 — all four steps halted, $2.36 to say
    nothing),
  * the **Manager's own** ReAct loop (6383 turn 1 — the raw string as the entire
    answer, and it appears in **no delegation report**, so any check reading
    only `delegations[].report` is blind to the corpus's starkest case).
"""

import asyncio

import pytest

from src.agent.agent_core import (
    process_user_request,
    run_deep_research,
    run_worker_agent,
)
from src.agent.provider_factory import set_request_provider_config
from src.utils.audit_trace import AuditCollector, set_audit_collector
from src.utils.research_halt import (
    apply_halt_disclosure,
    halt_marker_text,
    halt_notice,
    halt_worker_report,
    strip_halt_markers,
)

HALT = {"reason": "step_cap", "limit": 20, "steps": 20}
RAW = halt_marker_text(20)


@pytest.fixture
def _cfg():
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False,
    })
    yield
    set_request_provider_config({})


# ---------------------------------------------------------------------------
# The wording — acceptance (3) and (4), asserted on the strings themselves
# ---------------------------------------------------------------------------

def test_the_raw_marker_never_survives():
    text = f"Some findings.\n\n{RAW}\n\nMore findings."
    out, n = strip_halt_markers(text)
    assert n == 1
    assert "[Research halted" not in out
    assert "Some findings." in out and "More findings." in out


def test_the_marker_is_stripped_whatever_the_limit_is():
    """Matched loosely on the number: changing `max_turns` must not leave a
    marker behind un-stripped."""
    out, n = strip_halt_markers("[Research halted: exceeded 40 tool-call steps]")
    assert (out, n) == ("", 1)


def test_the_stated_reason_is_the_real_one():
    """6340 told the lawyer the agent had *"exceeded its operational limits
    (timed out)"*. It did not time out — it hit a cap on tool-call rounds."""
    for text in (halt_worker_report(HALT), halt_notice([HALT])):
        assert "20" in text                      # the real limit, stated
        assert "timed out" not in text.lower()   # never claimed
        # "timeout" may appear only inside an explicit denial.
        for frag in text.lower().split("timeout")[:-1]:
            assert "not" in frag[-12:], text
    assert "NOT a timeout" in halt_worker_report(HALT)
    assert "not** a timeout" in halt_notice([HALT])


def test_the_halt_is_not_a_negative_finding():
    """Invariant 1 cuts both ways: the disclosure must not read as evidence that
    the material does not exist, which is how a lawyer would otherwise take it."""
    report = halt_worker_report(HALT)
    assert "NOT evidence that the material does not exist" in report
    assert "not** a finding that the material does not exist" in halt_notice([HALT])


def test_the_worker_report_forbids_the_two_behaviours_6340_showed():
    """6340 renamed the cap a timeout and then supplied a cause for the absence —
    *"a broad enabling power has generated a very large volume of statutory
    instruments"* — for an Act that 404s in LEX. Carried per-occurrence in the
    tool result, like the proven `[Research Agent Error]` string."""
    report = halt_worker_report(HALT)
    assert "Do NOT state or speculate about why material was not found" in report
    assert "Do NOT call delegate_research again" in report
    assert "Do NOT present this as a legal finding" in report


def test_the_report_says_what_was_retrieved_before_it_stopped():
    assert "No sources had been retrieved" in halt_worker_report(HALT, 0)
    assert "7 source(s)" in halt_worker_report(HALT, 7)


def test_the_notice_names_the_plan_steps_when_it_knows_them():
    one = halt_notice([{**HALT, "step": 3, "title": "Check commencement"}])
    assert "step 3 (Check commencement)" in one
    two = halt_notice([
        {**HALT, "step": 2, "title": "A"}, {**HALT, "step": 4, "title": "B"},
    ])
    assert "step 2 (A)" in two and "step 4 (B)" in two


def test_the_disclosure_is_prepended_and_idempotent():
    """Prepended because it is a warning about everything below it, and a warning
    read after the findings have been relied on is not a warning."""
    once, disclosed = apply_halt_disclosure("The answer body.", [HALT])
    assert disclosed
    assert once.startswith("> **⚠ This answer is incomplete.**")
    assert once.rstrip().endswith("The answer body.")
    twice, _ = apply_halt_disclosure(once, [HALT])
    assert twice == once


def test_no_halt_leaves_the_answer_alone():
    """No false positives: an ordinary answer must be byte-identical."""
    body = "A complete answer with no problems at all."
    out, disclosed = apply_halt_disclosure(body, [])
    assert (out, disclosed) == (body, False)


# ---------------------------------------------------------------------------
# Route 1: a Manager delegate_research result (6340)
# ---------------------------------------------------------------------------

def _halting_chat_loop(halt_after_tools=True, manager_answer=None):
    """Stub chat_loop. As a worker it halts; as a manager it answers."""
    state = {"calls": 0}

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None):
        state["calls"] += 1
        return {"role": "assistant", "content": RAW, "halted": dict(HALT)}

    return chat_loop


@pytest.mark.asyncio
async def test_a_halted_worker_returns_structure_not_prose(_cfg):
    """Acceptance (5). A string in an assistant message is indistinguishable from
    findings — which is exactly how a step cap became a legal conclusion."""
    result = await run_worker_agent(
        _halting_chat_loop(), lambda *a, **k: None, "q", "test-model", None, 0,
    )
    assert result["halted"] == HALT
    assert "[Research halted" not in result["content"]
    assert "step limit reached" in result["content"].lower()


@pytest.mark.asyncio
async def test_the_manager_route_discloses_and_carries_metadata(_cfg):
    seen = {}

    async def halting_worker(*a, **kw):
        return {"content": halt_worker_report(HALT), "sources": [], "halted": dict(HALT)}

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        seen["tool_result"] = await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "Here is what I found."}

    final = await process_user_request(
        manager, halting_worker, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert "Research Incomplete" in seen["tool_result"]      # the Manager was told
    assert final["research_incomplete"]["reason"] == "step_cap"
    assert final["research_incomplete"]["halts"][0]["scope"] == "delegation"
    assert "This answer is incomplete" in final["content"]
    assert "[Research halted" not in final["content"]


@pytest.mark.asyncio
async def test_a_silent_halt_is_disclosed_anyway(_cfg):
    """**The test the whole row turns on.** The old acceptance ("produce no halt
    text") was satisfied by this exact answer, and 5 turns in the Wave 1 sweep
    produce it: a worker halts, the Manager writes a clean, plausible,
    normal-looking reply, and the lawyer is never told it is partial. The
    disclosure is emitted by code precisely so the model's cooperation is not
    required."""
    async def halting_worker(*a, **kw):
        return {"content": halt_worker_report(HALT), "sources": [], "halted": dict(HALT)}

    async def silent_manager(messages, model, cancel_event, num_ctx, tools,
                             tool_executor, on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {
            "role": "assistant",
            "content": (
                "1. **Summary Answer (BLUF):** Compulsory purchase in Scotland is "
                "governed by the 1947 Act.\n2. **References:** None found."
            ),
        }

    final = await process_user_request(
        silent_manager, halting_worker, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert "This answer is incomplete" in final["content"]
    assert final["research_incomplete"]["disclosed"] is True


# ---------------------------------------------------------------------------
# Route 2: the Manager's OWN loop (6383 turn 1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_managers_own_halt_is_caught_too(_cfg):
    """6383 turn 1: the raw marker was the entire 46-character answer, and it
    appears in **no** delegation report. A fix at the worker seam alone, or a
    check reading `delegations[].report`, is blind to it."""
    async def never_called_worker(*a, **kw):  # pragma: no cover
        raise AssertionError("no delegation in this scenario")

    final = await process_user_request(
        _halting_chat_loop(), never_called_worker,
        [{"role": "user", "content": "q"}], "test-model", None, None, 0,
    )
    assert "[Research halted" not in final["content"]
    assert "This answer is incomplete" in final["content"]
    assert final["research_incomplete"]["halts"][0]["scope"] == "manager"


# ---------------------------------------------------------------------------
# Route 3: a Deep Research plan step (6406)
# ---------------------------------------------------------------------------

def _plan(n):
    return {"scope_note": "scope",
            "steps": [{"id": i, "title": f"Step {i} title", "detail": "d"}
                      for i in range(1, n + 1)]}


async def _synthesis(messages, model, cancel_event, num_ctx, tools, executor,
                     on_chunk, emit_tool_details=False, timing_collector=None):
    return {"content": "INTEGRATED REPORT: the statutory framework is as follows."}


@pytest.mark.asyncio
async def test_one_halted_step_is_named_in_the_report(_cfg):
    async def worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        halted = "Step 2" in query
        return {
            "content": halt_worker_report(HALT) if halted else "findings",
            "sources": [],
            **({"halted": dict(HALT)} if halted else {}),
        }

    final = await run_deep_research(
        _synthesis, worker, _plan(3), [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert "step 2 (Step 2 title)" in final["content"]
    assert "INTEGRATED REPORT" in final["content"]        # findings preserved
    assert final["research_incomplete"]["steps_total"] == 3
    assert len(final["research_incomplete"]["halts"]) == 1


@pytest.mark.asyncio
async def test_a_report_whose_every_step_halted_says_so(_cfg):
    """6406: all four steps halted and the report cost $2.36 to say nothing. The
    row calls it the acceptance case."""
    async def worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        return {"content": halt_worker_report(HALT), "sources": [], "halted": dict(HALT)}

    final = await run_deep_research(
        _synthesis, worker, _plan(4), [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    inc = final["research_incomplete"]
    assert len(inc["halts"]) == 4 and inc["steps_total"] == 4
    assert final["content"].startswith("> **⚠ This answer is incomplete.**")
    assert "[Research halted" not in final["content"]


@pytest.mark.asyncio
async def test_a_deep_research_run_with_no_halts_is_untouched(_cfg):
    async def worker(query, model, cancel, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        return {"content": "findings", "sources": []}

    final = await run_deep_research(
        _synthesis, worker, _plan(2), [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert "incomplete" not in final["content"]
    assert "research_incomplete" not in final


# ---------------------------------------------------------------------------
# The audit trace — acceptance (5) for an eval harness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_trace_carries_the_halt_as_a_field_not_a_string(_cfg):
    """Schema v2. A harness previously had to string-match "[Research halted" in
    `report` — which the Manager-loop case never populates at all."""
    audit = AuditCollector("req1")
    set_audit_collector(audit)
    try:
        await run_worker_agent(
            _halting_chat_loop(), lambda *a, **k: None, "q", "test-model", None, 0,
        )
    finally:
        set_audit_collector(None)

    dg = audit.delegations[0]
    assert dg["halted"] == HALT
    assert "[Research halted" not in dg["report"]


def test_an_unhalted_delegation_reports_halted_as_none():
    audit = AuditCollector("req1")
    rec = audit.start_delegation("brief")
    audit.end_delegation(rec, report="a fine report")
    assert rec["halted"] is None
