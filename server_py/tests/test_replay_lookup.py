"""P3.7: the harness half — the `lookup` grader and the p37 scripts.

The row's acceptance is about DEFINITENESS. An instrument the index does not
hold must be reported as not held, because a lookup by number said so, not
because a ranked search failed to return it. A held-but-stub instrument must be
reported as held without its text, and a held one must never be reported
absent. The grader reads the model's prose with the code-written footer
removed, one sentence at a time, and only sentences that name the instrument by
number.
"""

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402
import replay_set as rs  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[2] / "docs" / "prepilot-fixes" / "evidence" / "scripts"


def _lookup_tool(lid, status, by_code=False):
    return {"name": "lookup_legislation", "args": {},
            "raw_result": json.dumps({"legislation_id": lid, "status": status,
                                      "routed_by_code": by_code})}


def _text_404(lid):
    return {"name": "get_legislation_text", "args": {"legislation_id": lid},
            "raw_result": 'Error executing tool: {"detail":"Legislation not found: %s"}' % lid}


def _t(n, answer, tools=(), delegations=1):
    dgs = [{"report": "r", "tools": list(tools)}] if delegations else []
    return {"turn": n, "answer": answer, "chat_mode": "conversational",
            "timing": {"sources_kept": 0}, "audit": {"delegations": dgs}}


def _doc(*turns, base="6409", from_turns=None):
    doc = {"session_id": f"p37_{base}", "rep": 1, "turns": list(turns)}
    if from_turns:
        doc["script"] = {"base": base, "turns": [{"from_turn": f} for f in from_turns]}
    else:
        doc["session_id"] = base
    return doc


FOOTER = ("\n\n*Search scope: the legislation index was searched for \"x\"; no filter. "
          "SSI 2025/377 was looked up by its number and is not held in this index.*")


def _verdicts(doc):
    return {r["src_turn"]: rr.lookup_verdict(r) for r in rr.lookup_rows(doc)}


def test_the_sentence_shapes():
    c = rr._lk_classify
    assert c("SSI 2025/377 is not held in the legislation index.") == "record_absent"
    assert c("The index does not hold Scottish Statutory Instrument 2026/170.") == "record_absent"
    assert c("The full text of SSI 2025/377 is not currently held in the database.") == "text_only"
    # The negation governs the text when the text word follows it.
    assert c("The legislation index does not hold the text or full title for SSI 2025/377.") \
        == "text_only"
    assert c("SSI 2025/377 could not be found in the legislation database.") == "hedged"
    assert c("Could you confirm the SSI number for 2025/377?") == "blame"
    assert c("The citation 2025/377 may contain an error.") == "blame"
    # A positive statement about the instrument is not a claim of absence.
    assert c("SSI 2025/377 brings section 18 into force.") == ""
    # "confirm" in a sentence about the records is not a request to the lawyer.
    assert c("The change records confirm that SSI 2025/377 brings section 18 "
             "into force.") == ""


def test_a_not_held_answer_passes_only_on_a_lookup_and_the_footer():
    said = "SSI 2025/377 is not held in the legislation index."
    doc = _doc(_t(1, said + FOOTER, [_lookup_tool("ssi/2025/377", "not_held", True)]),
               from_turns=[9])
    assert _verdicts(doc)[9] == ("PASS", "")
    # The de facto probe that predates P3.7 does not earn the claim...
    doc = _doc(_t(1, said, [_text_404("ssi/2025/377")]), from_turns=[11])
    v = _verdicts(doc)[11]
    assert v[0] == "FAIL" and "without a lookup" in v[1]
    # ...and a lookup the footer does not state is not definite to the lawyer.
    doc = _doc(_t(1, said, [_lookup_tool("ssi/2025/377", "not_held")]), from_turns=[10])
    v = _verdicts(doc)[10]
    assert v[0] == "FAIL" and "footer" in v[1]


def test_a_follow_up_is_earned_by_an_earlier_lookup_in_the_same_run():
    said = "As noted, SSI 2025/377 is not held in the index."
    doc = _doc(_t(1, said + FOOTER, [_lookup_tool("ssi/2025/377", "not_held", True)]),
               _t(2, said, delegations=0), from_turns=[9, 11])
    assert _verdicts(doc)[11] == ("PASS", "")


def test_text_only_hedged_and_blame_fail_an_absent_slot():
    for answer in ("The full text of SSI 2025/377 is not currently available in the database.",
                   "SSI 2025/377 could not be found in the database.",
                   "SSI 2025/377 is not held. Could you check the number for 2025/377?"):
        doc = _doc(_t(1, answer + FOOTER, [_lookup_tool("ssi/2025/377", "not_held", True)]),
                   from_turns=[9])
        assert _verdicts(doc)[9][0] == "FAIL", answer


def test_a_clarifying_question_is_no_claim_except_where_the_row_needs_an_answer():
    ask = "What would you like to know about these regulations?"
    doc = _doc(_t(1, ask, delegations=0), _t(2, ask, delegations=0), from_turns=[10, 9])
    v = _verdicts(doc)
    assert v[10][0] == "NO CLAIM"
    assert v[9][0] == "FAIL"


def test_a_stub_or_held_instrument_reported_missing_fails():
    doc = _doc(_t(1, "I could not find SSI 2025/119 in the database."),
               _t(2, "The full text of SSI 2025/119 is not currently held."),
               _t(3, "The 2025 asp 2 could not be found in the index."),
               _t(4, "The Act (2025 asp 2) is held; section 18 reads as follows."),
               from_turns=[8, 7, 2, 1])
    v = _verdicts(doc)
    assert v[8][0] == "FAIL"
    assert v[7] == ("PASS", "")      # held without text is the right report
    assert v[2][0] == "FAIL"
    assert 1 not in v                # not a graded slot


def test_an_unscripted_run_is_graded_on_its_own_turn_numbers():
    doc = _doc(_t(1, "q"), _t(2, "SSI 2026/170 could not be found."), base="6373")
    rows = {r["src_turn"]: r for r in rr.lookup_rows(doc)}
    assert set(rows) == {2}
    assert rr.lookup_verdict(rows[2])[0] == "FAIL"


def test_the_p37_scripts_hold_no_question_text_and_name_the_graded_turns():
    for name, base, turns in (("p37_6409", "6409", [1, 2, 7, 8, 9, 10, 11]),
                              ("p37_6373", "6373", [1, 2, 3])):
        script = rs.load_script(SCRIPTS / f"{name}.json")
        assert script["base"] == base
        assert [t["from_turn"] for t in script["turns"]] == turns
        assert all("question" not in t for t in script["turns"]), name
        assert all(t["research_mode"] == "legislation_only" for t in script["turns"])
        assert all(t["chat_mode"] == "conversational" for t in script["turns"])
        graded = {k for k, v in rr.LOOKUP_TARGETS[base].items() if v[3]}
        assert graded <= set(turns)
    # The reach-check scripts carry no question text either.
    for name in ("p37r_6374", "p37r_6383"):
        script = rs.load_script(SCRIPTS / f"{name}.json")
        assert all("question" not in t for t in script["turns"]), name
        assert all(t["chat_mode"] == "conversational" for t in script["turns"])
