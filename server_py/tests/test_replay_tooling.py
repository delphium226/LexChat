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


# --- P2.2's acceptance detector, and the artefact it started as --------------
#
# The first `NEG_ASSERTED` scored 61 of 153 Wave-1 turns, 61 failing — 100%,
# which this project treats as an artefact until proven otherwise. It was: it
# could not tell a research negative from a legal one. These four tests pin the
# distinction so the looser version cannot come back.


@pytest.mark.parametrize("answer", [
    "No commencement regulations have been made to date.",
    "The available database does not contain information on this specific issue.",
    "The research agent could not locate 'The X Regulations 2025' in the "
    "legislation database.",
    "SSI 2025/377 could not be found in the legislation database.",
    "No relevant case law was found matching your keywords.",
    "Comprehensive searches of the National Archives yielded no judgments "
    "concerning Community Justice Scotland.",
])
def test_a_research_negative_is_recognised(answer):
    """All six are real Wave-1 answers. The middle one — 27 occurrences across 21
    turns — is the commonest negative in the corpus and the older `NOT_FOUND`
    screen never saw it."""
    assert rr.NEG_ASSERTED.search(answer), answer


@pytest.mark.parametrize("answer", [
    # 6335 turn 2 — a correct statement of retrieved law.
    "No petition for winding up may be presented, and no winding-up order may "
    "be made, except by the company's directors.",
    # 6341 turn 4 — likewise, quoting s.43ZB(4).
    'Section 43ZB(4) clarifies that the "sale of goods" does not include the '
    "sale of meals, refreshments, or alcohol.",
    # 6341 turn 5 — a finding about a provision that WAS retrieved.
    "Section 3(2) of this Act does not provide a standalone definition but "
    "instead incorporates historical definitions by reference.",
])
def test_a_finding_of_law_is_not_a_research_negative(answer):
    """The failure that made the first draft a 100%. Grading these as bare
    negatives would push the model to hedge findings it had actually retrieved —
    the regression Invariant 1 exists to prevent, and the counter-pressure P3.3
    records from the other side (these users reward grounded decisiveness)."""
    assert not rr.NEG_ASSERTED.search(answer), answer


@pytest.mark.parametrize("answer", [
    # The exact sentence 6367 rep 1 produced, and the one the first version of
    # NEG_TERMS scored as naming no search terms at all.
    '*(Searched the legislation index 2 time(s) for: "Water Industry '
    'Commission for Scotland reports accounts".',
    'I searched for "care reform commencement" and found nothing.',
    "A search of the index for 'polygamous marriages' returned no instruments.",
    "The search terms used were: commencement, Social Security.",
])
def test_naming_the_search_terms_is_recognised_however_it_is_phrased(answer):
    """The verb and its object are routinely separated — "searched the
    legislation index … for" — and the first pattern demanded they be adjacent.
    Third time on this work that the detector was the thing that was wrong."""
    assert rr.NEG_TERMS.search(answer), answer


def test_the_three_conditions_are_jointly_satisfiable():
    """A dead conjunction would report 100% failing forever and look like a
    product defect. This is the answer P2.2's scope block asks the model for."""
    good = (
        "I searched for \"commencement regulations Social Security (Amendment) "
        "(Scotland) Act 2025\". No commencement regulations were found. The "
        "filters in force were jurisdiction=Scotland, years 2025-2026. This was "
        "a ranked keyword search of the LEX index and is not exhaustive; the "
        "instrument may be held and simply not surfaced, and absence from the "
        "index is not evidence of absence in law."
    )
    assert rr.NEG_ASSERTED.search(good)
    assert rr.NEG_TERMS.search(good)
    assert rr.NEG_LIMITS.search(good)
    assert rr.NEG_BLAMED_INDEX.search(good)
    assert not rr.NEG_BLAMED_USER.search(good)


def test_questioning_the_lawyers_citation_is_its_own_failure():
    """6373 questioned FrankieH's SSI 2026/170 and 6409 questioned SSI 2025/377
    three times. Both citations were right; both instruments are a 404 in LEX.
    The tool asked the lawyer to disprove a gap in its own index."""
    assert rr.NEG_BLAMED_USER.search(
        "SSI 2026/170 could not be found. Could you confirm the year or the SI "
        "number?")
    assert not rr.NEG_BLAMED_USER.search(
        "SSI 2026/170 is not held in the index, which is incomplete for 2026.")


def test_the_index_condition_survives_a_long_instrument_title():
    """6409 turn 7's whole answer named the database 90 characters after the
    "not", because the instrument's title is that long. A tight window scored the
    one turn that DOES name the database as not naming it."""
    assert rr.NEG_BLAMED_INDEX.search(
        "The research agent could not locate 'The Social Security (Amendment) "
        "(Scotland) Act 2025 (Commencement No. 1 and Saving and Transitional "
        "Provisions) Regulations 2025' in the legislation database.")


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


# --- P3.13: where the depth was lost, attributed to the last seam that had it -


def _tally(capsys, rows):
    rr._seam_transitions(rows)
    return capsys.readouterr().out


def test_the_seam_tally_attributes_to_the_last_seam_that_still_had_it(capsys):
    """The attribution IS the finding, so it is pinned rather than eyeballed.

    (mode, summary, report, answer) -> where. A requirement the answer carries
    is never a loss, whatever happened upstream; otherwise it is blamed on the
    latest seam that still had it at depth, because that is the only seam a fix
    can act on.
    """
    out = _tally(capsys, [
        ("conversational", "coarse", "deep", "deep"),      # carried
        ("conversational", "coarse", "deep", "coarse"),    # manager dropped it
        ("conversational", "deep", "coarse", "coarse"),    # worker dropped it
        ("conversational", "coarse", "coarse", "coarse"),  # summariser
    ])
    assert "conversational      4        1        1       1           1" in out


def test_a_delivered_answer_is_never_counted_as_a_loss(capsys):
    """Even where an upstream seam looks coarse: the summary can omit the
    subsection number while the Worker still writes it from the outline, which
    is P3.11's whole mechanism."""
    out = _tally(capsys, [("conversational", "coarse", "coarse", "deep")])
    assert "   1        1        0       0           0" in out


def test_the_tally_splits_by_the_mode_the_turn_ran_in(capsys):
    """P0.5's lesson applied to this metric: 6348's losses in Research mode and
    in Conversational mode are of different Workers and different Managers, and
    pooling them hides which seam a fix has to touch."""
    out = _tally(capsys, [
        ("research", "coarse", "coarse", "coarse"),
        ("conversational", "coarse", "deep", "coarse"),
        ("deep_research", "coarse", "deep", "coarse"),
    ])
    assert "research" in out and "conversational" in out and "deep_research" in out
    assert "ALL" in out  # the pooled row only appears with more than one mode


def test_one_mode_prints_no_pooled_row(capsys):
    out = _tally(capsys, [("conversational", "coarse", "deep", "coarse")])
    assert "ALL" not in out


def test_an_empty_tally_prints_nothing(capsys):
    """Fail-soft: a directory with no graded session must not print a header
    over an empty table."""
    assert _tally(capsys, []) == ""


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
    # 20 completed Deep Research reports (`dr_marker`), plus — since P4.1
    # (Session 21) — the 5 planner clarifications the client saves with no
    # model (`planner_marker`: 6346 turns 1-3, 6347 turn 1, 6343 turn 4) and
    # the 3 unanswered turns beside them that take their mode (6346 turns 4-5,
    # 6343 turn 5). 28 of 155 is still a minority.
    assert dr_turns == 28 and all_turns == 155
    by_id = {s.session_id: s for s in sessions}
    assert by_id["6409"].deep_research_turns == [6]
    assert by_id["6406"].deep_research_turns == [2, 3]
    assert by_id["6341"].deep_research_turns == [7]
    assert by_id["6346"].deep_research_turns == [1, 2, 3, 4, 5]
    assert by_id["6347"].deep_research_turns == [1, 2]
    assert by_id["6343"].deep_research_turns == [4, 5]
    planner = [(s.session_id, t.index) for s in sessions for t in s.turns
               if t.chat_mode_source == "planner_marker"]
    assert planner == [("6343", 4), ("6346", 1), ("6346", 2), ("6346", 3), ("6347", 1)]


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


# --- P0.5: Research vs Conversational is read off the answer, never defaulted -
#
# The mirror of `test_deep_research_marker_agrees_with_the_exported_session_mode`
# above, for the second marker. The first one was validated against a field the
# export already carried; this one has no such field to check against for the
# 15 sessions it exists to serve, so it is validated the other way round — it
# must fire on NONE of the 196 recorded answers, because the Research feature
# flag was off on the target for the whole pre-pilot. A marker that fired even
# once there would be matching something a conversational answer can also say,
# and the twelve sessions could not be re-graded on it.


def test_answer_shape_reads_every_heading_form_the_worker_actually_emits():
    r"""The headings are `agent_core._REPORT_SECTIONS`, reaching the lawyer
    through the Manager. The markup around them is NOT one fixed form — these
    are counted from the corpus, and enumerating them in a fixed order is how
    two earlier versions of this regex went wrong while `\bBLUF\b` quietly
    carried them. Any one heading is enough: the A4 reformat retry exists
    precisely because models drop some of them."""
    for heading in (
        "### 1. Summary Answer (BLUF)\nThe position is...",     # 253 in corpus
        "2. **Detailed Analysis:**\nSection 12 provides...",    # 76
        "**References:**\n- [Act](https://lex/x)",              # 35
        "### Jurisdiction & Status\nScotland, in force.",       # 18
        "### **1. Summary Answer (BLUF)**\nIn Scotland...",     # the fifth form
        "## Statutory Framework\n- the 2002 Act",
    ):
        assert rs.answer_shape(heading) == "research", heading


def test_answer_shape_calls_an_ordinary_answer_conversational():
    assert rs.answer_shape("The Act does not define the term.") == "conversational"
    # The marker requires the LINE TO OPEN with heading markup, so the same
    # words in prose are not a match. `wave0_conv` 6347 turn 2 is the measured
    # instance: a Deep Research planner asking "would you like to search for
    # the statutory framework discussed in this case" is a question, not a
    # research report, and the first version of this regex read it as one.
    for prose in (
        "Would you like the statutory framework discussed in this case?",
        "That is the detailed analysis you asked for.",
        "See the references below.",
    ):
        assert rs.answer_shape(prose) == "conversational", prose


def test_deep_research_wins_over_the_report_shape():
    """A Deep Research synthesis can carry report-ish headings of its own. The
    DR marker is the older, exactly-validated one (P0.2), so it decides first."""
    assert rs.answer_shape(
        "## Summary Answer\n**Key findings**\n- a\n- b") == "deep_research"


def test_an_unanswered_turn_has_no_shape():
    assert rs.answer_shape("") is None
    assert rs.answer_shape(None) is None


def _turns(*shapes):
    out = []
    for i, sh in enumerate(shapes, 1):
        out.append(rs.Turn(index=i, question="q", chat_mode="", chat_mode_source="",
                           got_reply=sh is not None, recorded_answer_shape=sh))
    return out


def test_a_recorded_snapshot_beats_the_marker():
    """29 of the 62 sessions carry `Filter: Chat mode`. Keeping it is what makes
    P0.5 move exactly the 48 turns it says it moves and leave every other sweep
    reading byte-identical."""
    turns = _turns("conversational", "conversational")
    rs._resolve_modes(turns, "conversational")
    assert [t.chat_mode_source for t in turns] == ["snapshot", "snapshot"]
    # ...except for Deep Research, which is per-turn and outranks the snapshot.
    turns = _turns("conversational", "deep_research")
    rs._resolve_modes(turns, "conversational")
    assert [t.chat_mode for t in turns] == ["conversational", "deep_research"]
    assert [t.chat_mode_source for t in turns] == ["snapshot", "dr_marker"]


def test_with_no_snapshot_the_marker_decides():
    turns = _turns("conversational", "research", "deep_research")
    rs._resolve_modes(turns, None)
    assert [t.chat_mode for t in turns] == [
        "conversational", "research", "deep_research"]
    assert [t.chat_mode_source for t in turns] == [
        "conversational_marker", "research_marker", "dr_marker"]


def test_an_unanswered_turn_takes_its_nearest_neighbour():
    turns = _turns(None, "conversational", "research")
    rs._resolve_modes(turns, None)
    assert turns[0].chat_mode == "conversational"
    assert turns[0].chat_mode_source == "neighbour"


def test_the_neighbour_before_wins_a_tie():
    """A tie is genuinely ambiguous; take the turn the lawyer had just seen."""
    turns = _turns("research", None, "conversational")
    rs._resolve_modes(turns, None)
    assert turns[1].chat_mode == "research"


def test_a_deep_research_turn_is_never_a_neighbour():
    """Deep Research is one-shot — the frontend reverts on completion — so a DR
    turn says nothing about the turn beside it, and copying one would also
    replay an unasked-for $0.71 Deep Research turn."""
    turns = _turns(None, "deep_research", "conversational")
    rs._resolve_modes(turns, None)
    assert turns[0].chat_mode == "conversational"
    assert turns[0].chat_mode_source == "neighbour"


def test_only_a_session_with_nothing_readable_reaches_the_default():
    turns = _turns(None, None)
    rs._resolve_modes(turns, None)
    assert [t.chat_mode for t in turns] == ["conversational", "conversational"]
    assert [t.chat_mode_source for t in turns] == ["default", "default"]
    # And the default itself is no longer `research`: every answered non-Deep
    # Research turn in the export is conversational-shaped, so `research` was
    # not merely unrecorded, it was contradicted.
    assert rs.DEFAULT_CHAT_MODE == "conversational"


@requires_csv
def test_the_research_marker_fires_on_no_recorded_prepilot_answer():
    """P0.5's load-bearing measurement, and the validation of the marker itself.

    The user is certain the Research feature flag was off on the target for the
    whole pre-pilot. If that is true, no recorded answer can be research-shaped
    — so a single hit here means the marker matches something a conversational
    answer says too, and the re-grading rests on nothing.
    """
    rep = rs.mode_report(rs.load_sessions())
    by = rep["by_recorded_mode"]
    assert sum(v["research"] for v in by.values()) == 0
    assert by["session_mode blank"] == {
        "sessions": 15, "research": 0, "conversational": 38,
        "deep_research": 0, "no_reply": 8, "blank_reply": 0}
    # The 24 sessions the export DOES record as conversational are the control:
    # the marker is silent on them too. (63, not the 64 first published — one of
    # those turns is a blank reply with no text to read. B13/P4.2.)
    assert by["session_mode=conversational, snapshot=conversational"] == {
        "sessions": 24, "research": 0, "conversational": 63,
        "deep_research": 0, "no_reply": 3, "blank_reply": 1}


@requires_csv
def test_the_marker_never_contradicts_a_recorded_snapshot():
    """Where the export DOES record the mode, the inference agrees with it —
    in both directions, on all 108 snapshot-sourced turns. That is what earns
    the marker the right to decide the turns where the field is blank."""
    assert rs.mode_report(rs.load_sessions())["snapshot_disagreements"] == []


@requires_csv
def test_no_turn_of_the_replay_set_falls_through_to_a_default():
    """P0.5's acceptance: every turn's mode is evidence."""
    rep = rs.mode_report(rs.load_sessions())
    assert rep["default_source_turns"] == []
    # `planner_marker` (P4.1, Session 21) took five turns off
    # `conversational_marker`: the blank-model planner clarifications.
    assert rep["sources"] == {
        "snapshot": 108, "conversational_marker": 47, "dr_marker": 27,
        "planner_marker": 5, "neighbour": 9}


@requires_csv
def test_the_twelve_sessions_the_harness_sent_as_research():
    """The blast radius, recounted from the export rather than from the row.

    ~~`DEFAULT_CHAT_MODE = "research"`~~ filled a blank `Filter: Chat mode` on
    these twelve, and every sweep from `baseline` to `wave3_p311` replayed them
    against the research Worker.
    """
    sessions = [s for s in rs.load_sessions() if s.verdict in ("FAIL", "DEFECT")]
    affected = sorted(
        s.session_id for s in sessions
        if any(t.chat_mode_source in ("conversational_marker", "research_marker",
                                      "neighbour")
               for t in s.turns)
    )
    assert affected == ["6333", "6334", "6335", "6338", "6340", "6341",
                        "6343", "6345", "6346", "6347", "6348", "6350"]
    by_id = {s.session_id: s for s in sessions}
    turns = [t for sid in affected for t in by_id[sid].turns]
    assert len(turns) == 50
    # 48 → 40 conversational with P4.1's `planner_marker` (Session 21): 6346
    # turns 1-3, 6347 turn 1 and 6343 turn 4 are planner clarifications, and
    # 6346 turns 4-5 and 6343 turn 5 take their mode from them. `wave0_conv`
    # replayed those eight as Conversational; the lawyers were in Deep
    # Research.
    assert sum(1 for t in turns if t.chat_mode == "conversational") == 40
    assert sum(1 for t in turns if t.chat_mode == "deep_research") == 10
    # 6341 turn 7 and 6347 turn 2 keep their Deep Research mode: the marker that
    # sets them is per-turn and outranks everything else.
    assert by_id["6341"].deep_research_turns == [7]
    assert by_id["6347"].deep_research_turns == [1, 2]


@requires_csv
def test_the_unanswered_turns_of_those_sessions_resolve_to_a_neighbour():
    """8 of the 48 got no reply, so no marker can read them. None reaches a
    default: each takes a mode from an answered turn of its own session."""
    sessions = [s for s in rs.load_sessions() if s.verdict in ("FAIL", "DEFECT")]
    nb = [(s.session_id, t.index) for s in sessions for t in s.turns
          if t.chat_mode_source == "neighbour"]
    assert nb == [("6335", 4), ("6335", 5), ("6341", 1), ("6343", 5),
                  ("6345", 1), ("6345", 2), ("6346", 4), ("6346", 5)]
    # A neighbour copies a conversational turn, or (P4.1) a planner
    # clarification — after which the client has NOT reverted, so the next
    # turn ran in Deep Research too (6346 turn 4 says so in the lawyer's words).
    modes = {(s.session_id, t.index): t.chat_mode for s in sessions for t in s.turns
             if t.chat_mode_source == "neighbour"}
    assert {k for k, v in modes.items() if v == "deep_research"} == {
        ("6343", 5), ("6346", 4), ("6346", 5)}
    assert all(v == "conversational" for k, v in modes.items()
               if k not in {("6343", 5), ("6346", 4), ("6346", 5)})


# --- P0.5: `replay_report modes`, the directory side --------------------------


def _mode_doc(session="6348", rep=1, turns=()):
    return {"session_id": session, "rep": rep,
            "turns": [dict(t) for t in turns]}


def test_mode_rows_read_the_mode_the_source_and_both_answer_shapes():
    doc = _mode_doc(turns=[{
        "turn": 1, "chat_mode": "conversational",
        "chat_mode_source": "conversational_marker",
        "answer": "The Act does not define it.",
        "prepilot": {"got_reply": True, "answer_shape": "conversational"},
    }])
    row = rr.mode_rows(doc, rs.answer_shape)[0]
    assert row["chat_mode"] == "conversational"
    assert row["source"] == "conversational_marker"
    assert row["replay_shape"] == "conversational"
    assert row["prepilot_shape"] == "conversational"


def test_a_run_file_written_before_p0_5_does_not_claim_the_lawyer_got_nothing():
    """28 directories predate the `prepilot.answer_shape` field. A missing shape
    on an ANSWERED turn is unknown, not `no_reply` — reading it as the latter
    would manufacture B13 evidence out of an instrument change."""
    doc = _mode_doc(turns=[
        {"turn": 1, "chat_mode": "research", "chat_mode_source": "default",
         "answer": "x", "prepilot": {"got_reply": True, "answer_chars": 700}},
        {"turn": 2, "chat_mode": "research", "chat_mode_source": "default",
         "answer": "x", "prepilot": {"got_reply": False, "answer_chars": 0}},
    ])
    rows = rr.mode_rows(doc, rs.answer_shape)
    assert [r["prepilot_shape"] for r in rows] == ["-", "no_reply"]


def test_a_turn_the_replay_never_reached_is_not_reported_as_a_lost_turn():
    """6347 turn 2 in `wave0_conv`, and the 19th instance of the instrument
    being wrong before the product is. A Deep Research turn whose planner asked
    for clarification returns before the `prepilot` block is built, so the run
    file carries `{}` — which is silence about the pre-pilot, not evidence that
    the lawyer got nothing. `replay.py` now writes the block on every path;
    this keeps the directories written before that readable."""
    doc = _mode_doc(turns=[{"turn": 2, "chat_mode": "deep_research",
                            "chat_mode_source": "dr_marker",
                            "answer": "Which jurisdiction?", "prepilot": {}}])
    assert rr.mode_rows(doc, rs.answer_shape)[0]["prepilot_shape"] == "unrecorded"


def test_a_guessed_mode_is_a_finding():
    """The P0.5 defect itself, in the one place a later sweep would meet it."""
    rows = rr.mode_rows(_mode_doc(turns=[
        {"turn": 1, "chat_mode": "research", "chat_mode_source": "default",
         "answer": "## Summary Answer\n..."}]), rs.answer_shape)
    assert len(rr.mode_findings(rows)) == 1
    assert "not evidence" in rr.mode_findings(rows)[0]


def test_an_empty_source_is_a_finding_too():
    """`needs_clarification` and planner errors built a `TurnResult` without
    one until P0.5; 6347 turn 2 in `wave2` is the measured instance."""
    rows = rr.mode_rows(_mode_doc(turns=[
        {"turn": 2, "chat_mode": "deep_research", "chat_mode_source": "",
         "answer": "Which jurisdiction?"}]), rs.answer_shape)
    assert len(rr.mode_findings(rows)) == 1


def test_a_conversational_turn_that_answers_like_the_research_worker_is_a_finding():
    """Either the mode did not take effect or the marker is wrong. Both stop
    the directory being quoted."""
    rows = rr.mode_rows(_mode_doc(turns=[
        {"turn": 1, "chat_mode": "conversational",
         "chat_mode_source": "conversational_marker",
         "answer": "## Jurisdiction & Status\nScotland."}]), rs.answer_shape)
    assert len(rr.mode_findings(rows)) == 1
    assert "research-shaped" in rr.mode_findings(rows)[0]


def test_a_research_turn_answering_conversationally_is_not_a_finding():
    """Measured at 9 of 48 in `baseline` and 6 of 48 in `wave2`: the Manager
    answers some Research-mode turns without delegating at all. Normal."""
    rows = rr.mode_rows(_mode_doc(turns=[
        {"turn": 1, "chat_mode": "research", "chat_mode_source": "snapshot",
         "answer": "The 2002 Act applies."}]), rs.answer_shape)
    assert rr.mode_findings(rows) == []


def test_findings_are_computed_over_every_rep():
    """`--all-reps` changes what is PRINTED, never what is graded: a mode
    mismatch in rep 3 must not hide behind a clean rep 1."""
    rows = []
    for rep, mode in ((1, "conversational"), (2, "conversational")):
        rows += rr.mode_rows(_mode_doc(rep=rep, turns=[{
            "turn": 1, "chat_mode": mode,
            "chat_mode_source": "conversational_marker",
            "answer": "## BLUF\nx" if rep == 2 else "plain",
        }]), rs.answer_shape)
    assert len(rr.mode_findings(rows)) == 1
    assert "r2" in rr.mode_findings(rows)[0]

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


@pytest.mark.parametrize("answer,expected", [
    ("The research agent timed out before finishing.", 1),
    ("the agent exceeded its operational limits (timed out)", 1),   # 6340, verbatim
    ("A timeout occurred during the search.", 1),
    # P2.1's own notice denies a timeout — it must not match itself, or the
    # acceptance check would fail on the very text that fixes the defect.
    ("it is **not** a timeout, and it is **not** a finding that the material "
     "does not exist", 0),
    ("It is NOT a timeout, NOT an API failure, and NOT evidence that", 0),
    ("A perfectly ordinary answer about compulsory purchase.", 0),
])
def test_a_halt_disclosed_as_a_timeout_is_disclosed_wrongly(answer, expected):
    """P2.1 condition (3). "Timed out" is not a harmless synonym for a step cap:
    a timeout implies the same question might succeed on a retry, where a cap
    says it will not."""
    sig = rr.analyse_run(_run(answer=answer))
    assert sig.halt_called_a_timeout == expected


def test_the_raw_marker_reaching_the_answer_is_counted_separately():
    """Disclosed-at-all and disclosed-readably are different questions: 6383
    turn 1 'disclosed' the halt by printing the marker as the whole answer."""
    sig = rr.analyse_run(_run(answer="[Research halted: exceeded 20 tool-call steps]"))
    assert sig.halt_raw_marker_in_answer == 1
    assert sig.halt_language_in_answer == 1   # it does count as a mention


# --- P2.3's acceptance detector, and the two artefacts it started as ---------
#
# Draft 1 scored **69 of 155 Wave-1 turns** on two bugs. The first was a regex
# alternation that reduced to a bare `\bis`: `r"\bis|are|was|were\s+enabled by"`
# groups as `\bis` OR `are` OR `was` OR `were\s+enabled by`, so every sentence
# containing "is" matched. The second was an instrument screen that accepted the
# bare word "regulations". Draft 2 over-corrected to **1 turn** by compiling the
# instrument screen case-SENSITIVELY, and so missed the heaviest claim in the
# corpus, which opens "Several SSIs ...".
#
# A rate of 100% is an artefact until proven otherwise; so, on this work, is a
# rate of nearly zero. These tests pin the shape in both directions, and every
# string below is a real sentence from a replay run.


@pytest.mark.parametrize("answer", [
    # 6383 t4 (wave1) — the heaviest claim in the corpus, and the BLUF.
    "Yes, multiple Scottish Statutory Instruments (SSIs) have been made under "
    "the enabling authority of section 95 of the Social Security (Scotland) "
    "Act 2018.",
    # 6383 t4 — a claim about preamble content no tool returns.
    "Several SSIs explicitly cite Section 95 to establish the judicial "
    "machinery for Scottish social security appeals:",
    # 6383 rep2 t4 (wave2_p21) — quantified, and entirely unretrievable.
    "Over 130 instruments explicitly cite section 95 in their preamble, "
    "including procedural rules.",
    # 6383 t3 — presentational, so the participial is assertive.
    "Yes, here are two examples of other Scottish Statutory Instruments made "
    "under section 95 of the Social Security (Scotland) Act 2018:",
    # 6374 t4 — the derivation rides a fronted adverbial.
    "Pursuant to the enabling power in section 126(8), several Scottish "
    "Administration (Offices) Orders have designated additional offices.",
    # 6340 t1 — a named instrument and an explicit enabling-power claim. TRUE
    # here, as it happens, and still a claim that needs the evidence.
    "*   **The Grant-Aided Secondary Schools (Scotland) Grant Amendment "
    "Regulations 1979 (SI 1979/766):** This instrument cites sections 75(c) "
    "and 144(5) of the 1962 Act as its enabling powers.",
    # 6383 rep1 t1 (wave2_p21) — a single named instrument, flat assertion.
    "The Council Tax Reduction (Scotland) Amendment Regulations 2019 "
    "(SSI 2019/29) is made under section 95 of the Social Security (Scotland) "
    "Act 2018 and contains the '£' symbol.",
])
def test_a_derivation_claim_is_recognised(answer):
    assert rr.derivation_claims(answer)[0], answer


@pytest.mark.parametrize("answer", [
    # THE hazard. Citing a provision is not asserting a derivation, and a
    # detector that cannot tell them apart pushes the model to hedge what it
    # retrieved — the regression Invariant 1 exists to prevent.
    "Under section 91 of the Act, Ministers must consult before making an "
    "order.",
    # 6383 t4 — a statement of law read straight off s.96, about a CLASS.
    "Under Section 96(4), regulations made under Section 95 are subject to "
    "the affirmative procedure if they add to the text of an Act.",
    # 6409 t6 — the Act's own power-conferring provision, correctly cited.
    "For the remaining provisions, section 27(2) provides the enabling power, "
    "stating that they come into force on such day as the Scottish Ministers "
    "may by regulations appoint.",
    # 6383 t4 — likewise.
    "Section 95 permits Scottish Ministers to make incidental, supplementary "
    "and consequential provisions.",
    # 6374 t4 — a statement about procedure, not about an instrument.
    'Paragraph 1 specifies that an Order made under section 126(8) is subject '
    'to "Type H" procedure.',
    # 6383 t1 — the user's own question restated, not a finding.
    "The search for all Scottish Statutory Instruments made under section 95 "
    "of the Social Security (Scotland) Act 2018 containing a '£' symbol is "
    "too broad and timed out.",
    # 6384 t4 / 6367 t1 — "made under" of something that is not an instrument.
    "This definition is expressly restricted to applications made under "
    "Section 14.",
    "A summary of action taken in response to representations made under the "
    "Consumers, Estate Agents and Redress Act 2007.",
])
def test_citing_a_provision_is_not_asserting_a_derivation(answer):
    """The whole point of the row's detector, and of Invariant 1.

    P2.2's first `NEG_ASSERTED` failed in exactly this shape and scored 100%."""
    assert rr.derivation_claims(answer)[0] == [], answer


@pytest.mark.parametrize("answer", [
    # 6383 t2 — the RIGHT answer, and it must never be graded as a defect.
    "However, the agent could not retrieve the preamble to definitively "
    "confirm if it was made under section 95 of the Social Security "
    "(Scotland) Act 2018.",
    # 6340 t1 — an honest negative about the derivation.
    "The research agent was unable to identify any Statutory Instruments that "
    "cite section 117 of the Education (Scotland) Act 1962 as their enabling "
    "power.",
    # 6409 t6 — a negative, correctly hedged.
    "The specific Scottish Statutory Instruments (SSIs) made under section "
    "27(2) to commence the remaining provisions of the Act have not been "
    "identified in this report.",
])
def test_an_honest_negative_about_the_derivation_is_a_pass(answer):
    """Invariant 1 is load-bearing here: "I cannot verify what this instrument
    was made under" is the CORRECT answer this row is trying to produce. A
    detector that counted it would reward the defect and punish the fix."""
    assert rr.derivation_claims(answer)[0] == [], answer


def test_a_modal_statement_about_what_such_regulations_may_do_is_not_a_claim():
    """6409 t6, read off s.27(3) — about a class, in the subjunctive."""
    answer = ("Section 27(3) specifies that regulations made under this "
              "commencement power may include transitional, transitory, or "
              "saving provisions.")
    asserted, filtered = rr.derivation_claims(answer)
    assert asserted == []


def test_the_recital_screen_finds_a_real_preamble_and_not_a_commencement_note():
    """The two shapes `legislation.description` actually carries, both real."""
    assert rr._DERIV_RECITAL.search(
        "In exercise of the powers conferred upon me by sections 75(c) and "
        "144(5) of the Education (Scotland) Act 1962(a)")
    assert not rr._DERIV_RECITAL.search(
        "These Regulations bring sections 31 and 36 and schedules 5 and 10 of "
        "the Social Security (Scotland) Act 2018 into force on 8 October 2020.")


def test_the_retrieval_check_reads_the_raw_result_not_the_final_one():
    """The recital is in `legislation.description` and a summariser drops it
    first. Grading on `final_result` would report every supported claim as
    unverified — the failing direction that forbids a claim the material
    supports."""
    turn = {"audit": {"delegations": [{"tools": [{
        "name": "get_legislation_text",
        "args": {"legislation_id": "uksi/1979/766"},
        "raw_result": json.dumps({"legislation": {
            "legislation_id": "uksi/1979/766",
            "description": "In exercise of the powers conferred upon me by "
                           "sections 75(c) and 144(5) of the Education "
                           "(Scotland) Act 1962(a)"}}),
        "final_result": "The regulations set out grant arrangements.",
    }]}]}}
    found = rr.retrieved_enabling(turn)
    assert [lid for lid, _ in found] == ["uksi/1979/766"]


def test_a_turn_that_retrieved_no_preamble_reports_none():
    turn = {"audit": {"delegations": [{"tools": [{
        "name": "get_legislation_text",
        "args": {"legislation_id": "ssi/2020/295"},
        "raw_result": json.dumps({"legislation": {
            "legislation_id": "ssi/2020/295",
            "description": "These Regulations bring sections 31 and 36 into "
                           "force on 8 October 2020."},
            "full_text": "Section 1) Citation and commencement"}),
    }]}]}}
    assert rr.retrieved_enabling(turn) == []


@pytest.mark.parametrize("answer", [
    # The exact sentence the FIRST acceptance run produced, and the one the
    # splitter cut into "For example, S.", "I.", "1963/2111 was made under …".
    "For example, S.I. 1963/2111 was made under section 69(4) of the National "
    "Insurance Act 1946, S.I. 1977/1261 was made under section 116 of the "
    "Education (Scotland) Act 1962.",
    # The title form SESSION_LOG already records as a trap, from the other side.
    "The Care Reform (Scotland) Act 2025 (Commencement No. 1) Regulations 2025 "
    "was made under section 82 of the 2025 Act.",
    "SSI 2019/29 (reg. 4) is made under section 95 of the 2018 Act.",
])
def test_abbreviation_dots_do_not_hide_a_claim(answer):
    """**The same full-stop trap, walked into from the other side.**

    SESSION_LOG records it for `NEG_BLAMED_INDEX`: every commencement SSI's
    title contains "Commencement No. 1", so a sentence window keyed on `.`
    cannot cross the titles this corpus is about. The derivation detector hit it
    on the very first acceptance run — the fragment that kept the predicate had
    lost its instrument, so a real claim scored as none.

    An under-read here is not harmless: it would have reported a turn making
    three derivation claims as making none, in the acceptance for the row that
    exists to count them."""
    assert rr.derivation_claims(answer)[0], answer


def test_masking_abbreviations_does_not_merge_real_sentences():
    """The mask must not swallow a genuine sentence break, or two sentences
    become one and a negation in the first would suppress a claim in the
    second."""
    text = ("No SSIs were found under section 95. SSI 2019/29 was made under "
            "section 95 of the 2018 Act.")
    asserted, filtered = rr.derivation_claims(text)
    assert len(asserted) == 1
    assert asserted[0].startswith("SSI 2019/29")


# ---------------------------------------------------------------------------
# blank_verdict — P4.2's acceptance detector (bucket B13)
# ---------------------------------------------------------------------------
#
# The detector that grades a stored turn against "non-empty body whenever cost
# > 0". Validated in both directions over all ten replay directories: it finds
# exactly the 8 billed blanks and the 1 free blank counted by hand, and the
# shortest bodies it leaves alone are real content (a 46-char halt marker, a
# 50-char clarifying question).

_FOOTER = (
    "\n\n*Search scope: the legislation index was searched for "
    '"Social Security (Scotland) Act 2018"; filters in force: '
    "jurisdiction = scotland.*"
)


def _turn(answer="", cost=0.0, **kw):
    t = {"answer": answer, "timing": {"total_cost_usd": cost}, "turn": 1}
    t.update(kw)
    return t


def test_blank_and_billed_is_the_violation():
    kind, cost, body, _ = rr.blank_verdict(_turn("", 0.0602))
    assert kind == "billed"
    assert cost == 0.0602 and body == 0


def test_a_footer_with_nothing_above_it_is_blank():
    """6383 rep 1 turn 4, the shape that made this row worse than it read.

    Since P2.2 a blank answer is not an empty string — the code-emitted scope
    footer is appended unconditionally, so the lawyer is shown 1,293 characters
    of footer and no answer. A detector grading `answer` rather than the body
    scores that turn as fine.
    """
    kind, _, body, answer_chars = rr.blank_verdict(_turn(_FOOTER, 0.4518))
    assert kind == "billed"
    assert body == 0
    assert answer_chars > 100  # there WAS text; none of it was an answer


def test_blank_and_free_is_excluded_not_counted():
    """6374 rep 3 turn 3: 0 delegations, 0 tools, $0. Nothing ran, so nothing
    was lost — a different failure from a turn that researched and then lost
    its answer, and the row's invariant excludes it by construction."""
    kind, cost, _, _ = rr.blank_verdict(_turn("", 0.0))
    assert kind == "free" and cost == 0.0


def test_a_short_real_answer_is_not_blank():
    """The false-positive direction. The shortest bodies in the corpus are
    clarifying questions of ~50 characters, and they are answers."""
    kind, _, body, _ = rr.blank_verdict(
        _turn("Which jurisdiction have you changed the filter to?" + _FOOTER, 0.02)
    )
    assert kind == "ok" and body == 50


def test_whitespace_only_body_is_blank():
    kind, _, _, _ = rr.blank_verdict(_turn("   \n\n\t " + _FOOTER, 0.01))
    assert kind == "billed"


def test_cost_is_read_from_total_cost_usd_not_cost_usd():
    """There is no `cost_usd` key on a run file. Reading one grades every turn
    as free and reports a clean directory — the instrument failing silent in
    the flattering direction, which is the failure mode this work has hit
    eighteen times."""
    t = {"answer": "", "timing": {"cost_usd": 0.5}, "turn": 1}
    assert rr.blank_verdict(t)[0] == "free"
    t["timing"]["total_cost_usd"] = 0.5
    assert rr.blank_verdict(t)[0] == "billed"


def test_missing_timing_does_not_raise():
    assert rr.blank_verdict({"answer": "", "turn": 1})[0] == "free"
    assert rr.blank_verdict({"turn": 1})[0] == "free"


# ---------------------------------------------------------------------------
# lost_sites — P4.5's pre-flight: where a lost completion landed
# ---------------------------------------------------------------------------
#
# Read off the outcome, because an `empty_completions` record carries no
# delegation id. Checked against every stored instance on P4.5's row before any
# number was quoted: 6409 r3 t11 (worker, scope only), 6375 r3 t2 (step, empty),
# 6374 r3 t4 (step, scope only), 6373 r1 t3 (worker, scope only),
# wave3_p313 rep 2 t1 (worker, scope only), wave3_p38/6374 r1 t1 (Manager
# fallback) and baseline/6363 r1 t5 (two empty steps, pre-v3).

_SCOPE_ONLY = (
    "\n\n[SEARCH SCOPE — what this research step actually did]\n"
    "Searched the legislation index 2 time(s) for: \"x\".\n[/SEARCH SCOPE]"
)


def _ldg(report="", kind="delegation", **kw):
    d = {"kind": kind, "report": report, "halted": None, "error": None}
    d.update(kw)
    return d


def _lturn(delegations, answer="An answer.", cost=0.1, chat_mode="research", **kw):
    t = {"turn": 1, "answer": answer, "chat_mode": chat_mode,
         "timing": {"total_cost_usd": cost},
         "audit": {"delegations": delegations, "empty_completions": []}}
    t.update(kw)
    return t


def test_a_scope_block_alone_is_a_lost_worker():
    """6409 r3 t11: the report is the code-appended scope block and nothing
    else, which reads to the Manager as searched-and-found-nothing."""
    sites = rr.lost_sites(_lturn([_ldg(_SCOPE_ONLY), _ldg("A real report.")]))
    assert sites == [{"site": "worker", "step": None, "shape": "scope"}]


def test_an_empty_case_law_step_is_a_lost_step():
    """6375 r3 t2: a case-law step has no scope block, so the report is ''."""
    t = _lturn([_ldg("", kind="deep_research_step", step=1),
                _ldg("Findings.", kind="deep_research_step", step=2)],
               chat_mode="deep_research")
    assert rr.lost_sites(t) == [{"site": "step", "step": 1, "shape": "empty"}]


def test_a_halted_or_failed_worker_is_not_a_lost_one():
    """A halt has its own label (P2.1) and a raised worker its own error
    string; neither is the lost-completion shape."""
    t = _lturn([_ldg("", halted={"reason": "step_cap"}), _ldg("", error="boom")])
    assert rr.lost_sites(t) == []


def test_the_managers_fallback_is_a_lost_manager_completion():
    """wave3_p38/6374 r1 t1: P4.2's labelled fallback served."""
    t = _lturn([_ldg("Report.")],
               answer="**The answering step returned no text, so this is not a "
                      "composed answer.** The research completed ...")
    assert rr.lost_sites(t) == [{"site": "manager", "step": None, "shape": "fallback"}]


def test_the_synthesis_fallback_is_a_lost_synthesis():
    t = _lturn([_ldg("F.", kind="deep_research_step", step=1)],
               answer="**The final synthesis step returned no text, so this "
                      "report is not an integrated answer.** ...",
               chat_mode="deep_research")
    assert rr.lost_sites(t)[0]["site"] == "synthesis"


def test_a_blank_billed_answer_before_p42_is_a_lost_manager():
    assert rr.lost_sites(_lturn([], answer="", cost=0.2)) == [
        {"site": "manager", "step": None, "shape": "blank"}]
    # free and blank: nothing ran, nothing was lost (P4.2's exclusion)
    assert rr.lost_sites(_lturn([], answer="", cost=0.0)) == []


def test_a_labelled_lost_report_is_recognised():
    label = "[Research Incomplete — answer lost]"
    sites = rr.lost_sites(_lturn([_ldg(label + "\nThe step ..." + _SCOPE_ONLY)]),
                          label=label)
    assert sites == [{"site": "worker", "step": None, "shape": "labelled"}]


def test_cmd_lost_ties_unrecovered_calls_to_sites(tmp_path, capsys):
    """One unrecovered call (three failed attempts) and one lost worker: tied,
    so the split is trusted. A second turn with an unrecovered call and no
    site is listed as a disagreement rather than guessed at."""
    probes = [{"model": "m", "sent_chars": 10, "react_turn": 3, "attempt": a,
               "retried": a < 3} for a in (1, 2, 3)]
    t1 = _lturn([_ldg(_SCOPE_ONLY)])
    t1["audit"]["empty_completions"] = probes
    t2 = _lturn([_ldg("Report.")])
    t2["turn"] = 2
    t2["audit"]["empty_completions"] = [dict(p, sent_chars=99) for p in probes]
    d = tmp_path / "dir"
    d.mkdir()
    (d / "1_rep1.json").write_text(
        json.dumps({"session_id": "1", "rep": 1, "turns": [t1, t2]}), encoding="utf-8")
    args = type("A", (), {"dir": str(d), "all_dirs": False, "list": False,
                          "require_label": True})()
    assert rr.cmd_lost(args) == 1  # the lost worker is not labelled
    out = capsys.readouterr().out
    assert "research worker 1" in out and "untied 1" in out
    assert "dir/1 r1 t2: 1 unrecovered call(s), sites none" in out


# ---------------------------------------------------------------------------
# scope_record_gap — P2.9's acceptance detector (bucket B5)
# ---------------------------------------------------------------------------
#
# Did a worker run record every search it issued? Compares the delegation's own
# `tools[]` against the `Searched the legislation index N time(s)` line in the
# scope block appended to its report — a direct measure of what the agent
# writing the negative was actually told.
#
# The discrimination that matters is pre-P2.2 vs all-memo, and the first version
# of this detector got it wrong in the alarming direction.

_BLOCK_OPEN = "[SEARCH SCOPE — what this research step actually did]"
_BLOCK_CLOSE = "[/SEARCH SCOPE]"


def _dg(n_calls, n_memo, recorded=None, block=True):
    """A delegation record: n_calls searches, n_memo of them memo hits, and a
    report whose scope block claims `recorded` searches (None = no such line)."""
    tools = [{"name": "search_legislation", "memo_hit": i < n_memo}
             for i in range(n_calls)]
    report = "findings"
    if block:
        report += f"\n\n{_BLOCK_OPEN}\n"
        if recorded is not None:
            report += f"Searched the legislation index {recorded} time(s) for: \"q\"\n"
        report += "Filters in force for the whole step: none.\n" + _BLOCK_CLOSE
    return {"tools": tools, "report": report}


def test_a_complete_record_reports_no_gap():
    assert rr.scope_record_gap(_dg(3, 0, recorded=3)) == (3, 0, 3)


def test_a_memo_served_search_shows_as_missing():
    """The defect: 4 issued, 1 of them memo-served, 3 recorded."""
    issued, memo, recorded = rr.scope_record_gap(_dg(4, 1, recorded=3))
    assert (issued, memo, recorded) == (4, 1, 3)
    assert issued - recorded == memo


def test_an_all_memo_run_has_a_block_but_records_nothing():
    """6374 rep 1 turn 2. Its only search was a memo hit, so the block carries
    no searched-for line at all — while still instructing that a negative "MUST
    quote the search terms above". `recorded` is 0, and that is the honest
    reading: the block exists, and it recorded no search."""
    assert rr.scope_record_gap(_dg(1, 1, recorded=None)) == (1, 1, 0)


def test_a_run_predating_p2_2_is_excluded_not_counted_as_total_loss():
    """The correction. `wave1` and `wave2_p21` have no scope block at all — the
    feature did not exist — so "recorded nothing" there means "nothing records
    anything", not "the memo ate it".

    The first version inferred block-absence from `recorded == 0`, which cannot
    tell a pre-P2.2 run from an all-memo one, and reported `wave1` as having 13
    runs "with a scope block" losing 100% of their searches. Keying on the block
    MARKER settles it: `wave1` is 182 runs excluded, none counted.
    """
    assert rr.scope_record_gap(_dg(3, 3, recorded=None, block=False)) is None
    # ...and the all-memo run above, which looks identical on the count alone,
    # is still counted.
    assert rr.scope_record_gap(_dg(3, 3, recorded=None, block=True)) == (3, 3, 0)


def test_a_run_that_issued_no_search_is_not_in_the_denominator():
    """A worker that only retrieved text has nothing to under-record."""
    assert rr.scope_record_gap({"tools": [{"name": "get_legislation_text"}],
                                "report": f"{_BLOCK_OPEN}\n{_BLOCK_CLOSE}"}) is None
    assert rr.scope_record_gap({"tools": [], "report": ""}) is None


def test_missing_keys_do_not_raise():
    assert rr.scope_record_gap({}) is None


# ---------------------------------------------------------------------------
# nosearch_rows / nosearch_verdict — P2.8's acceptance (P2.10 folded in)
# ---------------------------------------------------------------------------
#
# Promoted from SESSION_LOG Session 12's ad-hoc script, which graded "asserts a
# negative" with `NOT_FOUND` (the P0.3 baseline regex) instead of
# `NEG_ASSERTED` (P2.2's). It found 1 turn of shape (A) where there are 5, and a
# row was nearly closed on it. Validated over all ten replay directories: 608
# answered, 210 negative, (A) 5 negative, (B) 14 turns with 12 negative, which
# are Session 12's corrected figures exactly.

_P28_FRESH = (
    '\n\n*Search scope: the legislation index was searched for "SSI 2025/377"; '
    "no jurisdiction, type or date filter narrowed it. This is a ranked search "
    "of an index that is known to be incomplete, so anything reported above as "
    "not found was not found in this index, which is not the same as being "
    "absent from the law.*"
)
_P28_CARRIED = (
    "\n\n*Search scope: no search of the legislation index was run for this "
    'reply. Earlier in this conversation it was searched for "SSI 2025/377"; '
    "no jurisdiction, type or date filter narrowed it. Each was a ranked search "
    "of an index that is known to be incomplete, so a result reported as not "
    "found in those searches was not found in this index, which is not the same "
    "as being absent from the law.*"
)
_P28_NEG = ("As noted in the previous search, SSI 2025/377 is not currently "
            "available in the legislation database.")


def _ns_turn(n, answer, tools=None, delegated=None, peer=False):
    """A stored turn. `tools=None` with `delegated=False` is shape A."""
    if delegated is None:
        delegated = tools is not None
    audit = {"delegations": ([{"tools": [{"name": x} for x in (tools or [])]}]
                             if delegated else [])}
    if peer:
        audit["peer_consults"] = [{"peer_id": "parliament_bot"}]
    return {"turn": n, "answer": answer, "audit": audit}


def _ns(*turns):
    return {"session_id": "6409", "rep": 1, "turns": list(turns)}


def _verdicts(doc):
    return {r["turn"]: rr.nosearch_verdict(r) for r in rr.nosearch_rows(doc)}


def test_a_restated_negative_with_no_scope_line_is_the_defect():
    """6409 rep 1 turn 11's shape, before and after the fix."""
    before = _ns(_ns_turn(1, "Found." + _P28_FRESH, ["search_legislation"]),
                 _ns_turn(2, _P28_NEG))
    assert _verdicts(before) == {1: None, 2: "UNQUALIFIED"}
    after = _ns(_ns_turn(1, "Found." + _P28_FRESH, ["search_legislation"]),
                _ns_turn(2, _P28_NEG + _P28_CARRIED))
    assert _verdicts(after) == {1: None, 2: None}


def test_a_negative_with_no_earlier_search_is_not_this_rows_defect():
    """6347 turn 1's shape: nothing was searched earlier, so there is nothing to
    carry. That turn is P4.1's and P2.7's, and this command must not count it."""
    doc = _ns(_ns_turn(1, _P28_NEG, [], delegated=True))
    rows = rr.nosearch_rows(doc)
    assert rows[0]["shape"] == "B" and rows[0]["neg"] and not rows[0]["searched_before"]
    assert rr.nosearch_verdict(rows[0]) is None


def test_a_scope_statement_for_a_search_not_run_is_caught_every_way():
    fresh_on_nothing = _ns(_ns_turn(1, "Found." + _P28_FRESH, ["search_legislation"]),
                           _ns_turn(2, "Yes." + _P28_FRESH))
    carried_on_a_search = _ns(_ns_turn(1, "Found." + _P28_FRESH, ["search_legislation"]),
                              _ns_turn(2, "Yes." + _P28_CARRIED, ["search_legislation"]))
    carried_from_nothing = _ns(_ns_turn(1, "Yes." + _P28_CARRIED))
    assert _verdicts(fresh_on_nothing)[2] == "MISATTRIBUTED"
    assert _verdicts(carried_on_a_search)[2] == "MISATTRIBUTED"
    assert _verdicts(carried_from_nothing)[1] == "MISATTRIBUTED"


def test_selection_is_neg_asserted_on_the_prose_not_not_found():
    """The Session 12 error, pinned in both directions. `NOT_FOUND` misses the
    corpus-shaped refusal, and the carried line's own "not found" must not enrol
    a positive turn."""
    refusal = "The available database does not contain information on this specific issue."
    assert not rr.NOT_FOUND.search(refusal)
    doc = _ns(_ns_turn(1, "Found." + _P28_FRESH, ["search_legislation"]),
              _ns_turn(2, refusal, [], delegated=True),
              _ns_turn(3, "Yes, it was made." + _P28_CARRIED))
    rows = {r["turn"]: r for r in rr.nosearch_rows(doc)}
    assert rows[2]["neg"] is True
    assert rows[3]["neg"] is False
    assert rows[3]["line"] == "carried"


def test_shapes_and_the_history_rule():
    """A blank turn joins no history (`replay.py`), so a search it ran does not
    make the next turn "after a search"."""
    doc = _ns(_ns_turn(1, "", ["search_legislation"]),
              _ns_turn(2, _P28_NEG),
              _ns_turn(3, "Text.", ["get_legislation_text"]),
              _ns_turn(4, "Refs.", ["search_legislation_sections"]),
              _ns_turn(5, _P28_NEG, [], delegated=True))
    rows = {r["turn"]: r for r in rr.nosearch_rows(doc)}
    assert 1 not in rows
    assert rows[2]["shape"] == "A" and not rows[2]["searched_before"]
    assert rows[3]["shape"] == "C" and not rows[3]["searched_now"]
    assert rows[4]["searched_now"]            # a section search IS a search
    assert rows[5]["shape"] == "B" and rows[5]["searched_before"]
    assert rr.nosearch_verdict(rows[5]) == "UNQUALIFIED"


def test_a_peer_consult_turn_is_exempt():
    """The product stays silent there on purpose: the peer's searches are not in
    this turn's record."""
    doc = _ns(_ns_turn(1, "Found." + _P28_FRESH, ["search_legislation"]),
              _ns_turn(2, _P28_NEG, delegated=False, peer=True))
    assert _verdicts(doc)[2] is None


def _ec(attempt, retried, sent=16724, turn=3):
    return {"model": "google/gemini-3.1-pro-preview", "attempt": attempt,
            "attempts_max": 3, "retried": retried, "sent_chars": sent,
            "react_turn": turn}


def test_three_failed_attempts_are_one_unrecovered_call():
    """`wave2_p28/6409 rep 3 turn 11`, the real shape. The first `blanks` read
    it as two recoveries and one failure."""
    assert rr.empty_completion_calls(
        [_ec(1, True), _ec(2, True), _ec(3, False)]) == [(3, False)]


def test_a_call_whose_retry_succeeded_is_recovered():
    """The retry that worked leaves no record, so the last record says
    `retried: true`."""
    assert rr.empty_completion_calls([_ec(1, True)]) == [(1, True)]
    assert rr.empty_completion_calls([_ec(1, True), _ec(2, True)]) == [(2, True)]


def test_separate_calls_are_not_merged():
    probes = [_ec(1, True), _ec(1, True, sent=900, turn=1),
              _ec(2, False, sent=900, turn=1), _ec(1, False)]
    assert rr.empty_completion_calls(probes) == [(1, True), (2, False), (1, False)]
    # The same request recurring later, after its first call recovered, is a
    # new call, not a continuation.
    assert rr.empty_completion_calls([_ec(1, True), _ec(1, True)]) == [(1, True), (1, True)]
    assert rr.empty_completion_calls(None) == []
    assert rr.empty_completion_calls([None, "x"]) == []


def test_a_clean_v3_directory_is_not_reported_as_predating_the_field(tmp_path, capsys):
    """P4.2 made `empty_completions` present-and-empty on a healthy turn so that
    "nothing was lost" is distinguishable from "no field". `blanks` tested the
    list's truthiness and called `wave2_p28_smoke` pre-v3."""
    import argparse
    turn = {"turn": 1, "answer": "A body.", "timing": {"total_cost_usd": 0.1},
            "audit": {"schema_version": 3, "empty_completions": []}}
    (tmp_path / "6409_rep1.json").write_text(json.dumps(
        {"session_id": "6409", "rep": 1, "turns": [turn]}), encoding="utf-8")
    assert rr.cmd_blanks(argparse.Namespace(dir=str(tmp_path))) == 0
    out = capsys.readouterr().out
    assert "predates audit schema v3" not in out
    assert "empty completion attempts               0" in out

    del turn["audit"]["empty_completions"]
    (tmp_path / "6409_rep1.json").write_text(json.dumps(
        {"session_id": "6409", "rep": 1, "turns": [turn]}), encoding="utf-8")
    rr.cmd_blanks(argparse.Namespace(dir=str(tmp_path)))
    assert "predates audit schema v3" in capsys.readouterr().out


def test_the_invariant_one_check_reads_the_prose_not_the_footer(tmp_path, capsys):
    """P2.8 appends a line to answers that had none, so a full-length
    comparison grows by construction. The check must grade the model's prose,
    and only the sessions `--only` names."""
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    first = _ns_turn(1, "Found." + _P28_FRESH, ["search_legislation"])
    (before / "6409_r1.json").write_text(json.dumps(
        _ns(first, _ns_turn(2, _P28_NEG))), encoding="utf-8")
    (after / "6409_r1.json").write_text(json.dumps(
        _ns(first, _ns_turn(2, _P28_NEG + _P28_CARRIED))), encoding="utf-8")
    other = {"session_id": "6341", "rep": 1,
             "turns": [_ns_turn(1, "x" * 900, ["search_legislation"])]}
    (after / "6341_r1.json").write_text(json.dumps(other), encoding="utf-8")

    rr._invariant_one_prose(before, after, ["6409"])
    out = capsys.readouterr().out
    assert "sessions 6409" in out and "6341" not in out
    assert "0 of 2 grew" in out
    assert "turns asserting a negative / rep" in out


def test_nosearch_prints_the_cost_and_exits_on_a_finding(tmp_path, capsys):
    """The published cost (firings, and how many had a negative to qualify) is
    printed by the command, and a finding exits 1."""
    import argparse
    doc = _ns(_ns_turn(1, "Found." + _P28_FRESH, ["search_legislation"]),
              _ns_turn(2, _P28_NEG + _P28_CARRIED),
              _ns_turn(3, "Which one?" + _P28_CARRIED),
              _ns_turn(4, _P28_NEG))
    (tmp_path / "6409_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    args = argparse.Namespace(dir=str(tmp_path), all=False, answers=False,
                              chars=100, before=None, only=None)
    assert rr.cmd_nosearch(args) == 1
    out = capsys.readouterr().out
    assert ("no-search turns after a searched turn        3   of which negative 2"
            "   carrying the carried line 2") in out
    assert "UNQUALIFIED   restated negative, no scope statement   1" in out


def test_nosearch_missing_keys_do_not_raise():
    assert rr.nosearch_rows({}) == []
    assert rr.nosearch_rows({"turns": [{"answer": "x"}]})[0]["shape"] == "A"


# --- P3.1 (B10): the depth grader -------------------------------------------
#
# Every fixture is a shape a replay actually produced (`baseline`/`wave1`), not
# a synthetic label: P1.4's `test_bad_link_*` stayed green for three sessions
# because its fixtures were shapes no real answer has.

_WISA = "Water Industry (Scotland) Act 2002"
_PFA = "Public Finance and Accountability (Scotland) Act 2000"


def _link(act, label, act_id, sec):
    return (f"[{act} - {label}](http://www.legislation.gov.uk/{act_id}/"
            f"section/{sec})")


@pytest.mark.parametrize("text,num", [
    ("s.57(3)(a)", "57"), ("Section 57(3a) and (4)", "57"), ("s. 21(2)", "21"),
    ("section 45(2) of the 2002 Act", "45"), ("s.22(5)(a)", "22"),
    ("ss.21(3)-(5)", "21"),
])
def test_a_subsection_citation_is_deep(text, num):
    deep, coarse = rr._section_patterns(num)
    assert deep.search(text)
    assert not coarse.search(text)


def test_the_long_form_subsection_is_deep_although_its_tail_reads_coarse():
    """"subsection (3) of section 57" ends in a bare "section 57", so both
    patterns match; the grader tests deep first, so the verdict is deep."""
    deep, _ = rr._section_patterns("57")
    assert deep.search("subsection (3) of section 57")
    ans = _6365([(_WISA, "asp/2002/3", "s.45(1)"), (_WISA, "asp/2002/3", "s.57"),
                 (_PFA, "asp/2000/1", "s.21(2)"), (_PFA, "asp/2000/1", "s.22(5)")])
    ans += f"\nUnder the {_WISA}, subsection (3) of section 57 sets the periods."
    assert rr.depth_verdict("6365", ans)[0] == "DELIVERED"


@pytest.mark.parametrize("text,num", [
    ("Section 57", "57"), ("s. 21", "21"), ("s.45.", "45"),
    ("sections 21 and 22 of the 2000 Act", "22"),
    ("sections 26, 28, 50 and 51", "28"),
])
def test_a_whole_section_citation_is_coarse(text, num):
    deep, coarse = rr._section_patterns(num)
    assert coarse.search(text)
    assert not deep.search(text)


@pytest.mark.parametrize("text,num", [
    ("section 57A(1)", "57"), ("section 570", "57"),
    ("Scotland’s 20 days", "20"), ("Scotland's 20 days", "20"),
    ("http://www.legislation.gov.uk/asp/2000/1/section/21", "21"),
    ("SSI 2007/174", "2007"),
])
def test_a_different_provision_is_neither(text, num):
    deep, coarse = rr._section_patterns(num)
    assert not deep.search(text) and not coarse.search(text)


def test_attribution_takes_the_nearest_instrument_on_the_line():
    acts = rr.DEPTH_TRUTH["6365"]["acts"]
    text = (f"Ministers direct the deadline (**{_WISA}, Section 45**), but the "
            f"2000 Act caps it ({_link(_PFA, 's.21(2)', 'asp/2000/1', 21)}).")
    assert rr._attribute_instrument(text, text.index("Section 45"), acts) == "asp/2002/3"
    assert rr._attribute_instrument(text, text.index("s.21(2)"), acts) == "asp/2000/1"


def test_attribution_falls_back_to_the_last_instrument_named():
    acts = rr.DEPTH_TRUTH["6365"]["acts"]
    text = f"Under the {_PFA}:\n* the account goes to the Auditor General (s.21(2))."
    assert rr._attribute_instrument(text, text.index("s.21(2)"), acts) == "asp/2000/1"
    assert rr._attribute_instrument("s.21(2) alone", 0, acts) is None


def _6365(labels):
    return "\n".join(
        f"* step ({_link(act, lab, aid, lab.split('.')[1].split('(')[0])})."
        for act, aid, lab in labels)


def test_6365_all_whole_sections_is_shallow():
    """`baseline` rep 2 and the original: the lawyer's complaint exactly."""
    ans = _6365([(_WISA, "asp/2002/3", "s.45"), (_WISA, "asp/2002/3", "s.57"),
                 (_PFA, "asp/2000/1", "s.21"), (_PFA, "asp/2000/1", "s.22")])
    verdict, graded = rr.depth_verdict("6365", ans)
    assert verdict == "SHALLOW"
    assert [g[1] for g in graded] == ["coarse"] * 4


def test_6365_every_anchor_at_subsection_depth_is_delivered():
    ans = _6365([(_WISA, "asp/2002/3", "s.45(1)(c)"),
                 (_WISA, "asp/2002/3", "s.57(3)(a)"),
                 (_PFA, "asp/2000/1", "s.21(2)"), (_PFA, "asp/2000/1", "s.22(5)")])
    assert rr.depth_verdict("6365", ans)[0] == "DELIVERED"


def test_6365_a_subsection_attributed_to_the_other_act_does_not_count():
    """PFA(S)A s.21(2) cited under the 2002 Act's name is not PFA(S)A s.21."""
    ans = _6365([(_WISA, "asp/2002/3", "s.45(1)"), (_WISA, "asp/2002/3", "s.57(3)"),
                 (_WISA, "asp/2002/3", "s.21(2)"), (_PFA, "asp/2000/1", "s.22(5)")])
    verdict, graded = rr.depth_verdict("6365", ans)
    assert verdict == "PARTIAL"
    assert dict((g[0].label, g[1]) for g in graded)["PFA(S)A 2000 s.21"] == "missed"


_6396_DELIVERED = (
    "Under Schedule 1, Section 1(2) of [The Cattle Identification (Scotland) "
    "Regulations 2007](http://www.legislation.gov.uk/id/ssi/2007/174), the time "
    "limits are:\n\n*   **Dairy animals:** First ear tag within 36 hours of "
    "birth; second ear tag within 20 days of birth.\n*   **All other bovine "
    "animals:** Within 20 days of birth.")


@pytest.mark.parametrize("cite", [
    "Schedule 1, Section 1(2)", "Schedule 1, paragraph 1(2)(a)",
    "paragraph 1(2) of Schedule 1 to", "Sch. 1, para. 1(2)",
])
def test_6396_the_paragraph_with_both_limits_is_delivered(cite):
    ans = _6396_DELIVERED.replace("Schedule 1, Section 1(2)", cite)
    assert rr.depth_verdict("6396", ans)[0] == "DELIVERED"


def test_6396_the_limits_without_the_paragraph_are_shallow():
    """`baseline` rep 1: the right numbers, from memory, while saying the
    Regulations "could not be retrieved". Stating them is not citing them."""
    ans = ("The Cattle Identification (Scotland) Regulations 2007 could not be "
           "retrieved in this quick search. The 2007 Regulations generally set "
           "specific deadlines (e.g., 20 days for the second tag, or 36 hours "
           "for the first tag in dairy herds).")
    assert rr.depth_verdict("6396", ans)[0] == "SHALLOW"


def test_6396_one_limit_only_is_shallow_and_could_not_locate_is_missed():
    one = ("Under the Cattle Identification (Scotland) Regulations 2007 (SSI "
           "2007/174), a bovine animal must be identified within **20 days**.")
    assert rr.depth_verdict("6396", one)[0] == "SHALLOW"
    none = ("I was unable to locate the specific timeframe. The relevant "
            "provisions are likely within the Cattle Identification (Scotland) "
            "Regulations 2007.")
    assert rr.depth_verdict("6396", none)[0] == "MISSED"


_FOISA = "Freedom of Information (Scotland) Act 2002"


@pytest.mark.parametrize("sentence", [
    "*(Note: This is distinct from Section 36(2), which deals with information "
    "obtained from a third party where disclosure would constitute an "
    "actionable breach of confidence).*",
    "While an actionable breach of confidence under **Section 36(2)** is listed "
    "as an absolute exemption under **Section 2(2)(c)**, section 36(1) is not.",
    "Section 36 also exempts information obtained from another person where "
    "disclosure would be actionable.",
    "**Section 36(2):**\nInformation obtained from another person whose "
    "disclosure would be an actionable breach of confidence.",
])
def test_6348_s36_2_with_its_substance_is_delivered(sentence):
    ans = f"Under the {_FOISA}, section 36(1) covers privilege.\n\n{sentence}"
    assert rr.depth_verdict("6348", ans)[0] == "DELIVERED"


@pytest.mark.parametrize("ans", [
    # The original t1 and t2: s.36(1) only.
    f"Under section 36(1) of the [{_FOISA}](http://www.legislation.gov.uk/id/"
    "asp/2002/13), information is exempt if a claim to confidentiality of "
    "communications could be maintained in legal proceedings.",
    # Named, with no substance.
    f"Under the {_FOISA}, s.36(1) is qualified; s.36(2) is absolute under s.2(2)(c).",
    # Substance about a DIFFERENT provision is not s.36(2).
    f"Under the {_FOISA}, section 36(1) applies. Under the Data Protection Act "
    "2018, Schedule 2 paragraph 19 covers an actionable breach of confidence.",
])
def test_6348_s36_1_alone_or_s36_2_named_bare_is_shallow(ans):
    assert rr.depth_verdict("6348", ans)[0] == "SHALLOW"


def test_the_scope_footer_cannot_satisfy_the_grader():
    """P2.2's footer quotes the search terms. A worker that searched for
    "section 36(2) actionable breach of confidence" must not deliver 6348."""
    ans = (f"Under the {_FOISA}, section 36(1) applies.\n\n*Search scope: "
           'searched the legislation index for "section 36(2) actionable breach '
           'of confidence", no filters.*')
    assert rr.depth_verdict("6348", ans)[0] == "SHALLOW"


def test_depth_counts_is_the_stricter_readout_beside_the_verdict():
    """The first HEAD run of 6365 met s.57 through an amendment note while
    every timeline claim linked the bare section: DELIVERED on the lenient bar,
    1 of 3 on this one. The long form is not double-counted."""
    req = [r for r in rr.DEPTH_TRUTH["6365"]["reqs"] if r.label.endswith("s.57")][0]
    acts = rr.DEPTH_TRUTH["6365"]["acts"]
    ans = (f"{_link(_WISA, 's.57', 'asp/2002/3', 57)} and "
           f"{_link(_WISA, 's.57', 'asp/2002/3', 57)}; the 2005 Act substituted "
           f"Section 57(7)(a) of the {_WISA}.")
    assert rr.depth_counts(ans, req, acts) == (1, 3)
    assert rr.depth_counts(f"Under the {_WISA}, subsection (3) of section 57.",
                           req, acts) == (1, 1)


def test_depth_profile_counts_subdivisions():
    n, sub = rr.depth_profile("See s.57(3)(a), section 45, reg. 5(1) and "
                              "paragraph 19. *Search scope: s.99(1).*")
    assert (n, sub) == (4, 2)


def test_an_ungraded_session_is_not_applicable():
    assert rr.depth_verdict("6341", "anything") == ("n/a", [])


def test_the_depth_command_reads_a_directory_and_the_before_panel(tmp_path, capsys):
    import argparse
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    shallow = _6365([(_WISA, "asp/2002/3", "s.45"), (_WISA, "asp/2002/3", "s.57"),
                     (_PFA, "asp/2000/1", "s.21"), (_PFA, "asp/2000/1", "s.22")])
    deep = _6365([(_WISA, "asp/2002/3", "s.45(1)"), (_WISA, "asp/2002/3", "s.57(3)"),
                  (_PFA, "asp/2000/1", "s.21(2)"), (_PFA, "asp/2000/1", "s.22(5)")])
    for d, ans in ((before, shallow), (after, deep)):
        turn = {"turn": 1, "answer": ans,
                "audit": {"sources": [{"url": "u"}] * 3}}
        (d / "6365_rep1.json").write_text(json.dumps(
            {"session_id": "6365", "rep": 1, "turns": [turn]}), encoding="utf-8")
    (after / "6341_rep1.json").write_text(json.dumps(
        {"session_id": "6341", "rep": 1, "turns": [{"turn": 1, "answer": "x"}]}),
        encoding="utf-8")
    args = argparse.Namespace(dir=str(after), answers=True, drops=True,
                              all=True, before=str(before))
    assert rr.cmd_depth(args) == 0
    out = capsys.readouterr().out
    assert "6365  t1  DELIVERED 1/1" in out
    assert "(1 graded run file(s))" in out
    assert "-> asp/2000/1" in out
    assert "rail_sources 3.0 -> 3.0" in out
    assert "fell in: prose 0/1" in out


# ---------------------------------------------------------------------------
# P3.11: `depth --seams` - the requirement graded at each seam it passes through
# ---------------------------------------------------------------------------

_S36_URL = "http://www.legislation.gov.uk/id/asp/2002/13/section/36"
_S36_RAW = json.dumps({"results": [{
    "legislation_id": "asp/2002/13", "number": 36, "provision_type": "section",
    "title": "Confidentiality", "url": _S36_URL,
    "text": ("Section 36) **Confidentiality**\n\n"
             "1) Information in respect of which a claim to confidentiality of "
             "communications could be maintained in legal proceedings is exempt "
             "information. \n"
             "2) Information is exempt information if— \n"
             "\ta) it was obtained by a Scottish public authority from another "
             "person; and \n\tb) its disclosure would be a breach of confidence. "),
}], "returned": 1})


def _6348_run(summary, report, answer):
    return {"session_id": "6348", "rep": 1, "turns": [{
        "turn": 1, "answer": answer, "question": "q",
        "audit": {"sources": [], "delegations": [{
            "report": report,
            "tools": [{"name": "search_legislation_sections",
                       "args": {"legislation_id": "asp/2002/13", "query": "x"},
                       "raw_result": _S36_RAW, "summarised": True,
                       "final_result": summary
                       + "\n\n[CITATION URLS - these are the URLs this retrieval returned.]"
                       f"\n- section 36: {_S36_URL}"
                       "\n\n[SECTION OUTLINE — the numbered subsections]\n- s.36 "
                       "Confidentiality\n  (2) Information is exempt information if "
                       "obtained from another person\n[/SECTION OUTLINE]"
                       "\n\n[SEARCH SCOPE — 1 provision(s) of asp/2002/13.]"}],
        }]},
    }]}


def test_depth_seams_grades_the_summary_the_report_and_the_answer(tmp_path, capsys):
    """The measurement behind P3.11: the summariser kept s.36(2) in 1 of 11
    stored summaries. The readout must grade the summariser's OWN text - with
    the URL block, the outline and the scope note removed, or the outline
    would make every summary deep by construction."""
    import argparse
    d = tmp_path / "d"
    d.mkdir()
    summary = ("Freedom of Information (Scotland) Act 2002.\n### Section 36: "
               "Confidentiality\n* **36(1):** privileged communications are exempt.")
    (d / "6348_rep1.json").write_text(json.dumps(_6348_run(
        summary,
        "Under section 36(1) of the Freedom of Information (Scotland) Act 2002 the "
        "information is exempt.",
        "Section 36(1) of the Freedom of Information (Scotland) Act 2002 applies.",
    )), encoding="utf-8")
    args = argparse.Namespace(dir=str(d), answers=False, drops=False, all=False,
                              before=None, seams=True)
    assert rr.cmd_depth(args) == 0
    out = capsys.readouterr().out
    assert ("6348 rep1 t1  FOISA s.36(2), with its substance:  summary coarse  "
            "report coarse  answer coarse   s.36 subsections in the summaries: {1}") in out
    assert "summarised searches 1, outline non-empty for 1" in out


def test_depth_seams_reads_a_summary_that_kept_the_sibling(tmp_path, capsys):
    import argparse
    d = tmp_path / "d"
    d.mkdir()
    summary = ("Freedom of Information (Scotland) Act 2002. Section 36(2) exempts "
               "information obtained from another person; 36(1) covers privilege.")
    (d / "6348_rep1.json").write_text(json.dumps(_6348_run(
        summary,
        "Section 36(1) of the Freedom of Information (Scotland) Act 2002 only.",
        "Section 36(1) of the Freedom of Information (Scotland) Act 2002 only.",
    )), encoding="utf-8")
    args = argparse.Namespace(dir=str(d), answers=False, drops=False, all=False,
                              before=None, seams=True)
    assert rr.cmd_depth(args) == 0
    out = capsys.readouterr().out
    assert "summary deep  report coarse  answer coarse   s.36 subsections in the summaries: {1, 2}" in out


def test_subsections_mentioned_reads_both_ways_a_summary_writes_them():
    """Two of 6348's eleven stored summaries list a bare "(1)" under a
    "**Section 36: Confidentiality**" heading and never write "36(1)"; the
    first version of this readout printed them as mentioning nothing."""
    summary = ("Freedom of Information (Scotland) Act 2002.\n"
               "**Section 36: Confidentiality**\n(1) Privilege.\n(2) Obtained from another.\n\n"
               "**Section 50: Information notices**\n(5) Not obliged.\n"
               "Elsewhere s.36(2A) is cited.")
    assert rr._subsections_mentioned(summary, "36") == ["1", "2", "2A"]
    assert rr._subsections_mentioned(summary, "50") == ["5"]
    assert rr._subsections_mentioned("### Section 136\n(1) x", "36") == []
    # The third form, a numbered list under the heading (`wave3_p311/6348 r2`).
    assert rr._subsections_mentioned(
        "**Section 36: Confidentiality**\n1. Privilege.\n2. Other.", "36") == ["1", "2"]
    # The fourth: a bulleted heading with bulleted bold subsections (`wave3_p311/6348 r3`).
    assert rr._subsections_mentioned(
        "*   **Section 36 (Confidentiality)**\n    *   **(1)** Privilege.\n    *   **(2)** Other.\n"
        "*   **Section 50 (Notices)**\n    *   **(5)** x", "36") == ["1", "2"]


def test_summary_text_strips_every_appended_block_and_nothing_else():
    from src.utils.search_scope import strip_scope_blocks
    final = _6348_run("The summary.", "", "")["turns"][0]["audit"]["delegations"][0]["tools"][0]["final_result"]
    assert rr._summary_text(final, strip_scope_blocks) == "The summary."
    assert rr._section_number(rr.DEPTH_TRUTH["6348"]["reqs"][0]) == "36"
    assert rr._section_number(rr.DEPTH_TRUTH["6396"]["reqs"][0]) == ""
