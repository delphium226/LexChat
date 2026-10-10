"""Batch 13 E: `replay_report authorities` (P3.46's grader) taught the
first-statement rule and the back-reference, validated against batch 12 E's
hand-read (25 answer-turns: the grader agreed on 22 before, 25 after).

* **First statement.** An answer passes item 3 only where the FIRST sentence
  that says something of an out-of-corpus authority ties it to the judgment it
  came through, or where any sentence says the judgment is not held. A tie
  written after the holding was stated on its own terms does not pass it.
* **A bare listing** (a reference-list entry: the name and citation, no
  statement) is not a statement, and is skipped when finding the first one.
* **The back-reference.** "Gadget Ltd applied this principle", the sentence
  after one that names the authority, is read as a mention of it.

Every authority, judgment and answer here is synthetic.
"""
import json

import tools.replay_report as rr

_OOC = {"label": "Widget v E Gadget Sprocket & Co [1899] AC 52", "in_corpus": False,
        "mention": r"\bWidget\b|Gadget\s+Sprocket"}
_CARRIER = {"label": "Cog Ltd v Example plc [1901] EAT 27", "ncn": "[1901] EAT 27",
            "url": "eat/1901/27", "carrier": True, "need_turns": [1], "mention": "Cog Ltd"}
_RUBRIC = {"authorities": [_OOC, _CARRIER]}
_CARRIER_URL = "https://caselaw.nationalarchives.gov.uk/eat/1901/27"
_CARRIER_ROW = {"title": "Cog Ltd v Example plc", "ncn": "[1901] EAT 27", "url": _CARRIER_URL}
_LINK = f"[*Cog Ltd v Example plc* [1901] EAT 27]({_CARRIER_URL})"

HOLDING = "Widget v Gadget Sprocket [1899] AC 52 held that control decides."
TIED = f"In {_LINK}, the tribunal applied Widget v Gadget Sprocket [1899] AC 52 to hold that control decides."
BACKREF = f"In {_LINK}, the tribunal applied this principle to a group arrangement."
LISTED = "*   *Widget v E Gadget Sprocket & Co* [1899] AC 52 (HL)"


def _search(*rows):
    raw = json.dumps({"query": "widgets", "results": list(rows), "total": len(rows)})
    return {"name": "search_case_law", "args": {"query": "widgets"}, "raw_result": raw,
            "final_result": raw, "summarised": False, "api_calls": []}


def _turn(n, answer, tools=()):
    return {"turn": n, "question": "q", "chat_mode": "conversational", "answer": answer,
            "audit": {"delegations": [{"tools": list(tools)}]}}


def _mentions(*answers):
    doc = {"session_id": "9001", "rep": 1,
           "turns": [_turn(i + 1, a, [_search(_CARRIER_ROW)]) for i, a in enumerate(answers)]}
    run = rr.p322_run(doc, _RUBRIC)
    return next(a for a in run["auths"] if not a["in_corpus"])["mentions"]


def _verdicts(*answers):
    return [(e, v) for e, v, _ in _mentions(*answers)]


def _auth():
    return rr._p322_auths({"authorities": [_OOC]})[0]


# --- the verdict --------------------------------------------------------------------

def test_the_first_statement_decides():
    assert rr.p322_answer_verdict(["SECOND_HAND", "UNQUALIFIED"], False) == "PASS"
    assert rr.p322_answer_verdict(["UNQUALIFIED", "SECOND_HAND"], False) == "FAIL"
    assert rr.p322_answer_verdict(["UNQUALIFIED", "SECOND_HAND"], True) == "EARLIER"


def test_not_held_and_linked_are_read_in_every_sentence():
    assert rr.p322_answer_verdict(["UNQUALIFIED", "NOT_HELD"], False) == "PASS"
    assert rr.p322_answer_verdict(["SECOND_HAND", "LINKED"], False) == "FAIL"
    # LINKED wins over NOT_HELD: a link to another judgment is still a link.
    assert rr.p322_answer_verdict(["NOT_HELD", "LINKED"], False) == "FAIL"


def test_a_bare_listing_is_skipped_unless_it_is_all_there_is():
    assert rr.p322_answer_verdict(["UNQUALIFIED", "SECOND_HAND"], False, [True, False]) == "PASS"
    assert rr.p322_answer_verdict(["UNQUALIFIED", "SECOND_HAND"], False, [False, False]) == "FAIL"
    assert rr.p322_answer_verdict(["UNQUALIFIED"], False, [True]) == "FAIL"
    assert rr.p322_answer_verdict(["SECOND_HAND"], False, [True]) == "PASS"
    assert rr.p322_answer_verdict(["UNQUALIFIED", "SECOND_HAND"], False, None) == "FAIL"


# --- in a run -----------------------------------------------------------------------

def test_the_holding_stated_first_and_tied_later_fails():
    """Batch 12 E's three disagreements had this shape."""
    assert _verdicts(f"{HOLDING} {TIED}") == [(1, "FAIL")]


def test_the_tie_first_passes_and_a_later_holding_does_not_undo_it():
    assert _verdicts(f"{TIED} {HOLDING}") == [(1, "PASS")]


def test_a_reference_list_entry_before_the_tie_is_not_the_first_statement():
    assert _verdicts(f"{LISTED}\n{TIED}") == [(1, "PASS")]
    (_, _, sents), = _mentions(f"{LISTED}\n{TIED}")
    assert "a bare listing" in sents[0][1]


def test_an_answer_that_only_lists_it_fails_as_before():
    assert _verdicts(LISTED) == [(1, "FAIL")]


def test_an_earlier_pass_makes_a_later_unqualified_answer_earlier():
    assert _verdicts(TIED, HOLDING) == [(1, "PASS"), (2, "EARLIER")]


def test_saying_it_is_not_held_passes_wherever_it_is_said():
    no = "The judgment in Widget v Gadget Sprocket is not held in the database."
    assert _verdicts(f"{HOLDING} {no}") == [(1, "PASS")]


# --- the back-reference --------------------------------------------------------------

def test_a_back_reference_after_a_naming_sentence_is_a_mention():
    (_, verdict, sents), = _mentions(f"{HOLDING} {BACKREF}")
    assert [c for c, _, _ in sents] == ["UNQUALIFIED", "SECOND_HAND"]
    assert "a back-reference to the sentence before" in sents[1][1]
    # It records the tie, but the holding came first.
    assert verdict == "FAIL"


def test_a_back_reference_after_a_listing_is_the_first_statement():
    """A listing names it but states nothing; the back-reference after it is
    the first sentence to say something, and it carries the tie."""
    (_, verdict, sents), = _mentions(f"{LISTED}\n{BACKREF}")
    assert [c for c, _, _ in sents] == ["UNQUALIFIED", "SECOND_HAND"]
    assert verdict == "PASS"


def test_a_back_reference_needs_the_sentence_before_to_name_it():
    two_back = f"{HOLDING} The facts were unusual. {BACKREF}"
    (_, _, sents), = _mentions(two_back)
    assert len(sents) == 1
    assert _mentions(BACKREF) == []


def test_a_back_reference_needs_a_citing_word():
    (_, _, sents), = _mentions(f"{HOLDING} This principle is settled in {_LINK}.")
    assert len(sents) == 1


def test_a_back_reference_needs_a_rule_word_after_the_demonstrative():
    (_, _, sents), = _mentions(f"{HOLDING} In {_LINK}, the tribunal applied this to the facts.")
    assert len(sents) == 1


def test_the_back_reference_words():
    for s in ("applied this principle", "followed that test", "adopted these principles",
              "applied the same approach", "endorsed this well-known test",
              "applied that line of authority"):
        assert rr._P322_BACKREF.search(s), s
    for s in ("applied this case", "followed its test", "applied this to the facts"):
        assert not rr._P322_BACKREF.search(s), s


# --- the bare listing -------------------------------------------------------------

def test_is_bare():
    a = _auth()
    assert rr.p322_is_bare(LISTED, a) is True
    assert rr.p322_is_bare("*   Widget v E Gadget Sprocket & Co Ltd [1899] AC 52", a) is True
    assert rr.p322_is_bare("- [Widget v Gadget Sprocket](https://example.org/x) (HL)", a) is True
    assert rr.p322_is_bare("*   Widget v Gadget Sprocket https://example.org/widget", a) is True
    # A lower-case word of four or more letters is a statement.
    assert rr.p322_is_bare("Widget v Gadget Sprocket applies.", a) is False
    assert rr.p322_is_bare(HOLDING, a) is False
    # So is a first word outside the name, capitalised or not.
    assert rr.p322_is_bare("Following Widget v Gadget Sprocket [1899] AC 52", a) is False
    # Short words and capitalised words outside the name do not make a statement.
    assert rr.p322_is_bare("Widget v Gadget Sprocket [1899] AC 52 (see Cog)", a) is True
    # A sentence that does not name it is never a listing of it.
    assert rr.p322_is_bare("*   Cog Ltd v Example plc [1901] EAT 27", a) is False
