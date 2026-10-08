"""Batch 10 E: three grader fixes and a scripted-run gap closed.

* `authorities` (P3.22 item 3): an out-of-corpus authority is named by its full
  party names or its citation, never by one surname; a one-word short form
  counts only once the run has named it in full, and a judgment the run's
  `search_case_law` returned and the sentence cites is never the out-of-corpus
  authority (Session 41: three false FAILs from a different, retrieved judgment
  sharing a surname).
* `negcurrency` reads a section search in the `{"results": [...]}` shape as
  well as the bare list (4,748 of 5,314 stored section searches).
* `corpus`'s `description` label is true before P3.6 and after it.
* `commencements` grades a scripted run against its base session's truth,
  reporting each turn with the export turn it came from.

Every authority, instrument, session and answer here is synthetic.
"""

import argparse
import json
import re

import pytest

import tools.replay_report as rr

# --- authorities: synthetic rubric and search rows ----------------------------------

_OOC = {"label": "Widget v E Gadget Sprocket & Co [1899] AC 52", "in_corpus": False,
        "mention": r"\bWidget\b|Gadget\s+Sprocket"}
_CARRIER = {"label": "Cog Ltd v Example plc [1901] EAT 27", "ncn": "[1901] EAT 27",
            "url": "eat/1901/27", "carrier": True, "need_turns": [3], "mention": "Cog Ltd"}
_RUBRIC = {"authorities": [_OOC, _CARRIER]}

_SHARED_URL = "https://caselaw.nationalarchives.gov.uk/eat/1901/31"
_SHARED = {"title": "A Widget v Sample Ltd", "ncn": "[1901] EAT 31", "url": _SHARED_URL}
_CARRIER_URL = "https://caselaw.nationalarchives.gov.uk/eat/1901/27"
_CARRIER_ROW = {"title": "Cog Ltd v Example plc", "ncn": "[1901] EAT 27", "url": _CARRIER_URL}


def _tool(name, args=None, raw=None):
    raw_s = raw if isinstance(raw, str) or raw is None else json.dumps(raw)
    return {"name": name, "args": args or {}, "raw_result": raw_s,
            "final_result": raw_s or "", "summarised": False, "api_calls": []}


def _search(*rows):
    return _tool("search_case_law", {"query": "widgets"},
                 {"query": "widgets", "results": list(rows), "total": len(rows)})


def _turn(n, answer, tools=(), question="q"):
    return {"turn": n, "question": question, "chat_mode": "conversational", "answer": answer,
            "audit": {"delegations": [{"tools": list(tools)}]}}


def _run(turns, session_id="9001", rep=1, script=None):
    doc = {"session_id": session_id, "rep": rep, "turns": turns}
    if script:
        doc["script"] = script
    return doc


def _ooc(doc, rubric=None):
    run = rr.p322_run(doc, rubric or _RUBRIC)
    return next(a for a in run["auths"] if not a["in_corpus"])


def _verdicts(doc, rubric=None):
    return [(e, v) for e, v, _ in _ooc(doc, rubric)["mentions"]]


def _auth_of(entry):
    # `_p322_auths` reads `entry["authorities"]`.
    return rr._p322_auths({"authorities": [entry]})[0]


def _names(sentence, entry=None, anchored=False, titles=None):
    return rr.p322_names_ooc(sentence, _auth_of(entry or _OOC), anchored, titles or {})


# --- authorities: the full forms ------------------------------------------------------

def test_the_full_forms_name_it_and_one_surname_alone_does_not():
    # F1, the citation alone.
    assert _names("The rule comes from [1899] AC 52.") == (True, True)
    # F2, "A v B", with punctuation and corporate words in the second party.
    assert _names("Widget v E. Gadget & Co Ltd sets the test.") == (True, True)
    # F3, a party's first two distinctive words together.
    assert _names("The Gadget, Sprocket principle applies.") == (True, True)
    # One surname, unanchored: not the authority.
    assert _names("Widget sets the test.") == (False, False)
    # One surname, anchored (named in full earlier): a short form.
    assert _names("Widget sets the test.", anchored=True) == (True, False)
    # A different case sharing the first party's surname is not F2.
    assert _names("A Widget v Sample Ltd decided the point.") == (False, False)


def test_f2_does_not_reach_across_a_citation():
    # "Widget v Sample Ltd [1901] EAT 31 ... Gadget": the gap holds a bracket.
    assert _names("Widget v Sample Ltd [1901] EAT 31 (Gadget) decided it.") == (False, False)


def test_f2_needs_a_v_and_the_second_partys_first_word():
    # Another case sharing the first party's surname and a later word of the
    # second party ("Sprocket") is not the authority.
    assert _names("Widget v Sample Sprocket Ltd decided it.") == (False, False)
    # "and" is not "v".
    assert _names("Widget and E Gadget were both parties.") == (False, False)
    assert _names("Widget V. Gadget applies.") == (True, True)


def test_a_bracketed_party_name_is_kept_and_a_trailing_court_bracket_is_not_a_party():
    jr = dict(_OOC, label="R (Widget) v Gadgetshire", mention=r"\bWidget\b")
    assert rr._p322_parties(jr) == ["R (Widget)", "Gadgetshire"]
    assert _names("R (Widget) v Gadgetshire sets the test.", jr) == (True, True)
    court = dict(_OOC, label="Widget v Gadget (EAT 1899)", mention=r"\bWidget\b")
    assert rr._p322_parties(court) == ["Widget", "Gadget"]
    # The court's letters are not a second word of the second party.
    assert _names("The Gadget EAT ruling applies.", court) == (False, False)


def test_a_rubric_mention_of_two_words_is_a_full_form():
    entry = dict(_OOC, label="Widget (no parties in this label)", mention=r"Gadget\s+Sprocket|\bWidget\b")
    assert _names("Gadget Sprocket sets the test.", entry) == (True, True)
    assert _names("Widget sets the test.", entry) == (False, False)


def test_parties_and_citations_come_from_the_rubric_where_given():
    entry = dict(_OOC, label="Old widget case", parties=["Widget", "Gadget Sprocket"],
                 citations=["[1899] 2 KB 7"], mention=r"\bWidget\b")
    assert _names("Widget v Gadget Sprocket applies.", entry) == (True, True)
    assert _names("See [1899] 2 KB 7.", entry) == (True, True)
    # The label's citation is not read where `citations` is given.
    assert _names("See [1899] AC 52.", dict(entry, label=_OOC["label"])) == (False, False)
    # And with neither, the label is read for both.
    assert rr._p322_parties(_OOC) == ["Widget", "E Gadget Sprocket & Co"]
    assert _names("See [1899] AC 52.") == (True, True)


def test_corporate_and_short_words_are_not_distinctive():
    assert rr._p322_party_words("E Gadget Sprocket & Co Ltd") == ["Gadget", "Sprocket"]
    assert rr._p322_party_words("Cog & Son Ltd") == ["Cog"]
    assert rr._p322_party_words("Kingdom AC") == ["Kingdom"]


# --- authorities: a retrieved, cited judgment is never the authority -----------------

_TITLES = {k: _SHARED["title"] for k, _, _ in rr.cl_keys(_SHARED_URL)}


def test_a_retrieved_cited_judgment_sharing_the_surname_is_not_the_authority():
    s = f"In [*A Widget v Sample Ltd* [1901] EAT 31]({_SHARED_URL}), the EAT held X."
    # Even with the authority anchored, the surname is that judgment's.
    assert _names(s, anchored=True, titles=_TITLES) == (False, False)
    # Not retrieved (no title known): the anchored short form counts.
    assert _names(s, anchored=True, titles={}) == (True, False)
    # Retrieved but not cited in this sentence: the short form counts.
    assert _names("Widget sets the test.", anchored=True, titles=_TITLES) == (True, False)
    # A full form is not that judgment's name, so it still counts.
    assert _names(f"[A Widget v Sample Ltd]({_SHARED_URL}) applied Widget v Gadget Sprocket.",
                  titles=_TITLES) == (True, True)
    # ... even where it shares one of its words with that judgment's title:
    # every word of the match must be in the title, not one.
    assert _names(f"[A Widget v Sample Ltd]({_SHARED_URL}) applied Widget v E Gadget.",
                  titles=_TITLES) == (True, True)


def test_a_retrieved_title_without_a_v_still_names_its_parties():
    """The "v" is not a word the title must hold: a retrieved judgment titled
    without one, cited in the sentence, is still that judgment."""
    titles = {k: "Re Widget Gadget Holdings" for k, _, _ in rr.cl_keys(_SHARED_URL)}
    s = f"In [Widget v Gadget]({_SHARED_URL}), the court held X."
    assert _names(s, titles=titles) == (False, False)
    assert _names(s, titles={}) == (True, True)


def test_the_three_false_fails_clear_in_a_run():
    """Session 41's shape: a turn cites a different judgment sharing the
    out-of-corpus authority's surname, which the turn's search returned."""
    doc = _run([
        _turn(1, f"In [*A Widget v Sample Ltd* [1901] EAT 31]({_SHARED_URL}), the EAT held X.",
              [_search(_SHARED)]),
        _turn(2, "Nothing about it."),
    ])
    assert _verdicts(doc) == []


def test_the_guard_holds_where_the_run_has_named_it_in_full():
    doc = _run([
        _turn(1, "Widget v Gadget Sprocket [1899] AC 52 sets the test."),
        _turn(2, f"In *A Widget v Sample Ltd* [1901] EAT 31, the EAT held X.",
              [_search(_SHARED)]),
    ])
    assert _verdicts(doc) == [(1, "FAIL")]


def test_a_title_retrieved_in_an_earlier_turn_guards_a_later_one():
    doc = _run([
        _turn(1, "Widget v Gadget Sprocket [1899] AC 52 sets the test.", [_search(_SHARED)]),
        _turn(2, "In *A Widget v Sample Ltd* [1901] EAT 31, the EAT held X."),
    ])
    assert _verdicts(doc) == [(1, "FAIL")]


def test_a_title_retrieved_only_later_in_the_run_does_not_guard_an_earlier_turn():
    doc = _run([
        _turn(1, "Widget v Gadget Sprocket [1899] AC 52 is cited in the retrieved judgments. "
                 "In *A Widget v Sample Ltd* [1901] EAT 31, Widget was distinguished."),
        _turn(2, "Nothing.", [_search(_SHARED)]),
    ])
    sents = _ooc(doc)["mentions"][0][2]
    assert len(sents) == 2


def test_a_genuine_failure_stays_a_failure():
    doc = _run([
        _turn(1, f"[Cog Ltd v Example plc]({_CARRIER_URL}) decides it.", [_search(_CARRIER_ROW)]),
        _turn(2, "Widget v Gadget Sprocket [1899] AC 52 establishes the principle.",
              [_search(_SHARED)]),
    ])
    assert _verdicts(doc) == [(2, "FAIL")]


def test_a_short_form_counts_once_named_in_full_in_the_answer_or_earlier():
    doc = _run([
        _turn(1, "Widget sets the test."),                            # unanchored: not named
        _turn(2, "Widget applies. Cog Ltd v Example plc [1901] EAT 27 cites "
                 "Widget v Gadget Sprocket [1899] AC 52."),           # full, and a short form before it
        _turn(3, "Widget sets the test."),                            # anchored by turn 2
    ])
    m = _ooc(doc)["mentions"]
    assert [(e, v) for e, v, _ in m] == [(2, "PASS"), (3, "EARLIER")]
    assert len(m[0][2]) == 2


def test_a_link_labelled_with_a_retrieved_judgments_own_name_is_not_linked():
    s = f"[A Widget v Sample Ltd]({_SHARED_URL}) applied Widget v Gadget Sprocket [1899] AC 52."
    doc = _run([_turn(1, s, [_search(_SHARED)])])
    (_e, verdict, sents), = _ooc(doc)["mentions"]
    assert [c for c, _, _ in sents] == ["SECOND_HAND"] and verdict == "PASS"
    # The out-of-corpus name on a link is still LINKED.
    s2 = f"The test is in [Widget v Gadget Sprocket]({_SHARED_URL})."
    doc2 = _run([_turn(1, s2, [_search(_SHARED)])])
    (_e, verdict2, sents2), = _ooc(doc2)["mentions"]
    assert [c for c, _, _ in sents2] == ["LINKED"] and verdict2 == "FAIL"


def test_a_source_phrase_object_short_form_follows_the_same_rules():
    # Anchored: "As set out in Widget" names the authority itself, not second-hand.
    doc = _run([
        _turn(1, "Cog Ltd v Example plc [1901] EAT 27 cites Widget v Gadget Sprocket."),
        _turn(2, "As set out in Widget [1901] EAT 27, the test is control."),
    ])
    (_, _, s1), (e2, v2, s2) = _ooc(doc)["mentions"]
    assert (e2, v2) == (2, "EARLIER") and s2[0][0] == "UNQUALIFIED"


def test_the_command_exits_zero_on_the_false_fail_shape(tmp_path):
    rub = tmp_path / "p322.json"
    rub.write_text(json.dumps({"9001": _RUBRIC}), encoding="utf-8")
    d = tmp_path / "runs"
    d.mkdir()
    doc = _run([
        _turn(1, f"In [*A Widget v Sample Ltd* [1901] EAT 31]({_SHARED_URL}), the EAT held X.",
              [_search(_SHARED)]),
        _turn(2, "b"),
        _turn(3, f"[Cog Ltd v Example plc]({_CARRIER_URL}) decides it.", [_search(_CARRIER_ROW)]),
    ])
    (d / "9001_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    assert rr.main(["--dir", str(d), "authorities", "--rubric", str(rub)]) == 0


# --- negcurrency: both section-search shapes -------------------------------------------

_ACT = "asp/1901/1"
_MECHANISM = {"legislation_id": _ACT, "number": "9", "title": "Commencement",
              "text": "The other provisions of this Act come into force on such day as the "
                      "Scottish Ministers may by regulations appoint."}
_DATED = {"legislation_id": _ACT, "number": "9", "title": "Commencement",
          "text": "This Act comes into force on 1 April 2999."}


def _nc_turn(answer, *tools):
    return {"turn": 1, "question": "q", "answer": answer,
            "audit": {"delegations": [{"tools": list(tools)}]}}


def _sections(rows, shape):
    raw = rows if shape == "list" else {"results": rows, "returned": len(rows)}
    return {"name": "search_legislation_sections", "args": {"legislation_id": _ACT},
            "raw_result": json.dumps(raw) + "\n\n[NEXT STEP: a nudge after the JSON]"}


@pytest.mark.parametrize("shape", ["list", "dict"])
def test_a_commencement_provision_is_read_from_either_shape(shape):
    ev = rr.negcurrency_evidence(_nc_turn("x", _sections([_MECHANISM], shape)))
    assert ev["cmc_provisions"] == [(_ACT, "9", False)]
    ev = rr.negcurrency_evidence(_nc_turn("x", _sections([_DATED], shape)))
    assert ev["cmc_provisions"] == [(_ACT, "9", True)]


@pytest.mark.parametrize("shape", ["list", "dict"])
def test_the_verdict_reads_the_dict_shape_as_it_reads_the_list(shape):
    claims, _ = rr.negcurrency_turn(_nc_turn("The rest of the Act is not yet in force.",
                                             _sections([_DATED], shape)))
    (_s, _k, verdict, why), = claims
    assert verdict == "UNCLEAR" and "fixes a date" in why
    claims, _ = rr.negcurrency_turn(_nc_turn("The rest of the Act is not yet in force.",
                                             _sections([_MECHANISM], shape)))
    (_s, _k, verdict, why), = claims
    assert verdict == "UNSUPPORTED" and "names the mechanism" in why


def test_odd_section_shapes_are_read_as_nothing():
    for raw in ({"results": None}, {"returned": 0}, {"results": "x"}, {"results": [1, "a"]},
                {"results": 5}, {"results": {"text": "comes into force on 1 April 2999"}}):
        t = _nc_turn("x", {"name": "search_legislation_sections", "args": {},
                           "raw_result": json.dumps(raw)})
        assert rr.negcurrency_evidence(t)["cmc_provisions"] == []


# --- corpus: the description label -----------------------------------------------------

def test_the_corpus_labels_are_true_before_and_after_p36(tmp_path, capsys):
    d = tmp_path / "corpus"
    d.mkdir()
    doc = {"session_id": "9001", "rep": 1, "turns": [{"turn": 1, "answer": "a", "audit": {
        "delegations": [{"tools": [{"name": "search_legislation", "args": {"query": "w"},
                                    "raw_result": json.dumps({"results": [
                                        {"legislation_id": "ssi/1901/3", "title": "Widget Order 1901",
                                         "description": "Made under section 1."}]})}]}]}}]}
    (d / "9001_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    assert rr.cmd_corpus(argparse.Namespace(dir=str(d))) == 0
    out = capsys.readouterr().out
    assert "strips it (P3.6)" not in out and "the ONLY route" not in out
    assert re.search(r"carrying a `description`\s+1   <- 0 before P3\.6 \(_slim_search_results "
                     r"stripped it\); kept, cut to 600 characters, since", out)
    assert "lookup_legislation, P3.7" in out


# --- commencements: a scripted run is graded against its base session --------------------

_TRUTH = {"9001": ("asp/1901/2", ["ssi/1901/3"])}


def _cmc_run(answer_t1, answer_t2, script=True):
    turns = [_turn(1, answer_t1, question="When did the Widget Act commence?"),
             _turn(2, answer_t2, question="Has it all come into force?")]
    if not script:
        return _run(turns, session_id="9001")
    return _run(turns, session_id="p_9001",
                script={"base": "9001", "turns": [{"from_turn": 2}, {"from_turn": 5}]})


def test_a_scripted_run_is_graded_against_its_base(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(rr, "COMMENCEMENT_TRUTH", _TRUTH)
    d = tmp_path / "runs"
    d.mkdir()
    doc = _cmc_run("It was commenced by SSI 1901/3.",
                   "No commencement regulations have been made.")
    (d / "p_9001_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    assert rr.main(["--dir", str(d), "commencements"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"DELIVERED the relation\s+1\n", out)
    assert re.search(r"DENYING one exists, naming none\s+1\s", out)
    assert "OK    p_9001 rep1 t1 (export t2)" in out
    assert "FALSE p_9001 rep1 t2 (export t5)" in out


def test_a_session_run_is_reported_as_before(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(rr, "COMMENCEMENT_TRUTH", _TRUTH)
    d = tmp_path / "runs"
    d.mkdir()
    doc = _cmc_run("It was commenced by SSI 1901/3.", "Yes.", script=False)
    (d / "9001_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    assert rr.main(["--dir", str(d), "commencements"]) == 0
    out = capsys.readouterr().out
    assert "OK    9001 rep1 t1  When did" in out and "(export" not in out


def test_a_script_of_a_session_without_truth_is_not_graded(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(rr, "COMMENCEMENT_TRUTH", _TRUTH)
    d = tmp_path / "runs"
    d.mkdir()
    doc = _cmc_run("a", "b")
    doc["script"]["base"] = "9002"
    (d / "p_9002_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    assert rr.main(["--dir", str(d), "commencements"]) == 1
