"""P0.6: the research type the harness sends, and what it rests on.

`Filter: Research mode` is blank in the export for twelve replayed sessions,
and the harness filled it with `legislation_only`, labelled `default`. A human
read of the transcripts (`evidence/research_mode_reads.json`) found that wrong
on 16 of their 50 turns. These tests pin three things: no turn is ever
labelled `default` again; a reviewer read is sent and labelled as such, or,
where nothing settles a turn, `unknown`; and `replay_report modes` names the
unknown turns and fails a directory that sent a guess or a tool set the read
rules out.
"""

import csv as _csv
import json
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import replay_report as rr  # noqa: E402
import replay_set as rs  # noqa: E402
import tools.seam_replay as sr  # noqa: E402

TWELVE = ("6333", "6334", "6335", "6338", "6340", "6341",
          "6343", "6345", "6346", "6347", "6348", "6350")

requires_csv = pytest.mark.skipif(
    not Path(rs.DEFAULT_CSV).exists(),
    reason="transcript export is deliberately not committed; see FIX_PLAN "
           "'Data handling'. Regenerate from Admin Portal -> Developer.",
)


def _export(tmp_path, rows):
    """A minimal export: (session, research mode, [user turns...])."""
    path = tmp_path / "export.csv"
    head = ["Session ID", "Message #", "Message role", "Message content", "Message model",
            "Filter: Chat mode", "Filter: Research mode", "Session mode"]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(head)
        for sid, rmode, n in rows:
            for i in range(n):
                w.writerow([sid, str(2 * i + 1), "user", f"q{i + 1}", "", "", rmode, ""])
                w.writerow([sid, str(2 * i + 2), "assistant", "An answer.", "m", "", rmode, ""])
    cls = tmp_path / "classification.json"
    cls.write_text(json.dumps({sid: {"verdict": "FAIL"} for sid, _r, _n in rows}), encoding="utf-8")
    return str(path), str(cls)


def _reads(tmp_path, sessions):
    p = tmp_path / "reads.json"
    p.write_text(json.dumps({"sessions": {
        sid: {str(i): {"value": v, "source": "reviewer", "basis": "answer", "evidence": "x"}
              for i, v in turns.items()}
        for sid, turns in sessions.items()}}), encoding="utf-8")
    return str(p)


def _load(tmp_path, rows, reads=None):
    csv, cls = _export(tmp_path, rows)
    rpath = _reads(tmp_path, reads or {})
    return {s.session_id: s for s in rs.load_sessions(csv, cls, rpath)}


# ---------------------------------------------------------------------------
# the harness side
# ---------------------------------------------------------------------------

def test_a_blank_export_with_no_read_is_unknown_never_default(tmp_path):
    s = _load(tmp_path, [("1", "", 2)])["1"]
    assert [t.research_mode_source for t in s.turns] == ["unknown", "unknown"]
    # The API needs a value; a session with no read at all sends the default,
    # exactly as before — but the label no longer says it is evidence.
    assert [t.research_mode for t in s.turns] == [rs.DEFAULT_RESEARCH_MODE] * 2
    # The session-level record is the export's own value, and it had none.
    assert s.research_mode is None


def test_the_export_value_still_wins_and_is_labelled_snapshot(tmp_path):
    s = _load(tmp_path, [("2", "legislation_and_case_law", 2)])["2"]
    assert {(t.research_mode, t.research_mode_source) for t in s.turns} == {
        ("legislation_and_case_law", "snapshot")}
    assert s.research_mode == "legislation_and_case_law"


def test_a_reviewer_read_is_sent_and_labelled(tmp_path):
    s = _load(tmp_path, [("1", "", 3)], {"1": {
        1: "legislation_only", 2: "legislation_and_case_law", 3: "case_law_included"}})["1"]
    assert [(t.research_mode, t.research_mode_source) for t in s.turns] == [
        ("legislation_only", "reviewer"),
        ("legislation_and_case_law", "reviewer"),
        # Only the case-law half is settled: send the type that withholds
        # neither tool, and say the read was partial.
        ("legislation_and_case_law", "reviewer_partial"),
    ]


def test_an_unknown_turn_sends_the_nearest_read_and_says_unknown(tmp_path):
    """A global default would assert a research-type change nobody made — and
    fire P4.1's mode-change marker on it. The nearest read asserts none."""
    s = _load(tmp_path, [("1", "", 6)], {"1": {
        1: "unknown", 2: "legislation_and_case_law", 3: "unknown",
        4: "legislation_only", 5: "unknown"}})["1"]   # turn 6: no entry at all
    assert [t.research_mode_source for t in s.turns] == [
        "unknown", "reviewer", "unknown", "reviewer", "unknown", "unknown"]
    assert [t.research_mode for t in s.turns] == [
        "legislation_and_case_law",   # t1: the only neighbour is after it
        "legislation_and_case_law",
        "legislation_and_case_law",   # t3: a tie, so the one BEFORE
        "legislation_only",
        "legislation_only",
        "legislation_only",
    ]


def test_a_read_for_a_session_the_export_states_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="second claim"):
        _load(tmp_path, [("2", "legislation_only", 1)], {"2": {1: "legislation_only"}})


@pytest.mark.parametrize("bad,match", [
    ({"value": "hybrid"}, "value must be"),
    ({"source": "default"}, "source must be"),
    ({"basis": "guess"}, "basis must be"),
    ({"evidence": "  "}, "evidence note"),
    ({"question": "the lawyer's words"}, "unexpected key"),
])
def test_the_reads_loader_refuses_a_malformed_read(tmp_path, bad, match):
    read = {"value": "legislation_only", "source": "reviewer", "basis": "answer",
            "evidence": "x", **bad}
    p = tmp_path / "reads.json"
    p.write_text(json.dumps({"sessions": {"1": {"1": read}}}), encoding="utf-8")
    with pytest.raises(SystemExit, match=match):
        rs.load_research_reads(p)


def test_a_missing_reads_file_is_no_reads(tmp_path):
    assert rs.load_research_reads(tmp_path / "absent.json") == {}


# ---------------------------------------------------------------------------
# the committed reads
# ---------------------------------------------------------------------------

def test_the_committed_reads_are_valid_and_cover_the_twelve():
    reads = rs.load_research_reads()
    assert {s for s, _i in reads} == set(TWELVE)
    for sid in TWELVE:
        idx = sorted(i for s, i in reads if s == sid)
        assert idx == list(range(1, len(idx) + 1)), f"{sid}: turns not contiguous from 1"
    assert len(reads) == 50


def test_the_committed_read_counts():
    """The figures on the P0.6 row. 16 = 10 + 6 turns the old default sent
    WITHOUT the case-law tool the lawyer had."""
    values = [r["value"] for r in rs.load_research_reads().values()]
    assert {v: values.count(v) for v in set(values)} == {
        "legislation_only": 26, "legislation_and_case_law": 10,
        "case_law_included": 6, "unknown": 8}


def test_no_note_quotes_a_quotation():
    """A cheap guard that runs without the export: a note describes, it does
    not quote. (Straight double quotes cannot appear in a JSON string value
    unescaped; this catches the escaped and the typographic kinds.)"""
    for (sid, i), r in rs.load_research_reads().items():
        assert not re.search(r'["“”]', r["evidence"]), f"{sid} t{i}: quotation"


@requires_csv
def test_the_committed_reads_hold_no_question_text():
    """FIX_PLAN, Data handling: the lawyers' questions never enter the repo.
    No run of five words from any of a session's user turns may appear in its
    evidence notes (case names from public judgments are written as the
    judgment names them, which is not how the lawyers typed them)."""
    def shingles(text, n=5):
        w = re.findall(r"[a-z0-9]+", text.lower())
        return {" ".join(w[k:k + n]) for k in range(len(w) - n + 1)}

    sessions = {s.session_id: s for s in rs.load_sessions()}
    for (sid, i), r in rs.load_research_reads().items():
        asked = set().union(*(shingles(t.question) for t in sessions[sid].turns))
        leaked = shingles(r["evidence"]) & asked
        assert not leaked, f"{sid} t{i}: note repeats question text {sorted(leaked)[:2]}"


@requires_csv
def test_every_turn_of_the_twelve_has_a_read_and_nothing_is_a_default():
    sessions = {s.session_id: s for s in rs.load_sessions()}
    reads = rs.load_research_reads()
    for sid in TWELVE:
        assert len(sessions[sid].turns) == sum(1 for s, _i in reads if s == sid)
    assert rs.mode_report(list(sessions.values()))["research_default"] == []
    for s in sessions.values():
        for t in s.turns:
            assert t.research_mode in rs.RESEARCH_MODES
            assert t.research_mode_source in ("snapshot", "reviewer", "reviewer_partial", "unknown")


@requires_csv
def test_the_export_turns_whose_research_type_is_unknown():
    """The row's acceptance: named, by id. The replay set's eight are 6335 t5,
    6341 t6-8 and 6348 t1-4; the other sixteen are PASS sessions it never
    replays."""
    rep = rs.mode_report(rs.load_sessions())
    replayed = {i for i in rep["research_unknown"] if i.split(":")[0] in TWELVE}
    assert replayed == {"6335:5", "6341:6", "6341:7", "6341:8",
                        "6348:1", "6348:2", "6348:3", "6348:4"}
    assert set(rep["research_partial"]) == {
        "6335:6", "6347:2", "6347:3", "6347:4", "6350:3", "6350:4"}
    assert rep["research_sources"] == {
        "snapshot": 130, "reviewer": 36, "reviewer_partial": 6, "unknown": 24}


# ---------------------------------------------------------------------------
# `replay_report modes`
# ---------------------------------------------------------------------------

READS = {("6341", 2): {"value": "legislation_and_case_law"},
         ("6341", 6): {"value": "unknown"},
         ("6347", 2): {"value": "case_law_included"}}


def _doc(session, turns, rep=1, script=None, filters_rm=None):
    return {"session_id": session, "rep": rep, "script": script,
            "filters": {"research_mode": filters_rm},
            "turns": [{"turn": n, "chat_mode": "conversational",
                       "chat_mode_source": "conversational_marker", "answer": "An answer.",
                       "research_mode": rm, "research_mode_source": src}
                      for n, rm, src in turns]}


def _rows(doc):
    return rr.mode_rows(doc, rs.answer_shape, READS)


def test_a_default_label_is_a_finding():
    f = rr.mode_findings(_rows(_doc("6348", [(1, "legislation_only", "default")])))
    assert len(f) == 1 and "harness default" in f[0]


def test_a_type_the_read_rules_out_is_a_finding():
    f = rr.mode_findings(_rows(_doc("6341", [(2, "legislation_only", "reviewer")])))
    assert len(f) == 1 and "wrong tool set" in f[0]


def test_a_partial_read_rules_out_only_legislation_only():
    assert rr.research_contradicts("legislation_only", "case_law_included")
    assert not rr.research_contradicts("legislation_and_case_law", "case_law_included")
    assert not rr.research_contradicts("case_law_only", "case_law_included")
    assert not rr.research_contradicts("legislation_only", "unknown")
    assert not rr.research_contradicts("legislation_only", None)


def test_an_unknown_label_is_named_not_failed():
    rows = _rows(_doc("6341", [(6, "legislation_and_case_law", "unknown")]))
    assert rr.mode_findings(rows) == []


def test_a_run_file_before_p4_1_is_graded_on_the_filter_it_sent():
    """No per-turn type: the session's `filters.research_mode` was sent, and
    for the twelve that was the default. Graded against the read, not the
    (absent) label."""
    doc = _doc("6341", [(2, None, None)], filters_rm="legislation_only")
    rows = _rows(doc)
    assert rows[0]["research_source"] == "unrecorded"
    assert rows[0]["research_mode"] == "legislation_only"
    assert any("wrong tool set" in f for f in rr.mode_findings(rows))


def test_a_scripted_session_is_never_looked_up():
    """A script's turn indexes are the script's own; P4.1's scripts vary the
    type on purpose and must not be graded against the export's reads."""
    doc = _doc("6341", [(2, "legislation_only", "script")], script={"base": "6341"})
    rows = _rows(doc)
    assert rows[0]["research_read"] is None
    assert rr.mode_findings(rows) == []


def _write(d, name, doc):
    (d / name).write_text(json.dumps(doc), encoding="utf-8")


def test_modes_names_the_unknown_turns_and_exits_on_a_guess(tmp_path, capsys):
    """Against the committed reads: 6341 t6 is unknown, 6341 t2 is
    legislation_and_case_law, 6347 t2 is case-law-only-known."""
    d = tmp_path / "dir"
    d.mkdir()
    _write(d, "6341_rep1.json", _doc("6341", [
        (2, "legislation_and_case_law", "reviewer"),
        (6, "legislation_and_case_law", "unknown")]))
    _write(d, "6347_rep1.json", _doc("6347", [(2, "legislation_and_case_law", "reviewer_partial")]))
    assert rr.main(["--dir", str(d), "modes", "--no-export"]) == 0
    out = capsys.readouterr().out
    assert "turns whose tool set is unknown (no export value, no reviewer read): 6341 t6" in out
    assert "turns where only the case-law half is known: 6347 t2" in out
    assert "reviewer_partial" in out and "unknown" in out

    _write(d, "6348_rep1.json", _doc("6348", [(1, "legislation_only", "default")]))
    assert rr.main(["--dir", str(d), "modes", "--no-export"]) == 1
    assert "harness default" in capsys.readouterr().out


def test_the_census_counts_every_directory_beside_dir_and_exits_zero(tmp_path, capsys):
    """`modes --all-dirs` is the command behind P0.6's cross-directory
    figures: it must see every sibling directory, split P0.6's exits from
    the chat-mode ones, and never fail a run itself."""
    root = tmp_path / "replay"
    for name, doc in (("a_clean", _doc("6341", [(2, "legislation_and_case_law", "reviewer")])),
                      ("b_wrong", _doc("6341", [(2, "legislation_only", "reviewer")])),
                      ("c_default", _doc("6348", [(1, "legislation_only", "default")]))):
        (root / name).mkdir(parents=True)
        _write(root / name, "run_rep1.json", doc)
    assert rr.main(["--dir", str(root / "a_clean"), "modes", "--all-dirs"]) == 0
    out = capsys.readouterr().out
    assert "1 of 3 directories hold a turn" in out and ": 1 turn-runs." in out
    assert "modes exits 1 on 2: 2 only because of P0.6, 0 on chat mode as well." in out


def test_the_seam_takes_the_turn_research_type_not_the_session_filter():
    """The twelve's `filters.research_mode` is now None (the export had
    none); the seam must replay the type the turn sent."""
    doc = {"filters": {"research_mode": None}}
    turn = {"research_mode": "legislation_and_case_law", "chat_mode": "conversational"}
    assert sr._cfg_for(doc, turn)["_research_mode"] == "legislation_and_case_law"
    assert sr._cfg_for(doc, {"chat_mode": "conversational"})["_research_mode"] == "legislation_only"
