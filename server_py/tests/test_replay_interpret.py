"""P3.3: the `interpret` and `hedges` graders — retrieval versus interpretation.

`interpret` fails a rep that asserts a claim the text contradicts, omits a
statement a turn must make, states an interpretive claim with no hedge, or
applies a doctrine without the statement its rubric requires. `hedges` is
the decisiveness guard: a hedge on what a provision SAYS counts against, a
hedge on an interpretation does not. The real rubric names lawyers' matters
and is gitignored; every rubric and sentence here is synthetic.
"""

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402

RUBRIC = {
    "turns": [1, 2, 3],
    "topic": [r"\bwidget"],
    "wrong": [{"id": "old_code", "pattern": r"Widget Code 1950[^.]{0,80}\bgoverns",
               "unless": [r"does not govern", r"\bonly\b"]}],
    "must": {"1": [r"Widget Order 1901"]},
    "interpretive": [{"id": "scope", "pattern": r"widgets\s+(?:only\s+)?include\s+gadgets"}],
    "requires": [{"id": "status", "if": r"gadget doctrine",
                  "then": [r"not\s+(?:been\s+)?verified"]}],
}


def _turn(answer, n):
    return {"turn": n, "answer": answer, "audit": {"delegations": [{}]}}


def _doc(*answers, script=None):
    d = {"session_id": "9999", "rep": 1,
         "turns": [_turn(a, i) for i, a in enumerate(answers, 1)]}
    if script:
        d["script"] = script
    return d


def test_a_correct_hedged_answer_passes():
    g = rr.interpret_grade(_doc(
        "The Widget Order 1901 governs this Act.",
        "On one reading, widgets include gadgets.",
        "The gadget doctrine applies; whether it is part of this law has not been verified.",
    ), RUBRIC)
    assert g["pass"], g["findings"]
    assert g["rows"][1]["hedged"] and not g["rows"][1]["asserted"]


def test_a_contradicted_claim_fails_and_its_negation_does_not():
    bad = rr.interpret_grade(_doc("The Widget Order 1901 exists, but the Widget Code 1950 governs it."),
                             RUBRIC)
    assert not bad["pass"]
    assert any("old_code" in f for f in bad["findings"])
    ok = rr.interpret_grade(_doc("The Widget Order 1901 applies; the Widget Code 1950 does not govern it."),
                            RUBRIC)
    assert ok["pass"], ok["findings"]


def test_a_missing_required_statement_fails():
    g = rr.interpret_grade(_doc("Widgets are defined elsewhere."), RUBRIC)
    assert not g["pass"]
    assert g["findings"] == ["t1 required statement missing"]


def test_an_unhedged_interpretation_fails():
    g = rr.interpret_grade(_doc("The Widget Order 1901 applies.", "Widgets include gadgets."), RUBRIC)
    assert not g["pass"]
    assert any("'scope' as settled" in f for f in g["findings"])


def test_a_hedge_does_not_carry_across_an_ordinary_sentence():
    # "The text is silent. However, X." states X as settled.
    g = rr.interpret_grade(_doc("The Widget Order 1901 applies.",
                                "The Order does not expressly say. However, widgets include gadgets."),
                           RUBRIC)
    assert g["rows"][1]["asserted"], g["rows"][1]


def test_a_hedge_on_a_list_lead_in_covers_its_items():
    g = rr.interpret_grade(_doc("The Widget Order 1901 applies.",
                                "There is a plausible reading on which:\n* widgets include gadgets"),
                           RUBRIC)
    assert g["rows"][1]["hedged"] and not g["rows"][1]["asserted"], g["rows"][1]


def test_an_item_opening_in_bold_inherits_its_lead_in_hedge():
    # The sentence splitter leaves "2." apart from "**Scope:** ...", so the
    # walk is by the answer's lines (Session 32).
    g = rr.interpret_grade(_doc("The Widget Order 1901 applies.",
                                "On one reading of the two schemes:\n\n"
                                "1.  **Scope:** Widgets include gadgets.\n"
                                "2.  **More:** Nothing else."),
                           RUBRIC)
    assert g["rows"][1]["hedged"] and not g["rows"][1]["asserted"], g["rows"][1]


def test_an_item_under_an_unhedged_lead_in_is_asserted():
    g = rr.interpret_grade(_doc("The Widget Order 1901 applies.",
                                "The position is as follows:\n\n1.  **Scope:** Widgets include gadgets."),
                           RUBRIC)
    assert g["rows"][1]["asserted"], g["rows"][1]


def test_a_conditional_and_a_retraction_assert_nothing():
    g = rr.interpret_grade(_doc("The Widget Order 1901 applies.",
                                "If widgets include gadgets, more follows. "
                                "My view that widgets include gadgets was too rigid."),
                           RUBRIC)
    assert not g["rows"][1]["asserted"] and not g["rows"][1]["hedged"]


def test_a_required_condition_fires_only_when_its_trigger_does():
    fired = rr.interpret_grade(_doc("The Widget Order 1901 applies.", "Nothing here.",
                                    "The gadget doctrine applies here."), RUBRIC)
    assert "t3 'status' fired with no required statement" in fired["findings"]
    quiet = rr.interpret_grade(_doc("The Widget Order 1901 applies.", "Nothing here.",
                                    "No doctrine is relevant."), RUBRIC)
    assert quiet["pass"], quiet["findings"]


def test_a_required_statement_may_come_from_the_code_footer():
    footer = "\n\n*Search scope: the gadget doctrine's status here has not been verified.*"
    g = rr.interpret_grade(_doc("The Widget Order 1901 applies.", "Nothing here.",
                                "The gadget doctrine applies here." + footer), RUBRIC)
    assert g["pass"], g["findings"]


def test_a_link_is_read_as_its_label():
    g = rr.interpret_grade(_doc("The [Widget Order 1901](http://example/1901/1) applies."), RUBRIC)
    assert g["pass"], g["findings"]


def test_a_scripted_run_maps_back_to_export_turns():
    rub = dict(RUBRIC, must={"3": [r"Widget Order 1901"]})
    g = rr.interpret_grade(_doc("Widget Order 1901.",
                                script={"turns": [{"from_turn": 3}]}), rub)
    assert g["rows"][0]["base"] == 3 and g["pass"]


def test_turns_outside_the_rubric_are_not_graded():
    rub = dict(RUBRIC, turns=[2])
    g = rr.interpret_grade(_doc("Widgets include gadgets.", "On one reading, widgets include gadgets."),
                           rub)
    assert [r["base"] for r in g["rows"]] == [2] and g["pass"]


def test_on_topic_sentences_no_pattern_graded_are_drops():
    # `must` is read over the whole answer, not per sentence, so both are drops.
    g = rr.interpret_grade(_doc("The Widget Order 1901 applies. Widgets are blue. Cats purr."), RUBRIC)
    assert g["rows"][0]["drops"] == ["The Widget Order 1901 applies.", "Widgets are blue."]


def test_hedge_counts_separate_retrieval_hedges_from_interpretive_ones():
    c = rr.hedge_counts(
        "Section 4 appears to provide that widgets are exempt. "
        "Section 5 provides that gadgets are taxed. "
        "On one reading, section 6 covers both. "
        "Ministers may require a report under section 7. "
        "This is not legal advice.")
    assert c["retrieval"] == 4
    assert [s.split()[0:2] for s in c["hedged_retrieval"]] == [["Section", "4"]]
    assert len(c["caveats"]) == 1
    assert c["interp_hedges"] >= 2


def test_the_text_as_subject_of_a_modal_is_a_retrieval_hedge():
    c = rr.hedge_counts("The section may provide for an exemption (s.9).")
    assert len(c["hedged_retrieval"]) == 1


def test_interpret_command_exits_2_without_a_rubric_and_1_on_a_failure(tmp_path, capsys):
    run = tmp_path / "runs"
    run.mkdir()
    (run / "9999_rep1.json").write_text(json.dumps(_doc("Widgets include gadgets.")), encoding="utf-8")
    assert rr.main(["--dir", str(run), "interpret", "--rubric", str(tmp_path / "none.json")]) == 2
    rub = tmp_path / "r.json"
    rub.write_text(json.dumps({"9999": RUBRIC}), encoding="utf-8")
    assert rr.main(["--dir", str(run), "interpret", "--rubric", str(rub)]) == 1
    assert "graded reps: 1, failing: 1" in capsys.readouterr().out


def test_hedges_command_always_exits_0(tmp_path, capsys):
    run = tmp_path / "runs"
    run.mkdir()
    doc = _doc("Section 4 appears to provide X.")
    doc["turns"][0]["chat_mode"] = "conversational"
    (run / "9999_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    assert rr.main(["--dir", str(run), "hedges", "--chat-mode", "conversational", "--list"]) == 0
    out = capsys.readouterr().out
    assert "hedged" in out and "Section 4 appears" in out
