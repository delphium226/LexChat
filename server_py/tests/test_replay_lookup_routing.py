"""`replay_report lookup --routing` reads each brief as the product routes it (batch 12 D).

P3.10 puts a line naming the earlier steps' instruments in a Deep Research
step's brief, and `routed_lookup_block` reads the brief through
`step_handover.without_handover_line`, so those ids are never looked up. The
grader counted them as routed: on the 9 stored briefs carrying the line it
reported 3 to 5 routed ids each where the product made no lookup. It now reads
the brief the same way. Synthetic briefs and ids only.
"""
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402
from src.utils.step_handover import handover_line  # noqa: E402

LINE = handover_line(["The Widget Order 1901 (SSI 1901/3) and SSI 1901/4 apply."])


def _write(tmp, briefs):
    d = tmp / "dir"
    d.mkdir()
    dgs = [{"brief": b, "tools": [], "report": "r"} for b in briefs]
    (d / "9999_rep1.json").write_text(json.dumps(
        {"session_id": "9999", "turns": [{"turn": 1, "audit": {"delegations": dgs}}]}),
        encoding="utf-8")
    return d


def _routing(tmp, capsys, briefs):
    assert rr._lookup_routing([_write(tmp, briefs)], live=False) == 0
    return capsys.readouterr().out


def test_the_line_fixture_names_both_ids():
    assert LINE and "ssi/1901/3" in LINE and "ssi/1901/4" in LINE


def test_a_brief_whose_only_ids_are_on_the_handover_line_is_not_routed(tmp_path, capsys):
    brief = "TASK: check the changes to the identified orders.\n" + LINE + "\nCONTEXT: q"
    out = _routing(tmp_path, capsys, [brief])
    assert "0 of 1 delegation brief(s) name an instrument by number" in out
    assert "ssi/1901/3" not in out


def test_an_id_the_step_text_names_is_still_routed(tmp_path, capsys):
    brief = "TASK: read SSI 1901/7.\n" + LINE + "\nCONTEXT: q"
    out = _routing(tmp_path, capsys, [brief])
    assert "1 of 1 delegation brief(s)" in out and "1 distinct id(s)" in out
    assert "ssi/1901/7" in out and "ssi/1901/3" not in out


def test_a_brief_without_the_line_is_read_as_before(tmp_path, capsys):
    out = _routing(tmp_path, capsys, ["TASK: read SSI 1901/3 and SSI 1901/4."])
    assert "1 of 1 delegation brief(s)" in out and "2 distinct id(s)" in out
