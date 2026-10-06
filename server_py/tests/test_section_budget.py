"""P3.1: the one-section-search-per-Act rule, relaxed to three and capped in code.

The Worker prompts said "exactly ONE call per `legislation_id`". P3.1 relaxes
that to "start with one; up to three per instrument", and by user decision
(Session 16) enforces the three in code, the way P2.7 enforced the discovery
budget: **3 ReAct rounds of `search_legislation_sections` per instrument, per
worker run**, checked before the memo, failing open.

What this file pins:

1. the unit (rounds, per instrument, however the id is spelled), and that
   nothing but a section search is ever refused by it;
2. a refused call does not run, is not recorded as a search, and says it is a
   limit (never a finding), with no `results` to be misread;
3. the memo cannot launder a repeat past the budget;
4. the stop reaches the worker's block and the lawyer's footer, and the
   lawyer's clause trips no detector and survives P2.8's read-back;
5. the discovery budget, the parliamentary budget and case law are unchanged;
6. the instruments never count a refused section search as one that ran;
7. the whole thing is fail-soft.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src.agent import agent_shared  # noqa: E402
from src.agent.agent_core import run_worker_agent  # noqa: E402
from src.agent.agent_shared import run_worker_tool  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.utils import discovery_budget as db  # noqa: E402
from src.utils import search_scope  # noqa: E402
from src.utils.audit_trace import AuditCollector, set_audit_collector  # noqa: E402
from src.utils.discovery_budget import (  # noqa: E402
    SECTION_SEARCH_ROUNDS,
    instrument_key,
    legislation_budget_blocks,
    new_search_budget,
    section_budget_blocks,
    section_stop_message,
    set_react_round,
)
from src.utils.search_scope import (  # noqa: E402
    _earlier_footers,
    _section_budget_footer_clause,
    _section_budget_limb,
    answer_scope_footer,
    record_section_budget_stop,
    strip_answer_footer,
    strip_scope_blocks,
    worker_scope_block,
)
from src.utils.stopwatch import TimingCollector  # noqa: E402

FOISA = "asp/2002/13"
WISA = "asp/2002/3"


@pytest.fixture(autouse=True)
def _round_and_config():
    token = db._REACT_ROUND.set(None)
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model",
    })
    yield
    set_request_provider_config({})
    db._REACT_ROUND.reset(token)


@pytest.fixture
def calls(monkeypatch):
    seen = []

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        seen.append((name, dict(args)))
        if name == "search_legislation":
            return json.dumps({"results": [{"legislation_id": FOISA, "title": "FOISA",
                                            "url": "http://www.legislation.gov.uk/id/asp/2002/13"}],
                               "returned": 1, "total": 141})
        return json.dumps({"results": [{
            "legislation_id": args.get("legislation_id"), "provision_type": "section",
            "number": 36, "title": "Confidentiality",
            "url": "http://www.legislation.gov.uk/id/asp/2002/13/section/36",
            "text": "Section 36) Confidentiality\n1) First.\n2) Second."}], "returned": 1})

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    return seen


async def _chunk(*a, **k):
    return None


async def _sections(lid, q, budget, tc=None, log=None, memo=None):
    return await run_worker_tool(
        "search_legislation_sections", {"legislation_id": lid, "query": q}, "brief",
        _chunk, "test-model", timing_collector=tc, search_budget=budget,
        search_log=log, tool_memo=memo,
    )


def _refused(out: str) -> bool:
    try:
        return json.loads(out).get("searched") is False
    except (ValueError, AttributeError):
        return False


def _stops(*lids, run="r1"):
    return [{"tool": "section_budget", "blocked_tool": "search_legislation_sections",
             "legislation_id": lid, "query": "q", "limit": 3, "run": run} for lid in lids]


def _leg(*queries):
    return [{"tool": "search_legislation", "query": q, "legislation_id": "",
             "shown": 5, "matched": 141} for q in queries]


def _secs(*lids):
    return [{"tool": "search_legislation_sections", "query": "q", "legislation_id": lid,
             "shown": 10, "matched": None} for lid in lids]


# ---------------------------------------------------------------------------
# 1. The unit
# ---------------------------------------------------------------------------

def test_the_number_and_where_it_lives():
    assert SECTION_SEARCH_ROUNDS == 3
    for mode in ("legislation_only", "legislation_and_case_law"):
        b = new_search_budget(mode)
        assert (b["section_limit"], b["section_rounds"]) == (3, {})
        assert b["limit"] == 8          # P2.7's number, untouched
    for mode in ("parliamentary_records", "westminster_records"):
        assert "section_limit" not in new_search_budget(mode)
    assert new_search_budget("case_law_only") is None


@pytest.mark.parametrize("raw,key", [
    ("asp/2002/13", "asp/2002/13"),
    ("http://www.legislation.gov.uk/id/asp/2002/13", "asp/2002/13"),
    ("https://legislation.gov.uk/asp/2002/13/section/36", "asp/2002/13"),
    ("ASP/2002/13/", "asp/2002/13"),
    ("ssi/2007/174/schedule/1", "ssi/2007/174"),
    ("nisr/1996/487/regulation/3", "nisr/1996/487"),
    ("", ""), (None, ""), (12, "12"),
])
def test_one_instrument_is_one_key_however_it_is_spelled(raw, key):
    assert instrument_key(raw) == key


def test_three_rounds_per_instrument_batching_free_the_fourth_refused():
    b = new_search_budget("legislation_only")
    for rnd in range(3):
        set_react_round(rnd)
        assert not any(section_budget_blocks(b, "search_legislation_sections",
                                             {"legislation_id": FOISA}) for _ in range(4))
    set_react_round(3)
    assert section_budget_blocks(b, "search_legislation_sections", {"legislation_id": FOISA})
    # The same instrument spelled as a URL is the same budget.
    assert section_budget_blocks(b, "search_legislation_sections",
                                 {"legislation_id": "http://www.legislation.gov.uk/id/asp/2002/13"})
    # Another instrument, in the same round, has a budget of its own.
    assert not section_budget_blocks(b, "search_legislation_sections", {"legislation_id": WISA})
    assert b["section_rounds"] == {FOISA: {0, 1, 2}, WISA: {3}}


@pytest.mark.parametrize("tool", [
    "search_legislation", "get_legislation_text", "get_legislation_changes",
    "search_case_law", "get_case_law_text", "search_scottish_plenary",
])
def test_nothing_but_a_section_search_is_ever_refused_by_it(tool):
    b = new_search_budget("legislation_and_case_law")
    for rnd in range(20):
        set_react_round(rnd)
        assert not section_budget_blocks(b, tool, {"legislation_id": FOISA})
    assert b["section_rounds"] == {}


def test_the_discovery_budget_is_unchanged_beside_it():
    b = new_search_budget("legislation_only")
    for rnd in range(8):
        set_react_round(rnd)
        assert not legislation_budget_blocks(b, "search_legislation")
        assert not legislation_budget_blocks(b, "search_legislation_sections")
        section_budget_blocks(b, "search_legislation_sections", {"legislation_id": f"asp/2002/{rnd}"})
    set_react_round(8)
    assert legislation_budget_blocks(b, "search_legislation")
    assert len(b["rounds"]) == 8


# ---------------------------------------------------------------------------
# 2 + 3. Through run_worker_tool: not run, not a search, a limit; memo included
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_fourth_round_on_one_instrument_is_refused_and_others_still_run(calls):
    b, tc, log = new_search_budget("legislation_only"), TimingCollector("req"), []
    for rnd in range(3):
        set_react_round(rnd)
        assert not _refused(await _sections(FOISA, f"aspect {rnd}", b, tc, log))
    set_react_round(3)
    out = await _sections(FOISA, "one more", b, tc, log)
    stop = json.loads(out)
    assert stop["searched"] is False and stop["legislation_id"] == FOISA
    assert "results" not in stop and "total" not in stop
    assert "NOT run" in stop["notice"] and "3 rounds" in stop["notice"]
    # Another instrument, in the refused round, still retrieves.
    assert not _refused(await _sections(WISA, "accounts", b, tc, log))
    assert [c[1]["query"] for c in calls] == ["aspect 0", "aspect 1", "aspect 2", "accounts"]
    assert tc.search_budget_blocked == 1
    assert tc.worker_tool_calls == 4
    # Recorded as a stop, never as a search that ran.
    ran = [e for e in log if e["tool"] == "search_legislation_sections"]
    assert [e["query"] for e in ran] == ["aspect 0", "aspect 1", "aspect 2", "accounts"]
    (row,) = [e for e in log if e["tool"] == "section_budget"]
    assert (row["legislation_id"], row["query"], row["limit"], row["run"]) == (
        FOISA, "one more", 3, b["id"])


@pytest.mark.asyncio
async def test_a_memo_served_repeat_is_charged_and_refused_when_spent(calls):
    """P3.8's same-resource repeats are mostly exact repeats the memo serves.
    Checked before the memo, as P2.7 is, so the memo cannot launder the loop."""
    b, tc, memo = new_search_budget("legislation_only"), TimingCollector("req"), {}
    for rnd in range(3):
        set_react_round(rnd)
        assert not _refused(await _sections(FOISA, "same", b, tc, memo=memo))
    assert tc.memo_hits == 2 and len(calls) == 1
    set_react_round(3)
    assert _refused(await _sections(FOISA, "same", b, tc, memo=memo))
    assert tc.memo_hits == 2            # not served from the memo either


@pytest.mark.asyncio
async def test_the_refused_call_is_marked_in_the_audit_trace(calls):
    col = AuditCollector("req-p31")
    set_audit_collector(col)
    try:
        dg = col.start_delegation("brief")
        b = new_search_budget("legislation_only")
        b["section_rounds"][FOISA] = {0, 1, 2}
        set_react_round(3)
        out = await run_worker_tool("search_legislation_sections",
                                    {"legislation_id": FOISA, "query": "x"}, "brief",
                                    _chunk, "test-model", search_budget=b,
                                    audit_delegation=dg)
        (tool,) = dg["tools"]
        assert tool["budget_blocked"] is True
        assert tool["raw_result"] == tool["final_result"] == out
        assert not rr._ran(tool)
    finally:
        set_audit_collector(None)
    assert calls == []


@pytest.mark.asyncio
async def test_no_budget_means_no_refusal(calls):
    """Callers that thread no budget (case law, or any caller outside a worker
    run) keep exactly the previous behaviour."""
    for rnd in range(6):
        set_react_round(rnd)
        assert not _refused(await _sections(FOISA, f"q{rnd}", None))
    assert len(calls) == 6


# ---------------------------------------------------------------------------
# 4. What the agent and the lawyer are told
# ---------------------------------------------------------------------------

def test_the_stop_is_a_limit_and_never_a_finding():
    msg = json.loads(section_stop_message(new_search_budget("legislation_only"),
                                          {"legislation_id": FOISA}))
    text = msg["notice"] + " " + msg["instruction"]
    assert FOISA in msg["notice"]
    assert "cut short by a limit" in text
    assert "Do not say that the instrument does not contain it" in text
    assert "no relevant records were found" not in text


def test_the_limb_names_the_instrument_the_limit_and_the_count():
    limb = _section_budget_limb(_stops(FOISA, FOISA))
    assert limb.startswith(f"Searching within {FOISA} was cut short")
    assert "limit of 3 rounds of section searches on that instrument" in limb
    assert "2 further section searches it asked for were not run" in limb
    assert "MUST also say that searching within the instrument was stopped by a limit" in limb
    two = _section_budget_limb(_stops(FOISA) + _stops(WISA))
    assert f"{FOISA}, {WISA}" in two and "each of those instruments" in two
    assert "1 further section search it asked for was not run" in _section_budget_limb(_stops(FOISA))


def test_the_block_carries_the_limb_is_stripped_whole_and_counts_no_refusal():
    log = _leg("freedom of information") + _secs(FOISA) + _stops(FOISA)
    block = worker_scope_block(log, {})
    assert f"Searching within {FOISA} was cut short" in block
    # The refused call is not an instrument this step searched within.
    assert "Searched within 1 instrument(s)" in block
    assert rr._SCOPE_COUNT.findall(block) == ["1"]
    stripped, n = strip_scope_blocks("Findings." + block)
    assert n == 1 and stripped == "Findings."


def test_no_stop_no_limb_no_clause():
    log = _leg("q") + _secs(FOISA)
    assert _section_budget_limb(log) == ""
    assert "cut short" not in worker_scope_block(log, {})
    assert "inside one instrument" not in answer_scope_footer(log, {})


_CLAUSES = [
    _section_budget_footer_clause(_stops(FOISA)),
    _section_budget_footer_clause(_stops(FOISA, FOISA, WISA)),
    _section_budget_footer_clause(_stops(FOISA, run="a") + _stops(WISA, run="b")),
]


@pytest.mark.parametrize("clause", _CLAUSES)
def test_the_lawyer_clause_trips_no_detector(clause):
    assert clause
    for det in (rr.NEG_ASSERTED, rr.NOT_FOUND, rr.NEG_BLAMED_USER, rr.IN_FORCE_CLAIM,
                rr.HALT_PARAPHRASE, rr.HALT_AS_TIMEOUT, rr.HALT_LITERAL,
                rr.SCOTS_CASELAW_GAP):
        assert not det.search(clause), det.pattern[:60]
    assert rr.derivation_claims(clause)[0] == []
    assert not any(rr._currency_asserted(s) for s in rr._sentences(clause))
    assert rr.caselaw_gap_statements(clause) == []


def test_the_clause_says_what_happened_and_nothing_it_cannot_know():
    one, three, two_steps = _CLAUSES
    assert "one research step reached the cap" in one
    assert "1 further search of it was not run" in one
    assert "3 further searches of it were not run" in three
    assert "2 research steps reached the cap" in two_steps
    for c in _CLAUSES:
        for bad in ("does not contain", "not found", "timed out", "halted"):
            assert bad not in c.lower()


@pytest.mark.parametrize("prefix", ["", "Answer about FOISA.\n\n"])
def test_the_footer_with_the_clause_is_one_line_stripped_whole_and_read_back(prefix):
    log = (_leg("freedom of information", "confidentiality") + _secs(FOISA)
           + _stops(FOISA))
    fresh = answer_scope_footer(log, {})
    assert "Searching within an instrument was also limited" in fresh
    assert fresh.strip().count("\n") == 0 and fresh.count("*Search scope:") == 1
    prose = prefix + "Section 36(1) exempts privileged communications."
    assert rr._without_footer(prose + fresh) == prose
    assert strip_answer_footer(prose + fresh) == prose
    (parsed,) = _earlier_footers([{"role": "user", "content": "q"},
                                  {"role": "assistant", "content": prose + fresh}])
    assert parsed["terms"] == ["freedom of information", "confidentiality"]


def test_both_limits_in_one_footer_keep_their_order():
    log = _leg("q") + [{"tool": "discovery_budget", "blocked_tool": "search_legislation",
                        "query": "late", "limit": 8, "run": "r1"}] + _stops(FOISA)
    fresh = answer_scope_footer(log, {})
    assert (fresh.index("This is a ranked search")
            < fresh.index("Searching was also limited")
            < fresh.index("Searching within an instrument was also limited"))


# ---------------------------------------------------------------------------
# End to end: a worker run, and the Manager's answer
# ---------------------------------------------------------------------------

async def _worker_run(rounds, research_mode="legislation_only"):
    set_request_provider_config({"_provider": "openrouter", "_research_mode": research_mode,
                                 "model": "test-model", "_tool_memo_enabled": False})

    async def loop(messages, model, cancel_event, num_ctx, tools, executor,
                   on_chunk=None, emit_tool_details=False, timing_collector=None, worker_call=False):
        for i, round_calls in enumerate(rounds):
            set_react_round(i)
            for name, args in round_calls:
                await executor(name, args)
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** Section 36(1) applies.\n"
            "2. **References:** None.")}

    return await run_worker_agent(loop, lambda *a, **k: None, "q", "test-model", None, 0)


def _section_rounds(n, lid=FOISA):
    return [[("search_legislation_sections", {"legislation_id": lid, "query": f"q{i}"})]
            for i in range(n)]


@pytest.mark.asyncio
async def test_a_worker_that_hits_the_cap_says_so_in_its_block(calls):
    result = await _worker_run([[("search_legislation", {"query": "foi"})]]
                               + _section_rounds(5))
    content = result["content"]
    assert f"Searching within {FOISA} was cut short" in content
    assert "2 further section searches it asked for were not run" in content
    assert [e["tool"] for e in result["searches"]].count("section_budget") == 2
    assert [c[0] for c in calls].count("search_legislation_sections") == 3


@pytest.mark.asyncio
async def test_a_worker_within_the_cap_is_unchanged(calls):
    result = await _worker_run([[("search_legislation", {"query": "foi"})]]
                               + _section_rounds(3))
    assert "cut short" not in result["content"]
    assert all(e["tool"] != "section_budget" for e in result["searches"])


@pytest.mark.asyncio
async def test_the_manager_answer_carries_the_clause(monkeypatch, calls):
    from src.agent.agent_core import process_user_request

    async def worker(*a, **kw):
        return await _worker_run([[("search_legislation", {"query": "foi"})]]
                                 + _section_rounds(4))

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "Section 36(1) applies."}

    final = await process_user_request(
        manager, worker, [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    content = final["content"]
    assert content.startswith("Section 36(1) applies.")
    assert content.count("*Search scope:") == 1
    assert ("Searching within an instrument was also limited: one research step reached "
            "the cap on how many times a step may search inside one instrument, and 1 "
            "further search of it was not run") in content
    assert "cut short" not in content and "SEARCH SCOPE" not in content
    assert "research_incomplete" not in final


# ---------------------------------------------------------------------------
# 5 + 6. Other budgets unchanged; the instruments skip a refused call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_parliamentary_budget_ignores_section_searches(monkeypatch):
    async def fake_parl(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return json.dumps({"results": [{"id": 1}]})

    monkeypatch.setattr(agent_shared, "execute_parliament_tool", fake_parl)
    b = new_search_budget("parliamentary_records")
    for rnd in range(3):
        set_react_round(rnd)
        out = await run_worker_tool("search_scottish_plenary", {"query": "q"}, "b",
                                    _chunk, "m", search_budget=b)
        assert not _refused(out)
    assert b == {"remaining": 0}


def test_discovery_runs_count_no_refused_section_search():
    def tool(name, t, blocked=False, **args):
        return {"name": name, "args": args, "started_at": t, "budget_blocked": blocked,
                "memo_hit": False}
    doc = {"session_id": "6348", "rep": 1, "turns": [{"turn": 1, "audit": {"delegations": [{
        "tools": [tool("search_legislation", 0.0, query="foi"),
                  tool("search_legislation_sections", 10.0, legislation_id=FOISA),
                  tool("search_legislation_sections", 20.0, legislation_id=FOISA),
                  tool("search_legislation_sections", 30.0, legislation_id=FOISA),
                  tool("search_legislation_sections", 40.0, blocked=True, legislation_id=FOISA)],
        "report": ""}]}}]}
    (row,) = rr.discovery_runs(doc)
    assert row["sections"] == 3
    assert row["budget_blocked"] == 1


# ---------------------------------------------------------------------------
# 7. Fail-soft
# ---------------------------------------------------------------------------

def test_an_unknown_round_fails_open_and_warns_once(caplog):
    b = new_search_budget("legislation_only")
    assert not any(section_budget_blocks(b, "search_legislation_sections",
                                         {"legislation_id": FOISA}) for _ in range(10))
    assert sum("no ReAct round" in r.message for r in caplog.records) == 1


@pytest.mark.parametrize("budget,args", [
    ({"kind": "legislation_rounds", "section_limit": "three", "section_rounds": {}},
     {"legislation_id": FOISA}),
    ({"kind": "legislation_rounds", "section_limit": 3, "section_rounds": None},
     {"legislation_id": FOISA}),
    ({"kind": "legislation_rounds", "section_limit": 3, "section_rounds": {FOISA: None}},
     {"legislation_id": FOISA}),
    ({"kind": "legislation_rounds", "section_rounds": {}}, None),
    ({"kind": "legislation_rounds", "section_rounds": {}}, {"legislation_id": ""}),
    ({"kind": "legislation_rounds", "section_rounds": {}}, "not a dict"),
    ({"remaining": 0}, {"legislation_id": FOISA}),
    (None, {"legislation_id": FOISA}),
])
def test_a_broken_budget_or_args_never_raise_and_never_refuse(budget, args):
    set_react_round(99)
    assert section_budget_blocks(budget, "search_legislation_sections", args) is False
    json.loads(section_stop_message(budget, args))


def test_a_budget_from_before_p3_1_is_budgeted_not_broken():
    """A budget dict without the section keys (built by an older caller) gets
    them on first use instead of raising."""
    b = {"kind": "legislation_rounds", "limit": 8, "rounds": set(), "id": "x"}
    for rnd in range(3):
        set_react_round(rnd)
        assert not section_budget_blocks(b, "search_legislation_sections",
                                         {"legislation_id": FOISA})
    set_react_round(3)
    assert section_budget_blocks(b, "search_legislation_sections", {"legislation_id": FOISA})


@pytest.mark.parametrize("entries", [
    [None, 3, "x"],
    [{"tool": "section_budget"}],
    [{"tool": "section_budget", "legislation_id": None, "limit": None, "run": None}],
    [{"tool": "section_budget", "legislation_id": 12, "limit": "x"}],
])
def test_odd_records_never_raise(entries):
    _section_budget_limb(entries)
    _section_budget_footer_clause(entries)
    worker_scope_block(_leg("q") + [e for e in entries if isinstance(e, dict)], {})
    answer_scope_footer(_leg("q") + [e for e in entries if isinstance(e, dict)], {})


def test_recording_never_raises():
    record_section_budget_stop(None, "search_legislation_sections", {}, {})
    log = []
    record_section_budget_stop(log, "search_legislation_sections", None, None)
    assert log == [{"tool": "section_budget", "blocked_tool": "search_legislation_sections",
                    "legislation_id": "", "query": "", "limit": None, "run": None}]


def test_a_broken_clause_never_costs_the_footer(monkeypatch):
    def boom(entries):
        raise RuntimeError("section budget disclosure broke")

    monkeypatch.setattr(search_scope, "_section_budget_rows", boom)
    log = _leg("q") + _stops(FOISA)
    assert "*Search scope:" in answer_scope_footer(log, {})
    assert "[SEARCH SCOPE" in worker_scope_block(log, {})


# ---------------------------------------------------------------------------
# 8. Batch 8 A2: the cap on an instrument whose COMPLETE provision list code
#    read in the same worker run (P3.12's route) says what that list holds
# ---------------------------------------------------------------------------
#
# The integrator's sweep: told in code that the index holds no schedule for an
# instrument, a Worker kept searching it, hit this cap, and the cap's text
# ("may still be in it") won, so the answer put the missing Schedule down to
# the limit. Synthetic ids only.

LID = "ssi/1901/3"
OTHER = "ssi/1901/4"
URI = f"http://www.legislation.gov.uk/id/{LID}"
NONE_HELD = {"provisions": 3, "units": []}
SOME_HELD = {"provisions": 6, "units": ["Schedule 2", "Annex II"]}

_OLD_STOP = (
    '{"notice": "Section-search limit reached: this research step has already searched '
    'within ssi/1901/4 in 3 rounds, the most one step may use on one instrument. This '
    'search was NOT run.", "searched": false, "legislation_id": "ssi/1901/4", '
    '"instruction": "Do not call search_legislation_sections for this legislation_id '
    'again in this step. Work from the provisions your earlier searches of it returned, '
    'then write your report. If a provision you need was not among them, your report '
    'must say that it was not retrieved because searching within this instrument was cut '
    'short by a limit, and name the provision you were looking for. Do not say that the '
    'instrument does not contain it."}')
_OLD_LIMB = (
    "Searching within ssi/1901/4 was cut short: this step used its limit of 3 rounds of "
    "section searches on that instrument, and 1 further section search it asked for was "
    "not run. Provisions this step did not retrieve may still be in it. If the answer "
    "you write reports a provision of it as absent or not found, it MUST also say that "
    "searching within the instrument was stopped by a limit before it finished.")
_OLD_CLAUSE = (
    " Searching within an instrument was also limited: one research step reached the cap "
    "on how many times a step may search inside one instrument, and 1 further search of "
    "it was not run, so the answer above may not cover every provision of that instrument.")
_FACT_NONE = ("the index holds 3 provisions for ssi/1901/3, and none of them is a "
              "schedule or an annex")


def _held_stops(lid, held, n=1, run="r1"):
    log = []
    for _ in range(n):
        record_section_budget_stop(log, "search_legislation_sections",
                                   {"legislation_id": lid, "query": "q"},
                                   {"section_limit": 3, "id": run}, held=held)
    return log


def _sched_classes(text):
    import re as _re
    return [c for c, _, _ in rr.sched_unit_clauses(
        text, _re.compile(r"\b(?:schedules?|annex(?:es)?)\b", _re.I))]


def test_without_a_complete_list_the_stop_limb_and_clause_are_exactly_as_before():
    b = {"section_limit": 3}
    for held in (None, {}, {"provisions": "three"}, {"units": []}):
        assert section_stop_message(b, {"legislation_id": OTHER}, held=held) == _OLD_STOP
    assert section_stop_message(b, {"legislation_id": OTHER}) == _OLD_STOP
    log = _held_stops(OTHER, None)
    assert log == _stops(OTHER)
    assert _section_budget_limb(log) == _OLD_LIMB
    assert _section_budget_footer_clause(log) == _OLD_CLAUSE


def test_a_complete_code_read_list_is_what_the_stop_states():
    msg = json.loads(section_stop_message({"section_limit": 3}, {"legislation_id": LID},
                                          held=NONE_HELD))
    assert msg["searched"] is False and "results" not in msg and "total" not in msg
    assert "NOT run" in msg["notice"]
    assert msg["provision_list"] == (
        "Code has already read the index's complete provision list for ssi/1901/3 in "
        f"this step: {_FACT_NONE}.")
    ins = msg["instruction"]
    assert ins.startswith("Do not call search_legislation_sections for this legislation_id")
    assert ("The index holds only the 3 provisions in that list for ssi/1901/3, so this "
            "limit kept nothing outside that list from you") in ins
    assert "do not put it down to this limit" in ins
    # The old text that won in the sweep is gone; a listed provision the step
    # did not reach is still put down to the limit.
    assert "Do not say that the instrument does not contain it" not in ins
    assert "If a provision you need is in that list" in ins and "cut short by a limit" in ins
    some = json.loads(section_stop_message({"section_limit": 3}, {"legislation_id": LID},
                                           held=SOME_HELD))
    assert some["provision_list"].endswith(
        "the index holds 6 provisions for ssi/1901/3, and its schedules and annexes among "
        "them are Schedule 2 and Annex II.")
    assert _sched_classes(msg["provision_list"]) == ["INDEX"]


@pytest.mark.parametrize("outcome,facts", [
    ({"status": "ok", "complete": True, "rows": [{"uri": f"{URI}/article/1"}]},
     {"provisions": 1, "units": []}),
    ({"status": "ok", "complete": True,
      "rows": [{"uri": f"{URI}/article/1"}, {"uri": f"{URI}/schedule/2"}]},
     {"provisions": 2, "units": ["Schedule 2"]}),
    ({"status": "ok", "complete": False, "rows": [{"uri": f"{URI}/article/1"}]}, None),
    ({"status": "ok", "complete": True, "rows": []}, None),
    ({"status": "failed"}, None),
    ({"status": "failed", "text": None}, None),
    ({"status": "no_text"}, None),
    (None, None),
    ("ok", None),
])
def test_only_a_complete_list_with_rows_establishes_anything(outcome, facts):
    from src.utils.schedule_units import provision_list_facts
    assert provision_list_facts(outcome) == facts


def _route_stub(monkeypatch, rows):
    """The route's `/section/lookup` call answered with `rows`; the section
    search itself returns one article and no schedule."""
    from src.agent.tools import executor
    import httpx
    asked = []

    async def fake_retry(client, method, url, *, name="", **kwargs):
        asked.append(url)
        return httpx.Response(200, json=rows, request=httpx.Request(method, url))

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return json.dumps({"results": [{
            "legislation_id": LID, "provision_type": "section", "number": 1,
            "title": "Citation", "url": f"{URI}/article/1",
            "text": "Section 1) Citation\n1) Widget Order 1901."}], "returned": 1})

    monkeypatch.setattr(executor, "_request_with_retry", fake_retry)
    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    return asked


_THREE = [{"uri": f"{URI}/article/{i}", "text": f"Section {i}) x"} for i in (1, 2, 3)]


@pytest.mark.asyncio
@pytest.mark.parametrize("route_spelling,cap_spelling", [(URI, LID), (LID, URI)])
async def test_the_stop_reads_the_list_the_route_read_in_this_run(
        monkeypatch, route_spelling, cap_spelling):
    """The real wiring: the route fills `provision_fetches` on a section search
    naming "the Schedule"; the cap, three rounds later, reads it, however the
    route and the cap were each handed the instrument (an id or a URL)."""
    asked = _route_stub(monkeypatch, _THREE)
    b, log, fetches = new_search_budget("legislation_only"), [], {}
    outs = []
    for rnd, lid in enumerate([route_spelling] * 3 + [cap_spelling]):
        set_react_round(rnd)
        outs.append(await run_worker_tool(
            "search_legislation_sections", {"legislation_id": lid, "query": "the Schedule widgets"},
            "brief", _chunk, "test-model", search_budget=b, search_log=log,
            provision_fetches=fetches))
    assert "none of them is a schedule or an annex: the Schedule is not one of them" in outs[0]
    assert len(asked) == 1                       # one list read for the run
    stop = json.loads(outs[3])
    assert stop["searched"] is False
    assert stop["provision_list"].endswith(
        f"the index holds 3 provisions for {cap_spelling}, and none of them is a "
        "schedule or an annex.")
    (row,) = [e for e in log if e["tool"] == "section_budget"]
    assert (row["provisions"], row["units"]) == (3, [])


@pytest.mark.asyncio
@pytest.mark.parametrize("fetches", [
    None,
    {},
    {LID: {"status": "ok", "complete": False, "rows": _THREE}},
    {LID: {"status": "failed", "text": None}},
    {LID: {"status": "no_text"}},
    {"ssi/1901/9": {"status": "ok", "complete": True, "rows": _THREE}},
])
async def test_a_list_cut_short_failed_absent_or_for_another_instrument_changes_nothing(
        monkeypatch, fetches):
    _route_stub(monkeypatch, _THREE)
    b, log = new_search_budget("legislation_only"), []
    b["section_rounds"][LID] = {0, 1, 2}
    set_react_round(3)
    out = await run_worker_tool(
        "search_legislation_sections", {"legislation_id": LID, "query": "widgets"},
        "brief", _chunk, "test-model", search_budget=b, search_log=log,
        provision_fetches=fetches)
    assert out == section_stop_message(b, {"legislation_id": LID})
    assert "provision_list" not in json.loads(out)
    (row,) = [e for e in log if e["tool"] == "section_budget"]
    assert "provisions" not in row and "units" not in row


def test_the_limb_states_the_list_for_that_instrument_and_keeps_the_rest():
    limb = _section_budget_limb(_held_stops(LID, NONE_HELD, n=2))
    assert limb.startswith(
        "Searching within ssi/1901/3 was stopped by this step's limit of 3 rounds of "
        "section searches on one instrument, and 2 further section searches it asked for "
        "were not run.")
    assert ("Before that, code had read the index's complete provision list for "
            f"ssi/1901/3: {_FACT_NONE}.") in limb
    assert ("so the limit kept nothing outside that list from this step: if the answer "
            "you write speaks of a provision of ssi/1901/3 outside that list, it must say "
            "what the index holds for ssi/1901/3, and must not put it down to the limit.") in limb
    assert "may still be in it" not in limb
    # A listed provision the step did not reach is still the limit's.
    assert "Provisions in that list that this step did not retrieve may still bear" in limb
    assert "INDEX" in _sched_classes(limb) and "LIMIT" not in _sched_classes(limb)
    mixed = _section_budget_limb(_stops(OTHER) + _held_stops(LID, NONE_HELD))
    assert mixed.startswith(_OLD_LIMB + " Searching within ssi/1901/3 was stopped")
    assert mixed.count("may still be in it") == 1


def test_the_footer_clause_adds_what_the_list_established():
    clause = _section_budget_footer_clause(_held_stops(LID, NONE_HELD))
    assert clause == (
        _OLD_CLAUSE + " For ssi/1901/3, the index's complete list of provisions had been "
        f"read before that cap was reached: {_FACT_NONE}, so the cap did not cause any "
        "provision outside that list to be missed.")
    assert "LIMIT" not in _sched_classes(clause)
    assert "INDEX" in _sched_classes(clause)
    log = _leg("widgets") + _secs(LID) + _held_stops(LID, SOME_HELD)
    fresh = answer_scope_footer(log, {})
    assert "its schedules and annexes among them are Schedule 2 and Annex II, so the cap" in fresh
    assert fresh.strip().count("\n") == 0 and fresh.count("*Search scope:") == 1
    prose = "Article 1 cites the Widget Order 1901."
    assert rr._without_footer(prose + fresh) == prose
    assert strip_answer_footer(prose + fresh) == prose
    (parsed,) = _earlier_footers([{"role": "user", "content": "q"},
                                  {"role": "assistant", "content": prose + fresh}])
    assert parsed["terms"] == ["widgets"]


@pytest.mark.asyncio
async def test_a_worker_run_carries_the_list_to_its_block(monkeypatch):
    """End to end through `run_worker_agent`: the refusal the Worker reads
    (its tool result) and the limb the Manager reads (the block on the
    report) both state the list, from the route's one read."""
    _route_stub(monkeypatch, _THREE)
    seen = []
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "model": "test-model", "_tool_memo_enabled": False})

    async def loop(messages, model, cancel_event, num_ctx, tools, executor,
                   on_chunk=None, emit_tool_details=False, timing_collector=None, worker_call=False):
        for i in range(4):
            set_react_round(i)
            seen.append(await executor("search_legislation_sections",
                                       {"legislation_id": LID, "query": f"the Schedule {i}"}))
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** Article 1 applies.\n2. **References:** None.")}

    result = await run_worker_agent(loop, lambda *a, **k: None, "q", "test-model", None, 0)
    assert json.loads(seen[3])["provision_list"].endswith(f"{_FACT_NONE}.")
    assert f"Before that, code had read the index's complete provision list for {LID}" \
        in result["content"]
    assert "may still be in it" not in result["content"]
