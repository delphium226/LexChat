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

import pytest

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


@pytest.mark.parametrize("phrase,deep", [
    ("no order may be made to wind up the company", True),
    ("no order may be made to wind-up the company", True),
    ("no resolution may be passed for its winding up", True),
    ("no winding-up order may be made", True),
    ("no order may be made for the company to be wound up", False),
    ("no order may be made against the company", False),
])
def test_6335_paragraph_42_reads_wind_up_as_well_as_winding_up(phrase, deep):
    """Batch 13 B: a draw that wrote "an order to wind up a company" was read
    as coarse (batch 12 A's hand-read: delivered)."""
    p42 = f"Under paragraph 42 of Schedule B1 to the Insolvency Act 1986, {phrase}."
    _, graded = rr.depth_verdict("6335", "\n\n".join((p42, _P43, _P44)))
    assert graded[0][1] == ("deep" if deep else "coarse"), phrase


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


# --- batch 8 B2: P3.12's true-negative lines read INDEX; the held wording does not ---
#
# The strings below are agent A's built wording (`src/utils/schedule_units.py`
# on A's branch), copied verbatim with the synthetic id `ssi/1901/3`. A's
# true-negative lines put the index in one clause and the unit in the next
# (", and none of them is a schedule ...", ", so it holds none for ..."), so
# before B2 they classed '' and a model echoing one read SILENT on 6374's guard.

_ANY_UNIT = re.compile(r"\b(?:schedules?|annex(?:es)?)\b", re.I)

_A_TRUE_NEGATIVES = (
    "[PROVISION FETCHED BY CODE — the index holds 1 provisions for ssi/1901/3, and none "
    "of them is a schedule or an annex: Schedule 2 is not one of them. This search's "
    "results left it out for that reason.]",
    "[PROVISION FETCHED BY CODE — the index holds ssi/1901/3 without its provision text, "
    "so it holds none for Schedule 2 either.]",
    "[PROVISION FETCHED BY CODE — the index holds 3 provisions for ssi/1901/3, and its "
    "schedules and annexes among them are Schedule 1 and Schedule 3: Schedule 2 is not "
    "one of them. This search's results left it out for that reason.]",
    # Read INDEX before B2 too; kept so the set is A's whole true-negative set.
    "[PROVISION FETCHED BY CODE — the index lists Schedule 2 of ssi/1901/3 as a "
    "provision and holds no text for it.]",
    "[SCHEDULES AND ANNEXES — the index holds no schedule or annex text for ssi/1901/3, "
    "so this text is its sections only.]",
)

_ECHOES = (
    "The index holds three provisions for the Widget Order 1901, and none of them is a schedule.",
    "The index holds 4 provisions for the Order, and none of them is a schedule or an annex.",
    "The index holds the Widget Order 1901 without its provision text, so it holds none "
    "for its Schedule either.",
    "The legislation index lists the Order but holds none for the Schedule.",
    "The legislation index holds none of the Order's schedules.",
    "The database holds the Widget Order 1901 without the text of its Schedule.",
)

_URL = "http://www.legislation.gov.uk/id/ssi/1901/3/schedule/2"
_LIST_LEAD = (f"[PROVISION FETCHED BY CODE — the index holds Schedule 2 of ssi/1901/3 as one "
              f"provision (url: {_URL}). This search's results left it out, so code fetched "
              "it from the index's provision list.")
_TEXT_LEAD = ("[PROVISION FETCHED BY CODE — the index's provision list for ssi/1901/3 did not "
              "come back, so code cut Schedule 2 out of the instrument's whole text with its "
              "schedules, at its heading and the next schedule or annex heading.")
_TAILS = (" Below is the part of it this search named, labelled.",
          " Below is the whole of Schedule 2.",
          " Below is Schedule 2 summarised for this research question, because it runs to "
          "123,456 characters. The summary is not the statutory text: quote the provision "
          "only from retrieved text.")
_REASONS = ("", " Paragraph 4 has no single heading of its own in it to cut at.",
            " Paragraphs 4 and 5 have no single heading of their own in it to cut at.",
            " It carries no heading for Chapter II to cut at.")

_A_HELD = tuple(lead + tail + reason + "]" for lead in (_LIST_LEAD, _TEXT_LEAD)
                for tail in _TAILS for reason in _REASONS) + (
    "[/PROVISION FETCHED BY CODE]",
    "[SCHEDULES AND ANNEXES — this text of ssi/1901/3 carries, after its sections, the "
    "schedule and annex text the index holds, under this heading: Schedule 1.]",
    "[SCHEDULES AND ANNEXES — this text of ssi/1901/3 carries, after its sections, the "
    "schedule and annex text the index holds, under these headings: Schedule 1 and "
    "Schedule 2. Some text with no schedule or annex heading comes before the first of them.]",
    "[SCHEDULES AND ANNEXES — this text of ssi/1901/3 carries, after its sections, further "
    "text that the index holds as schedule or annex text. It carries no schedule or annex "
    "heading.]",
    "[SCHEDULES AND ANNEXES — this text of ssi/1901/3 was requested with its schedules and "
    "annexes included, where the index holds them. Which ones it carries was not checked.]",
    "Paragraph 4 of Schedule 2, cut at its own heading and the next one:",
    "The text of Schedule 2 from the heading of paragraph 4 to the next headed paragraph. It "
    "runs through paragraphs 4 to 7, because the paragraphs after 4 in it carry no heading "
    "of their own:",
    "The text of Schedule 2 from the heading of paragraph 4 to the next headed paragraph, "
    "which may hold more than paragraph 4:",
    "The text of Schedule 2 from the heading of paragraph 4 to its end, which may hold later "
    "paragraphs that carry no heading of their own:",
    "Chapter II of Annex IV, cut at its heading and the next chapter's heading:",
    # P3.12's OPEN line: "was not among them" says nothing about what is held.
    "[PROVISION FETCHED BY CODE — whether the index holds Schedule 2 of ssi/1901/3 is open: "
    "code fetched only the first 200 provisions of its list, and Schedule 2 was not among them.]",
    "[PROVISION FETCHED BY CODE — the index's provision list for ssi/1901/3 did not come back, "
    "so code could fetch Schedule 2 neither from it nor from the whole text. Whether the index "
    "holds Schedule 2 is open: do not report it as absent.]",
)


def _unit_classes(text):
    return [k for k, _, _ in rr.sched_unit_clauses(text, _ANY_UNIT)]


def test_a_s_true_negative_lines_read_as_index():
    for text in _A_TRUE_NEGATIVES:
        got = _unit_classes(text)
        assert "INDEX" in got and set(got) <= {"", "INDEX"}, (text[:70], got)


def test_an_echo_of_a_s_true_negative_lines_reads_as_index():
    for text in _ECHOES:
        got = _unit_classes(text)
        assert "INDEX" in got and set(got) <= {"", "INDEX"}, (text[:70], got)


def test_none_of_a_s_held_unit_wording_reads_as_a_negative():
    assert len(_A_HELD) == 36
    for text in _A_HELD:
        assert set(_unit_classes(text)) <= {""}, (text[:90], _unit_classes(text))


def test_a_reading_of_the_law_with_one_of_them_is_not_an_index_negative():
    # The anaphor clause is about the Schedule, but its subject is not the unit.
    got = _unit_classes("The Schedule lists five offences, and theft is not one of them.")
    assert set(got) <= {""}, got
    assert rr.sched_clause_class("the Schedule lists offences: theft is not one of them") == ""


def test_the_guard_passes_an_echo_of_the_none_is_a_schedule_line(tmp_path, capsys):
    doc = _run("9001", ["The index holds three provisions for the Widget Order 1901, and "
                        "none of them is a schedule."])
    d, rub = _write(tmp_path, [doc])
    assert rr.cmd_schedules(_args(d, rub)) == 0
    out = capsys.readouterr().out
    assert "PASS" in out and "SILENT" not in out


# --- batch 8 B2: corpus's leak check knows P3.27's and P3.12's blocks ------------

def test_corpus_counts_a_leaked_schedules_or_fetched_block(tmp_path, capsys):
    answers = ["A clean answer.",
               "Text. [SCHEDULES AND ANNEXES — the index holds no schedule or annex text "
               "for ssi/1901/3, so this text is its sections only.]",
               "Text. [PROVISION FETCHED BY CODE — the index lists Schedule 2 of ssi/1901/3 "
               "as a provision and holds no text for it.]",
               "Paragraph 4 of Schedule 2 says widgets are gadgets.\n"
               "[/PROVISION FETCHED BY CODE]"]
    d = tmp_path / "corpus"
    d.mkdir()
    (d / "9004_rep1.json").write_text(json.dumps(_run("9004", answers)), encoding="utf-8")
    import argparse
    assert rr.cmd_corpus(argparse.Namespace(dir=str(d))) == 0
    out = capsys.readouterr().out
    m = re.search(r"LEAKED an agent-facing block\s*(\d+)", out)
    assert m and int(m.group(1)) == 3, out
