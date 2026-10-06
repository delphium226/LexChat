"""Batch 9 E: the sweep instruments for P3.22, P3.21 and P3.4.

* `authorities` grades batch 8 C's bar for P3.22 per run, from a gitignored
  rubric: each in-corpus authority retrieved / read / cited (neutral citation
  and Find Case Law URL merged), the lead authority's run count, every answer
  naming an out-of-corpus authority (second-hand or not held, Invariant 1),
  and the carrier retrieved by its need turns.
* `cmcdates` grades P3.21's acceptance: every commencement date an answer
  states, against what the same conversation retrieved (agent C's feed dates
  on `changes[].in_force`, descriptions, text; a summary supports nothing),
  and the negative branch.
* `jurisdiction` grades P3.4's acceptance (b): Scotland named, or all four
  nations with divergence (or sameness) flagged where the question says "the UK".

Every authority, instrument, rubric and answer here is synthetic.
"""

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[2] / "docs" / "prepilot-fixes" / "evidence" / "scripts"


def _tool(name, args=None, raw=None, final=None, summarised=False, api=None):
    raw_s = raw if isinstance(raw, str) or raw is None else json.dumps(raw)
    return {"name": name, "args": args or {}, "raw_result": raw_s,
            "final_result": final if final is not None else (raw_s or ""),
            "summarised": summarised, "api_calls": api or []}


def _turn(n, answer, tools=(), question="", chat_mode="conversational"):
    return {"turn": n, "question": question, "chat_mode": chat_mode, "answer": answer,
            "audit": {"delegations": [{"tools": list(tools)}]}}


def _run(turns, session_id="9001", rep=1, script=None):
    doc = {"session_id": session_id, "rep": rep, "turns": turns}
    if script:
        doc["script"] = script
    return doc


def _write_dir(path: Path, docs):
    path.mkdir(parents=True, exist_ok=True)
    for d in docs:
        (path / f"{d['session_id']}_rep{d.get('rep', 1)}.json").write_text(
            json.dumps(d), encoding="utf-8")
    return path


# --- P3.22: keys ------------------------------------------------------------------

def test_a_neutral_citation_and_its_find_case_law_url_are_one_key():
    pairs = [("[1901] UKSC 3", "https://caselaw.nationalarchives.gov.uk/uksc/1901/3"),
             ("[1901] EWCA Civ 4", "https://caselaw.nationalarchives.gov.uk/ewca/civ/1901/4"),
             ("[1901] UKUT 5 (TCC)", "https://caselaw.nationalarchives.gov.uk/ukut/tcc/1901/5"),
             ("[1901] EAT 2", "https://caselaw.nationalarchives.gov.uk/id/eat/1901/2")]
    for ncn, url in pairs:
        (a, how_a, _), = rr.cl_keys(ncn)
        (b, how_b, _), = rr.cl_keys(url)
        assert a == b and (how_a, how_b) == ("ncn", "url"), (ncn, url)
    # The Court of Appeal's division is part of the key: Civ and Crim differ.
    assert rr.cl_keys("[1901] EWCA Civ 4")[0][0] != rr.cl_keys("[1901] EWCA Crim 4")[0][0]


def test_a_law_report_is_not_a_judgment_key():
    assert rr.cl_keys("Old Widget v Ancient Ltd [1899] AC 52") == []
    assert rr.cl_keys("Widget v Gadget [1901] IRLR 8") == []
    assert rr.cl_keys("[1901] 1 KB 344") == []


# --- P3.22: a sentence naming an out-of-corpus authority ---------------------------

_OLD = __import__("re").compile(r"Old Widget", __import__("re").I)
_CARRIERS = [__import__("re").compile(r"Gadget Ltd", __import__("re").I)]
_LINK = "https://caselaw.nationalarchives.gov.uk/eat/1901/2"


def _cls(sentence, window=""):
    return rr.p322_mention_class(sentence, _OLD, _CARRIERS, window)[0]


def test_a_link_labelled_with_an_out_of_corpus_name_is_linked():
    s = "The test is set out in [Old Widget v Ancient Ltd](https://caselaw.nationalarchives.gov.uk/uksc/1899/1)."
    assert _cls(s) == "LINKED"
    # A link labelled with the carrier is not the out-of-corpus authority's.
    s2 = f"[Gadget Ltd v Sample plc [1901] EAT 2]({_LINK}) cites Old Widget v Ancient Ltd."
    assert _cls(s2) == "SECOND_HAND"


def test_said_not_to_be_in_the_database_is_not_held():
    assert _cls("Old Widget v Ancient Ltd is not held in the case-law database.") == "NOT_HELD"
    assert _cls("I could not retrieve Old Widget v Ancient Ltd itself.") == "NOT_HELD"


def test_a_citing_word_needs_the_judgment_it_came_through():
    assert _cls("Gadget Ltd v Sample plc [1901] EAT 2 cites Old Widget v Ancient Ltd.") == "SECOND_HAND"
    assert _cls("Old Widget v Ancient Ltd was applied in Gadget Ltd v Sample plc.") == "SECOND_HAND"
    assert _cls("Old Widget v Ancient Ltd is cited in the retrieved judgments.") == "SECOND_HAND"
    # The judgment named in the sentences before.
    assert _cls("The tribunal referenced the principles in Old Widget v Ancient Ltd.",
                window="In Gadget Ltd v Sample plc the tribunal decided the point.") == "SECOND_HAND"
    assert _cls("The tribunal referenced the principles in Old Widget v Ancient Ltd.") == "UNQUALIFIED"


def test_a_source_phrase_naming_the_authority_itself_is_not_second_hand():
    assert _cls("As set out in Old Widget v Ancient Ltd [1899] AC 52, the test is control.") \
        == "UNQUALIFIED"
    # Even with a judgment named later in the same phrase's reach.
    assert _cls("As set out in Old Widget v Ancient Ltd and in Gadget Ltd v Sample plc "
                "[1901] EAT 2, the test is control.") == "UNQUALIFIED"
    # The phrase's object is the judgment it came through: second-hand.
    assert _cls("The control test (as summarised in Gadget Ltd v Sample plc [1901] EAT 2) "
                "comes from Old Widget v Ancient Ltd.") == "SECOND_HAND"


def test_named_as_if_read_is_unqualified():
    assert _cls("The leading authority is Old Widget v Ancient Ltd [1899] AC 52.") == "UNQUALIFIED"


def test_the_answer_verdict_reads_every_sentence_and_the_earlier_answers():
    assert rr.p322_answer_verdict(["UNQUALIFIED", "SECOND_HAND"], False) == "PASS"
    assert rr.p322_answer_verdict(["NOT_HELD"], False) == "PASS"
    assert rr.p322_answer_verdict(["UNQUALIFIED"], True) == "EARLIER"
    assert rr.p322_answer_verdict(["UNQUALIFIED"], False) == "FAIL"
    assert rr.p322_answer_verdict(["SECOND_HAND", "LINKED"], True) == "FAIL"


# --- P3.22: one run graded -------------------------------------------------------

_RUBRIC_322 = {"9001": {"authorities": [
    {"label": "Widget", "ncn": "[1901] UKSC 3", "url": "uksc/1901/3", "lead": True,
     "mention": "Widget Co"},
    {"label": "Sprocket", "ncn": "[1901] EWCA Civ 4", "url": "ewca/civ/1901/4",
     "mention": "Sprocket"},
    {"label": "Gadget", "ncn": "[1901] EAT 2", "url": "eat/1901/2", "carrier": True,
     "need_turns": [2], "mention": "Gadget Ltd"},
    {"label": "Old Widget", "in_corpus": False, "mention": "Old Widget"},
]}}


def _search(*rows):
    return _tool("search_case_law", {"query": "widgets"},
                 {"query": "widgets", "results": list(rows), "total": len(rows)})


_W = {"title": "Widget Co v Example Ltd", "ncn": "[1901] UKSC 3",
      "url": "https://caselaw.nationalarchives.gov.uk/uksc/1901/3"}
_S = {"title": "Sprocket v Cog", "ncn": "",
      "url": "https://caselaw.nationalarchives.gov.uk/ewca/civ/1901/4"}
_G = {"title": "Gadget Ltd v Sample plc", "ncn": "[1901] EAT 2", "url": ""}


def _by_label(run):
    return {a["label"]: a for a in run["auths"]}


def test_retrieved_read_and_cited_are_matched_by_citation_or_url():
    doc = _run([
        _turn(1, "Widget Co v Example Ltd [1901] UKSC 3 decides it. Sprocket agrees.",
              [_search(_W, _S),
               _tool("get_case_law_text", {"url": _W["url"]},
                     {"ncn": "[1901] UKSC 3", "url": _W["url"], "text": "x"})]),
        _turn(2, f"See [the Court of Appeal]({_S['url']}) and [Gadget]({_LINK}).",
              [_search(_G)]),
    ])
    a = _by_label(rr.p322_run(doc, _RUBRIC_322["9001"]))
    assert a["Widget"]["retrieved"] == [(1, ["ncn", "url"])]
    assert a["Widget"]["read"] == [1]
    assert a["Widget"]["cited"] == [(1, ["ncn"])]
    # Sprocket's row carries a URL only; the answer names it, then links it.
    assert a["Sprocket"]["retrieved"] == [(1, ["url"])]
    assert a["Sprocket"]["named_only"] == [1] and a["Sprocket"]["cited"] == [(2, ["url"])]
    # Gadget's row carries an NCN only, and the answer cites it by URL: merged.
    assert a["Gadget"]["retrieved"] == [(2, ["ncn"])] and a["Gadget"]["cited"] == [(2, ["url"])]
    assert a["Gadget"]["carrier_verdict"][0] == "PASS"


def test_the_carrier_must_be_retrieved_by_its_last_need_turn():
    late = _run([_turn(1, "a"), _turn(2, "b"), _turn(3, "c", [_search(_G)])])
    assert _by_label(rr.p322_run(late, _RUBRIC_322["9001"]))["Gadget"]["carrier_verdict"][0] == "FAIL"
    unreached = _run([_turn(1, "a", [_search(_G)])])
    assert _by_label(rr.p322_run(unreached, _RUBRIC_322["9001"]))["Gadget"]["carrier_verdict"][0] == "n/a"


def test_a_scripted_run_is_graded_on_export_turns():
    script = {"base": "9001", "turns": [{"from_turn": 1}, {"from_turn": 2}]}
    doc = _run([_turn(1, "a"), _turn(2, "b", [_search(_G)])], session_id="p_9001", script=script)
    assert _by_label(rr.p322_run(doc, _RUBRIC_322["9001"]))["Gadget"]["carrier_verdict"][0] == "PASS"
    # Run turn 1 is export turn 2 (the need turn, answered); the search is in
    # export turn 3, after it.
    script["turns"] = [{"from_turn": 2}, {"from_turn": 3}]
    assert _by_label(rr.p322_run(doc, _RUBRIC_322["9001"]))["Gadget"]["carrier_verdict"][0] == "FAIL"
    script["turns"] = [{"from_turn": 1}, {"from_turn": 3}]
    assert _by_label(rr.p322_run(doc, _RUBRIC_322["9001"]))["Gadget"]["carrier_verdict"][0] == "n/a"


def test_an_out_of_corpus_mention_is_graded_per_answer_with_the_earlier_ones():
    doc = _run([
        _turn(1, "Gadget Ltd v Sample plc [1901] EAT 2 cites Old Widget v Ancient Ltd. "
                 "Old Widget v Ancient Ltd sets the test."),
        _turn(2, "Old Widget v Ancient Ltd sets the test."),
    ])
    old = _by_label(rr.p322_run(doc, _RUBRIC_322["9001"]))["Old Widget"]
    assert [(e, v) for e, v, _ in old["mentions"]] == [(1, "PASS"), (2, "EARLIER")]
    doc2 = _run([_turn(1, "Old Widget v Ancient Ltd sets the test.")])
    old2 = _by_label(rr.p322_run(doc2, _RUBRIC_322["9001"]))["Old Widget"]
    assert [(e, v) for e, v, _ in old2["mentions"]] == [(1, "FAIL")]


def test_other_cited_judgments_are_listed_and_the_rubric_ones_are_not():
    doc = _run([_turn(1, "See [1901] UKSC 3 and [1901] UKSC 9.")])
    assert rr.p322_run(doc, _RUBRIC_322["9001"])["others"] == {"1901 uksc 9": [1]}


def test_the_command_exits_on_items_three_and_four_and_on_a_before_regression(tmp_path, capsys):
    rub = tmp_path / "p322.json"
    rub.write_text(json.dumps(_RUBRIC_322), encoding="utf-8")
    good = _write_dir(tmp_path / "good", [_run([
        _turn(1, "Widget Co v Example Ltd decides it.", [_search(_W)]),
        _turn(2, "Gadget Ltd v Sample plc [1901] EAT 2 cites Old Widget v Ancient Ltd.",
              [_search(_G)])])])
    assert rr.main(["--dir", str(good), "authorities", "--rubric", str(rub)]) == 0
    bad3 = _write_dir(tmp_path / "bad3", [_run([
        _turn(1, "The leading case is Old Widget v Ancient Ltd.", [_search(_W, _G)]),
        _turn(2, "Nothing more.")])])
    assert rr.main(["--dir", str(bad3), "authorities", "--rubric", str(rub)]) == 1
    bad4 = _write_dir(tmp_path / "bad4", [_run([_turn(1, "a", [_search(_W)]), _turn(2, "b")])])
    assert rr.main(["--dir", str(bad4), "authorities", "--rubric", str(rub)]) == 1
    # Item 1 / 2 against --before: Widget retrieved in 1 of 1 before, 0 of 1 after.
    after = _write_dir(tmp_path / "after", [_run([_turn(1, "a"), _turn(2, "b", [_search(_G)])])])
    capsys.readouterr()
    assert rr.main(["--dir", str(after), "authorities", "--rubric", str(rub),
                    "--before", str(good)]) == 1
    out = capsys.readouterr().out
    assert "[Widget] retrieved 1/1 before -> 0/1 after   FAIL (fewer)   (lead)" in out
    assert "item 2: 9001 [Widget]" in out


def test_before_compares_rates_where_the_run_counts_differ(tmp_path, capsys):
    rub = tmp_path / "p322.json"
    rub.write_text(json.dumps(_RUBRIC_322), encoding="utf-8")
    hit = [_turn(1, "a", [_search(_W)]), _turn(2, "b", [_search(_G)])]
    miss = [_turn(1, "a"), _turn(2, "b", [_search(_G)])]
    before = _write_dir(tmp_path / "before", [_run(hit, rep=1), _run(miss, rep=2)])
    after = _write_dir(tmp_path / "after", [_run(hit, rep=1), _run(hit, rep=2), _run(miss, rep=3)])
    # 1 of 2 before, 2 of 3 after: more runs and a higher rate, not a regression.
    assert rr.main(["--dir", str(after), "authorities", "--rubric", str(rub),
                    "--before", str(before)]) == 0
    after2 = _write_dir(tmp_path / "after2", [_run(hit, rep=1), _run(miss, rep=2), _run(miss, rep=3)])
    # 1 of 2 before, 1 of 3 after: the same count, a lower rate.
    assert rr.main(["--dir", str(after2), "authorities", "--rubric", str(rub),
                    "--before", str(before)]) == 1


# --- P3.21: dates and claims -------------------------------------------------------

def test_dates_in_every_written_form():
    got = {raw: ymd for _, _, ymd, raw in rr.cd_dates(
        "10 May 1901, 10th May 1901, May 10, 1901, 1901-05-10, 10/05/1901 and May 1901; "
        "not 31/13/1901.")}
    assert got == {"10 May 1901": (1901, 5, 10), "10th May 1901": (1901, 5, 10),
                   "May 10, 1901": (1901, 5, 10), "1901-05-10": (1901, 5, 10),
                   "10/05/1901": (1901, 5, 10), "May 1901": (1901, 5, 0)}


def _claim_dates(text):
    return [rr._cd_fmt(ymd) for _, ymd, _, _, _ in rr.cd_claims(text)[0]]


def test_a_claim_needs_a_commencement_cue():
    assert _claim_dates("Sections 1 and 2 came into force on 10 May 1901.") == ["1901-05-10"]
    assert _claim_dates("* **1 April 1901**: Sections 1 to 3 came into force.") == ["1901-04-01"]
    assert _claim_dates("The Order commenced section 4 on 2 June 1901.") == ["1901-06-02"]
    assert _claim_dates("The judgment was given on 10 May 1901.") == []


def test_another_events_date_is_not_a_claim():
    assert _claim_dates("The Act received Royal Assent on 3 May 1901 and sections 1 to 3 "
                        "came into force on 4 May 1901.") == ["1901-05-04"]
    assert _claim_dates("As of September 1901, no commencement regulations had been made.") == []
    assert _claim_dates("No commencement regulations were found up to September 1901.") == []
    assert _claim_dates("As today's date is 24 September 1901, the commenced provisions apply.") == []


def test_a_commencement_on_royal_assent_is_a_claim_tagged():
    claims = rr.cd_claims("Sections 1 to 3 came into force on the day it was passed "
                          "(19 November 1901).")[0]
    assert [(rr._cd_fmt(c[1]), c[3]) for c in claims] == [("1901-11-19", ["assent"])]


def test_each_date_reads_its_own_stretch_of_the_sentence():
    text = ("Made 3rd March 1901 Laid before the Widget Parliament 5th March 1901 "
            "Coming into force 10th May 1901")
    assert [rr._cd_fmt(y) for y, _, _ in rr.cd_statements(text)[0]] == ["1901-05-10"]


def test_a_table_row_under_a_commencement_heading_is_a_claim():
    table = ("| Provision | Commenced by | Commencement date |\n"
             "|---|---|---|\n"
             "| s. 1 | SSI 1901/3 | 10 May 1901 |\n"
             "| s. 2 | SSI 1901/3 | 1 June 1901 |\n\n"
             "| Provision | Note |\n|---|---|\n| s. 3 | 2 July 1901 |\n")
    assert _claim_dates(table) == ["1901-05-10", "1901-06-01"]


def test_instruments_named_by_link_citation_or_title():
    text = ("[SSI 1901/3](https://www.legislation.gov.uk/id/ssi/1901/3), S.S.I. 1901/4, "
            "the Widget Act 1901 (1901 asp 2), uksi/1901/5 and the Gadget Order 1901.")
    got = rr.cd_lids(text, {"wsi/1901/6": "the Gadget Order 1901"})
    assert got == {"ssi/1901/3", "ssi/1901/4", "asp/1901/2", "uksi/1901/5", "wsi/1901/6"}


# --- P3.21: evidence ---------------------------------------------------------------

def _feed(in_force="1901-05-10", direction="to", status="retrieved", qual="wholly in force"):
    rec = {"legislation_id": "asp/1901/2" if direction == "to" else "ssi/1901/3",
           "direction": direction, "commencement_dates": status,
           "related": [{"legislation_id": "ssi/1901/3" if direction == "to" else "asp/1901/2",
                        "self": False, "type_of_effect": "coming into force", "count": 2,
                        "changes": [{"by": "reg. 2", "changed": ["s. 1", "s. 2"],
                                     "in_force": in_force, "qualification": qual}]}]}
    return _tool("get_legislation_changes", {"legislation_id": rec["legislation_id"]}, rec)


def test_feed_dates_are_read_in_c_s_shape_in_every_form():
    for value in ("1901-05-10", ["1901-05-10"], {"s. 1": "1901-05-10", "s. 2": "1901-05-10"}):
        ev = rr.cd_evidence(_turn(1, "", [_feed(in_force=value)]), 1)
        items = [(e["src"], e["lid"], e["subject"], rr._cd_fmt(e["ymd"])) for e in ev["items"]]
        assert set(items) == {("feed", "ssi/1901/3", "asp/1901/2", "1901-05-10")}, value
        assert set().union(*(e["provisions"] for e in ev["items"])) == {"s. 1", "s. 2"}
    ev = rr.cd_evidence(_turn(1, "", [_feed()]), 1)
    assert ev["items"][0]["qualification"] == "wholly in force"
    assert ev["statuses"] == [("asp/1901/2", "retrieved", "")]
    assert ev["commencing"] == {"ssi/1901/3", "asp/1901/2"}


def test_a_by_record_names_the_commencing_instrument_as_its_subject():
    ev = rr.cd_evidence(_turn(1, "", [_feed(direction="by")]), 1)
    e = ev["items"][0]
    assert (e["lid"], e["subject"]) == ("ssi/1901/3", "asp/1901/2")


def test_a_not_retrieved_status_with_its_reason_is_read():
    rec = {"legislation_id": "asp/1901/2", "direction": "to", "related": [],
           "commencement_dates": {"status": "not_retrieved", "reason": "timeout"}}
    ev = rr.cd_evidence(_turn(1, "", [_tool("get_legislation_changes",
                                            {"legislation_id": "asp/1901/2"}, rec)]), 1)
    assert ev["statuses"] == [("asp/1901/2", "not_retrieved", "timeout")] and not ev["items"]


_DESC = "These Regulations bring sections 1 and 2 of the Widget Act 1901 into force on 10 May 1901."


def test_descriptions_are_read_from_every_record_that_carries_one():
    tools = [
        _tool("lookup_legislation", {}, {"legislation_id": "ssi/1901/3", "status": "held",
                                         "title": "The Widget Act 1901 (Commencement) Regulations 1901",
                                         "description": _DESC}),
        _tool("get_legislation_text", {"legislation_id": "ssi/1901/4"},
              {"legislation": {"id": "ssi/1901/4", "title": "T",
                               "description": _DESC.replace("10 May", "11 May")},
               "full_text": "1) This Order may be cited."}),
        _tool("search_legislation", {}, {"results": [
            {"legislation_id": "ssi/1901/5", "title": "U",
             "description": _DESC.replace("10 May", "12 May")}]}),
    ]
    ev = rr.cd_evidence(_turn(1, "", tools), 1)
    assert sorted((e["lid"], rr._cd_fmt(e["ymd"]), e["src"]) for e in ev["items"]) == [
        ("ssi/1901/3", "1901-05-10", "description"), ("ssi/1901/4", "1901-05-11", "description"),
        ("ssi/1901/5", "1901-05-12", "description")]
    assert ev["titles"]["ssi/1901/3"].startswith("The Widget Act 1901 (Commencement)")


def test_section_search_text_is_read_in_both_stored_shapes():
    row = {"legislation_id": "ssi/1901/3", "text": "The appointed day is 1st July 1901."}
    for raw in ([row], {"results": [row], "returned": 1}):
        ev = rr.cd_evidence(_turn(1, "", [_tool("search_legislation_sections",
                                                {"legislation_id": "ssi/1901/3"}, raw)]), 1)
        assert [(e["lid"], rr._cd_fmt(e["ymd"]), e["src"]) for e in ev["items"]] == [
            ("ssi/1901/3", "1901-07-01", "text")], raw


def test_a_summary_supports_only_what_its_raw_result_carries():
    raw = {"results": [{"legislation_id": "ssi/1901/3", "text": "Article 3 sets the day."}]}
    summary = ("* Article 3: the Order came into force on 1 July 1901.\n"
               "* The Act came into force on 2 July 1901.")
    raw_with = {"results": [{"legislation_id": "ssi/1901/3",
                             "text": "Article 3. The day is 1st July 1901."}]}
    ev = rr.cd_evidence(_turn(1, "", [_tool("search_legislation_sections",
                                            {"legislation_id": "ssi/1901/3"}, raw,
                                            final=summary, summarised=True)]), 1)
    assert {(rr._cd_fmt(e["ymd"]), e["src"]) for e in ev["items"]} == {
        ("1901-07-01", "summary"), ("1901-07-02", "summary")}
    ev = rr.cd_evidence(_turn(1, "", [_tool("search_legislation_sections",
                                            {"legislation_id": "ssi/1901/3"}, raw_with,
                                            final=summary, summarised=True)]), 1)
    assert ("1901-07-01", "text (summarised)") in {(rr._cd_fmt(e["ymd"]), e["src"])
                                                   for e in ev["items"]}


# --- P3.21: verdicts ---------------------------------------------------------------

def _ev(*tools):
    return rr.cd_evidence(_turn(1, "", list(tools)), 1)


_LOOKUP = _tool("lookup_legislation", {}, {"legislation_id": "ssi/1901/3", "status": "held",
                                           "title": "The Widget Act 1901 (Commencement) Regulations 1901",
                                           "description": _DESC})


def _v(sentence, ev, window="", question=""):
    return rr.cmcdate_verdict(sentence, rr.cd_dates(sentence)[-1][2], ev, window, question)[:2]


def test_a_date_stated_for_the_instrument_or_provision_named_is_supported():
    ev = _ev(_LOOKUP)
    assert _v("SSI 1901/3 brought sections 1 and 2 into force on 10 May 1901.", ev)[0] == "SUPPORTED"
    assert _v("Sections 1 and 2 came into force on 10 May 1901.", ev)[0] == "SUPPORTED"
    fev = _ev(_feed())
    assert _v("Section 2 of the Widget Act 1901 came into force on 10 May 1901.", fev)[0] == "SUPPORTED"


def test_a_date_no_source_states_is_unsupported():
    v, why = _v("SSI 1901/3 brought sections 1 and 2 into force on 1 April 1901.", _ev(_LOOKUP))
    assert v == "UNSUPPORTED" and "the sources state 1901-05-10" in why


def test_a_date_only_a_summary_states_is_unsupported():
    ev = _ev(_tool("search_legislation_sections", {"legislation_id": "ssi/1901/3"},
                   {"results": [{"legislation_id": "ssi/1901/3", "text": "Article 3."}]},
                   final="The Order came into force on 1 July 1901.", summarised=True))
    v, why = _v("SSI 1901/3 came into force on 1 July 1901.", ev)
    assert v == "UNSUPPORTED" and "only a summary states it" in why


def test_a_date_only_in_a_raw_api_response_says_so():
    tool = _tool("search_legislation", {}, {"results": []},
                 api=[{"response": {"results": [{"description": "comes into force on 3 May 1901"}]}}])
    v, why = _v("SSI 1901/3 came into force on 3 May 1901.", _ev(tool))
    assert v == "UNSUPPORTED" and "raw API response" in why


def test_a_retrieved_date_for_something_else_is_unclear():
    other = _tool("lookup_legislation", {}, {"legislation_id": "ssi/1901/9", "status": "held",
                                             "title": "Gadget", "description": _DESC})
    assert _v("SSI 1901/4 came into force on 10 May 1901.", _ev(other))[0] == "UNCLEAR"


def test_provisions_the_source_does_not_list_are_unclear():
    ev = _ev(_LOOKUP)
    v, why = _v("SSI 1901/3 brought sections 1 to 3 into force on 10 May 1901.", ev)
    assert v == "UNCLEAR" and "s. 3" in why


def test_a_sentence_naming_nothing_is_tied_by_the_lines_before_then_the_question():
    ev = _ev(_LOOKUP)
    s = "These provisions were commenced on 10 May 1901."
    assert _v(s, ev)[0] == "UNCLEAR"
    assert _v(s, ev, window="SSI 1901/3 is the first commencement instrument.")[0] == "SUPPORTED"
    v, why = _v(s, ev, question="What about The Widget Act 1901 (Commencement) Regulations 1901?")
    assert v == "SUPPORTED" and "named in the question" in why


# --- P3.21: rows and the command ----------------------------------------------------

def test_a_date_retrieved_earlier_in_the_conversation_supports_a_later_claim():
    doc = _run([_turn(1, "It is held.", [_LOOKUP], question="Is SSI 1901/3 in force?"),
                _turn(2, "SSI 1901/3 brought sections 1 and 2 into force on 10 May 1901.",
                      question="Tell me more.")])
    rows = rr.cmcdate_rows(doc)
    assert [c["verdict"] for c in rows[1]["claims"]] == ["SUPPORTED"]
    assert rows[0]["asked"] and not rows[0]["claims"] and rows[0]["retrieved"] == 1


def test_only_relevant_dates_count_as_retrieved_for_the_question():
    unrelated = _tool("search_legislation_sections", {"legislation_id": "ssi/1901/8"},
                      {"results": [{"legislation_id": "ssi/1901/8",
                                    "text": "This Order comes into force on 1 June 1901."}]})
    doc = _run([_turn(1, "No.", [unrelated], question="Is the Widget Act 1901 in force?")])
    assert rr.cmcdate_rows(doc)[0]["retrieved"] == 0
    doc = _run([_turn(1, "No.", [unrelated, _feed()], question="Is the Widget Act 1901 in force?")])
    assert rr.cmcdate_rows(doc)[0]["retrieved"] == 1


def test_known_commencing_instruments_are_reported_dated_or_not(monkeypatch):
    monkeypatch.setitem(rr.COMMENCEMENT_TRUTH, "9003", ("asp/1901/2", ["ssi/1901/3", "ssi/1901/4"]))
    doc = _run([_turn(1, "SSI 1901/3 brought sections 1 and 2 into force on 10 May 1901.",
                      [_LOOKUP], question="Is the Widget Act in force?")], session_id="9003")
    assert rr.cmcdate_rows(doc)[0]["dated_for"] == {"ssi/1901/3": (True, True),
                                                    "ssi/1901/4": (False, False)}


def test_the_command_fails_an_unsupported_claim_and_any_claim_on_the_negative_branch(
        tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "CMCDATE_NEGATIVE_BRANCH", {"9002"})
    good = _write_dir(tmp_path / "good", [_run([_turn(
        1, "SSI 1901/3 brought sections 1 and 2 into force on 10 May 1901.", [_LOOKUP])])])
    assert rr.main(["--dir", str(good), "cmcdates"]) == 0
    bad = _write_dir(tmp_path / "bad", [_run([_turn(
        1, "SSI 1901/3 brought sections 1 and 2 into force on 1 April 1901.", [_LOOKUP])])])
    assert rr.main(["--dir", str(bad), "cmcdates"]) == 1
    neg = _write_dir(tmp_path / "neg", [_run([_turn(
        1, "SSI 1901/3 brought sections 1 and 2 into force on 10 May 1901.", [_LOOKUP])],
        session_id="9002")])
    assert rr.main(["--dir", str(neg), "cmcdates"]) == 1
    assert rr.main(["--dir", str(neg), "cmcdates", "--negative-allows-supported"]) == 0
    silent = _write_dir(tmp_path / "silent", [_run([_turn(1, "No date is stated.", [_LOOKUP])],
                                                   session_id="9002")])
    assert rr.main(["--dir", str(silent), "cmcdates"]) == 0


def test_product_wording_states_no_commencement_date():
    """No product text a model can echo trips the claim detector today: the
    currency limb with a text-version date, the lawyer's footer clause, and
    P3.24's commencement lines. (Agent C's P3.21 wording states dates: an echo
    of it is graded against the feed date it came from, so it is screened by
    `test_an_echoed_feed_date_is_supported` instead.)"""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.utils.search_scope import (
        _commencement_lines, _currency_footer_clause, _currency_limb, record_currency)
    log = [{"tool": "search_legislation"},
           {"tool": "currency", "kind": "valid_date", "legislation_id": "ssi/1901/3",
            "valid_date": "1901-03-11"}]
    texts = [_currency_limb(log)]
    for rec in ({"legislation_id": "asp/1901/2", "provisions_commenced": 2,
                 "commencement_orders_of_amendments": 0, "repeal_or_revocation_relations": 0,
                 "related": [{"legislation_id": "ssi/1901/3", "self": False,
                              "type_of_effect": "coming into force", "count": 2,
                              "changes": [{"by": "reg. 2", "changed": ["s. 1"]}]}]},
                {"legislation_id": "ssi/1901/1", "provisions_commenced": 0,
                 "commencement_orders_of_amendments": 0, "repeal_or_revocation_relations": 0}):
        clog = []
        record_currency(clog, "get_legislation_changes",
                        {"legislation_id": rec["legislation_id"]}, rec)
        texts += [_currency_footer_clause(clog), _commencement_lines(clog)]
    assert "1901-03-11" in texts[0]
    for text in texts:
        assert text and rr.cd_claims(text)[0] == [], text


def test_an_echoed_feed_date_is_supported():
    doc = _run([_turn(1, "Under SSI 1901/3, regulation 2, sections 1 and 2 came into force "
                         "on 1901-05-10 (wholly in force).", [_feed()])])
    (claim,) = rr.cmcdate_rows(doc)[0]["claims"]
    assert claim["verdict"] == "SUPPORTED" and claim["qual_stated"]
    assert claim["quals"] == ["wholly in force"]


# --- P3.4: jurisdiction --------------------------------------------------------------

_RX = rr._jx_compile({})


def test_titles_links_and_institutions_are_not_statements_of_jurisdiction():
    assert rr.jx_sentence("[Widget (Scotland) Regulations 1901](https://www.legislation.gov.uk/"
                          "id/ssi/1901/3)", _RX)[0] == set()
    assert rr.jx_sentence("The Scottish Ministers may make regulations.", _RX)[0] == set()
    assert rr.jx_sentence("Under the Widget (Scotland) Regulations 1901 a licence is needed.",
                          _RX)[0] == set()
    assert rr.jx_sentence("In Scotland, a licence is needed.", _RX)[0] == {"scotland"}
    assert rr.jx_sentence("Across Great Britain the rule applies.", _RX)[0] == {
        "england", "wales", "scotland"}


def test_scotland_expected():
    v = lambda p: rr.jx_verdict(p, "scotland", _RX)[0]  # noqa: E731
    assert v("In Scotland, the Widget Rules 1901 apply.") == "PASS"
    assert v("Under the Widget (Scotland) Rules 1901, the minister decides.") == "IMPLICIT"
    assert v("In England and Wales, the Widget Rules 1901 apply.") == "FAIL"
    assert v("Under the Widget Act 1901, the minister decides.") == "FAIL"


def test_all_four_expected_with_divergence_or_sameness():
    v = lambda p: rr.jx_verdict(p, "uk_all", _RX)[:2]  # noqa: E731
    assert v("The rules differ: in Scotland, Wales and Northern Ireland a widget needs a "
             "licence; in England it does not.")[0] == "PASS"
    assert v("The rule applies equally across the UK, in England, Wales, Scotland and "
             "Northern Ireland.")[0] == "PASS"
    verdict, why = v("In Scotland and Wales a widget needs a licence.")
    assert verdict == "FAIL" and "england" in why and "ni" in why
    verdict, why = v("In England, Wales, Scotland and Northern Ireland a widget needs a licence. "
                     "The older UK-wide Widget Regulations 1901 were revoked.")
    assert verdict == "FAIL" and "flags no divergence" in why


def test_the_command_reads_the_expectation_from_the_question_and_export_turns(tmp_path):
    rub = tmp_path / "p34.json"
    rub.write_text(json.dumps({"9101": {"turns": [1], "expect": "scotland"},
                               "9102": {"turns": [1]}}), encoding="utf-8")
    script = {"base": "9101", "turns": [{"from_turn": 1}, {"from_turn": 2}]}
    d = _write_dir(tmp_path / "d", [
        _run([_turn(1, "In Scotland, a widget needs a licence."),
              _turn(2, "Under the Widget Act 1901 it does not.")],
             session_id="p_9101", script=script),
        _run([_turn(1, "In Scotland a widget needs a licence.",
                    question="Are there widget rules in the UK?")], session_id="9102"),
    ])
    assert rr.main(["--dir", str(d), "jurisdiction", "--rubric", str(rub)]) == 1
    # Only export turn 1 of the script is graded: the 9102 run is graded
    # against "the UK" from its question, and fails.
    d2 = _write_dir(tmp_path / "d2", [
        _run([_turn(1, "In Scotland, a widget needs a licence."),
              _turn(2, "Under the Widget Act 1901 it does not.")],
             session_id="p_9101", script=script)])
    assert rr.main(["--dir", str(d2), "jurisdiction", "--rubric", str(rub)]) == 0


# --- P3.4's scripts ----------------------------------------------------------------

@pytest.mark.parametrize("name,base", [("p34_6378", "6378"), ("p34_6360", "6360")])
def test_the_p34_scripts_are_turn_one_conversational_legislation_only(name, base):
    script = json.loads((SCRIPTS / f"{name}.json").read_text(encoding="utf-8"))
    assert script["session_id"] == name and script["base"] == base
    assert script["turns"] == [{"from_turn": 1, "research_mode": "legislation_only",
                                "chat_mode": "conversational"}]
    assert "question" not in json.dumps(script["turns"])
