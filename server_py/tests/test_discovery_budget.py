"""P2.7: a discovery budget for the legislation Worker.

Nothing stopped a legislation Worker searching until the 20-round step cap
stopped it, and a halted worker writes no findings at all. The budget is
**8 ReAct rounds in which `search_legislation` may be called**, per worker run
(decided with the user, Session 15, from the round distribution: halted runs
search in a median of 14 rounds, completed ones in a median of 2).

What this file pins, in the order the handover listed them:

1. the budget hard-stops discovery and never touches Phase-2 retrieval;
2. it counts ROUNDS, and a memo-served search is charged (decided);
3. the parliament and Westminster budgets and stop messages are unchanged;
4. the lawyer's clause trips no detector, and the agent-facing text never
   reaches an answer;
5. a stop reaches `worker_scope_block` and the lawyer's footer, on the Manager
   and Deep Research paths;
6. P2.8's `_FRESH_FOOTER` still reads the footer back (also parametrised in
   `test_search_scope.py`);
7. both providers' `chat_loop` publish the round to the round's tool calls;
8. the instruments never count a refused call as a search that ran;
9. the whole thing is fail-soft.
"""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src.agent import agent_core, agent_shared, ollama_client, openrouter_client  # noqa: E402
from src.agent.agent_core import run_deep_research, run_worker_agent  # noqa: E402
from src.agent.agent_shared import run_worker_tool  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.config import EFFICIENCY_PROFILES  # noqa: E402
from src.utils import discovery_budget as db  # noqa: E402
from src.utils import search_scope  # noqa: E402
from src.utils.audit_trace import AuditCollector, set_audit_collector  # noqa: E402
from src.utils.discovery_budget import (  # noqa: E402
    LEGISLATION_SEARCH_ROUNDS,
    current_react_round,
    legislation_budget_blocks,
    legislation_stop_message,
    new_search_budget,
    set_react_round,
)
from src.utils.search_scope import (  # noqa: E402
    _budget_footer_clause,
    _budget_limb,
    _earlier_footers,
    answer_scope_footer,
    record_budget_stop,
    strip_answer_footer,
    strip_scope_blocks,
    worker_scope_block,
)
from src.utils.stopwatch import TimingCollector  # noqa: E402

from tests.test_stream_retry import (  # noqa: E402,F401
    _mock_http,
    _no_sleep,
    _sequence_handler,
    _sse,
)


@pytest.fixture(autouse=True)
def _round_and_config():
    """No round and no provider config leak into or out of a test."""
    token = db._REACT_ROUND.set(None)
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model",
    })
    yield
    set_request_provider_config({})
    db._REACT_ROUND.reset(token)


_SEARCH = {"results": [
    {"legislation_id": "asp/2002/13", "title": "Freedom of Information (Scotland) Act 2002",
     "url": "http://www.legislation.gov.uk/id/asp/2002/13",
     "status": "revised", "year": 2002, "extent": ["Scotland"]}],
    "returned": 1, "total": 141}


@pytest.fixture
def calls(monkeypatch):
    seen = []

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        seen.append((name, dict(args)))
        if name == "search_legislation":
            return json.dumps(_SEARCH)
        if name == "get_legislation_changes":
            return json.dumps({"legislation_id": args.get("legislation_id"), "results": []})
        return json.dumps({"results": [{"legislation_id": "asp/2002/13",
                                        "number": "36", "text": "Section 36 text."}]})

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    return seen


async def _chunk(*a, **k):
    return None


async def _search(q, budget, tc=None, log=None, memo=None):
    return await run_worker_tool(
        "search_legislation", {"query": q}, "brief", _chunk, "test-model",
        timing_collector=tc, search_budget=budget, search_log=log, tool_memo=memo,
    )


def _refused(out: str) -> bool:
    try:
        return json.loads(out).get("searched") is False
    except (ValueError, AttributeError):
        return False


def _stops(*queries, run="r1"):
    return [{"tool": "discovery_budget", "blocked_tool": "search_legislation",
             "query": q, "limit": 8, "run": run} for q in queries]


def _leg(*queries):
    return [{"tool": "search_legislation", "query": q, "legislation_id": "",
             "shown": 5, "matched": 141} for q in queries]


# ---------------------------------------------------------------------------
# 1 + 2. It stops discovery, by round, and never retrieval
# ---------------------------------------------------------------------------

def test_the_number_and_the_unit():
    assert LEGISLATION_SEARCH_ROUNDS == 8
    b = new_search_budget("legislation_only")
    assert (b["kind"], b["limit"], b["rounds"]) == ("legislation_rounds", 8, set())
    assert new_search_budget("legislation_and_case_law")["limit"] == 8


def test_batching_within_a_round_is_free_and_the_ninth_round_is_refused():
    b = new_search_budget("legislation_only")
    for rnd in range(8):
        set_react_round(rnd)
        assert not any(legislation_budget_blocks(b, "search_legislation") for _ in range(5))
    set_react_round(8)
    assert legislation_budget_blocks(b, "search_legislation")
    assert legislation_budget_blocks(b, "search_legislation")   # every call in it
    set_react_round(9)
    assert legislation_budget_blocks(b, "search_legislation")   # and every later round
    # A round already charged stays free (never happens in production, where
    # rounds only increase, but a refusal must not un-charge anything).
    set_react_round(3)
    assert not legislation_budget_blocks(b, "search_legislation")
    assert len(b["rounds"]) == 8


@pytest.mark.parametrize("tool", [
    "search_legislation_sections", "get_legislation_text", "get_legislation_changes",
    "search_case_law", "get_case_law_text",
])
def test_nothing_but_search_legislation_is_ever_refused(tool):
    """Phase 2 is untouched, and case law is not budgeted (user decision)."""
    b = new_search_budget("legislation_and_case_law")
    for rnd in range(30):
        set_react_round(rnd)
        assert not legislation_budget_blocks(b, tool)
    assert b["rounds"] == set()


@pytest.mark.asyncio
async def test_run_worker_tool_refuses_the_ninth_round_and_retrieves_after_it(calls):
    b, tc, log = new_search_budget("legislation_only"), TimingCollector("req"), []
    for rnd in range(8):
        set_react_round(rnd)
        for q in ("a", "b"):
            assert not _refused(await _search(f"{q}{rnd}", b, tc, log))
    set_react_round(8)
    out = await _search("one more", b, tc, log)
    stop = json.loads(out)
    assert stop["searched"] is False
    # A refused search must not read as one that matched nothing.
    assert "results" not in stop and "total" not in stop
    # Retrieval in the refused round, and after it, still runs.
    for name, args in (("search_legislation_sections", {"legislation_id": "asp/2002/13", "query": "s36"}),
                       ("get_legislation_text", {"legislation_id": "asp/2002/13"}),
                       ("get_legislation_changes", {"legislation_id": "asp/2002/13", "direction": "to"})):
        res = await run_worker_tool(name, args, "brief", _chunk, "test-model",
                                    timing_collector=tc, search_budget=b, search_log=log)
        assert not _refused(res)
    names = [c[0] for c in calls]
    assert names.count("search_legislation") == 16
    assert "one more" not in [c[1].get("query") for c in calls]
    assert len(names) == 19
    # Counted on its own counter, and kept out of the call and phase counts.
    assert tc.search_budget_blocked == 1
    assert tc.worker_tool_calls == 19
    assert tc.phase1_search_calls == 16
    # Recorded as a stop, and NOT as a search that ran.
    assert [e["query"] for e in log if e["tool"] == "search_legislation"].count("one more") == 0
    (stop_row,) = [e for e in log if e["tool"] == "discovery_budget"]
    assert stop_row["query"] == "one more" and stop_row["limit"] == 8
    assert stop_row["run"] == b["id"]


@pytest.mark.asyncio
async def test_a_memo_served_search_is_charged_a_round_and_refused_when_spent(calls):
    """Decided at Session 15: 57 of 81 memo hits on halted runs repeat the same
    step's own search, which is the loop the budget is for."""
    b, tc, memo, log = new_search_budget("legislation_only"), TimingCollector("req"), {}, []
    set_react_round(0)
    await _search("same", b, tc, log, memo)
    for rnd in range(1, 8):
        set_react_round(rnd)
        assert not _refused(await _search("same", b, tc, log, memo))
    assert len(b["rounds"]) == 8
    assert tc.memo_hits == 7
    set_react_round(8)
    assert _refused(await _search("same", b, tc, log, memo))
    assert tc.memo_hits == 7            # not served from the memo either
    assert len(calls) == 1              # one API call in all of it
    # The seven memo hits are still recorded as searches (P2.9); the refusal is not.
    assert [e["tool"] for e in log].count("search_legislation") == 8
    assert [e["tool"] for e in log].count("discovery_budget") == 1


@pytest.mark.asyncio
async def test_a_later_step_reusing_an_earlier_search_spends_one_round_of_its_own(calls):
    memo = {}
    set_react_round(0)
    await _search("shared", new_search_budget("legislation_only"), memo=memo)
    step2 = new_search_budget("legislation_only")
    set_react_round(0)
    for q in ("shared", "shared", "fresh"):
        assert not _refused(await _search(q, step2, memo=memo))
    assert step2["rounds"] == {0}


@pytest.mark.asyncio
async def test_the_refused_call_is_marked_in_the_audit_trace(calls):
    col = AuditCollector("req-p27")
    set_audit_collector(col)
    try:
        dg = col.start_delegation("brief")
        b = new_search_budget("legislation_only")
        b["rounds"].update(range(8))
        set_react_round(8)
        out = await run_worker_tool("search_legislation", {"query": "x"}, "brief",
                                    _chunk, "test-model", search_budget=b,
                                    audit_delegation=dg)
        (tool,) = dg["tools"]
        assert tool["budget_blocked"] is True
        assert tool["memo_hit"] is False
        assert tool["raw_result"] == tool["final_result"] == out
        assert calls == []
    finally:
        set_audit_collector(None)


# ---------------------------------------------------------------------------
# 3. The parliamentary budgets are unchanged
# ---------------------------------------------------------------------------

_SP_STOP = json.dumps({
    "notice": "Search limit reached — you have already performed the maximum number of parliamentary searches.",
    "instruction": (
        "STOP calling search_scottish_plenary, search_scottish_parliament, or "
        "search_scottish_committee_transcripts. "
        "You MUST now either: (a) call get_scottish_plenary_debate or "
        "get_scottish_committee_transcript with the IDs from your previous search results to "
        "retrieve full text (search_scottish_parliament results are excerpt-only and need no "
        "retrieval), or (b) if no results were found at all, synthesize your answer stating that "
        "no relevant records were found."
    ),
    "results": [],
    "total": 0,
})
_HANSARD_STOP = json.dumps({
    "notice": "Search limit reached — you have already performed the maximum number of parliamentary searches.",
    "instruction": (
        "STOP calling search_hansard. You MUST now either: (a) call get_hansard_debate "
        "with a debate_ext_id from your previous search results to retrieve the full "
        "verbatim contributions, or (b) if no results were found at all, synthesize your "
        "answer stating that no relevant records were found."
    ),
    "results": [],
    "total": 0,
})


@pytest.mark.parametrize("mode,expected", [
    ("parliamentary_records", {"remaining": 3}),
    ("westminster_records", {"remaining": 3}),
    ("case_law_only", None),
    ("drafting", None),
    ("", None),
])
def test_budget_by_mode(mode, expected):
    assert new_search_budget(mode) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [
    "parliamentary_records", "westminster_records", "legislation_only",
    "legislation_and_case_law", "case_law_only",
])
async def test_run_worker_agent_hands_each_run_a_fresh_budget_of_its_mode(monkeypatch, mode):
    set_request_provider_config({"_provider": "openrouter", "_research_mode": mode,
                                 "model": "test-model"})
    seen = []

    async def fake_tool(name, args, query, *a, search_budget=None, **kw):
        seen.append(search_budget)
        return "{}"

    async def loop(messages, model, cancel_event, num_ctx, tools, executor, on_chunk=None, **kw):
        await executor("search_legislation", {"query": "q"})
        return {"role": "assistant", "content": "done"}

    monkeypatch.setattr(agent_core, "run_worker_tool", fake_tool)
    for _ in range(2):
        await run_worker_agent(loop, lambda *a, **k: None, "q", "test-model", None, 0)
    if mode in ("parliamentary_records", "westminster_records"):
        assert seen[0] == {"remaining": 3}
    elif mode == "case_law_only":
        assert seen[0] is None
    else:
        assert seen[0]["kind"] == "legislation_rounds" and seen[0]["limit"] == 8
        assert seen[0] is not seen[1] and seen[0]["id"] != seen[1]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,tool,expected", [
    ("parliamentary_records", "search_scottish_plenary", _SP_STOP),
    ("parliamentary_records", "search_scottish_parliament", _SP_STOP),
    ("parliamentary_records", "search_scottish_committee_transcripts", _SP_STOP),
    ("westminster_records", "search_hansard", _HANSARD_STOP),
])
async def test_parliamentary_stop_messages_are_byte_for_byte_unchanged(mode, tool, expected):
    set_request_provider_config({"_provider": "openrouter", "_research_mode": mode})
    tc = TimingCollector("req")
    out = await run_worker_tool(tool, {"query": "housing"}, "brief", _chunk, "m",
                                timing_collector=tc, search_budget={"remaining": 0})
    assert out == expected
    assert tc.search_budget_blocked == 1


@pytest.mark.asyncio
async def test_the_parliamentary_budget_still_counts_calls_not_rounds(monkeypatch):
    set_request_provider_config({"_provider": "openrouter",
                                 "_research_mode": "parliamentary_records"})
    ran = []

    async def fake_parl(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        ran.append(name)
        return json.dumps({"results": [], "total": 0})

    monkeypatch.setattr(agent_shared, "execute_parliament_tool", fake_parl)
    budget = {"remaining": 3}
    set_react_round(0)       # all in ONE round: rounds are irrelevant here
    outs = [await run_worker_tool("search_scottish_plenary", {"query": f"q{i}"}, "b",
                                  _chunk, "m", search_budget=budget) for i in range(4)]
    assert len(ran) == 3
    assert outs[3] == _SP_STOP
    assert budget == {"remaining": 0}


@pytest.mark.asyncio
async def test_a_parliamentary_memo_hit_is_still_served_after_the_budget(monkeypatch):
    """The parliamentary check stays AFTER the memo, unlike the legislation one."""
    set_request_provider_config({"_provider": "openrouter",
                                 "_research_mode": "parliamentary_records"})
    ran = []

    async def fake_parl(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        ran.append(name)
        return json.dumps({"results": [{"meeting_id": 1}], "total": 1})

    monkeypatch.setattr(agent_shared, "execute_parliament_tool", fake_parl)
    memo = {}
    first = await run_worker_tool("search_scottish_plenary", {"query": "q"}, "b",
                                  _chunk, "m", search_budget={"remaining": 1}, tool_memo=memo)
    again = await run_worker_tool("search_scottish_plenary", {"query": "q"}, "b",
                                  _chunk, "m", search_budget={"remaining": 0}, tool_memo=memo)
    assert again == first and len(ran) == 1


@pytest.mark.asyncio
async def test_a_parliamentary_tool_name_under_a_legislation_budget_is_not_a_keyerror(
        calls, monkeypatch):
    async def fake_parl(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return json.dumps({"results": [], "total": 0})

    monkeypatch.setattr(agent_shared, "execute_parliament_tool", fake_parl)
    b = new_search_budget("legislation_only")
    set_react_round(0)
    for name in ("search_hansard", "search_scottish_plenary"):
        out = await run_worker_tool(name, {"query": "q"}, "b", _chunk, "m",
                                    search_budget=b)
        assert isinstance(out, str) and not _refused(out)


# ---------------------------------------------------------------------------
# 4. Detectors
# ---------------------------------------------------------------------------

_CLAUSES = [
    _budget_footer_clause(_stops("x")),
    _budget_footer_clause(_stops("x", "y", "z")),
    _budget_footer_clause(_stops("x", run="a") + _stops("y", "z", run="b")),
]


@pytest.mark.parametrize("clause", _CLAUSES)
def test_the_lawyer_clause_trips_no_detector(clause):
    """P2.2's footer tripped `NEG_ASSERTED` and corrupted its own denominator.
    A budget stop is not a halt either: a halt detector reading this clause
    would grade halts as disclosed on turns that never halted."""
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
    assert "1 further search it asked for was not run" in one
    assert "3 further searches it asked for were not run" in three
    assert "2 research steps reached the cap" in two_steps
    for c in _CLAUSES:
        # The parliamentary hazard, and P2.1's two falsehoods.
        for bad in ("no relevant records", "does not exist", "timed out", "halted"):
            assert bad not in c.lower()


@pytest.mark.parametrize("prefix", ["", "Answer about shops.\n\n"])
def test_the_footer_with_the_clause_is_one_line_stripped_whole_and_read_back(prefix):
    log = _leg("shop definition", "Shops Act", "Sunday Trading") + _stops("late")
    fresh = answer_scope_footer(log, {"_jurisdiction": "scotland"})
    assert "Searching was also limited" in fresh
    assert fresh.strip().count("\n") == 0
    assert fresh.count("*Search scope:") == 1
    prose = prefix + "The Shops Act 1950 defines a shop."
    assert rr._without_footer(prose + fresh) == prose
    assert strip_answer_footer(prose + fresh) == prose
    (parsed,) = _earlier_footers([{"role": "user", "content": "q"},
                                  {"role": "assistant", "content": prose + fresh}])
    assert parsed["terms"] == ["shop definition", "Shops Act"]
    assert parsed["rest"] == 1
    # It sits after the part the parse anchors on, and before the case-law clause.
    assert fresh.index("This is a ranked search") < fresh.index("Searching was also limited")


def test_no_stop_no_clause():
    assert "Searching was also limited" not in answer_scope_footer(_leg("q"), {})
    assert _budget_limb(_leg("q")) == ""
    assert "cut short" not in worker_scope_block(_leg("q"), {})


def test_the_stop_message_is_not_the_parliamentary_one():
    msg = json.loads(legislation_stop_message(new_search_budget("legislation_only")))
    assert "8 rounds" in msg["notice"] and "NOT run" in msg["notice"]
    text = msg["notice"] + msg["instruction"]
    assert "no relevant records were found" not in text
    assert "cut short by a limit" in text
    for tool in ("search_legislation_sections", "get_legislation_text", "get_legislation_changes"):
        assert tool in text


def test_the_agent_facing_limb_never_reaches_a_lawyer():
    block = worker_scope_block(_leg("a") + _stops("b"), {})
    assert "Searching was cut short" in block
    stripped, n = strip_scope_blocks("Findings." + block)
    assert n == 1 and stripped == "Findings."
    # And it cannot be read as a count of searches that ran.
    assert rr._SCOPE_COUNT.findall(block) == ["1"]
    assert not rr.HALT_LITERAL.search(block)


# ---------------------------------------------------------------------------
# 5. It reaches the agent that writes the answer, and the lawyer
# ---------------------------------------------------------------------------

def test_the_limb_names_the_limit_the_count_and_the_queries():
    limb = _budget_limb(_stops("a", "b", "a", "c", "d"))
    assert "limit of 8 rounds" in limb
    assert "5 further searches it asked for were not run" in limb
    assert '(for: "a"; "b"; "c")' in limb
    assert "MUST also say that searching was stopped by a limit" in limb
    assert "delegate_research again with the same brief" in limb
    assert "1 further search it asked for was not run" in _budget_limb(_stops("a"))
    # The smoke run's queries, verbatim: quoted and backslash-escaped.
    messy = _budget_limb(_stops('"shop" means', '"meaning of \\"shop\\""', "“shop” includes"))
    assert '(for: "shop means"; "meaning of shop"; "shop includes")' in messy


async def _worker_run(monkeypatch, rounds, research_mode="legislation_only"):
    """A worker whose fake loop issues `rounds` (a list of call lists), one
    ReAct round each, publishing the round as `chat_loop` does."""
    set_request_provider_config({"_provider": "openrouter", "_research_mode": research_mode,
                                 "model": "test-model", "_tool_memo_enabled": False})

    async def loop(messages, model, cancel_event, num_ctx, tools, executor,
                   on_chunk=None, emit_tool_details=False, timing_collector=None, worker_call=False):
        for i, round_calls in enumerate(rounds):
            set_react_round(i)
            for name, args in round_calls:
                await executor(name, args)
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** A shop is defined in several Acts.\n"
            "2. **References:** None.")}

    return await run_worker_agent(loop, lambda *a, **k: None, "q", "test-model", None, 0)


def _search_rounds(n, prefix="q"):
    return [[("search_legislation", {"query": f"{prefix}{i}"})] for i in range(n)]


@pytest.mark.asyncio
async def test_a_stopped_worker_says_so_in_its_block(monkeypatch, calls):
    result = await _worker_run(monkeypatch, _search_rounds(10) + [
        [("search_legislation_sections", {"legislation_id": "asp/2002/13", "query": "shop"})]])
    content = result["content"]
    assert "Searching was cut short" in content
    assert content.index("[SEARCH SCOPE") < content.index("Searching was cut short")
    assert "2 further searches it asked for were not run" in content
    assert "Searched the legislation index 8 time(s)" in content
    assert [e["tool"] for e in result["searches"]].count("discovery_budget") == 2
    assert calls[-1][0] == "search_legislation_sections"


@pytest.mark.asyncio
async def test_a_worker_within_budget_is_unchanged(monkeypatch, calls):
    result = await _worker_run(monkeypatch, _search_rounds(8))
    assert "cut short" not in result["content"]
    assert all(e["tool"] != "discovery_budget" for e in result["searches"])


@pytest.mark.asyncio
async def test_case_law_only_is_never_budgeted(monkeypatch, calls):
    result = await _worker_run(
        monkeypatch, [[("search_case_law", {"query": f"c{i}"})] for i in range(12)],
        research_mode="case_law_only")
    assert "cut short" not in result["content"]
    assert len(calls) == 12


@pytest.mark.asyncio
async def test_the_manager_answer_carries_the_clause(monkeypatch, calls):
    from src.agent.agent_core import process_user_request

    async def worker(*a, **kw):
        return await _worker_run(monkeypatch, _search_rounds(9))

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        await tool_executor("delegate_research", {"query": "q2"})
        return {"role": "assistant", "content": "Here are the definitions."}

    final = await process_user_request(
        manager, worker, [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    content = final["content"]
    assert content.startswith("Here are the definitions.")
    assert content.count("*Search scope:") == 1
    assert ("Searching was also limited: 2 research steps reached the cap on how much "
            "searching a step may do, and 2 further searches it asked for were not run") in content
    assert "cut short" not in content            # the agent-facing limb is stripped
    assert "SEARCH SCOPE" not in content
    # A budget stop is not a halt: no halt notice, no incompleteness flag.
    assert "This answer is incomplete" not in content
    assert "research_incomplete" not in final


_PLAN = {"scope_note": "", "steps": [
    {"id": 1, "title": "Shops", "detail": "Definitions."},
    {"id": 2, "title": "Trading", "detail": "Sunday trading."},
]}


async def _synthesis(messages, model, cancel_event, num_ctx, tools, tool_executor,
                     on_chunk=None, emit_tool_details=False, timing_collector=None, worker_call=False):
    _synthesis.seen = messages[-1]["content"]
    return {"role": "assistant", "content": "Integrated report."}


@pytest.mark.asyncio
async def test_deep_research_steps_carry_their_stops_to_synthesis_and_lawyer(monkeypatch, calls):
    async def worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        return await _worker_run(monkeypatch, _search_rounds(9, prefix=query[:5]))

    result = await run_deep_research(
        _synthesis, worker, _PLAN, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0)
    assert _synthesis.seen.count("Searching was cut short") == 2
    content = result["content"]
    assert content.startswith("Integrated report.")
    assert "2 research steps reached the cap" in content
    assert "research_incomplete" not in result


# ---------------------------------------------------------------------------
# 7. Both providers publish the round to the round's tool calls
# ---------------------------------------------------------------------------

def _or_tool_round(*queries):
    calls_ = [{"index": i, "id": f"c{i}", "function": {
        "name": "search_legislation", "arguments": json.dumps({"query": q})}}
        for i, q in enumerate(queries)]
    return _sse(json.dumps({"choices": [{"delta": {"tool_calls": calls_}}]}))


def _ollama_tool_round(*queries):
    return json.dumps({"message": {"content": "", "tool_calls": [
        {"function": {"name": "search_legislation", "arguments": {"query": q}}}
        for q in queries]}, "done": True}) + "\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("client", ["openrouter", "ollama"])
async def test_chat_loop_publishes_the_round_to_every_call_in_it(client, _no_sleep, _mock_http):
    if client == "openrouter":
        bodies = [_or_tool_round("a", "b"), _or_tool_round("c"),
                  _sse('{"choices":[{"delta":{"content":"done"}}]}')]
    else:
        bodies = [_ollama_tool_round("a", "b"), _ollama_tool_round("c"),
                  '{"message":{"content":"done"},"done":true}\n']
    _mock_http(_sequence_handler([httpx.Response(200, text=b) for b in bodies]))
    seen = []

    async def executor(name, args):
        seen.append((args["query"], current_react_round()))
        return "{}"

    mod = openrouter_client if client == "openrouter" else ollama_client
    result = await mod.chat_loop(
        messages=[{"role": "user", "content": "q"}], model="test/model",
        cancel_event=None, num_ctx=0,
        tools=[{"type": "function", "function": {
            "name": "search_legislation", "description": "d",
            "parameters": {"type": "object", "properties": {}}}}],
        tool_executor=executor,
    )
    assert result["content"] == "done"
    assert sorted(seen) == [("a", 0), ("b", 0), ("c", 1)]


# ---------------------------------------------------------------------------
# 8. The instruments
# ---------------------------------------------------------------------------

def _tool(name, t, blocked=False, memo=False, **args):
    return {"name": name, "args": args, "started_at": t, "memo_hit": memo,
            "budget_blocked": blocked, "final_result": json.dumps(
                {"notice": "x", "searched": False} if blocked else _SEARCH)}


def _doc(*delegations):
    return {"session_id": "9999", "rep": 1, "turns": [{
        "turn": 1, "answer": "A.", "audit": {"schema_version": 3,
                                             "delegations": list(delegations)}}]}


def test_discovery_counts_rounds_and_keeps_refused_calls_out():
    tools = []
    for rnd in range(8):                      # 8 search rounds, 2 calls each
        t = rnd * 5.0
        tools += [_tool("search_legislation", t, query=f"a{rnd}"),
                  _tool("search_legislation", t + 0.01, memo=rnd > 0, query=f"a{rnd}")]
    tools += [_tool("search_legislation", 60.0, blocked=True, query="late"),
              _tool("search_legislation_sections", 60.02, legislation_id="asp/2002/13"),
              _tool("search_legislation_sections", 65.0, legislation_id="asp/2002/13")]
    (r,) = rr.discovery_runs(_doc({"kind": "delegation", "tools": tools}))
    assert r["search_rounds"] == 8
    assert r["rounds_rebuilt"] == 10
    assert r["leg_refused"] == 1
    assert (r["leg"], r["leg_memo"]) == (9, 7)
    assert r["leg_distinct"] == 8             # "late" never ran


def test_scope_record_does_not_expect_a_refused_search_in_the_record():
    report = "Findings." + worker_scope_block(_leg("a", "b") + _stops("c"), {})
    dg = {"report": report, "tools": [_tool("search_legislation", 0, query="a"),
                                      _tool("search_legislation", 0, query="b"),
                                      _tool("search_legislation", 5, blocked=True, query="c")]}
    assert rr.scope_record_gap(dg) == (2, 0, 2)


def test_a_refused_query_is_not_a_searched_term_and_not_a_search():
    turn = _doc({"kind": "delegation", "tools": [
        _tool("search_legislation", 0, query="ran"),
        _tool("search_legislation", 5, blocked=True, query="refused")]})["turns"][0]
    assert rr._turn_queries(turn) == ["ran"]
    only_refused = _doc({"kind": "delegation", "tools": [
        _tool("search_legislation", 5, blocked=True, query="refused")]})
    (row,) = rr.nosearch_rows(only_refused)
    assert row["searched_now"] is False


def test_the_discovery_command_prints_the_round_table(tmp_path, capsys):
    tools = [_tool("search_legislation", i * 5.0, query=f"q{i}") for i in range(9)]
    (tmp_path / "9999_rep1.json").write_text(
        json.dumps(_doc({"kind": "delegation", "tools": tools})), encoding="utf-8")
    assert rr.main(["--dir", str(tmp_path), "discovery", "--runs"]) == 0
    out = capsys.readouterr().out
    assert "REFUSED by the P2.7 budget: 0" in out
    k8 = next(ln for ln in out.splitlines() if ln.startswith("  K8 |"))
    assert k8.split("|")[1].split() == ["0", "of", "0", "1", "of", "1"]


def _slot_doc(rep, kept, halted, refused=0):
    tools = [_tool("search_legislation", i * 5.0, query=f"q{i}") for i in range(3)]
    tools += [_tool("search_legislation", 100.0, blocked=True, query="late")] * refused
    return {"session_id": "9999", "rep": rep, "turns": [{
        "turn": 1, "answer": "Prose." + answer_scope_footer(_leg("q0"), {}),
        "timing": {"sources_kept": kept, "max_turns_halted": int(halted)},
        "audit": {"schema_version": 3, "delegations": [{
            "kind": "delegation", "tools": tools,
            "halted": {"reason": "step_cap", "limit": 20, "steps": 20} if halted else None}]},
    }]}


def test_the_pass_bar_compares_halts_and_sources_per_slot(tmp_path, capsys):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    for rep, (kept, halted) in enumerate([(10, True), (6, False)], 1):
        (before / f"9999_rep{rep}.json").write_text(
            json.dumps(_slot_doc(rep, kept, halted)), encoding="utf-8")
    for rep, kept in enumerate([9, 9], 1):
        (after / f"9999_rep{rep}.json").write_text(
            json.dumps(_slot_doc(rep, kept, False, refused=2)), encoding="utf-8")
    (row,) = rr.discovery_turns(_slot_doc(1, 7, True, refused=1))
    assert (row["sources_kept"], row["at_cap"], row["halted_runs"], row["leg"],
            row["refused"], row["chars"]) == (7, True, 1, 3, 1, len("Prose."))
    assert rr.main(["--dir", str(after), "discovery", "--before", str(before),
                    "--only", "9999"]) == 0
    out = capsys.readouterr().out
    assert "HALTED worker runs / rep                   0.5 (n=2) ->     0.0 (n=2)" in out
    assert "searches refused by the budget / rep       0.0 (n=2) ->     2.0 (n=2)" in out
    assert "sources_kept fell in 0 of 1" in out
    assert "sources    8.0 ->    9.0 held" in out
    # And the other direction.
    for rep in (1, 2):
        (after / f"9999_rep{rep}.json").write_text(
            json.dumps(_slot_doc(rep, 7, False)), encoding="utf-8")
    rr.main(["--dir", str(after), "discovery", "--before", str(before)])
    out = capsys.readouterr().out
    assert "sources_kept fell in 1 of 1" in out
    assert "sources    8.0 ->    7.0 FELL" in out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_the_legislation_profile_shows_an_indicator_and_raises_no_breach():
    leg = EFFICIENCY_PROFILES["legislation"]
    assert leg["bands"]["budget_blocked"] == (0.05, 0.15)
    assert "max_budget_blocked" not in leg
    assert EFFICIENCY_PROFILES["parliamentary_records"]["max_budget_blocked"] == 0


# ---------------------------------------------------------------------------
# 9. Fail-soft
# ---------------------------------------------------------------------------

def test_an_unknown_round_fails_open_and_warns_once(caplog):
    b = new_search_budget("legislation_only")
    assert current_react_round() is None
    assert not any(legislation_budget_blocks(b, "search_legislation") for _ in range(30))
    assert sum("no ReAct round" in r.message for r in caplog.records) == 1


@pytest.mark.parametrize("budget", [
    {"kind": "legislation_rounds", "limit": "eight", "rounds": set()},
    {"kind": "legislation_rounds", "limit": 8, "rounds": None},
    {"kind": "legislation_rounds", "limit": 8, "rounds": []},
    {"kind": "legislation_rounds"},
    {"remaining": 0},
    None,
    {},
])
def test_a_broken_budget_never_raises_and_never_refuses(budget):
    set_react_round(99)
    assert legislation_budget_blocks(budget, "search_legislation") is False
    json.loads(legislation_stop_message(budget))


@pytest.mark.parametrize("entries", [
    [None, 3, "x"],
    [{"tool": "discovery_budget"}],
    [{"tool": "discovery_budget", "query": None, "limit": None, "run": None}],
    [{"tool": "discovery_budget", "query": 12, "limit": "x"}],
])
def test_odd_records_never_raise(entries):
    _budget_limb(entries)
    _budget_footer_clause(entries)
    worker_scope_block(_leg("q") + [e for e in entries if isinstance(e, dict)], {})
    answer_scope_footer(_leg("q") + [e for e in entries if isinstance(e, dict)], {})


def test_recording_never_raises():
    record_budget_stop(None, "search_legislation", {"query": "q"}, {})
    log = []
    record_budget_stop(log, "search_legislation", None, None)
    assert log == [{"tool": "discovery_budget", "blocked_tool": "search_legislation",
                    "query": "", "limit": None, "run": None}]


def test_a_broken_clause_never_costs_the_footer(monkeypatch):
    def boom(entries):
        raise RuntimeError("budget disclosure broke")

    monkeypatch.setattr(search_scope, "_budget_rows", boom)
    log = _leg("q") + _stops("late")
    assert _budget_footer_clause(log) == "" and _budget_limb(log) == ""
    assert answer_scope_footer(log, {}).endswith("absent from the law.*")
    assert worker_scope_block(log, {}).endswith("[/SEARCH SCOPE]")
