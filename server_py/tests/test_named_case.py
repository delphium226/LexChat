"""P3.46: a case a `search_case_law` query names that the search did not return.

Batch 12 E's hand-read: answers stated what an authority the National Archives
does not hold had decided, as if its judgment had been read, and each such
answer in one session followed a search whose query named that case and whose
results did not include it. The Worker was told nothing. Now the result says
so, in code (`caselaw.named_case_note`, wired in `run_worker_tool`):

* a case is named "A v B" (capitalised parties), by a neutral citation, or by
  a law report; a report beside a name or a citation travels with it;
* it counts as returned when a result's title carries a distinctive word of
  each party, or a result carries its neutral citation (citation, title or
  Find Case Law URL). It errs towards "returned": a false "not returned"
  would tell the Worker a held judgment is absent (Invariant 1);
* a law report alone cannot be matched, and is never said to be missing;
* Find Case Law's list and, with P3.20's setting on, the Scottish list are
  read; a list whose search did not run counts for nothing.

Every case, party and citation here is synthetic.
"""
import json
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.tools.caselaw import (
    NAMED_CASE_BOTH,
    NAMED_CASE_FCL,
    NAMED_CASE_SCTS,
    case_returned,
    named_case_note,
    named_cases,
)
from src.utils.search_scope import strip_scope_blocks

U = "https://caselaw.nationalarchives.gov.uk/"
OTHER = {"title": "Gadget plc v Example Council", "ncn": "[1901] EWHC 3 (Ch)",
         "url": U + "ewhc/ch/1901/3"}
WIDGET = {"title": "Widget Co v Example Ltd", "ncn": "[1901] UKSC 4", "url": U + "uksc/1901/4"}
SCOT = {"title": "Sprocket v Cog", "ncn": "[1901] CSOH 5", "court": "Court of Session",
        "url": "https://www.scotcourts.gov.uk/media/x.pdf", "decision_date": "1901-01-01"}


def fcl(rows, total=None, exact=None):
    n = len(rows)
    return {"results": rows, "shown": n, "total": n if total is None else total,
            "total_exact": (total is None) if exact is None else exact}


def both(rows, scot, scot_total=None, status="ok"):
    d = fcl(rows)
    d["scottish_results"] = scot
    d["scottish"] = {"status": status, "shown": len(scot),
                     "total": len(scot) if scot_total is None else scot_total}
    return d


def note(query, data):
    return named_case_note({"query": query}, data)


def _one(query):
    cases = named_cases(query)
    assert len(cases) == 1, cases
    return cases[0]


# --- what a query names ---------------------------------------------------------------

def test_a_name_its_parties_and_quotes():
    c = _one('"Widget Co v Example Ltd" duty of care')
    assert c["shown"] == "Widget Co v Example Ltd"
    assert c["a"] == {"widget"} and c["b"] == {"example"}
    assert c["ncn"] is None and c["report"] is False


def test_a_name_with_a_comma_and_joiners_keeps_every_word():
    c = _one("Gadget v Sprocket, Cogwheel and Ratchet duty")
    assert c["shown"] == "Gadget v Sprocket, Cogwheel and Ratchet"
    assert c["b"] == {"sprocket", "cogwheel", "ratchet"}


def test_a_neutral_citation_beside_a_name_is_that_cases():
    c = _one("Widget Co v Example Ltd [1901] EWCA Civ 7 consent")
    assert c["ncn"] == "1901 EWCACIV 7" and c["shown"] == "Widget Co v Example Ltd (1901) EWCA Civ 7"


def test_a_law_report_beside_a_name_travels_with_it_and_the_name_decides():
    c = _one("Widget Co v Example Ltd [1901] AC 9")
    assert c["report"] is False and c["ncn"] is None
    assert c["shown"] == "Widget Co v Example Ltd (1901) AC 9"


def test_a_neutral_citation_alone():
    c = _one("[1901] UKSC 9")
    assert c["ncn"] == "1901 UKSC 9" and c["shown"] == "the judgment cited as (1901) UKSC 9"


@pytest.mark.parametrize("cite,key", [
    ("[1901] EWHC 12 (Admin)", "1901 EWHC 12"),
    ("[1901] UKUT 3 (IAC)", "1901 UKUT 3"),
    ("[1901] EAT 27", "1901 EAT 27"),
    ("[1901] CSOH 5", "1901 CSOH 5"),
    ("[1901] SAC (Civ) 2", "1901 SACCIV 2"),
    ("[1901] SC EDIN 4", "1901 SCEDIN 4"),
    ("[1901] HCJAC 6", "1901 HCJAC 6"),
])
def test_neutral_citations_of_every_court_family(cite, key):
    assert _one(cite)["ncn"] == key


@pytest.mark.parametrize("cite", ["[1901] AC 9", "[1901] 2 All ER 7", "(1901) 1 QB 3",
                                  "1901 SLT 7", "1901 SC 12"])
def test_a_law_report_alone_is_named_and_marked_unmatchable(cite):
    c = _one(f"{cite} control test")
    assert c["report"] is True and c["ncn"] is None


def test_two_names_joined_by_and_are_two_cases():
    cases = named_cases("Widget v Example and Gizmo v Sprocket")
    assert [c["shown"] for c in cases] == ["Widget v Example", "Gizmo v Sprocket"]


def test_two_names_with_nothing_between_split_at_the_second_names_last_word():
    cases = named_cases("Widget v Example Gizmo v Sprocket")
    assert [c["shown"] for c in cases] == ["Widget v Example", "Gizmo v Sprocket"]


def test_names_split_by_a_comma_or_a_semicolon():
    assert [c["shown"] for c in named_cases("Widget v Example, Gizmo v Sprocket")] == \
        ["Widget v Example", "Gizmo v Sprocket"]
    assert [c["shown"] for c in named_cases("Widget v Example; Gizmo v Sprocket")] == \
        ["Widget v Example", "Gizmo v Sprocket"]


def test_or_queries_name_each_case_once():
    cases = named_cases('"Widget v Example" OR "Gizmo v Sprocket" OR "Widget v Example"')
    assert [c["shown"] for c in cases] == ["Widget v Example", "Gizmo v Sprocket"]


def test_a_party_with_no_distinctive_word_is_not_required():
    c = _one("R (on the application of Widget) v SSHD")
    assert c["a"] == {"widget"} and c["b"] == set()
    c = _one("Rex v Sprocket (Gizmo)")
    assert c["a"] == set() and c["b"] == {"sprocket", "gizmo"}


def test_a_name_with_no_distinctive_word_is_kept_only_with_a_citation():
    assert named_cases("R v Secretary of State for the Home Department") == []
    c = _one("R (SC) v Secretary of State for Work and Pensions [1901] UKSC 26")
    assert c["ncn"] == "1901 UKSC 26"
    assert c["shown"] == "R (SC) v Secretary of State for Work and Pensions (1901) UKSC 26"
    # ... and with a law report it cannot be matched.
    assert _one("R (SC) v Secretary of State for Work and Pensions [1901] AC 9")["report"] is True


@pytest.mark.parametrize("query", [
    "duty of care negligence",
    "employment status worker v employee",       # lower case: not a case name
    "WIDGET V EXAMPLE",                          # capitals throughout
    "In re Widget",                              # no "v"
    "A v B",                                     # anonymised: no distinctive word
    "Widget v",                                  # no second party
    "v Example",                                 # no first party
    "",
])
def test_forms_that_name_no_case(query):
    assert named_cases(query) == []
    assert note(query, fcl([OTHER])) == ""


def test_a_clause_break_ends_the_first_party():
    c = _one("Liability: Widget v Example")
    assert c["shown"] == "Widget v Example"


def test_joiners_at_either_end_of_a_party_are_trimmed():
    assert _one("liability of Widget v Example")["shown"] == "Widget v Example"
    assert _one("Widget v Example and duty")["shown"] == "Widget v Example"
    assert _one("Widget v Example and duty")["b"] == {"example"}


def test_a_colon_ends_the_second_party_on_the_word_that_carries_it():
    c = _one("Widget v Example: Duty Of Care")
    assert c["shown"] == "Widget v Example" and c["b"] == {"example"}


def test_a_citation_is_a_names_only_when_nothing_but_a_space_or_comma_parts_them():
    c = _one("Widget v Example,  [1901] UKSC 9")
    assert c["ncn"] == "1901 UKSC 9"
    for q in ("Widget v Example and [1901] UKSC 9", "Widget v Example; [1901] UKSC 9",
              "Widget v Example duty [1901] UKSC 9"):
        cases = named_cases(q)
        assert [c["ncn"] for c in cases] == [None, "1901 UKSC 9"], q
    # A citation BEFORE a name is never that name's.
    cases = named_cases("[1901] UKSC 9 Widget v Example")
    assert [(c["shown"], c["ncn"]) for c in cases] == [
        ("the judgment cited as (1901) UKSC 9", "1901 UKSC 9"), ("Widget v Example", None)]


def test_acronyms_and_corporate_words_are_not_distinctive():
    c = _one("Widget HMRC Ltd v Example plc")
    assert c["a"] == {"widget"} and c["b"] == {"example"}


# --- whether the results return it ----------------------------------------------------

def test_returned_by_a_distinctive_word_of_each_party():
    c = _one("Widget Co v Example Ltd")
    assert case_returned(c, [OTHER, WIDGET]) is True
    assert case_returned(c, [OTHER]) is False
    assert case_returned(c, []) is False


def test_one_shared_party_word_is_not_the_case():
    """Batch 12's shape: other judgments sharing the first party's surname."""
    c = _one("Widget v Sprocket Gizmo")
    rows = [{"title": "Anna Widget v The Commissioners"}, {"title": "Kite v Widget"}]
    assert case_returned(c, rows) is False
    assert case_returned(c, [{"title": "Widget v Gizmo & Sprocket Holdings"}]) is True


def test_a_party_without_a_distinctive_word_is_satisfied_by_the_other():
    c = _one("R (Widget) v Secretary of State for the Home Department")
    assert case_returned(c, [{"title": "R (on the application of Widget) v SSHD"}]) is True


def test_returned_by_neutral_citation_in_its_field_title_or_url():
    c = _one("[1901] UKSC 4")
    assert case_returned(c, [{"title": "x", "ncn": "[1901] UKSC 4"}]) is True
    assert case_returned(c, [{"title": "Widget v Example [1901] UKSC 4"}]) is True
    assert case_returned(c, [{"title": "x", "url": U + "uksc/1901/4"}]) is True
    assert case_returned(c, [{"title": "x", "url": U + "id/uksc/1901/4"}]) is True
    assert case_returned(c, [{"title": "x", "url": U + "uksc/1901/40"}]) is False


def test_the_court_of_appeals_division_is_part_of_its_citation():
    civ = _one("[1901] EWCA Civ 7")
    assert case_returned(civ, [{"title": "x", "url": U + "ewca/civ/1901/7"}]) is True
    assert case_returned(civ, [{"title": "x", "url": U + "ewca/crim/1901/7"}]) is False
    assert case_returned(civ, [{"title": "x", "ncn": "[1901] EWCA Crim 7"}]) is False
    # The High Court's division is not: its numbers run across divisions.
    hc = _one("[1901] EWHC 12 (Admin)")
    assert case_returned(hc, [{"title": "x", "url": U + "ewhc/kb/1901/12"}]) is True


def test_a_name_with_a_citation_is_returned_by_either():
    c = _one("Widget Co v Example Ltd [1901] UKSC 4")
    assert case_returned(c, [{"title": "Unrelated", "ncn": "[1901] UKSC 4"}]) is True
    assert case_returned(c, [{"title": "Widget Co v Example Ltd"}]) is True


def test_a_law_report_alone_cannot_be_told():
    assert case_returned(_one("[1901] AC 9"), [WIDGET]) is None


def test_odd_rows_are_skipped():
    c = _one("Widget Co v Example Ltd")
    assert case_returned(c, [None, "x", 3, {}]) is False


# --- the note ------------------------------------------------------------------------

def _variants() -> dict:
    """Every wording `named_case_note` produces, on synthetic input."""
    return {
        "name, partial page": note("Widget Co v Example Ltd duty", fcl([OTHER] * 50, total=900, exact=False)),
        "name, whole set": note("Widget Co v Example Ltd", fcl([OTHER, OTHER])),
        "name, 1 result": note("Widget Co v Example Ltd", fcl([OTHER])),
        "name, 0 results": note('"Widget Co v Example Ltd"', fcl([])),
        "neutral citation alone": note("[1901] UKSC 9", fcl([OTHER])),
        "name with neutral citation": note("Widget Co v Example Ltd [1901] UKSC 9", fcl([OTHER])),
        "name with law report": note("Widget Co v Example Ltd [1901] AC 9", fcl([OTHER])),
        "law report alone": note("[1901] AC 9 control test", fcl([OTHER, OTHER])),
        "two names": note('"Widget Co v Example Ltd" OR "Gizmo v Sprocket"', fcl([OTHER, OTHER])),
        "two names, 0 results": note('"Widget v Example" OR "Gizmo v Sprocket"', fcl([])),
        "two names, 1 result": note("Widget v Example and Gizmo v Sprocket", fcl([OTHER])),
        "three names, 1 result": note("Widget v Example; Gizmo v Sprocket; Ratchet v Pawl", fcl([OTHER])),
        "one returned, one not": note("Widget Co v Example Ltd or Gizmo v Sprocket", fcl([WIDGET, OTHER])),
        "name and a law report": note("Gizmo v Sprocket [1901] AC 9 and [1902] QB 7", fcl([OTHER])),
        "two law reports": note("[1901] AC 9 [1902] 1 QB 7", fcl([OTHER])),
        "both lists, whole": note("Widget Co v Example Ltd", both([OTHER], [SCOT])),
        "both lists, Scottish partial": note("Widget Co v Example Ltd", both([OTHER], [SCOT], scot_total=40)),
        "Scottish only (FCL errored)": note("Widget Co v Example Ltd",
                                            dict(both([], [SCOT]), error="failed")),
        "both lists, law report": note("1901 SLT 7", both([OTHER], [SCOT])),
        "Scottish capped": note("Widget Co v Example Ltd", both([OTHER] * 3, [], status="capped")),
        "R (X) v Secretary of State": note(
            "R (Widget) v Secretary of State for the Home Department [1901] UKSC 9", fcl([OTHER])),
    }


def test_every_variant_renders_as_read():
    v = _variants()
    assert len(set(v.values())) == len(v) and all(v.values())
    assert v["name, partial page"] == (
        "\n\n[SEARCH SCOPE — a case this search names is not among its results: none of the 50 "
        "judgments it returned is Widget Co v Example Ltd. That is all it shows: the judgment may "
        "well exist, Find Case Law may hold it among the matching judgments not shown or under "
        "words this search did not use, and it is no sign that the name or citation is wrong. "
        "Unless another search returns it and you retrieve it, its text has not been read: do not "
        "state what it decided as though you had read it. Say instead that it was not among the "
        "judgments returned, or attribute what you say about it to a retrieved judgment that "
        "cites it, and name that judgment.]")
    assert "may hold it under words" in v["name, whole set"]
    assert "the 1 judgment it returned is not Widget Co v Example Ltd." in v["name, 1 result"]
    assert ("this search returned 0 judgments, so a case it names is not among them: "
            "Widget Co v Example Ltd.") in v["name, 0 results"]
    assert "is not the judgment cited as (1901) UKSC 9." in v["neutral citation alone"]
    assert "is not Widget Co v Example Ltd (1901) UKSC 9." in v["name with neutral citation"]
    assert "is not Widget Co v Example Ltd (1901) AC 9." in v["name with law report"]
    assert v["law report alone"] == (
        "\n\n[SEARCH SCOPE — this search names a law report, (1901) AC 9, which cannot be matched "
        "to its results: Find Case Law lists judgments by title and neutral citation, not by law "
        "report, so none of the judgments returned is shown to be the case reported there. Unless "
        "a judgment you retrieve proves to be that case, do not state what it decided as though "
        "you had read it. Say instead that it could not be matched to the judgments returned, or "
        "attribute what you say about it to a retrieved judgment that cites it, and name that "
        "judgment.]")
    assert ("cases this search names are not among its results: none of the 2 judgments it "
            "returned is Widget Co v Example Ltd or Gizmo v Sprocket.") in v["two names"]
    assert "names or citations are wrong" in v["two names"]
    assert "so the cases it names are not among them: Widget v Example and Gizmo v Sprocket." \
        in v["two names, 0 results"]
    assert "is neither Widget v Example nor Gizmo v Sprocket." in v["two names, 1 result"]
    assert "is none of Widget v Example, Gizmo v Sprocket or Ratchet v Pawl." \
        in v["three names, 1 result"]
    assert "is Gizmo v Sprocket." in v["one returned, one not"]
    assert "Widget" not in v["one returned, one not"]
    assert "This search also names a law report, (1902) QB 7," in v["name and a law report"]
    assert "they were not among, or could not be matched to, the judgments returned" \
        in v["name and a law report"]
    assert "law reports, (1901) AC 9 and (1902) 1 QB 7," in v["two law reports"]
    assert "they could not be matched to the judgments returned" in v["two law reports"]
    assert f"{NAMED_CASE_BOTH} may hold it under words" in v["both lists, whole"]
    assert f"{NAMED_CASE_BOTH} may hold it among the matching judgments not shown" \
        in v["both lists, Scottish partial"]
    assert f"the judgment may well exist, {NAMED_CASE_SCTS} may hold it" \
        in v["Scottish only (FCL errored)"]
    assert f"{NAMED_CASE_BOTH} list judgments by title" in v["both lists, law report"]
    assert f"{NAMED_CASE_FCL} may hold it under words" in v["Scottish capped"]
    assert "is not R (Widget) v Secretary of State for the Home Department (1901) UKSC 9." \
        in v["R (X) v Secretary of State"]


def test_no_note_when_every_named_case_is_returned():
    assert note("Widget Co v Example Ltd", fcl([OTHER, WIDGET])) == ""
    assert note("[1901] UKSC 4", fcl([WIDGET])) == ""
    assert note("Sprocket v Cog", both([OTHER], [SCOT])) == ""


def test_no_note_when_no_search_ran():
    assert note("Widget Co v Example Ltd", {"error": "Invalid court", "results": [], "total": 0}) == ""
    # Find Case Law errored and the Scottish search did not run either.
    assert note("Widget Co v Example Ltd",
                dict(both([], [], status="error"), error="failed")) == ""


def test_a_list_whose_search_did_not_run_counts_for_nothing():
    # The Scottish search capped: its (empty) list is not read, and the
    # database named is Find Case Law alone.
    n = note("Widget Co v Example Ltd", both([OTHER], [], status="capped"))
    assert NAMED_CASE_SCTS not in n and "the 1 judgment it returned" in n
    # Find Case Law errored: its rows (none) are not counted, the Scottish ones are.
    n = note("Widget Co v Example Ltd", dict(both([OTHER], [SCOT]), error="failed"))
    assert "the 1 judgment it returned" in n and NAMED_CASE_FCL not in n


def test_the_page_is_partial_only_when_more_matched_than_were_shown():
    assert "not shown" not in note("Widget v Example", fcl([OTHER] * 3))
    assert "not shown" in note("Widget v Example", fcl([OTHER] * 3, total=30, exact=False))
    # Exact, but more than shown (a figure the feed gave for a full page).
    assert "not shown" in note("Widget v Example", fcl([OTHER] * 3, total=30, exact=True))
    assert "not shown" not in note("Widget v Example", fcl([]))
    # An old stored result with no `total_exact`: a page with rows is partial.
    assert "not shown" in note("Widget v Example", {"results": [OTHER], "total": 1})
    assert "not shown" in note("Widget v Example", both([OTHER], [SCOT], scot_total=9))


def test_the_query_is_read_from_the_result_when_args_have_none():
    data = dict(fcl([OTHER]), query="Widget Co v Example Ltd")
    assert named_case_note({}, data) and named_case_note(None, json.dumps(data))


@pytest.mark.parametrize("bad", [None, "", "not json", "[]", 3, {"results": "x"}])
def test_never_raises(bad):
    assert isinstance(named_case_note({"query": "Widget v Example"}, bad), str)


def test_a_non_list_results_field_reads_as_empty():
    n = note("Widget v Example", {"results": "x", "total": 0, "total_exact": True})
    assert "returned 0 judgments" in n


def test_every_variant_is_one_bracket_free_block_the_strip_removes():
    for label, n in _variants().items():
        block = n.strip()
        assert n.startswith("\n\n[SEARCH SCOPE — "), label
        assert block.endswith("]"), label
        assert "[" not in block[1:-1] and "]" not in block[1:-1], label
        out, k = strip_scope_blocks("The answer." + n)
        assert k == 1 and out == "The answer.", label


def test_every_variant_trips_no_detector():
    """Screened like `test_caselaw_window.test_window_note_trips_no_detector`
    (batch 6's lesson: any text an answer can echo is read by every grader),
    plus `NEGATIVE_EXPLAINED` and `SCHED_LIMIT`, sentence by sentence where a
    detector is per sentence."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.replay_report import (
        HALT_AS_TIMEOUT, HALT_LITERAL, HALT_PARAPHRASE, IN_FORCE_CLAIM,
        NEG_ASSERTED, NEG_BLAMED_INDEX, NEG_BLAMED_USER, NEG_LIMITS, NEG_TERMS,
        NEGATIVE_EXPLAINED, NOT_FOUND, OPENER_VOCAB, SCHED_LIMIT, SCOTS_CASELAW_GAP,
        _CMC_CONTEXT, _CMC_DENIED, _CUR_DISCLOSED, _currency_asserted, _sentences,
        _without_footer, derivation_claims, negcurrency_claim, sched_clause_class,
        sched_unit_clauses,
    )
    unit_rx = re.compile(r"\b(?:schedules?|annex(?:es)?)\b", re.I)
    for label, n in _variants().items():
        for rx in (NEG_ASSERTED, NOT_FOUND, NEG_BLAMED_INDEX, NEG_BLAMED_USER,
                   NEG_LIMITS, NEG_TERMS, NEGATIVE_EXPLAINED, HALT_LITERAL,
                   HALT_PARAPHRASE, HALT_AS_TIMEOUT, IN_FORCE_CLAIM, OPENER_VOCAB,
                   SCOTS_CASELAW_GAP, _CUR_DISCLOSED, SCHED_LIMIT):
            assert not rx.search(n), (label, rx.pattern[:40])
        assert "ranked" not in n.lower(), label
        assert _without_footer(n) == n.strip(), label
        assert derivation_claims(n)[0] == [], label
        assert sched_unit_clauses(n, unit_rx) == [], label
        for s in _sentences(n):
            assert not (_CMC_CONTEXT.search(s) and _CMC_DENIED.search(s)), s
            assert not _currency_asserted(s), s
            assert negcurrency_claim(s)[0] is None, s
            assert sched_clause_class(s) == "", s


# --- wired into run_worker_tool ----------------------------------------------------

async def _run(raw: dict, query: str) -> str:
    from src.agent.agent_shared import run_worker_tool

    async def chunk(*a, **k):
        return None

    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=json.dumps(raw))):
        return await run_worker_tool("search_case_law", {"query": query},
                                     "brief", chunk, "test-model")


@pytest.mark.asyncio
async def test_the_note_comes_before_the_window_and_the_imperative_stays_last():
    out = await _run(dict(fcl([OTHER]), query="Widget Co v Example Ltd"), "Widget Co v Example Ltd")
    i_note = out.index("[SEARCH SCOPE — a case this search names")
    i_window = out.index("[SEARCH SCOPE — all 1 judgment(s)")
    i_next = out.index("MANDATORY NEXT STEP")
    assert i_note < i_window < i_next
    assert out.count("a case this search names") == 1


@pytest.mark.asyncio
async def test_the_note_comes_before_the_zero_note_and_its_stop_rule():
    out = await _run(dict(fcl([]), query='"Widget Co v Example Ltd"'), '"Widget Co v Example Ltd"')
    assert out.index("this search returned 0 judgments, so a case it names") \
        < out.index("This search returned 0 results")


@pytest.mark.asyncio
async def test_the_note_on_a_result_with_the_scottish_list():
    raw = dict(both([OTHER], [SCOT]), query="Widget Co v Example Ltd")
    raw["scottish"].update(total_exact=True, match="all", query_sent="Widget")
    out = await _run(raw, "Widget Co v Example Ltd")
    assert f"{NAMED_CASE_BOTH} may hold it" in out
    assert out.index("a case this search names") < out.index("MANDATORY NEXT STEP")


@pytest.mark.asyncio
async def test_no_note_when_the_query_names_no_case_or_the_case_was_returned():
    for query, rows in (("widget duty of care", [OTHER]), ("Widget Co v Example Ltd", [WIDGET])):
        out = await _run(dict(fcl(rows), query=query), query)
        assert "this search names" not in out and "MANDATORY NEXT STEP" in out


@pytest.mark.asyncio
async def test_another_tools_result_gets_no_note():
    from src.agent.agent_shared import run_worker_tool

    async def chunk(*a, **k):
        return None

    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=json.dumps({"results": []}))):
        out = await run_worker_tool("get_case_law_text", {"url": U + "uksc/1901/4",
                                                          "query": "Widget v Example"},
                                    "brief", chunk, "test-model")
    assert "this search names" not in out and "a case it names" not in out
    assert named_case_note({"query": "Widget v Example"}, {"results": []})   # it would fire
