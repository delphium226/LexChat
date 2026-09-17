"""P2.4 (bucket B12): a code-emitted disclosure of the case-law corpus gap.

The National Archives' Find Case Law holds Scottish appeals decided by the UK
Supreme Court, and no decision of the Court of Session, the Sheriff Appeal
Court, the Sheriff Courts or the High Court of Justiciary. A Scots-law query
does not come back empty: it comes back with 50 English judgments. So the one
note the code already had (on ZERO results) never fired where it mattered, and
6375 turn 2, a Deep Research run with 18-30 case-law searches, told the lawyer
nothing.

**Gate: any turn that called `search_case_law`** (user decision, 2026-09-17).
6375 ran with no jurisdiction filter, and reading the question for "Scots law"
would be a prose detector in the product.

**What this file pins, in the order the handover listed the hazards:**

1. the wording is the true one (UKSC Scottish appeals ARE indexed, four courts
   are not, no "Privy Council", no "comprehensively");
2. it reaches the lawyer on the Manager, Deep Research and `case_law_only`
   paths, and on nothing that did not search case law;
3. it is ONE line: joined to the legislation line when there is one, so P2.8's
   carried-line parse (last line only) and `corpus`'s duplicate counter are
   both undisturbed;
4. it is stripped by `_without_footer` and `_ECHOED_FOOTER` and trips no
   detector, so the model column stays the model's;
5. it is fail-soft.
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
from src.agent.agent_core import run_deep_research, run_worker_agent  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.utils import search_scope  # noqa: E402
from src.utils.search_scope import (  # noqa: E402
    CASE_LAW_COVERAGE_SENTENCE,
    _earlier_footers,
    _lawyer_filters_phrase,
    answer_scope_footer,
    carried_scope_footer,
    case_law_scope_clause,
    case_law_scope_footer,
    record_case_law_search,
    strip_answer_footer,
    worker_scope_block,
)

FOUR_COURTS = ("Court of Session", "Sheriff Appeal Court", "Sheriff Courts",
               "High Court of Justiciary")


def _cl(*queries, ok=True):
    return [{"tool": "search_case_law", "query": q, "shown": 50, "ok": ok}
            for q in queries]


def _leg(*queries):
    return [{"tool": "search_legislation", "query": q, "legislation_id": "",
             "shown": 5, "matched": 141} for q in queries]


def _history(*footers, answer="An earlier answer."):
    msgs = []
    for i, footer in enumerate(footers):
        msgs.append({"role": "user", "content": f"question {i}"})
        msgs.append({"role": "assistant", "content": answer + footer})
    msgs.append({"role": "user", "content": "follow-up"})
    return msgs


def _caselaw_result(n=50, scottish=False):
    """A `search_case_law` response in its real shape: 50 non-Scottish judgments,
    which is what a Scots-law query returns (P5.2)."""
    rows = [{"title": f"Party {i} v Party {i + 1}", "ncn": f"[2020] EWHC {i}",
             "court": "ewhc", "date": "2020-01-01",
             "url": f"https://caselaw.nationalarchives.gov.uk/ewhc/2020/{i}"}
            for i in range(n)]
    if scottish:
        rows[0] = {"title": "Daly v His Majesty's Advocate (Scotland)",
                   "ncn": "[2025] UKSC 1", "court": "uksc", "date": "2025-01-01",
                   "url": "https://caselaw.nationalarchives.gov.uk/uksc/2025/1"}
    return {"results": rows, "total": n, "query": "q"}


# ---------------------------------------------------------------------------
# 1. The wording
# ---------------------------------------------------------------------------

def test_the_wording_names_the_uksc_route_and_the_four_missing_courts():
    line = case_law_scope_footer(_cl("common interest privilege Scotland"))
    assert "Scottish appeals decided by the UK Supreme Court" in line
    for court in FOUR_COURTS:
        assert court in line
    assert "Inner or Outer House" in line
    # The trap is a FULL result of the wrong jurisdiction, not an empty one.
    assert "may come from courts outside Scotland" in line
    assert '"common interest privilege Scotland"' in line


@pytest.mark.parametrize("forbidden", [
    "Privy Council",            # unverified (three probes proved nothing)
    "comprehensively",          # false: the gap is total
    "no Scottish case law",     # false: UKSC Scottish appeals are indexed
    "Scottish courts are not",
    "may be incomplete",        # vague where the fact is precise
])
def test_the_wording_never_says_the_false_or_vague_thing(forbidden):
    line = case_law_scope_footer(_cl("q"))
    assert forbidden.lower() not in line.lower()


@pytest.mark.asyncio
async def test_the_prompts_and_the_code_no_longer_contradict_each_other():
    """The prompt-side statements are aligned with what the code emits: the
    gap is total, UKSC Scottish appeals are included, and "Privy Council" is
    not claimed as a Scottish route. The zero-result note is read as emitted."""
    from unittest.mock import AsyncMock, patch
    from src import prompts
    from src.agent.agent_shared import run_worker_tool
    from src.agent.tools.schemas import CASE_LAW_TOOLS

    async def chunk(*a, **k):
        return None

    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=json.dumps(_caselaw_result(n=0)))):
        zero_note = await run_worker_tool("search_case_law", {"query": "q"},
                                          "brief", chunk, "test-model")
    assert zero_note.startswith('{"results": []')

    desc = next(t["function"]["description"] for t in CASE_LAW_TOOLS
                if t["function"]["name"] == "search_case_law")
    note = prompts._JURISDICTION_EXTENT_NOTES["scotland"]
    texts = {
        "case-law worker": prompts.WORKER_SYSTEM_PROMPT_CASE_LAW,
        "hybrid worker": prompts.WORKER_SYSTEM_PROMPT_HYBRID,
        "scotland note": note,
        "tool description": desc,
        "zero-result note": zero_note,
    }
    for where, text in texts.items():
        assert "comprehensively index" not in text, where
        assert "Court of Session" in text, where
        assert "Supreme Court" in text or "UKSC" in text, where
    for where in ("case-law worker", "hybrid worker", "scotland note", "tool description"):
        t = texts[where]
        assert "Sheriff Appeal Court" in t and "High Court of Justiciary" in t, where
        assert not re.search(r"Scottish matters[^.]*Privy Council", t), where
    assert "Privy Council decisions" not in desc


# ---------------------------------------------------------------------------
# 2. The record, and the gate
# ---------------------------------------------------------------------------

def test_a_case_law_search_is_recorded_and_nothing_else_is():
    log = []
    record_case_law_search(log, "search_case_law", {"query": "privilege"},
                           json.dumps(_caselaw_result()))
    record_case_law_search(log, "get_case_law_text", {"url": "x"}, "{}")
    record_case_law_search(log, "search_legislation", {"query": "y"}, "{}")
    assert log == [{"tool": "search_case_law", "query": "privilege",
                    "shown": 50, "ok": True}]


@pytest.mark.parametrize("data", [
    "Error executing tool: boom",                               # executor failure
    json.dumps({"error": "Invalid court filter 'csoh'.",       # rejected court code
                "results": [], "total": 0}),
    None,
    12,
])
def test_an_errored_search_is_recorded_as_not_ok(data):
    log = []
    record_case_law_search(log, "search_case_law", {"query": "q"}, data)
    assert len(log) == 1 and log[0]["ok"] is False


def test_a_failed_search_is_never_described_as_run():
    line = case_law_scope_footer(_cl("q", ok=False))
    assert "was attempted" in line and "returned an error" in line
    assert "was searched" not in line
    # The coverage statement is still true, so it still goes out.
    assert CASE_LAW_COVERAGE_SENTENCE in line
    # One success among failures: only what ran is listed as searched.
    mixed = _cl("ran") + _cl("failed", ok=False)
    line = case_law_scope_footer(mixed)
    assert '"ran"' in line and '"failed"' not in line
    assert "attempted" not in line


@pytest.mark.parametrize("log", [None, [], _leg("a"),
                                 [{"tool": "change_record"}, {"tool": "currency"}]])
def test_a_turn_with_no_case_law_search_gets_nothing(log):
    assert case_law_scope_clause(log) == ""
    assert case_law_scope_footer(log) == ""
    assert "case-law" not in answer_scope_footer(log, {})


def test_recording_never_raises():
    record_case_law_search(None, "search_case_law", {}, "{}")
    log = []
    record_case_law_search(log, "search_case_law", None, object())
    assert log and log[0]["ok"] is False


def test_the_worker_block_is_untouched_by_a_case_law_record():
    """Recorded for the lawyer's footer only. A case-law-only step must not get
    a block demanding "the search terms above" with none above (P2.9's defect),
    and a mixed step's block is byte-identical to the one it had before."""
    assert worker_scope_block(_cl("a", "b"), {}) == ""
    leg = _leg("x") + [{"tool": "search_legislation_sections", "query": "y",
                        "legislation_id": "asp/2002/13"}]
    assert worker_scope_block(leg + _cl("a"), {}) == worker_scope_block(leg, {})
    assert worker_scope_block(_cl("a") + leg, {}) == worker_scope_block(leg, {})


# ---------------------------------------------------------------------------
# 3. One line, and P2.8 still reads it
# ---------------------------------------------------------------------------

def test_a_turn_that_searched_both_gets_one_line_with_the_clause_last():
    line = answer_scope_footer(_leg("FOISA section 36") + _cl("limited waiver"), {})
    assert line.startswith("\n\n*Search scope: the legislation index was searched for")
    assert line.count("*Search scope:") == 1
    assert "\n" not in line.strip()
    assert line.endswith("courts outside Scotland.*")
    assert line.index("absent from the law.") < line.index("case-law database")
    # The legislation part is exactly what it was without case law.
    assert line.startswith(answer_scope_footer(_leg("FOISA section 36"), {})[:-1])


@pytest.mark.parametrize("log,cfg", [
    (_leg("q") + _cl("c"), {}),
    (_leg(*[f"q{i}" for i in range(5)]) + _cl(*[f"c{i}" for i in range(9)]),
     {"_jurisdiction": "scotland", "_year_from": 2020}),
    (_leg('"Education (Scotland) Act 1962" 117') + _cl('"Court of Session" privilege'), {}),
    (_leg("q") + _cl("c", ok=False), {"_legislation_type": "ssi"}),
])
def test_p28_reads_back_a_fresh_footer_that_carries_the_clause(log, cfg):
    """**Hazard 3, the silent one.** `_earlier_footers` parses only the LAST line
    of the trailing footer block. The clause is inside that line, after the
    part the parse anchors on, so the carried line still sees exactly the
    legislation terms and not the case-law ones."""
    fresh = answer_scope_footer(log, cfg)
    parsed = _earlier_footers(_history(fresh))
    assert len(parsed) == 1
    got = parsed[0]
    head = fresh[: fresh.index("; ")]
    assert got["terms"] == re.findall(r'"([^"]*)"', head)
    assert got["filters"] == _lawyer_filters_phrase(cfg)
    m = re.search(r"\((\d+) further quer", head)
    assert got["rest"] == (int(m.group(1)) if m else 0)
    # And the carried line built from it restates legislation terms only.
    carried = carried_scope_footer(_history(fresh), [])
    assert carried and "case-law" not in carried


def test_a_standalone_case_law_line_is_never_read_as_a_legislation_search():
    """6385's shape (`case_law_only`): the history holds only case-law lines,
    so a later reply that searched nothing gets no carried line. "No search of
    the legislation index was run" would be true, but there were never any
    legislation searches to restate."""
    standalone = case_law_scope_footer(_cl("privilege"))
    assert _earlier_footers(_history(standalone)) == []
    assert carried_scope_footer(_history(standalone), []) == ""


def test_a_hybrid_follow_up_that_searched_only_case_law_keeps_one_line():
    fresh = answer_scope_footer(_leg("FOISA section 36"), {})
    line = carried_scope_footer(_history(fresh), _cl("limited waiver"))
    assert "no search of the legislation index was run for this reply" in line
    assert "For this reply the case-law database" in line
    assert '"limited waiver"' in line
    assert line.count("*Search scope:") == 1 and "\n" not in line.strip()
    # And the next turn still parses the ORIGINAL fresh footer, not this one.
    assert len(_earlier_footers(_history(fresh, line))) == 1


# ---------------------------------------------------------------------------
# 4. Stripped whole, and no detector trips on it
# ---------------------------------------------------------------------------

_PROSE = "Yes. *Daly v HM Advocate* [2025] UKSC 1 applies the rule in Scotland."


@pytest.mark.parametrize("footer", [
    case_law_scope_footer(_cl("privilege", "waiver", "Scotland common interest")),
    case_law_scope_footer(_cl("q", ok=False)),
    answer_scope_footer(_leg("FOISA") + _cl("privilege"), {"_jurisdiction": "scotland"}),
    carried_scope_footer(_history(answer_scope_footer(_leg("FOISA"), {})), _cl("x")),
])
def test_the_line_is_stripped_whole_and_trips_nothing_in_the_models_prose(footer):
    answer = _PROSE + footer
    # `replay_report` grades the model on this.
    assert rr._without_footer(answer) == _PROSE
    # The product removes a copy the model echoed before appending its own.
    assert strip_answer_footer(answer) == _PROSE
    assert (strip_answer_footer(answer) + footer).count("*Search scope:") == 1
    # `corpus` counts two openers as a duplicate footer.
    assert answer.count("*Search scope:") == 1
    # The P2.4 subcommand: disclosed on the full answer, not by the model.
    rows = rr.caselaw_rows({"turns": [{"turn": 1, "answer": answer}]})
    assert rows[0]["disclosed"] and rows[0]["code"] and rows[0]["model"] == []


def test_the_case_law_sentence_trips_no_detector_of_its_own():
    """Graded on the case-law part alone: the legislation part says "not found"
    by design and by record, which is why `_without_footer` exists. This row
    adds no new trip, so no instrument that reads a WHOLE answer moves because
    of it except the one meant to (`SCOTS_CASELAW_GAP`, see `caselaw`)."""
    for text in (case_law_scope_clause(_cl("a", "b", "c")),
                 case_law_scope_clause(_cl("a", ok=False)),
                 case_law_scope_footer(_cl("a"))):
        assert text
        for det in (rr.NEG_ASSERTED, rr.NOT_FOUND, rr.NEG_BLAMED_USER,
                    rr.IN_FORCE_CLAIM, rr.HALT_PARAPHRASE, rr.HALT_AS_TIMEOUT,
                    rr.HALT_LITERAL):
            assert not det.search(text), det.pattern[:60]
        assert rr.derivation_claims(text)[0] == []
        assert not any(rr._currency_asserted(s) for s in rr._sentences(text))
        assert rr.caselaw_gap_statements(text)          # it IS a gap statement
        assert rr.SCOTS_CASELAW_GAP.search(text)        # hazard 1, by design


def test_the_instrument_is_coupled_to_the_product_sentence():
    assert CASE_LAW_COVERAGE_SENTENCE.startswith(rr.CASE_LAW_CODE)


# ---------------------------------------------------------------------------
# 5. Fail-soft
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entries", [
    [None, 3, "x"],
    [{"tool": "search_case_law", "query": None}],
    [{"tool": "search_case_law"}],
    [{"tool": "search_case_law", "query": 12, "ok": "maybe"}],
])
def test_odd_records_never_raise(entries):
    case_law_scope_clause(entries)
    case_law_scope_footer(entries)
    answer_scope_footer(_leg("q") + [e for e in entries if isinstance(e, dict)], {})


def test_a_broken_clause_never_costs_the_legislation_line(monkeypatch):
    def boom(entries):
        raise RuntimeError("disclosure machinery broke")

    monkeypatch.setattr(search_scope, "_case_law_body", boom)
    log = _leg("FOISA") + _cl("privilege")
    assert case_law_scope_clause(log) == ""
    assert case_law_scope_footer(log) == ""
    line = search_scope.answer_scope_footer(log, {})
    assert line.endswith("absent from the law.*")


# ---------------------------------------------------------------------------
# 2 (continued). End to end, through each seam
# ---------------------------------------------------------------------------

async def _turn(monkeypatch, research_mode, worker_calls, manager_text,
                messages=None, delegations=1, fail_first=False):
    """A Manager turn whose worker makes `worker_calls` against fake tools."""
    from src.agent import agent_shared
    from src.agent.agent_core import process_user_request

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": research_mode,
        "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None):
        if name == "search_case_law":
            return json.dumps(_caselaw_result(n=5))
        return json.dumps({"results": [
            {"legislation_id": "asp/2002/13", "title": "FOISA",
             "url": "http://www.legislation.gov.uk/id/asp/2002/13",
             "status": "revised", "year": 2002, "extent": ["Scotland"]}],
            "returned": 1, "total": 141})

    async def worker_chat_loop(messages, model, cancel_event, num_ctx, tools,
                               executor, on_chunk=None, emit_tool_details=False,
                               timing_collector=None):
        for name, args in worker_calls:
            await executor(name, args)
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** Privilege survives a limited waiver.\n"
            "2. **References:** None.")}

    state = {"n": 0}

    async def worker(*a, **kw):
        state["n"] += 1
        if fail_first and state["n"] == 1:
            raise RuntimeError("provider stalled")
        return await run_worker_agent(
            worker_chat_loop, lambda *x, **y: None, "q", "test-model", None, 0,
        )

    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        for _ in range(delegations):
            await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": manager_text}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        return await process_user_request(
            manager, worker, messages or [{"role": "user", "content": "q"}],
            "test-model", None, None, 0,
        )
    finally:
        set_request_provider_config({})


_CL_CALL = ("search_case_law", {"query": "common interest privilege Scotland"})
_LEG_CALL = ("search_legislation", {"query": "FOISA section 36"})


@pytest.mark.asyncio
async def test_case_law_only_turn_gets_the_standalone_line(monkeypatch):
    """6385's path: no legislation search, so `answer_scope_footer` is empty and
    a clause on it would never reach the lawyer."""
    final = await _turn(monkeypatch, "case_law_only", [_CL_CALL], "Answer.")
    assert final["content"].startswith("Answer.")
    assert final["content"].endswith(case_law_scope_footer(
        _cl("common interest privilege Scotland")))
    assert final["content"].count("*Search scope:") == 1
    assert "SEARCH SCOPE" not in final["content"]


@pytest.mark.asyncio
async def test_hybrid_turn_that_searched_both_gets_one_merged_line(monkeypatch):
    final = await _turn(monkeypatch, "legislation_and_case_law",
                        [_LEG_CALL, _CL_CALL], "Answer.")
    content = final["content"]
    assert content.count("*Search scope:") == 1
    assert '"FOISA section 36"' in content
    assert '"common interest privilege Scotland"' in content
    assert content.endswith("courts outside Scotland.*")


@pytest.mark.asyncio
async def test_a_turn_that_searched_no_case_law_is_unchanged(monkeypatch):
    final = await _turn(monkeypatch, "legislation_and_case_law", [_LEG_CALL], "Answer.")
    assert "case-law database" not in final["content"]
    assert final["content"].endswith("absent from the law.*")


@pytest.mark.asyncio
async def test_a_retrieval_without_a_search_is_not_a_search(monkeypatch):
    """The gate is `search_case_law`. Reading one judgment by URL is not a
    search of the corpus."""
    final = await _turn(
        monkeypatch, "case_law_only",
        [("get_case_law_text", {"url": "https://caselaw.nationalarchives.gov.uk/uksc/2025/1"})],
        "Answer.")
    assert final["content"] == "Answer."


@pytest.mark.asyncio
async def test_a_failed_delegation_does_not_suppress_the_line(monkeypatch):
    """`scope_unknown` silences P2.8's carried line, because "no search was run"
    might be false. The case-law line claims only searches that were recorded,
    and those ran, so it still goes out."""
    fresh = answer_scope_footer(_leg("earlier"), {})
    final = await _turn(monkeypatch, "legislation_and_case_law", [_CL_CALL],
                        "Partial answer.", messages=_history(fresh),
                        delegations=2, fail_first=True)
    assert "no search of the legislation index" not in final["content"]
    assert final["content"].endswith(case_law_scope_footer(
        _cl("common interest privilege Scotland")))


@pytest.mark.asyncio
async def test_a_hybrid_follow_up_carries_the_earlier_scope_with_the_clause(monkeypatch):
    fresh = answer_scope_footer(_leg("earlier search"), {})
    final = await _turn(monkeypatch, "legislation_and_case_law", [_CL_CALL],
                        "Answer.", messages=_history(fresh))
    content = final["content"]
    assert content.count("*Search scope:") == 1
    assert "no search of the legislation index was run for this reply" in content
    assert '"earlier search"' in content
    assert content.endswith("courts outside Scotland.*")


@pytest.mark.asyncio
async def test_a_memo_served_case_law_search_is_still_recorded():
    from unittest.mock import AsyncMock, patch
    from src.agent.agent_shared import run_worker_tool

    async def chunk(*a, **k):
        return None

    memo, first, second = {}, [], []
    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=json.dumps(_caselaw_result()))) as ex:
        for log in (first, second):
            await run_worker_tool("search_case_law", {"query": "privilege"},
                                  "brief", chunk, "test-model",
                                  tool_memo=memo, search_log=log)
    assert ex.await_count == 1
    assert second == [{"tool": "search_case_law", "query": "privilege",
                       "shown": 50, "ok": True}]


def _dr_worker(results):
    async def run_worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                         emit_tool_details=False, timing_collector=None,
                         tool_memo=None, retrieved_urls=None):
        run_worker.n += 1
        return results[run_worker.n - 1]
    run_worker.n = 0
    return run_worker


async def _synthesis(messages, model, cancel_event, num_ctx, tools, tool_executor,
                     on_chunk=None, emit_tool_details=False, timing_collector=None):
    return {"role": "assistant", "content": "Integrated report."}


_PLAN = {"scope_note": "", "steps": [
    {"id": 1, "title": "Statute", "detail": "FOISA."},
    {"id": 2, "title": "Case law", "detail": "Common interest privilege."},
]}


@pytest.mark.asyncio
async def test_deep_research_carries_the_case_law_record_across_steps():
    """6375 turn 2's path. The case-law searches are in step 2 and the
    legislation searches in step 1; the report gets one merged line."""
    worker = _dr_worker([
        {"content": "f1", "sources": [], "searches": _leg("FOISA")},
        {"content": "f2", "sources": [], "searches": _cl(*[f"c{i}" for i in range(20)])},
    ])
    result = await run_deep_research(
        _synthesis, worker, _PLAN, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    content = result["content"]
    assert content.startswith("Integrated report.")
    assert content.count("*Search scope:") == 1
    assert '"FOISA"' in content
    assert '"c0", "c1" (18 further queries not listed)' in content
    assert content.endswith("courts outside Scotland.*")


@pytest.mark.asyncio
async def test_deep_research_with_only_case_law_gets_the_standalone_line():
    worker = _dr_worker([
        {"content": "f1", "sources": [], "searches": _cl("a")},
        {"content": "f2", "sources": [], "searches": []},
    ])
    result = await run_deep_research(
        _synthesis, worker, _PLAN, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert result["content"] == "Integrated report." + case_law_scope_footer(_cl("a"))


@pytest.mark.asyncio
async def test_deep_research_with_no_case_law_is_unchanged():
    worker = _dr_worker([
        {"content": "f1", "sources": [], "searches": _leg("FOISA")},
        {"content": "f2", "sources": [], "searches": []},
    ])
    result = await run_deep_research(
        _synthesis, worker, _PLAN, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    assert result["content"] == "Integrated report." + answer_scope_footer(_leg("FOISA"), {})


# ---------------------------------------------------------------------------
# The instrument: `replay_report caselaw`
# ---------------------------------------------------------------------------

def _doc(*turns):
    return {"session_id": "9999", "rep": 1, "turns": list(turns)}


def _t(turn, answer, cl_calls=0, results=None):
    tools = [{"name": "search_case_law",
              "raw_result": json.dumps(results or _caselaw_result())}] * cl_calls
    return {"turn": turn, "chat_mode": "research", "answer": answer,
            "audit": {"delegations": [{"tools": tools}]}}


@pytest.mark.parametrize("sentence,stated,old", [
    # The model's real disclosures (baseline/wave1 6370, 6407).
    ("Please note that the available case law database does not index decisions "
     "from the Scottish Court of Session or Sheriff Courts unless they were "
     "appealed to the UK Supreme Court.", True, True),
    ("It does not comprehensively index decisions from the Scottish Court of "
     "Session (CSOH/CSIH) or the Sheriff Courts.", True, True),
    # The real over-reads of SCOTS_CASELAW_GAP, which are not disclosures.
    ("Under Rule 35.8 of the [Rules of the Court of Session 1994](http://x), the "
     "process for determining confidentiality is procedural.", False, True),
    ("*   **2015:** The Clerk of the Sheriff Appeal Court and Deputy Clerk of the "
     "Sheriff Appeal Court ([Order 2015](http://x)).", False, True),
    ("The [Courts Reform (Scotland) Act 2014](http://x) does contain specific "
     "definitions relating to interdicts for the purposes of sheriff court "
     "jurisdiction:", False, True),
    ("If you need a comprehensive review of Scottish case law on this topic, I "
     "suggest switching to Research mode.", False, False),
    # 6341 (legislation_only): about the LEGISLATION database lacking case law.
    # Counted, a known over-read; it can only move the all-turns column, never
    # the acceptance, which reads turns that searched case law.
    ("The available database does not contain information on Scottish case law "
     "interpreting the term.", True, False),
])
def test_the_gap_detector_in_both_directions(sentence, stated, old):
    assert bool(rr.caselaw_gap_statements(sentence)) is stated
    # The old detector's reading, for the record: it over-reads a court's name.
    assert bool(rr.SCOTS_CASELAW_GAP.search(sentence)) is old


def test_the_verdicts():
    code = case_law_scope_footer(_cl("q"))
    model = ("The database does not index the Court of Session, so this is "
             "English authority.")
    rows = rr.caselaw_rows(_doc(
        _t(1, "Answer." + code, cl_calls=2),        # disclosed by code
        _t(2, "Answer.", cl_calls=1),               # the defect
        _t(3, model, cl_calls=1),                   # disclosed by the model
        _t(4, "Answer." + code, cl_calls=0),        # code on a turn with no search
        _t(5, "A." + code + code, cl_calls=1),      # two lines
        _t(6, "Answer."),                           # nothing to disclose
    ))
    got = [(r["turn"], rr.caselaw_verdict(r), r["code"], bool(r["model"]))
           for r in rows]
    assert got == [
        (1, None, True, False),
        (2, "UNDISCLOSED", False, False),
        (3, None, False, True),
        (4, "MISATTRIBUTED", True, False),
        (5, "TWO_LINES", True, False),
        (6, None, False, False),
    ]


def test_scottish_uksc_citations_are_counted_from_the_prose_only():
    """Invariant 1's specific worry: the line must not make the model less
    willing to cite a sound Scottish appeal. Counted by title from the audit."""
    answer = ("See [Daly v His Majesty's Advocate (Scotland) [2025] UKSC 1]"
              "(https://caselaw.nationalarchives.gov.uk/uksc/2025/1) and "
              "[Party 1 v Party 2](https://caselaw.nationalarchives.gov.uk/ewhc/2020/1)."
              + case_law_scope_footer(_cl("q")))
    row = rr.caselaw_rows(_doc(_t(1, answer, cl_calls=1,
                                  results=_caselaw_result(scottish=True))))[0]
    assert row["caselaw_links"] == 2
    assert row["uksc_cited"] == 1
    assert row["uksc_scottish_cited"] == 1


def test_the_subcommand_exits_1_on_a_finding_and_0_when_clean(tmp_path, capsys):
    clean = tmp_path / "clean"
    dirty = tmp_path / "dirty"
    for d in (clean, dirty):
        d.mkdir()
    code = case_law_scope_footer(_cl("q"))
    (clean / "9999_rep1.json").write_text(json.dumps(
        _doc(_t(1, "A." + code, cl_calls=1), _t(2, "B."))), encoding="utf-8")
    (dirty / "9999_rep1.json").write_text(json.dumps(
        _doc(_t(1, "A.", cl_calls=1))), encoding="utf-8")
    assert rr.main(["--dir", str(clean), "caselaw"]) == 0
    assert rr.main(["--dir", str(dirty), "caselaw"]) == 1
    out = capsys.readouterr().out
    assert "UNDISCLOSED   1" in out
    assert "predates P2.4" in out


# ---------------------------------------------------------------------------
# The 6373 half: a record the index does not hold is not a wrong citation
# ---------------------------------------------------------------------------
#
# Measured at HEAD before building (`wave2_p24_pre`, n=3): all three Worker
# reports blamed FrankieH's correct citation, and each had just been handed
# `Legislation not found: ssi/2026/170` by `get_legislation_text`.

from src.utils.search_scope import not_held_note, record_not_held  # noqa: E402

_NOT_FOUND_RESULT = 'Error executing tool: {"detail":"Legislation not found: ssi/2026/170"}'


def test_a_not_found_retrieval_gets_the_note():
    note = not_held_note({"legislation_id": "ssi/2026/170"}, _NOT_FOUND_RESULT)
    assert note.startswith("\n\n[SEARCH SCOPE — not held:")
    assert "ssi/2026/170" in note
    assert "not about the user's citation" in note
    for forbidden_act in ("check, verify or confirm", "may be wrong",
                          "different instrument (another year or number)"):
        assert forbidden_act in note
    # The same bounded coverage figures every other note carries.
    assert search_scope.LEX_COVERAGE_SENTENCE in note


@pytest.mark.parametrize("data", [
    json.dumps({"legislation": {"id": "ssi/2025/119"}, "full_text": "x"}),   # held
    "Error executing tool: 503 Service Unavailable",                       # outage
    'Error executing tool: {"detail":"Internal error"}',
    {"detail": "Legislation not found: ssi/2026/170"},     # not the executor's shape
    None,
])
def test_anything_else_gets_no_note(data):
    assert not_held_note({"legislation_id": "ssi/2026/170"}, data) == ""
    log = []
    record_not_held(log, "get_legislation_text", {"legislation_id": "x"}, data)
    assert log == []


def test_the_note_is_stripped_before_a_lawyer_sees_it():
    note = not_held_note({"legislation_id": "ssi/2026/170"}, _NOT_FOUND_RESULT)
    out, n = search_scope.strip_scope_blocks("It is not held." + note)
    assert out == "It is not held." and n == 1


def test_the_manager_is_told_in_the_workers_block():
    log = [{"tool": "search_legislation", "query": "SSI 2026/170", "shown": 5,
            "matched": 141}]
    record_not_held(log, "get_legislation_text", {"legislation_id": "ssi/2026/170"},
                    _NOT_FOUND_RESULT)
    record_not_held(log, "get_legislation_text", {}, _NOT_FOUND_RESULT)   # id from detail
    block = worker_scope_block(log, {})
    assert block.count("ssi/2026/170") == 1              # deduped
    assert "Not held in this index" in block
    assert "not an error in the user's citation" in block
    # Lawyer-facing lines are unchanged by it: held/absent is P3.7's.
    assert answer_scope_footer(log, {}) == answer_scope_footer(log[:1], {})
    # And the block is stripped whole, as every worker block is.
    assert search_scope.strip_scope_blocks("Report." + block) == ("Report.", 1)


@pytest.mark.asyncio
async def test_the_note_reaches_the_worker_and_survives_the_memo():
    from unittest.mock import AsyncMock, patch
    from src.agent.agent_shared import run_worker_tool

    async def chunk(*a, **k):
        return None

    memo, first, second = {}, [], []
    args = {"legislation_id": "ssi/2026/170"}
    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=_NOT_FOUND_RESULT)) as ex:
        seen = [await run_worker_tool("get_legislation_text", dict(args), "brief",
                                      chunk, "test-model", tool_memo=memo,
                                      search_log=log)
                for log in (first, second)]
    assert ex.await_count == 1
    for got in seen:
        assert got.startswith(_NOT_FOUND_RESULT)
        assert "[SEARCH SCOPE — not held:" in got
    for log in (first, second):
        assert [e["tool"] for e in log] == ["not_held"]


@pytest.mark.parametrize("prompt_name", ["MANAGER_SYSTEM_PROMPT",
                                         "MANAGER_SYSTEM_PROMPT_CONVERSATIONAL"])
def test_both_legislation_managers_carry_the_rule(prompt_name):
    """6373 is conversational; its Manager relayed the blame in 2 of 3 reps."""
    from src import prompts
    text = getattr(prompts, prompt_name)
    assert "NOT HELD IS NOT A WRONG CITATION" in text
    assert text.count("NOT HELD IS NOT A WRONG CITATION") == 1
    # The rule must not itself read as questioning a citation.
    assert not rr.NEG_BLAMED_USER.search(text.split("NOT HELD IS NOT A WRONG CITATION")[1][:400])
