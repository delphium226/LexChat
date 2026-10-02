"""P4.17 (bucket B5): the scope line for a turn that searched only WITHIN
instruments.

A turn that reached its legislation by lookup and section search, and ran no
`search_legislation`, got no fresh footer (gated on that tool), no carried line
(it opens "no search ... was run for this reply", false after a section search)
and, unless a lookup found something not held, no lookup line. A negative on
such a turn reached the lawyer with no attribution, and P2.3's, P2.5's and
P3.5's clauses were dropped by the gate.

What this file pins (the row's booked acceptance, item 1):

1. `section_scope_footer` fires if and only if the turn recorded a
   `search_legislation_sections` and no `search_legislation`, on the Manager
   path (after the carried line, before the lookup line) and the Deep Research
   path (after the fresh footer);
2. it names the instruments by id and the terms in `_listed_terms`' form;
3. it carries the fresh footer's clauses (section budget, enabling, relations,
   currency, lookup, case law), in the fresh footer's order;
4. it is one `*Search scope: ...*` line, removed whole by
   `strip_answer_footer` (P4.14's echo-then-real case included) and by
   `replay_report._without_footer`;
5. P2.8's round trip: `_earlier_footers` does not read it, and a later
   no-search turn's carried line is unchanged by it;
6. `_earlier_lookups` reads its lookup clause back;
7. it is not suppressed by `scope_unknown`;
8. its new sentence trips no detector but `NEG_BLAMED_INDEX`;
9. the grader line, `replay_report sectionscope`.

Every text here is synthetic.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src.agent.agent_core import run_deep_research, run_worker_agent  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.utils.search_scope import (  # noqa: E402
    CASE_LAW_DOCTRINE_SENTENCE,
    SECTION_SCOPE_SENTENCE,
    _budget_footer_clause,
    _currency_footer_clause,
    _earlier_footers,
    _earlier_lookups,
    _enabling_footer_clause,
    _listed_terms,
    _lookup_footer_clause,
    _relations_footer_clause,
    _section_budget_footer_clause,
    answer_scope_footer,
    carried_scope_footer,
    case_law_scope_clause,
    case_law_scope_footer,
    lookup_scope_footer,
    record_currency,
    section_scope_footer,
    strip_answer_footer,
)

_ID = "ssi/1901/1"


def _sec(*queries, lid=_ID):
    return [{"tool": "search_legislation_sections", "query": q, "legislation_id": lid,
             "shown": 10, "matched": None} for q in queries]


def _leg(*queries):
    return [{"tool": "search_legislation", "query": q, "legislation_id": "",
             "shown": 5, "matched": 141} for q in queries]


def _cl(*queries):
    return [{"tool": "search_case_law", "query": q, "shown": 50, "ok": True}
            for q in queries]


def _lookup(status, lid="ssi/1901/2", label="SSI 1901/2"):
    return [{"tool": "lookup", "legislation_id": lid, "label": label, "status": status}]


def _history(*footers, answer="An earlier answer."):
    msgs = []
    for i, footer in enumerate(footers):
        msgs.append({"role": "user", "content": f"question {i}"})
        msgs.append({"role": "assistant", "content": answer + footer})
    msgs.append({"role": "user", "content": "follow-up"})
    return msgs


def _all_clauses_log():
    """A section-search turn carrying every clause the fresh footer can."""
    log = _sec("widget licence", "gadget")
    log += [{"tool": "discovery_budget", "blocked_tool": "search_legislation",
             "query": "late", "limit": 8, "run": "a1"}]
    log += [{"tool": "section_budget", "blocked_tool": "search_legislation_sections",
             "legislation_id": _ID, "query": "late section", "limit": 3, "run": "a1"}]
    log += [{"tool": "enabling_power", "legislation_id": _ID, "stated": False}]
    log += [{"tool": "change_record", "legislation_id": _ID, "direction": "to",
             "relations": 0, "by_other": 0, "others": [], "complete": True}]
    record_currency(log, "get_legislation_changes", {"legislation_id": _ID},
                    {"legislation_id": _ID, "provisions_commenced": 2,
                     "commencement_orders_of_amendments": 0,
                     "repeal_or_revocation_relations": 0})
    log += _lookup("not_held")
    log += _cl("widget case")
    return log


# ---------------------------------------------------------------------------
# 1. The gate, at the builder
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("log,fires", [
    (_sec("q"), True),
    (_sec("q") + _lookup("held"), True),
    (_sec("q") + _cl("c"), True),
    (_sec("q") + _leg("r"), False),           # the fresh footer's turn
    (_leg("r"), False),
    (_lookup("not_held"), False),              # P3.7's lookup line's turn
    (_cl("c"), False),                         # P2.4's case-law line's turn
    ([{"tool": "section_budget", "blocked_tool": "search_legislation_sections",
       "legislation_id": _ID, "query": "q", "limit": 3, "run": "a1"}], False),
    ([], False),
    (None, False),
])
def test_it_fires_if_and_only_if_a_section_search_ran_and_no_ranked_search(log, fires):
    assert bool(section_scope_footer(log)) is fires


def test_a_turn_with_a_ranked_search_keeps_the_fresh_footer_unchanged():
    log = _leg("widget order") + _sec("article 4")
    assert section_scope_footer(log) == ""
    assert answer_scope_footer(log, {}).startswith(
        "\n\n*Search scope: the legislation index was searched for")


# ---------------------------------------------------------------------------
# 2. What it names
# ---------------------------------------------------------------------------

def test_it_names_the_instruments_by_id_and_the_terms_in_listed_terms_form():
    log = _sec('"widget licence"', "gadget", "sprocket") + _sec("other", lid="uksi/1902/7")
    line = section_scope_footer(log)
    _, listed = _listed_terms(e["query"] for e in log)
    assert line.startswith(
        f"\n\n*Search scope: for this reply the text of {_ID} and uksi/1902/7 in the "
        f"legislation index was searched for {listed}. {SECTION_SCOPE_SENTENCE}")
    assert '"widget licence", "gadget" (2 further queries not listed)' in line


def test_more_than_three_instruments_are_counted_not_listed():
    log = []
    for i in range(5):
        log += _sec("q", lid=f"ssi/1901/{i + 1}")
    line = section_scope_footer(log)
    assert "the text of ssi/1901/1, ssi/1901/2 and ssi/1901/3 and 2 more in the" in line


def test_a_section_search_with_no_terms_or_id_still_says_what_ran():
    log = [{"tool": "search_legislation_sections", "query": "", "legislation_id": ""}]
    line = section_scope_footer(log)
    assert line.startswith("\n\n*Search scope: for this reply the text of an instrument "
                           "in the legislation index was searched. ")


# ---------------------------------------------------------------------------
# 3. The clause set
# ---------------------------------------------------------------------------

def test_it_carries_the_fresh_footers_clauses_in_the_fresh_footers_order():
    log = _all_clauses_log()
    clauses = [
        _budget_footer_clause(log),
        _section_budget_footer_clause(log),
        _enabling_footer_clause(log),
        _relations_footer_clause(log),
        _currency_footer_clause(log),
        _lookup_footer_clause(log),
        case_law_scope_clause(log),
    ]
    assert all(clauses)
    line = section_scope_footer(log)
    head = line[: line.index(SECTION_SCOPE_SENTENCE) + len(SECTION_SCOPE_SENTENCE)]
    assert line == head + "".join(clauses) + "*"
    # The case-law clause is last, so the line still ends with the doctrine
    # sentence, as the fresh footer does.
    assert line.endswith(CASE_LAW_DOCTRINE_SENTENCE + "*")


def test_a_bare_section_search_carries_no_clause():
    line = section_scope_footer(_sec("q"))
    assert line.endswith(SECTION_SCOPE_SENTENCE + "*")


# ---------------------------------------------------------------------------
# 4. One line, stripped whole
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("log", [_sec("q"), _all_clauses_log()])
def test_it_is_one_line_and_is_stripped_whole(log):
    line = section_scope_footer(log)
    assert line.startswith("\n\n*Search scope: ") and line.endswith("*")
    assert "\n" not in line.strip()
    assert line.count("*Search scope:") == 1
    prose = "The Widget Order 1901 defines a widget."
    assert strip_answer_footer(prose + line) == prose
    # P4.14's case: the model echoed the line, then the code appended its own.
    assert strip_answer_footer(prose + line + line) == prose
    assert rr._without_footer(prose + line) == prose


# ---------------------------------------------------------------------------
# 5 and 6. P2.8's round trip, and P3.7's earlier-lookup parse
# ---------------------------------------------------------------------------

def test_p28_never_reads_it_as_a_fresh_footer():
    line = section_scope_footer(_all_clauses_log())
    assert _earlier_footers(_history(line)) == []
    # So a later no-search turn after it alone has nothing to carry ...
    assert carried_scope_footer(_history(line), []) == ""


@pytest.mark.parametrize("log", [_sec("q"), _sec("q") + _cl("c")])
def test_a_later_no_search_turns_carried_line_is_unchanged_by_it(log):
    fresh = answer_scope_footer(_leg("widget order"), {})
    line = section_scope_footer(log)
    with_it = carried_scope_footer(_history(fresh, line), [])
    without_it = carried_scope_footer(_history(fresh, ""), [])
    assert with_it and with_it == without_it


def test_its_lookup_clause_is_read_back_by_p37():
    line = section_scope_footer(_sec("q") + _lookup("not_held") +
                                _lookup("held_without_text", "ssi/1901/3", "SSI 1901/3"))
    got = {(e["label"], e["status"]) for e in _earlier_lookups(_history(line))}
    assert got == {("SSI 1901/2", "not_held"), ("SSI 1901/3", "held_without_text")}
    # ... which is how a later unsearched turn restates it (P3.7, by design).
    later = lookup_scope_footer([], _history(line))
    assert "Earlier in this conversation, SSI 1901/2 was looked up" in later


# ---------------------------------------------------------------------------
# 8. Detectors
# ---------------------------------------------------------------------------

def test_its_new_sentence_trips_no_detector_but_neg_blamed_index():
    """Batch 3's lesson: C's first wording ("did not return") tripped
    `NEG_ASSERTED`, and "ranked" trips `NEG_LIMITS`. The attribution is the
    point, so `NEG_BLAMED_INDEX` is the one trip, by design."""
    s = SECTION_SCOPE_SENTENCE
    assert rr.NEG_BLAMED_INDEX.search(s)
    for name in ("NEG_ASSERTED", "NOT_FOUND", "NEG_BLAMED_USER", "IN_FORCE_CLAIM",
                 "HALT_PARAPHRASE", "HALT_AS_TIMEOUT", "HALT_LITERAL", "NEG_LIMITS",
                 "NEG_TERMS", "SCOTS_CASELAW_GAP", "NEGATIVE_EXPLAINED"):
        assert not getattr(rr, name).search(s), name
    assert not rr._names_search_terms(s)
    assert rr.derivation_claims(s)[0] == []
    assert not any(rr._currency_asserted(x) for x in rr._sentences(s))
    assert rr.caselaw_gap_statements(s) == []
    # The head names the terms, as the fresh footer does; the line as a whole
    # trips no negative detector of its own.
    line = section_scope_footer(_sec("widget licence", "gadget")).strip()
    assert rr._names_search_terms(line)
    assert not rr.NEG_ASSERTED.search(line)
    assert not rr.NOT_FOUND.search(line)


def test_it_never_raises():
    assert section_scope_footer([{"tool": "search_legislation_sections",
                                  "query": None, "legislation_id": None}])
    assert section_scope_footer([object()]) == ""


# ---------------------------------------------------------------------------
# 1 and 7, end to end: the Manager path and the Deep Research path
# ---------------------------------------------------------------------------

def _fake_result(name, args):
    if name == "search_case_law":
        return {"results": [{"title": "Alpha v Beta", "ncn": "[2020] EWHC 1",
                             "court": "ewhc", "date": "2020-01-01",
                             "url": "https://caselaw.nationalarchives.gov.uk/ewhc/2020/1"}],
                "total": 1, "query": "q"}
    if name == "lookup_legislation":
        return {"tool": "lookup_legislation", "status": "not_held",
                "legislation_id": "ssi/1901/2", "label": "SSI 1901/2"}
    if name == "search_legislation_sections":
        return {"results": [{"legislation_id": _ID, "title": "Widget Order 1901",
                             "section": "regulation 2",
                             "url": f"http://www.legislation.gov.uk/id/{_ID}/regulation/2",
                             "text": "In this Order, a widget means a small device."}],
                "returned": 1}
    return {"results": [{"legislation_id": _ID, "title": "Widget Order 1901",
                         "url": f"http://www.legislation.gov.uk/id/{_ID}",
                         "status": "revised", "year": 1901, "extent": ["Scotland"]}],
            "returned": 1, "total": 141}


async def _turn(monkeypatch, worker_calls, messages=None, delegations=1,
                fail_first=False, research_mode="legislation_and_case_law"):
    from src.agent import agent_shared
    from src.agent.agent_core import process_user_request

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": research_mode,
        "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return json.dumps(_fake_result(name, args))

    async def worker_chat_loop(messages, model, cancel_event, num_ctx, tools,
                               executor, on_chunk=None, emit_tool_details=False,
                               timing_collector=None, worker_call=False):
        for name, args in worker_calls:
            await executor(name, args)
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** A widget is a small device.\n"
            "2. **References:** None.")}

    state = {"n": 0}

    async def worker(*a, **kw):
        state["n"] += 1
        if fail_first and state["n"] == 1:
            raise RuntimeError("provider stalled")
        return await run_worker_agent(
            worker_chat_loop, lambda *x, **y: None, "q", "test-model", None, 0)

    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        for _ in range(delegations):
            await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": "Answer."}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        return await process_user_request(
            manager, worker, messages or [{"role": "user", "content": "q"}],
            "test-model", None, None, 0)
    finally:
        set_request_provider_config({})


_SEC_CALL = ("search_legislation_sections", {"legislation_id": _ID, "query": "widget"})
_LEG_CALL = ("search_legislation", {"query": "widget order"})
_LOOKUP_CALL = ("lookup_legislation", {"legislation_id": "ssi/1901/2"})
_CL_CALL = ("search_case_law", {"query": "widget case"})
# What `run_worker_tool` records for `_SEC_CALL`: the search, and (an SSI's
# text was looked at) P2.3's enabling-power entry, which the line then states.
_SEC_RECORD = _sec("widget") + [
    {"tool": "enabling_power", "legislation_id": _ID, "stated": False}]


@pytest.mark.asyncio
async def test_manager_a_section_search_only_turn_gets_the_line(monkeypatch):
    final = await _turn(monkeypatch, [_SEC_CALL], research_mode="legislation_only")
    content = final["content"]
    assert content == "Answer." + section_scope_footer(_SEC_RECORD)
    assert content.count("*Search scope:") == 1


@pytest.mark.asyncio
async def test_manager_the_line_carries_the_lookup_clause_and_no_lookup_line_fires(monkeypatch):
    """Before the lookup line: a turn that searched within an instrument AND
    looked one up gets ONE line naming both, not P3.7's "for this reply," line."""
    final = await _turn(monkeypatch, [_LOOKUP_CALL, _SEC_CALL],
                        research_mode="legislation_only")
    content = final["content"]
    assert content.count("*Search scope:") == 1
    assert "*Search scope: for this reply the text of ssi/1901/1" in content
    assert "SSI 1901/2 was looked up by its number and is not held in this index" in content
    assert "*Search scope: for this reply, SSI" not in content


@pytest.mark.asyncio
async def test_manager_a_hybrid_turn_gets_the_line_with_the_case_law_clause_last(monkeypatch):
    final = await _turn(monkeypatch, [_SEC_CALL, _CL_CALL])
    content = final["content"]
    assert content.count("*Search scope:") == 1
    assert "*Search scope: for this reply the text of ssi/1901/1" in content
    assert content.endswith(CASE_LAW_DOCTRINE_SENTENCE + "*")
    assert case_law_scope_footer(_cl("widget case")).strip() not in content


@pytest.mark.asyncio
async def test_manager_after_the_carried_line_a_searched_follow_up_is_not_carried(monkeypatch):
    """The carried line comes first and stays silent on this turn (it searched),
    so the section line, not P2.8's, describes it."""
    fresh = answer_scope_footer(_leg("earlier widget search"), {})
    final = await _turn(monkeypatch, [_SEC_CALL], messages=_history(fresh))
    content = final["content"]
    assert "no search of the legislation index was run for this reply" not in content
    assert "earlier widget search" not in content
    assert content.endswith(section_scope_footer(_SEC_RECORD))


@pytest.mark.asyncio
async def test_manager_a_ranked_search_turn_is_unchanged(monkeypatch):
    final = await _turn(monkeypatch, [_LEG_CALL, _SEC_CALL],
                        research_mode="legislation_only")
    content = final["content"]
    assert "*Search scope: the legislation index was searched for" in content
    assert "for this reply the text of" not in content


@pytest.mark.asyncio
async def test_manager_a_failed_delegation_does_not_suppress_the_line(monkeypatch):
    """`scope_unknown` silences the carried and lookup lines, because "no search
    was run" might be false. This line states only the searches this turn
    recorded, and those ran, so it still goes out."""
    final = await _turn(monkeypatch, [_SEC_CALL], delegations=2, fail_first=True,
                        research_mode="legislation_only")
    assert final["content"].endswith(section_scope_footer(_SEC_RECORD))


def _dr_worker(results):
    async def run_worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                         emit_tool_details=False, timing_collector=None,
                         tool_memo=None, retrieved_urls=None):
        run_worker.n += 1
        return results[run_worker.n - 1]
    run_worker.n = 0
    return run_worker


async def _synthesis(messages, model, cancel_event, num_ctx, tools, tool_executor,
                     on_chunk=None, emit_tool_details=False, timing_collector=None,
                     worker_call=False):
    return {"role": "assistant", "content": "Integrated report."}


_PLAN = {"scope_note": "", "steps": [
    {"id": 1, "title": "Order", "detail": "The Widget Order."},
    {"id": 2, "title": "Case law", "detail": "Widget cases."},
]}


@pytest.mark.asyncio
async def test_deep_research_a_report_from_section_searches_only_gets_the_line():
    log1 = _sec("widget") + _lookup("not_held")
    log2 = _cl("widget case")
    worker = _dr_worker([
        {"content": "f1", "sources": [], "searches": log1},
        {"content": "f2", "sources": [], "searches": log2},
    ])
    result = await run_deep_research(
        _synthesis, worker, _PLAN, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0)
    assert result["content"] == "Integrated report." + section_scope_footer(log1 + log2)
    assert result["content"].count("*Search scope:") == 1


@pytest.mark.asyncio
async def test_deep_research_a_ranked_search_keeps_the_fresh_footer_first():
    log1 = _leg("widget order") + _sec("widget")
    worker = _dr_worker([
        {"content": "f1", "sources": [], "searches": log1},
        {"content": "f2", "sources": [], "searches": []},
    ])
    result = await run_deep_research(
        _synthesis, worker, _PLAN, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0)
    assert result["content"] == "Integrated report." + answer_scope_footer(log1, {})


# ---------------------------------------------------------------------------
# 9. The grader line: `replay_report sectionscope`
# ---------------------------------------------------------------------------

def _doc(*turns):
    return {"session_id": "9999", "rep": 1, "turns": list(turns)}


def _t(turn, answer, *tool_names, blocked=()):
    tools = [{"name": n} for n in tool_names]
    tools += [{"name": n, "budget_blocked": True} for n in blocked]
    return {"turn": turn, "chat_mode": "conversational", "answer": answer,
            "research_mode": "legislation_only",
            "audit": {"delegations": [{"tools": tools}]}}


_LINE = section_scope_footer(_sec("widget"))
_FRESH = answer_scope_footer(_leg("widget order"), {})


def test_the_grader_verdicts():
    rows = rr.sectionscope_rows(_doc(
        _t(1, "A." + _LINE, "search_legislation_sections", "lookup_legislation"),
        _t(2, "A.", "search_legislation_sections"),                  # MISSING
        _t(3, "A." + _LINE, "search_legislation", "search_legislation_sections"),
        _t(4, "A." + _LINE, "get_legislation_text"),                 # no section search
        _t(5, "A." + _FRESH, "search_legislation", "search_legislation_sections"),
        _t(6, "A.", "search_legislation_sections", blocked=("search_legislation",)),
        _t(7, "A.", blocked=("search_legislation_sections",)),       # refused: not run
        _t(8, ""),                                                   # unanswered
    ))
    got = [(r["turn"], r["shape"], r["line"], rr.sectionscope_verdict(r)) for r in rows]
    assert got == [
        (1, True, True, None),
        (2, True, False, "MISSING"),
        (3, False, True, "MISATTRIBUTED"),
        (4, False, True, "MISATTRIBUTED"),
        (5, False, False, None),
        (6, True, False, "MISSING"),
        (7, False, False, None),
    ]


def test_the_lookup_and_case_law_lines_are_not_read_as_the_section_line():
    lookup_line = lookup_scope_footer(_sec("q") + _lookup("not_held"))
    assert lookup_line.startswith("\n\n*Search scope: for this reply,")
    for other in (lookup_line, case_law_scope_footer(_cl("c")), _FRESH,
                  carried_scope_footer(_history(_FRESH), [])):
        assert other and rr.SECTION_SCOPE not in other
    assert rr.SECTION_SCOPE in _LINE


def test_the_subcommand_exits_1_on_a_finding_and_0_when_clean(tmp_path, capsys):
    clean, missing, misattr = (tmp_path / n for n in ("clean", "missing", "misattr"))
    for d in (clean, missing, misattr):
        d.mkdir()
    (clean / "9999_rep1.json").write_text(json.dumps(_doc(
        _t(1, "A." + _LINE, "search_legislation_sections"),
        _t(2, "B." + _FRESH, "search_legislation"))), encoding="utf-8")
    (missing / "9999_rep1.json").write_text(json.dumps(_doc(
        _t(1, "A.", "search_legislation_sections"))), encoding="utf-8")
    (misattr / "9999_rep1.json").write_text(json.dumps(_doc(
        _t(1, "A." + _LINE, "search_legislation"))), encoding="utf-8")
    assert rr.main(["--dir", str(clean), "sectionscope"]) == 0
    assert rr.main(["--dir", str(missing), "sectionscope"]) == 1
    out = capsys.readouterr().out
    assert "MISSING       shape turn without the line      1" in out
    assert rr.main(["--dir", str(misattr), "sectionscope"]) == 1
    out = capsys.readouterr().out
    assert "MISATTRIBUTED line on a turn not of the shape  1" in out
