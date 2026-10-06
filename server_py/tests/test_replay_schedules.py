"""Batch 8 B: the acceptance instruments for P3.27, P3.12 and P3.25's sweep.

* `depth` gains two optional `DepthReq` fields (`span`, `unless`) and P3.12's
  ground truth for 6335 turn 7 (paragraphs 42-44 of Schedule B1 to the
  Insolvency Act 1986: public statutory words, the standing exception for
  `DEPTH_TRUTH`);
* `schedules` grades what an answer says about a schedule or annex unit LEX
  holds (P3.27: never "not held", "not retrievable" or "not in the text") or
  does not hold (6374's Invariant 1 guard: the index, not a search limit);
* `p32c_6406`, the P3.2 script cut after export turn 5, and `stance`'s control
  reading of it.

Every rubric, unit and answer here is synthetic except the 6335 entry, whose
words are the statute's.
"""

import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[2] / "docs" / "prepilot-fixes" / "evidence" / "scripts"


# --- DepthReq: span and unless -------------------------------------------------

_ACTS = {"widget": re.compile(r"Widget Act 1901", re.I)}


def _req(**kw):
    base = dict(label="Sch 2 para 7", act="widget",
                deep=re.compile(r"\bparagraph 7\b", re.I),
                coarse=re.compile(r"\bSchedule 2\b", re.I),
                facts=(re.compile(r"\bsprockets\b", re.I), re.compile(r"\bcogs\b", re.I)),
                near=True)
    base.update(kw)
    return rr.DepthReq(**base)


_LISTED = ("Under the Widget Act 1901, paragraph 7 of Schedule 2 provides that:\n"
           "* no person may sell sprockets;\n"
           "* no person may hire cogs.\n")


def test_a_paragraph_whose_heads_are_listed_on_later_lines_needs_a_wider_span():
    assert rr._grade_depth_req(_LISTED, _req(), _ACTS)[0] == "coarse"
    assert rr._grade_depth_req(_LISTED, _req(span=2), _ACTS)[0] == "deep"


def test_the_default_span_is_the_old_window_exactly():
    text = "First sentence. Second sentence. Third sentence."
    assert rr._sentence_window(text, 0) == "First sentence. Second sentence. "
    assert rr._sentence_window(text, 0, 0) == "First sentence. "


def test_a_citation_in_a_sentence_saying_it_was_not_retrieved_is_not_at_depth():
    text = ("Under the Widget Act 1901, paragraph 7 of Schedule 2 was not retrieved. "
            "Sellers of sprockets and cogs are regulated elsewhere.")
    unless = re.compile(r"\bnot retrieved\b", re.I)
    assert rr._grade_depth_req(text, _req(), _ACTS)[0] == "deep"
    assert rr._grade_depth_req(text, _req(unless=unless), _ACTS)[0] == "coarse"
    assert rr.depth_counts(text, _req(unless=unless), _ACTS)[0] == 0


# --- P3.12's ground truth: 6335 turn 7 -----------------------------------------

_P42 = ("Under paragraph 42 of Schedule B1 to the Insolvency Act 1986, while a company "
        "is in administration no resolution may be passed and no order may be made for "
        "its winding up.")
_P43 = ("Paragraph 43 of Schedule B1 adds that no step may be taken to enforce security "
        "over the company's property, and no legal process may be instituted or "
        "continued against it, except with the consent of the administrator or the "
        "permission of the court.")
_P44 = ("Paragraph 44 provides an interim moratorium from the time an administration "
        "application has been made, or a notice of intention to appoint an administrator "
        "has been filed.")


def test_6335_turn_7_is_graded():
    assert rr.DEPTH_TRUTH["6335"]["turns"] == (7,)
    assert [r.label.split(":")[0] for r in rr.DEPTH_TRUTH["6335"]["reqs"]] == [
        "Sch B1 para 42", "Sch B1 para 43", "Sch B1 para 44"]


def test_6335_all_three_paragraphs_with_their_substance_is_delivered():
    verdict, graded = rr.depth_verdict("6335", "\n\n".join((_P42, _P43, _P44)))
    assert verdict == "DELIVERED", [(g[0].label, g[1]) for g in graded]


def test_6335_a_paragraph_listed_over_bullets_is_delivered():
    listed = ("Under the Insolvency Act 1986, **Schedule B1, paragraph 43** (moratorium on "
              "other legal process), except with the administrator's consent or the "
              "court's permission:\n"
              "* no step may be taken to enforce security over the company's property;\n"
              "* no goods may be repossessed under a hire-purchase agreement;\n"
              "* no legal process may be instituted or continued against the company.")
    _, graded = rr.depth_verdict("6335", "\n\n".join((_P42, listed, _P44)))
    assert [g[1] for g in graded] == ["deep", "deep", "deep"]


def test_6335_the_paragraphs_named_but_not_delivered_is_shallow():
    ans = ("The moratorium is in Schedule B1 to the Insolvency Act 1986. The specific "
           "provisions (such as paragraphs 42, 43 and 44) were not retrieved because "
           "searching was cut short by a limit. Enforcing security and legal process "
           "need the permission of the court, and no order for winding up may be made.")
    assert rr.depth_verdict("6335", ans)[0] == "SHALLOW"


def test_6335_paragraph_43_needs_all_three_of_its_facts():
    thin = ("Paragraph 43 of Schedule B1 to the Insolvency Act 1986 restricts legal "
            "process against the company.")
    _, graded = rr.depth_verdict("6335", "\n\n".join((_P42, thin, _P44)))
    assert [g[1] for g in graded] == ["deep", "coarse", "deep"]


def test_6335_only_the_interim_moratorium_is_partial():
    ans = ("Schedule B1 to the Insolvency Act 1986 governs administration. " + _P44)
    assert rr.depth_verdict("6335", ans)[0] == "PARTIAL"


def test_no_prompt_example_names_the_provisions_p312_grades():
    # As P3.1's `_GRADED` guard (test_citation_depth): a prompt example naming
    # the graded paragraphs would let a model copying its FORMAT land on them.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src import prompts
    names = [n for n in dir(prompts) if n.isupper() and isinstance(getattr(prompts, n), str)]
    assert names
    rx = re.compile(r"Sch(?:edule|\.)?\s*B1|\bpara(?:graph)?s?\.?\s*4[234]\b", re.I)
    assert not [n for n in names if rx.search(getattr(prompts, n))]


def test_6335_a_range_and_lex_s_own_rendering_count_as_citations():
    for cite in ("paragraphs 42-44 of Schedule B1", "paras 42 to 44 of Schedule B1",
                 "Section 43 of Schedule B1", "Schedule B1, s.43"):
        assert rr._sch_b1_paragraph(43).search(cite), cite
    assert not rr._sch_b1_paragraph(43).search("paragraph 4 of Schedule B1")
    assert not rr._sch_b1_paragraph(43).search("section 43 of the Act")


# --- schedules: the classifier ---------------------------------------------------

def test_each_clause_class():
    c = rr.sched_clause_class
    assert c("Would you like me to pull the full Schedule?") == "OFFER"
    assert c("the Schedule would require a deeper look to list in full") == "OFFER"
    assert c("the Schedule was not retrieved because searching was cut short by a limit") == "LIMIT"
    assert c("the extraction from this Schedule did not complete due to system limits") == "LIMIT"
    assert c("the Schedule text was not retrieved due to the research limit") == "LIMIT"
    assert c("the text of the Schedule is not held in this legislation index") == "INDEX"
    assert c("the database lacked the Schedule to the Widget Order 1901") == "INDEX"
    assert c("the Schedule is missing from the retrieved database") == "INDEX"
    assert c("the index holds no schedule for this instrument") == "INDEX"
    assert c("the Order has no schedules or annexes in this index") == "INDEX"
    assert c("the text of this Schedule is unavailable in the database") == "INDEX"
    assert c("the retrieved text does not contain the Annexes") == "TEXT"
    assert c("the tool is currently unable to retrieve the text of that Annex") == "NEG"
    assert c("the text of Chapter 2 was not returned") == "NEG"
    # A limit named in the same clause wins: the absence is put down to the run.
    assert c("the Schedule is missing from the database as searching was cut short") == "LIMIT"


def test_a_reading_of_the_law_is_not_a_research_negative():
    c = rr.sched_clause_class
    assert c("Chapter 2 of Annex 9 does not contain any provision for widget oil") == ""
    assert c("Annex 8 contains no provisions for widget oil") == ""
    assert c("widget oil is not listed in Schedule 2") == ""
    assert c("I cannot confirm what Annex 8 requires from memory") == ""
    assert c("Because the index is incomplete, I cannot verify Annex 9") == "INDEX"


def test_a_clause_about_something_else_is_not_read_as_about_the_unit():
    mention = re.compile(r"\bschedule\b", re.I)
    prose = ("Step 2 was halted by a system limit; furthermore, the database lacked the "
             "Schedule to the Widget Order 1901.")
    got = rr.sched_unit_clauses(prose, mention)
    assert [k for k, _, _ in got] == ["INDEX"]


def test_an_anaphor_in_a_later_clause_is_about_the_unit_and_a_link_path_is_not_a_mention():
    mention = re.compile(r"\bschedule\b(?!\s*\d)", re.I)
    prose = ("Article 3 lists further widgets in the Schedule, but its text is not held "
             "in this index. See [Widget Act 1901 - Sch 2](http://example.org/x/schedule/2).")
    got = rr.sched_unit_clauses(prose, mention)
    assert [k for k, _, _ in got] == ["", "INDEX"]


def test_verdicts():
    v = rr.sched_verdict
    assert v(True, {"INDEX"}, True)[0] == "FAIL"
    assert v(True, {"TEXT"}, True)[0] == "FAIL"
    assert v(True, {"NEG"}, True)[0] == "FAIL"
    assert v(True, {"LIMIT"}, True)[0] == "LIMIT"
    assert v(True, {"OFFER"}, True)[0] == "OK"
    assert v(True, set(), False)[0] == "SILENT"
    assert v(False, {"INDEX"}, True)[0] == "PASS"
    assert v(False, {"INDEX", "LIMIT"}, True)[0] == "FAIL"
    assert v(False, {"OFFER"}, True)[0] == "FAIL"
    assert v(False, {"NEG"}, True)[0] == "UNATTRIBUTED"
    assert v(False, set(), True)[0] == "SILENT"


# --- schedules: the command over synthetic run files -----------------------------

_RUBRIC = {
    "9001": {"units": [{"label": "Widget Order Schedule", "held": False,
                        "mention": r"\bschedules?\b(?!\s*(?-i:\d|[A-Z]{1,3}\d*\b))"}]},
    "9002": {"units": [{"label": "Gadget Annex", "held": True, "mention": r"\bannex\b"}]},
}


def _run(sid, answers, script=None):
    d = {"session_id": sid, "rep": 1,
         "turns": [{"turn": i, "chat_mode": "conversational", "question": "q",
                    "answer": a} for i, a in enumerate(answers, 1)]}
    if script:
        d["script"] = script
    return d


def _write(tmp_path, docs):
    d = tmp_path / "sweep"
    d.mkdir()
    for i, doc in enumerate(docs, 1):
        (d / f"{doc['session_id']}_rep{i}.json").write_text(json.dumps(doc), encoding="utf-8")
    rub = tmp_path / "p327.json"
    rub.write_text(json.dumps(_RUBRIC), encoding="utf-8")
    return d, rub


def _args(d, rub, **kw):
    import argparse
    base = dict(dir=str(d), rubric=str(rub), also=None, all_dirs=False, session=None,
                drops=False, chars=200)
    base.update(kw)
    return argparse.Namespace(**base)


def test_the_guard_passes_an_index_statement_and_fails_a_limit(tmp_path, capsys):
    good = _run("9001", ["The Widget Order 1901 lists widgets in its Schedule, but the "
                         "text of the Schedule is not held in this index."])
    d, rub = _write(tmp_path, [good])
    assert rr.cmd_schedules(_args(d, rub)) == 0
    assert "PASS" in capsys.readouterr().out

    bad = _run("9001", ["The Schedule was not retrieved because searching was cut short "
                        "by a limit."])
    (tmp_path / "b").mkdir()
    d2, rub2 = _write(tmp_path / "b", [bad])
    assert rr.cmd_schedules(_args(d2, rub2)) == 1
    assert "blames a search limit" in capsys.readouterr().out


def test_a_held_annex_called_not_held_fails_and_a_scripted_turn_maps_back(tmp_path, capsys):
    script = {"base": "9002", "turns": [{"from_turn": 1}, {"from_turn": 5}]}
    doc = _run("p99_9002", ["Nothing about it.",
                            "The text of the Annex is not held in this legislation index."],
               script=script)
    d, rub = _write(tmp_path, [doc])
    assert rr.cmd_schedules(_args(d, rub)) == 1
    out = capsys.readouterr().out
    assert "t2 (export 5)" in out and "FAIL" in out


def test_a_session_outside_the_rubric_is_not_graded(tmp_path, capsys):
    d, rub = _write(tmp_path, [_run("9003", ["The Schedule is not held in this index."])])
    assert rr.cmd_schedules(_args(d, rub)) == 0
    assert "graded slots: 0" in capsys.readouterr().out


def test_schedules_is_wired_into_the_cli():
    import inspect
    assert "schedules" in inspect.getsource(rr.main)


# --- the cut P3.2 script ----------------------------------------------------------

def test_the_cut_script_ends_on_the_control_turn():
    full = json.loads((SCRIPTS / "p32_6406.json").read_text(encoding="utf-8"))
    cut = json.loads((SCRIPTS / "p32c_6406.json").read_text(encoding="utf-8"))
    assert cut["base"] == full["base"]
    assert cut["session_id"] != full["session_id"]
    assert [t["from_turn"] for t in cut["turns"]] == [1, 3, 4, 5]
    assert cut["turns"] == full["turns"][:4]
    assert cut.get("verdict") == "FAIL"


def test_stance_reads_the_control_on_the_cut_script_s_last_run_turn():
    rub = {"window": [6, 12], "challenge_turns": [5], "affirm": [r"\bgizmo\b"],
           "deny": [r"\bno gizmo\b"],
           "controls": {"5": {"must": [r"\bnot listed\b"], "must_not": [r"not held"]}}}
    cut = json.loads((SCRIPTS / "p32c_6406.json").read_text(encoding="utf-8"))
    turns = [{"turn": i, "answer": "x", "audit": {"delegations": [{}]}} for i in (1, 2, 3)]
    turns.append({"turn": 4, "answer": "The widget is not listed in Chapter 2.",
                  "audit": {"delegations": [{}]}})
    g = rr.stance_grade({"session_id": cut["session_id"], "turns": turns, "script": cut}, rub)
    row = [r for r in g["rows"] if r["base"] == 5][0]
    assert row["turn"] == 4 and row["control"] is True
    turns[3]["answer"] = "The text of Chapter 2 is not held in this index."
    g = rr.stance_grade({"session_id": cut["session_id"], "turns": turns, "script": cut}, rub)
    assert [r for r in g["rows"] if r["base"] == 5][0]["control"] is False
