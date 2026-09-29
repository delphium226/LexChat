"""P4.6: the harness half — the `scripted` grader and the p46 scripts.

The row's acceptance counts the negatives the Worker prompts scripted, in the
Worker REPORT (where the Worker composes them) and in the ANSWER (where the
Manager keeps or drops them). Its scripts replay chosen turns in Research
chat mode under the research type the export or the reviewer's read gives,
because only there does the Worker whose prompt carried the lines write.
"""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402
import replay_set as rs  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[2] / "docs" / "prepilot-fixes" / "evidence" / "scripts"

OLD_DB = "The available database does not contain information on this specific issue."
OLD_CL = ("No reported case law directly addresses this specific issue in the "
          "National Archives database.")
OLD_P4 = ("No directly relevant case law was found in the National Archives Find "
          "Case Law database for this query.")


def _doc(*turns, sid="p46_x", rep=1):
    return {"session_id": sid, "rep": rep,
            "filters": {"research_mode": None}, "turns": list(turns)}


def _t(n, answer, reports=(), tools=1, kept=0, rm="legislation_only"):
    return {"turn": n, "answer": answer, "chat_mode": "research", "research_mode": rm,
            "timing": {"sources_kept": kept},
            "audit": {"delegations": [
                {"report": r, "tools": [{"name": "search_legislation"}] * tools}
                for r in reports]}}


def test_the_three_lines_are_findings_in_the_report_and_in_the_answer():
    rows = rr.scripted_rows(_doc(
        _t(1, "Answer. " + OLD_DB, reports=[OLD_DB]),
        _t(2, "Answer.", reports=["Report. " + OLD_CL]),     # the Manager dropped it
        _t(3, "Answer.", reports=["Retry before concluding nothing exists."]),
    ))
    found = rr.scripted_findings(rows)
    assert any("t1" in f and "report" in f for f in found)
    assert any("t1" in f and "answer" in f for f in found)
    assert any("t2" in f and "report" in f and "caselaw" in f for f in found)
    assert not any("t2" in f and "answer" in f for f in found)
    assert any("t3" in f and "nothing_exists" in f for f in found)


def test_the_scoped_phase_4_line_and_a_paraphrase_are_counted_not_failed():
    """The case-law PHASE 4 line says "for this query", so it is scoped to the
    search; `corpus` is the loose shape that makes a paraphrase visible. Both
    are printed, neither fails the directory."""
    para = "The database does not contain any judgment on the point."
    rows = rr.scripted_rows(_doc(_t(1, para, reports=[OLD_P4 + " " + para])))
    assert rr.scripted_findings(rows) == []
    assert rows[0]["report"]["caselaw_p4"] == 1
    assert rows[0]["report"]["corpus"] == 1 and rows[0]["answer"]["corpus"] == 1


def test_the_new_wording_is_not_a_finding():
    new = ("The material retrieved in this search does not establish the answer. "
           "Case law was not searched in this research.")
    rows = rr.scripted_rows(_doc(_t(1, new, reports=[new])))
    assert rr.scripted_findings(rows) == []


def test_invariant_one_columns():
    rows = rr.scripted_rows(_doc(
        _t(1, "See [s.1](http://www.legislation.gov.uk/asp/2014/18/section/1).",
           reports=["r"], tools=0, kept=3)))
    r = rows[0]
    assert (r["links"], r["sources_kept"], r["tools_per_report"]) == (1, 3, [0])


def test_the_command_exits_1_on_a_finding_and_0_without(tmp_path, capsys):
    import json

    d = tmp_path / "d"
    d.mkdir()
    (d / "p46_x_rep1.json").write_text(json.dumps(_doc(_t(1, OLD_DB, reports=[OLD_DB]))),
                                       encoding="utf-8")
    assert rr.main(["--dir", str(d), "scripted"]) == 1
    b = tmp_path / "b"
    b.mkdir()
    (b / "p46_x_rep1.json").write_text(json.dumps(_doc(_t(1, "Clean.", reports=["r"]))),
                                       encoding="utf-8")
    assert rr.main(["--dir", str(b), "scripted", "--before", str(d)]) == 0
    assert "summed over the shared slots" in capsys.readouterr().out


def test_the_p46_scripts_run_the_research_worker_under_a_read_type():
    """Every p46 turn is in Research chat mode, with ONE research type per
    script, and a legislation-only script only replays turns the reviewer
    read as legislation-only (P0.6). 6385's type is the export's own
    (`case_law_only`), which is not in the repo, so it is only held fixed."""
    reads = rs.load_research_reads()
    paths = sorted(SCRIPTS.glob("p46_*.json"))
    assert {p.stem for p in paths} >= {"p46_6335", "p46_6343", "p46_6346",
                                       "p46_6347", "p46_6350", "p46_6385"}
    for p in paths:
        script = rs.load_script(p)
        types = {t["research_mode"] for t in script["turns"]}
        assert len(types) == 1, p.name
        assert all(t.get("chat_mode") == "research" for t in script["turns"]), p.name
        assert all("question" not in t for t in script["turns"]), p.name
        (rm,) = types
        if rm == "legislation_only":
            for t in script["turns"]:
                read = reads.get((script["base"], t["from_turn"])) or {}
                assert read.get("value") == "legislation_only", (p.name, t["from_turn"])
        else:
            assert (script["base"], rm) == ("6385", "case_law_only")


def test_seam_sweep_selects_delegations_whose_report_matches(tmp_path, monkeypatch):
    """`tools.seam_sweep` draws only the stored delegations that showed the
    defect, and says how many tools each ran (a zero-tool one is drawn at the
    first round)."""
    import json

    import tools.seam_sweep as ss

    d = tmp_path / "wave2"
    d.mkdir()
    doc = _doc(_t(1, "a", reports=["clean"]),
               _t(3, "b", reports=[OLD_DB], tools=0),
               _t(4, "c", reports=[OLD_DB], tools=2), sid="6335")
    (d / "6335_rep1.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(ss, "REPLAY", tmp_path)
    got = ss.select(["wave2"], ss._parse_turns(["6335:1,3"]), ss.REPORT_MATCHES["p46"])
    assert [(g[1], g[2], g[3], g[4]) for g in got] == [("6335", 3, 1, 0)]
    got = ss.select(["wave2", "absent"], ss._parse_turns(["6335:1,3,4"]),
                    ss.REPORT_MATCHES["p46"])
    assert [(g[2], g[4]) for g in got] == [(3, 0), (4, 2)]
