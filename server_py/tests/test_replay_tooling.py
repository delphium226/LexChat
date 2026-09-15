"""Tests for the pre-pilot replay tooling (`server_py/tools/`).

These guard the **measurement instrument**, not the product. Every replay-based
acceptance test in `docs/prepilot-fixes/FIX_PLAN.md` reads its verdict out of
`replay_report`'s detectors, so a silently-wrong detector would mark a row green
without the defect being fixed. In particular:

* `test_filter_loss_*` pins the arithmetic behind P1.1 and P1.3 — the
  before/after number for the jurisdiction filter discarding every result.
* `test_bad_link_*` pins P1.4's *granularity* check ("every link whose label
  names a section/regulation/article/schedule contains the matching path
  segment"). ~~It **is** P1.4's stated acceptance check.~~ **It is not, and
  believing that cost three sessions.** It was written against synthetic labels
  no real corpus produces, so it stayed green while the detector read an SI's
  title year ("...Regulations 2013") as a provision number and over-counted B14
  six-fold. A green unit test is not protection if its fixtures are not the
  shape the product emits — every fixture below is now a real payload shape.
* `test_a_url_*` / `test_provenance_*` pin the question `bad_links` cannot ask:
  where did this provision URL come from? Three outcomes, not two — shown to the
  model, reconstructed after summarisation ate it, or manufactured. Collapsing
  the last two hid the real defect behind the benign one (P1.6).
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
    assert fl.wiped_out is True
    assert fl.filters_bit is True
    # Only the shortfall below the cap is attributable to filtering.
    assert fl.rows_lost_min == rr.RESULT_CAP
    # B5's second half: the API's real match count did not reach the model.
    assert fl.total_misreported is True
    assert sig.searches_wiped_out == 1
    assert sig.rows_lost_min == rr.RESULT_CAP


def test_filter_loss_clean_search_is_not_flagged():
    doc = _run(tools=[_tool(
        "search_legislation",
        final_result=json.dumps({"results": [{"id": i} for i in range(5)], "total": 5}),
        api_response={"results": [{"id": i} for i in range(5)], "total": 5},
    )])
    sig = rr.analyse_run(doc)
    assert sig.searches_wiped_out == 0
    assert sig.searches_filters_bit == 0
    assert sig.rows_lost_min == 0
    assert sig.filter_losses[0].total_misreported is False


def test_a_cap_bound_search_is_not_evidence_either_way():
    """20 in, exactly 5 out is what the `[:5]` cap does with no filtering at
    all. Counting it as filter loss is the mistake that overstates B2."""
    doc = _run(tools=[_tool(
        "search_legislation",
        final_result=json.dumps({"results": [{"id": i} for i in range(5)], "total": 5}),
        api_response={"results": [{"id": i} for i in range(20)], "total": 189},
    )])
    sig = rr.analyse_run(doc)
    assert sig.searches_filters_bit == 0
    assert sig.rows_lost_min == 0
    # ...but the overwritten total is still P1.3, and is independent of filters.
    assert sig.searches_total_misreported == 1


def test_the_phase_2_nudge_does_not_break_the_count():
    """`run_worker_tool` appends the nudge after the JSON. A plain json.loads
    raises there, which would silently mark every PRODUCTIVE search
    unmeasurable and leave the metric describing only empty ones."""
    payload = json.dumps({"results": [{"id": i} for i in range(3)], "total": 3})
    nudge = (
        '\n\n[NEXT STEP: Call search_legislation_sections for:\n'
        '  - legislation_id: "asp/2014/18"]'
    )
    doc = _run(tools=[_tool(
        "search_legislation",
        final_result=payload + nudge,
        api_response={"results": [{"id": i} for i in range(20)], "total": 97},
    )])
    sig = rr.analyse_run(doc)
    assert sig.filter_losses[0].tool_returned == 3, "nudge must not defeat the parse"
    assert sig.searches_filters_bit == 1
    assert sig.rows_lost_min == 2


def test_filter_loss_partial_filtering_is_not_wiped_out():
    """Some results removed is a filter working, not a filter destroying."""
    doc = _run(tools=[_tool(
        "search_legislation",
        final_result=json.dumps({"results": [{"id": 1}, {"id": 2}], "total": 2}),
        api_response={"results": [{"id": i} for i in range(20)], "total": 97},
    )])
    sig = rr.analyse_run(doc)
    assert sig.filter_losses[0].wiped_out is False
    assert sig.filter_losses[0].filters_bit is True
    assert sig.rows_lost_min == 3  # 5 (cap) - 2 seen
    assert sig.searches_total_misreported == 1


def test_filter_loss_zero_from_the_api_is_not_attributed_to_filters():
    doc = _run(tools=[_tool(
        "search_legislation",
        final_result=json.dumps({"results": [], "total": 0}),
        api_response={"results": [], "total": 0},
    )])
    sig = rr.analyse_run(doc)
    assert sig.searches_wiped_out == 0, "no results in means nothing was discarded"
    assert sig.searches_filters_bit == 0
    assert sig.rows_lost_min == 0


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


# --- P1.6: where did this provision URL come from? ---------------------------
#
# Added 2026-09-15, after the ninth instrument trap. `_urls_returned_by_tools`
# read only `final_result`, which is the SUMMARISED text when summarisation
# fired — and 70% of section searches are summarised, the summary keeping the
# section numbers and dropping every URL. Every provision URL the retrieval
# genuinely returned but the summariser ate was therefore scored "manufactured".
# Wave 1's published "26 manufactured (19%)" was in fact 0 manufactured and 26
# reconstructed. There was no test here at all, which is why it survived.


def _prov_run(answer, raw=None, final=None, summarised=False):
    t = _tool("search_legislation_sections", final_result=final or "")
    t["raw_result"] = raw or ""
    t["summarised"] = summarised
    return _run(answer=answer, tools=[t])


_S21 = "http://www.legislation.gov.uk/id/asp/2000/1/section/21"
_SECTION_JSON = json.dumps({"results": [
    {"legislation_id": "asp/2000/1", "provision_type": "section",
     "number": 21, "url": _S21, "text": "..."},
]})
_ANSWER = f"Accounts are governed by [PFA Act 2000 - s.21]({_S21})."


def test_a_url_the_model_was_shown_is_neither_manufactured_nor_reconstructed():
    sig = rr.analyse_run(_prov_run(_ANSWER, raw=_SECTION_JSON, final=_SECTION_JSON))
    assert sig.provision_links == 1
    assert sig.provision_links_manufactured == 0
    assert sig.provision_links_reconstructed == 0


def test_a_url_summarisation_ate_is_reconstructed_not_manufactured():
    """The trap, pinned. The retrieval returned section 21's URL; the summary
    the model actually saw is prose with no URL in it, so the model rebuilt the
    link. The provision WAS retrieved — calling that manufactured hides the
    sessions where nothing was."""
    summary = "Section 21 requires accounts to be sent to the Auditor General."
    sig = rr.analyse_run(
        _prov_run(_ANSWER, raw=_SECTION_JSON, final=summary, summarised=True)
    )
    assert sig.provision_links_manufactured == 0
    assert sig.provision_links_reconstructed == 1


def test_a_url_no_tool_returned_anywhere_is_manufactured():
    """The real defect: 6365 appending `/section/21` to an Act it only held at
    Act level. A manufactured URL resolves to a real page, so it reads to a
    lawyer as a verified citation."""
    act_only = json.dumps({"results": [
        {"legislation_id": "asp/2000/1", "url": "http://www.legislation.gov.uk/asp/2000/1"},
    ]})
    sig = rr.analyse_run(_prov_run(_ANSWER, raw=act_only, final=act_only))
    assert sig.provision_links_manufactured == 1
    assert sig.provision_links_reconstructed == 0


def test_p1_6_citation_url_block_counts_as_shown():
    """P1.6 appends the URLs after summarisation, so `final_result` is prose +
    a bracketed block — not JSON. A detector that parsed `final_result` instead
    of scanning it would report the fix as having changed nothing."""
    final = (
        "Section 21 requires accounts.\n\n[CITATION URLS - ...]\n"
        f"- section 21: {_S21}"
    )
    sig = rr.analyse_run(
        _prov_run(_ANSWER, raw=_SECTION_JSON, final=final, summarised=True)
    )
    assert sig.provision_links_manufactured == 0
    assert sig.provision_links_reconstructed == 0


@pytest.mark.parametrize("cited", [
    "https://www.legislation.gov.uk/asp/2000/1/section/21",   # scheme upgraded, /id/ dropped
    "http://legislation.gov.uk/id/asp/2000/1/section/21",     # www dropped
    "http://www.legislation.gov.uk/id/asp/2000/1/section/21/",  # trailing slash
])
def test_provenance_survives_the_model_respelling_the_url(cited):
    """LEX returns `http://` and the `/id/` form; models emit `https://` without
    it. Comparing raw strings would call a correctly-copied link manufactured —
    the instrument failing, not the product. Mirrors
    `src/utils/citation_links.normalise_leg_url`, which the enforcement uses."""
    sig = rr.analyse_run(
        _prov_run(f"See [s.21]({cited}).", raw=_SECTION_JSON, final=_SECTION_JSON)
    )
    assert sig.provision_links == 1
    assert sig.provision_links_manufactured == 0
    assert sig.provision_links_reconstructed == 0


def test_provenance_is_a_run_level_question_not_a_turn_level_one():
    """A URL retrieved in turn 1 is legitimately cited in turn 4."""
    t1 = _run(answer="Found it.", tools=[_tool(
        "search_legislation_sections", final_result=_SECTION_JSON)])["turns"][0]
    t2 = _run(answer=_ANSWER, tools=[])["turns"][0]
    t2["turn"] = 2
    doc = _run(answer="")
    doc["turns"] = [t1, t2]
    sig = rr.analyse_run(doc)
    assert sig.provision_links_manufactured == 0


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


# --- P2.1: a halt is read from three places, because each has a hole ----------


def _halt_run(answer, report="", halted=None, timing_halt=False):
    d = _run(answer=answer, report=report, cost=0.1)
    dg = d["turns"][0]["audit"]["delegations"][0]
    dg["report"] = report
    if halted is not None:
        dg["halted"] = halted
    d["turns"][0]["timing"]["max_turns_halted"] = 1 if timing_halt else 0
    return d


def test_halt_seen_via_the_v2_audit_field():
    """Schema v2 removes the marker from the report, so a detector reading only
    the report text would stop seeing halts the moment P2.1 shipped."""
    sig = rr.analyse_run(_halt_run(
        "A perfectly normal-looking answer.",
        report="[Research Incomplete — step limit reached] ...",
        halted={"reason": "step_cap", "limit": 20},
    ))
    assert sig.halt_in_worker_report == 1
    assert sig.halts_undisclosed == 1  # the answer never says so


def test_halt_seen_via_the_legacy_marker_in_the_report():
    """v1 run files — the whole Wave 0 and Wave 1 corpus — carry only this."""
    sig = rr.analyse_run(_halt_run(
        "A normal answer.", report="[Research halted: exceeded 20 tool-call steps]"))
    assert sig.halt_in_worker_report == 1


def test_a_manager_loop_halt_is_seen_via_the_products_own_counter():
    """6383 turn 1: no delegation report carries it, because the MANAGER's loop
    halted. `timing.max_turns_halted` is the only signal that survives."""
    sig = rr.analyse_run(_halt_run("A normal answer.", timing_halt=True))
    assert sig.halts_undisclosed == 1


def test_p2_1s_code_emitted_disclosure_counts_as_disclosure():
    """The fix must be visible to the metric that grades it — the P1.6 lesson,
    applied before the sweep rather than after."""
    sig = rr.analyse_run(_halt_run(
        "> **⚠ This answer is incomplete.** One research step reached a fixed "
        "internal limit of 20 tool-call rounds.\n\nThe findings follow.",
        timing_halt=True,
    ))
    assert sig.halts_undisclosed == 0
    assert sig.halt_language_in_answer == 1
