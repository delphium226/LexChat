"""`replay_report discovery` — P2.7's pre-flight instrument (end of Session 14).

The number a legislation search budget is set to must come from the
distribution of discovery calls per worker run. These tests pin what the
instrument counts, because every earlier instrument in this work was wrong on
its first real data at least once.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.replay_report as rr  # noqa: E402


def _tool(name, memo=False, blocked=False, **args):
    return {"name": name, "args": args, "memo_hit": memo, "budget_blocked": blocked}


def _doc(*delegations, schema=3):
    return {"session_id": "9999", "rep": 1, "turns": [{
        "turn": 1, "answer": "A.",
        "audit": {"schema_version": schema, "delegations": list(delegations)},
    }]}


def test_memo_hits_are_not_issued_calls():
    """A memo hit returns before the budget check in `run_worker_tool`, so it
    never spends budget. It is counted separately, because it still spends a
    ReAct round."""
    dg = {"kind": "delegation", "tools": [
        _tool("search_legislation", query="a"),
        _tool("search_legislation", query="b"),
        _tool("search_legislation", memo=True, query="a"),
        _tool("search_case_law", query="c"),
        _tool("search_case_law", memo=True, query="c"),
    ]}
    (r,) = rr.discovery_runs(_doc(dg))
    assert (r["leg"], r["leg_memo"], r["leg_distinct"]) == (2, 1, 2)
    assert (r["cl"], r["cl_memo"]) == (1, 1)
    assert r["tools"] == 5


def test_both_repeat_shapes_are_counted_and_kept_apart():
    """6335's shape: many section searches of ONE Act with different queries.
    Production's redundancy key (tool + resource) scores those; an exact
    repeat also needs the same query."""
    dg = {"kind": "delegation", "tools": [
        _tool("search_legislation_sections", legislation_id="asp/2002/13", query="x"),
        _tool("search_legislation_sections", legislation_id="asp/2002/13", query="y"),
        _tool("search_legislation_sections", legislation_id="asp/2002/13", query="y"),
        _tool("get_legislation_changes", legislation_id="asp/2002/13", direction="to"),
        _tool("get_legislation_changes", legislation_id="asp/2002/13", direction="from"),
    ]}
    (r,) = rr.discovery_runs(_doc(dg))
    assert r["same_resource"] == 2      # two extra section searches of one Act
    assert r["repeat_retrievals"] == 1  # one literal repeat
    assert r["sections"] == 3 and r["changes"] == 2


def test_halted_comes_from_the_audit_field_or_the_v1_marker():
    meta = {"kind": "deep_research_step", "step": 2, "tools": [],
            "halted": {"reason": "step_cap", "limit": 20, "steps": 20}}
    marker = {"kind": "delegation", "tools": [],
              "report": "[Research halted: the research agent reached ...]"}
    clean = {"kind": "delegation", "tools": [], "report": "Findings."}
    rows = rr.discovery_runs(_doc(meta, marker, clean, schema=1))
    assert [r["halted"] for r in rows] == [True, True, False]
    assert [r["halt_source"] for r in rows] == ["meta", "marker", ""]
    assert rows[0]["rounds"] == 20


def test_budget_table_counts_runs_beyond_n(tmp_path, capsys):
    busy = {"kind": "delegation", "halted": {"steps": 20},
            "tools": [_tool("search_legislation", query=f"q{i}") for i in range(12)]}
    quiet = {"kind": "delegation",
             "tools": [_tool("search_legislation", query="q")]}
    (tmp_path / "9999_rep1.json").write_text(json.dumps(_doc(busy, quiet)),
                                             encoding="utf-8")
    assert rr.main(["--dir", str(tmp_path), "discovery", "--runs"]) == 0
    out = capsys.readouterr().out
    assert "worker runs 2  (halted 1, completed 1)" in out
    # N=10: the busy run (12 issued) is stopped and 2 calls are blocked; the
    # quiet run is not.
    line = next(ln for ln in out.splitlines() if ln.startswith("  10 |"))
    assert line.split("|")[1].split() == ["1", "of", "1", "0", "of", "1", "2"]


def test_an_empty_directory_is_not_an_error(tmp_path, capsys):
    assert rr.main(["--dir", str(tmp_path), "discovery"]) == 0
