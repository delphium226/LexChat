"""Tests for the pre-pilot replay tooling (`server_py/tools/`).

These guard the **measurement instrument**, not the product. Every replay-based
acceptance test in `docs/prepilot-fixes/FIX_PLAN.md` reads its verdict out of
`replay_report`'s detectors, so a silently-wrong detector would mark a row green
without the defect being fixed. In particular:

* `test_filter_loss_*` pins the arithmetic behind P1.1 and P1.3 — the
  before/after number for the jurisdiction filter discarding every result.
* `test_bad_link_*` **is** P1.4's stated acceptance check ("every link whose
  label names a section/regulation/article/schedule contains the matching path
  segment"), written against synthetic answers so it is available before the fix.
* `test_source_cited_*` pins the mirror of `agent_core._source_is_used`, which
  is subtle: `audit["sources"]` is the already-filtered list, so the diagnostic
  deliberately drops the `excerpt` branch.

The replay-set tests need the transcript export, which is deliberately not in
this repo (lawyers' verbatim casework questions), so they skip when it is absent
rather than failing.
"""

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402
import replay_set as rs  # noqa: E402


# --- helpers -----------------------------------------------------------------


def _tool(name, args=None, final_result=None, api_response=None):
    return {
        "id": "t1",
        "name": name,
        "args": args or {},
        "raw_result": "",
        "final_result": final_result if final_result is not None else "",
        "summarised": False,
        "local_cache_hit": False,
        "memo_hit": False,
        "api_calls": (
            [{"id": "c1", "url": "https://lex/legislation/search", "method": "POST",
              "request": {}, "status": 200, "response": api_response,
              "elapsed_ms": 1}]
            if api_response is not None else []
        ),
    }


def _run(answer="", tools=None, sources=None, report="", cost=0.0, turns=None):
    turn = {
        "turn": 1,
        "question": "q",
        "chat_mode": "research",
        "chat_mode_source": "snapshot",
        "prepilot": {},
        "status": "ok",
        "answer": answer,
        "error": None,
        "elapsed_s": 1.0,
        "suggestions": [],
        "plan": None,
        "plan_clarification": None,
        "events_seen": {},
        "timing": {"total_cost_usd": cost},
        "audit": {
            "type": "audit",
            "schema_version": 1,
            "model": "google/gemini-3.1-pro-preview",
            "answer": answer,
            "sources": sources or [],
            "delegations": [
                {"id": "d1", "kind": "delegation", "step": None, "title": None,
                 "brief": "", "report": report, "reformatted": False,
                 "error": None, "tools": tools or []}
            ],
            "peer_consults": [],
            "error": None,
        },
    }
    return {
        "schema": "aila-replay/1",
        "session_id": "9999",
        "rep": 1,
        "verdict_at_prepilot": "FAIL",
        "primary_bucket": "B2",
        "secondary_buckets": [],
        "diag_at_prepilot": "",
        "filters": {},
        "model_mismatch": [],
        "total_cost_usd": cost,
        "elapsed_s": 1.0,
        "turns": turns if turns is not None else [turn],
    }


# --- P1.1 / P1.3: the filter-loss arithmetic ---------------------------------


def test_filter_loss_counts_both_sides_of_the_filters():
    """The exact shape B2 produces: LEX returns results, the model sees none."""
    doc = _run(tools=[_tool(
        "search_legislation",
        args={"query": "homelessness accommodation Scotland"},
        final_result=json.dumps({"results": [], "total": 0}),
        api_response={"results": [{"id": i} for i in range(20)], "total": 97},
    )])
    sig = rr.analyse_run(doc)
    assert sig.searches == 1
    fl = sig.filter_losses[0]
    assert fl.api_total == 97 and fl.api_returned == 20
    assert fl.tool_returned == 0 and fl.tool_total == 0
    assert fl.discarded == 20
    assert fl.wiped_out is True
    # B5's second half: the API's real match count did not reach the model.
    assert fl.total_misreported is True
    assert sig.searches_wiped_out == 1
    assert sig.results_discarded == 20


def test_filter_loss_clean_search_is_not_flagged():
    doc = _run(tools=[_tool(
        "search_legislation",
        final_result=json.dumps({"results": [{"id": i} for i in range(5)], "total": 5}),
        api_response={"results": [{"id": i} for i in range(5)], "total": 5},
    )])
    sig = rr.analyse_run(doc)
    assert sig.searches_wiped_out == 0
    assert sig.results_discarded == 0
    assert sig.filter_losses[0].total_misreported is False


def test_filter_loss_partial_filtering_is_not_wiped_out():
    """Some results removed is a filter working, not a filter destroying."""
    doc = _run(tools=[_tool(
        "search_legislation",
        final_result=json.dumps({"results": [{"id": 1}, {"id": 2}], "total": 2}),
        api_response={"results": [{"id": i} for i in range(20)], "total": 97},
    )])
    sig = rr.analyse_run(doc)
    assert sig.filter_losses[0].wiped_out is False
    assert sig.results_discarded == 18
    assert sig.searches_total_misreported == 1


def test_filter_loss_zero_from_the_api_is_not_attributed_to_filters():
    doc = _run(tools=[_tool(
        "search_legislation",
        final_result=json.dumps({"results": [], "total": 0}),
        api_response={"results": [], "total": 0},
    )])
    sig = rr.analyse_run(doc)
    assert sig.searches_wiped_out == 0, "no results in means nothing was discarded"
    assert sig.results_discarded == 0


# --- P1.4: provision links must point at the provision -----------------------


@pytest.mark.parametrize("label,url", [
    ("section 10", "http://www.legislation.gov.uk/id/ukpga/1985/68/section/10"),
    ("s. 35A", "http://www.legislation.gov.uk/id/asp/2009/12/section/35A"),
    ("regulation 2", "http://www.legislation.gov.uk/id/ssi/2025/119/regulation/2"),
    ("Article 43", "http://www.legislation.gov.uk/id/eur/2009/1069/article/43"),
    ("Schedule 1", "http://www.legislation.gov.uk/id/ukpga/1985/68/schedule/1"),
])
def test_bad_link_accepts_correct_provision_links(label, url):
    sig = rr.analyse_run(_run(answer=f"See [{label}]({url}) for the detail."))
    assert sig.bad_links == []
    assert sig.total_links == 1


@pytest.mark.parametrize("label,url,expected", [
    ("section 10", "http://www.legislation.gov.uk/id/ukpga/1985/68", "/section/10"),
    ("regulation 2", "http://www.legislation.gov.uk/id/ssi/2025/119", "/regulation/2"),
    # Right kind of segment, wrong provision — the case a contents-page check misses.
    ("section 10", "http://www.legislation.gov.uk/id/ukpga/1985/68/section/11", "/section/10"),
])
def test_bad_link_flags_links_that_miss_their_provision(label, url, expected):
    sig = rr.analyse_run(_run(answer=f"See [{label}]({url})."))
    assert len(sig.bad_links) == 1
    assert sig.bad_links[0].expected_segment == expected


def test_bad_link_ignores_labels_that_name_no_provision():
    answer = ("The [Courts Reform (Scotland) Act 2014]"
              "(http://www.legislation.gov.uk/id/asp/2014/18) applies.")
    sig = rr.analyse_run(_run(answer=answer))
    assert sig.bad_links == []
    assert sig.total_links == 1


def test_bad_link_ignores_paragraph_labels():
    """`paragraph` has no stable legislation.gov.uk segment of its own — it
    lives under a schedule — so asserting on it would manufacture failures."""
    answer = ("[paragraph 3](http://www.legislation.gov.uk/id/ukpga/1985/68"
              "/schedule/1) of the Schedule.")
    sig = rr.analyse_run(_run(answer=answer))
    assert sig.bad_links == []


# --- B1 / P2.1: the halt, at source and as shown -----------------------------


def test_halt_detected_in_the_worker_report_and_in_the_answer():
    doc = _run(
        answer="The research agent exceeded its operational limits (timed out).",
        report='A system message indicating: "[Research halted: exceeded 20 '
               'tool-call steps]". No legal content.',
    )
    sig = rr.analyse_run(doc)
    assert sig.halt_in_worker_report == 1
    assert sig.halt_language_in_answer == 1


def test_halt_detector_does_not_fire_on_an_ordinary_answer():
    doc = _run(
        answer="Under s.10 of the Act the authority must respond within 20 "
               "working days.",
        report="**Summary Answer (BLUF):** ...",
    )
    sig = rr.analyse_run(doc)
    assert sig.halt_in_worker_report == 0
    assert sig.halt_language_in_answer == 0


# --- P4.2: billed but empty --------------------------------------------------


def test_billed_but_empty_is_the_condition_p4_2_asserts_on():
    doc = _run(answer="", cost=0.0217)
    sig = rr.analyse_run(doc)
    assert sig.turns_empty_answer == 1
    assert sig.turns_billed_but_empty == 1


def test_empty_and_unbilled_is_empty_but_not_billed():
    sig = rr.analyse_run(_run(answer="", cost=0.0))
    assert sig.turns_empty_answer == 1
    assert sig.turns_billed_but_empty == 0


# --- B5 / P2.2: explained vs bare negatives ----------------------------------


def test_bare_negative_is_one_that_says_nothing_about_the_search():
    sig = rr.analyse_run(_run(
        answer="No commencement regulations have been made yet."))
    assert sig.bare_negatives == 1
    assert sig.explained_negatives == 0


def test_a_negative_that_names_its_search_and_filters_is_explained():
    sig = rr.analyse_run(_run(
        answer="I searched for 'care reform commencement' with the jurisdiction "
               "filter set to Scotland; no results were returned."))
    assert sig.explained_negatives == 1
    assert sig.bare_negatives == 0


# --- B8 / P4.3: cited vs consulted -------------------------------------------


def test_source_cited_matches_on_the_bare_legislation_id():
    """`_lid` is stripped from the audit payload, so `cite` carries the id —
    and the id is a substring of any provision URL built from it."""
    src = {"title": "Climate Change (Scotland) Act 2009",
           "url": "http://www.legislation.gov.uk/id/asp/2009/12",
           "cite": "asp/2009/12"}
    answer = ("See [section 35](http://www.legislation.gov.uk/id/asp/2009/12"
              "/section/35).")
    assert rr._source_cited(src, answer) is True
    sig = rr.analyse_run(_run(answer=answer, sources=[src]))
    assert sig.sources_kept == 1 and sig.sources_unused == 0
    assert sig.turns_source_fallback == 0


def test_source_kept_but_never_mentioned_is_consulted_not_cited():
    src = {"title": "Shops Act 1950",
           "url": "http://www.legislation.gov.uk/id/ukpga/1950/28",
           "cite": "ukpga/1950/28", "excerpt": "s.38 text"}
    sig = rr.analyse_run(_run(answer="The position is governed by other rules.",
                              sources=[src]))
    assert sig.sources_unused == 1
    # Every source uncited means the rail is showing an unvouched-for list.
    assert sig.turns_source_fallback == 1


def test_short_tokens_do_not_count_as_citations():
    """Mirrors `_source_is_used`'s >=6-char floor: a 3-char cite would match
    almost any prose by accident."""
    src = {"cite": "abc", "url": "", "title": "x"}
    assert rr._source_cited(src, "the abc of it") is False


# --- The replay set (needs the uncommitted export) ---------------------------


def _csv_present() -> bool:
    return Path(rs.DEFAULT_CSV).exists()


requires_csv = pytest.mark.skipif(
    not _csv_present(),
    reason="transcript export is deliberately not committed; see FIX_PLAN "
           "'Data handling'. Regenerate from Admin Portal -> Developer.",
)


@requires_csv
def test_replay_set_covers_exactly_the_defect_carrying_sessions():
    """P0.2's stated acceptance."""
    sessions = rs.load_sessions()
    cls = json.loads(Path(rs.DEFAULT_CLASSIFICATION).read_text(encoding="utf-8"))
    expected = {k for k, v in cls.items() if v["verdict"] in ("FAIL", "DEFECT")}
    got = {s.session_id for s in sessions if s.verdict in ("FAIL", "DEFECT")}
    assert got == expected
    assert len(got) == 41


@requires_csv
def test_deep_research_marker_agrees_with_the_exported_session_mode():
    """The per-turn marker is an inference (P0.4 replaces it with stored data).
    It is only usable while it reconciles exactly with the thread-level value
    the exporter derived from `messages.research_plan`."""
    report = rs.reconciliation_report(rs.load_sessions())
    assert report == {
        "marker_but_not_session_mode": [],
        "session_mode_but_no_marker": [],
        "session_mode_blank_with_marker": [],
    }


@requires_csv
def test_deep_research_is_a_minority_of_turns_and_not_always_the_first():
    """Guards the correction that chat mode is per-turn: replaying a flagged
    session entirely in deep_research mode would measure a system nobody used."""
    sessions = [s for s in rs.load_sessions() if s.verdict in ("FAIL", "DEFECT")]
    dr_turns = sum(len(s.deep_research_turns) for s in sessions)
    all_turns = sum(len(s.turns) for s in sessions)
    assert dr_turns == 20 and all_turns == 155
    by_id = {s.session_id: s for s in sessions}
    assert by_id["6409"].deep_research_turns == [6]
    assert by_id["6406"].deep_research_turns == [2, 3]
    assert by_id["6341"].deep_research_turns == [7]


@requires_csv
def test_unanswered_turns_match_the_frozen_analysis():
    """B13/P4.2's headline figure, recounted from the export."""
    sessions = rs.load_sessions()
    lost = [(s.session_id, t.index) for s in sessions for t in s.turns
            if not t.got_reply]
    assert len(lost) == 15
    assert len({sid for sid, _ in lost}) == 11


@requires_csv
def test_bare_year_filters_are_read_as_years_not_dates():
    """The export writes `2026` into a date column; sending that as an ISO
    `date_to` would void the filter silently."""
    s = next(s for s in rs.load_sessions() if s.session_id == "6404")
    assert s.year_to == 2026
    assert s.date_to is None
