"""P4.7's instruments: `replay_report drgaps` and `seam_sweep --synthesis`.

`drgaps` is the pre-flight read put behind a command: every answered Deep
Research turn by research type, and every sentence naming case law as a
source, classified as searched-and-absent, excluded, or a mention. The defect
is a case-law 'not found' in a report whose research type has no case-law
tool. The classifier was corrected once before first use (a sentence saying
case law was "not searched or retrieved" read as a negative); that sentence is
pinned below.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402
import tools.seam_sweep as ss  # noqa: E402


def _kinds(text):
    return [k for k, _ in rr.dr_classify(text)]


# --- the classifier ---------------------------------------------------------


def test_d17s_own_example_is_the_defect_even_with_its_parenthesis():
    s = ("No reported case law was found on the duty (case law was excluded from "
         "the research scope by the approved plan).")
    assert _kinds(s) == ["absent_excluded"]


@pytest.mark.parametrize("s", [
    "No reported case law was found on the duty.",
    "No relevant judgments were identified.",
    "The search did not find any case law on the point.",
    "No case law addresses this question.",
])
def test_a_case_law_negative_reads_as_absent(s):
    assert _kinds(s) == ["absent"]


@pytest.mark.parametrize("s", [
    "Case law was excluded from this research.",
    "Case law was not searched in this research.",
    "The research type is 'Legislation only', which does not search case law.",
    # The correction made before first use (wave2_p28_smoke/6341 t7's form):
    "Under the Legislation Only filter, no reported case law was searched or retrieved.",
])
def test_an_exclusion_reads_as_excluded(s):
    assert _kinds(s) == ["excluded"]


@pytest.mark.parametrize("s", [
    "The final judgment of the tribunal is appealable.",
    "The judicial machinery of the Act is set out in Part 2.",
])
def test_a_case_law_word_that_is_not_a_source_is_not_classified(s):
    assert rr.dr_classify(s) == []
    assert rr.DR_CASE_WORD.search(s)


def test_the_footer_is_not_graded():
    text = "Body.\n\n*Search scope: no reported case law was found in this index.*"
    assert rr.dr_classify(text) == []


# --- rows, defects and the command ------------------------------------------


def _doc(research_mode="legislation_only", answer="", plan=True, step=True):
    turn = {"turn": 1, "chat_mode": "deep_research", "answer": answer,
            "research_mode": research_mode,
            "plan": {"steps": [{"title": "S"}]} if plan else None,
            "audit": {"research_mode": research_mode,
                      "delegations": [{"step": 1 if step else None, "report": "r"}]}}
    return {"session_id": "9999", "rep": 1, "filters": {}, "turns": [turn]}


@pytest.mark.parametrize("rm,defect", [
    ("legislation_only", True), ("parliamentary_records", True),
    ("westminster_records", True), ("legislation_and_case_law", False),
    ("case_law_only", False),
])
def test_a_negative_is_a_defect_only_where_case_law_was_never_searched(rm, defect):
    (row,) = rr.dr_rows(_doc(rm, "No reported case law was found on X."))
    assert rr.dr_defect(row) is defect


def test_turn_kinds():
    assert rr.dr_turn_kind(_doc()["turns"][0]) == "synthesis"
    t = _doc(plan=False)["turns"][0]
    assert rr.dr_turn_kind(t) == "planner"


def test_an_unanswered_or_non_deep_research_turn_is_not_a_row():
    d = _doc(answer="  ")
    assert rr.dr_rows(d) == []
    d = _doc(answer="Report.")
    d["turns"][0]["chat_mode"] = "research"
    assert rr.dr_rows(d) == []


def _write(tmp_path, name, doc):
    d = tmp_path / name
    d.mkdir()
    (d / "9999_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    return d


def test_the_command_exits_1_on_a_defect_and_0_on_an_exclusion(tmp_path, capsys):
    bad = _write(tmp_path, "bad", _doc(answer="No reported case law was found on X."))
    ok = _write(tmp_path, "ok", _doc(answer="Case law was excluded from this research."))
    assert rr.main(["--dir", str(bad), "drgaps"]) == 1
    assert rr.main(["--dir", str(ok), "drgaps"]) == 0
    # --all-dirs pools every directory beside --dir, so the defect is found.
    assert rr.main(["--dir", str(ok), "drgaps", "--all-dirs"]) == 1
    out = capsys.readouterr().out
    assert "No reported case law" not in out     # sentences only with --sentences


# --- the synthesis sweep ----------------------------------------------------


def test_the_payload_sets_are_distinct_and_the_union_is_both():
    leg, hyb = ss.P47_SETS["p47_legislation"], ss.P47_SETS["p47_hybrid"]
    assert len(set(leg)) == len(leg) == 20
    assert len(set(hyb)) == len(hyb) == 8
    assert ss.P47_SETS["p47"] == leg + hyb


def test_pinned_pairs_read_the_label_pinpoint_against_the_provision_url():
    url = "http://www.legislation.gov.uk/asp/2002/3/section/57"
    pairs = ss.pinned_pairs(f"See [Act - s.57(3)(a)]({url}) and [Act]({url}).")
    assert len(pairs) == 1
    ((u, pin),) = pairs
    assert u.endswith("asp/2002/3/section/57") and "57(3)(a)" in pin


@pytest.mark.parametrize("a,b", [
    ("Section 126(7)(a)", "s. 126(7)(a)"), ("s.126(6)", "section 126(6)"),
    ("Sch 5 para 1(1)", "schedule 5, paragraph 1(1)"), ("Article 3(5)", "art. 3(5)"),
    ("regulation 2(1)", "reg 2(1)"),
])
def test_pinpoints_are_compared_in_one_spelling(a, b):
    """Corrected at first use: 'Section 126(7)(a)' in the findings and
    's. 126(7)(a)' in the report are one pinpoint kept, not one lost."""
    assert ss.pin_key(a) == ss.pin_key(b)
    assert ss.pin_key("s.126(6)") != ss.pin_key("s.126(7)")


def test_a_gap_by_what_happened_counts_as_a_case_law_gap():
    """Corrected at first use: 'step 1 did not return findings, so the common
    law cases were not established' states the gap by what happened."""
    assert ss.case_law_gap_sentences(
        "Step 1 did not return findings; so the leading common law cases are not set out.") == 1
    assert ss.case_law_gap_sentences("No reported case law was found on X.") == 1
    # A legislation title is not case law.
    assert ss.case_law_gap_sentences(
        "For the Specified Authority Order, no repeal record was retrieved.") == 0


def test_a_judgment_label_with_a_bracketed_year_is_still_a_link():
    """Corrected at first use: `replay_report.MD_LINK` misses this link, so a
    hybrid draw that linked six judgments this way graded as dropping them."""
    t = "[*Berezovsky v Hine & Ors* [2011] EWCA Civ 1089](https://caselaw.nationalarchives.gov.uk/ewca/civ/2011/1089)"
    assert rr.MD_LINK.findall(t) == []
    assert ss.link_targets(t) == {"https://caselaw.nationalarchives.gov.uk/ewca/civ/2011/1089"}


def test_link_targets_fold_scheme_and_id_and_ignore_repeats():
    t = ("[a](http://www.legislation.gov.uk/id/asp/2016/10/section/3) "
         "[b](https://www.legislation.gov.uk/asp/2016/10/section/3/) "
         "[c](https://caselaw.nationalarchives.gov.uk/ewca/civ/2011/1089)")
    assert len(ss.link_targets(t)) == 2


def test_the_synthesis_sweep_needs_an_explicit_rev_on_the_without_side(tmp_path):
    with pytest.raises(SystemExit):
        ss.main(["--synthesis", "p47", "--out", str(tmp_path), "--without-fix"])
    with pytest.raises(SystemExit):
        ss.main(["--synthesis", "p47"])                    # no --out
