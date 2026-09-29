"""P3.3: `tools/summary_probe` finds summaries that add what the raw text lacks.
Synthetic run files; the real patterns live in the gitignored rubric."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import summary_probe as sp  # noqa: E402


def _doc(*tools):
    return {"session_id": "9999", "turns": [{"turn": 1, "audit": {"delegations": [
        {"brief": "b", "tools": list(tools)}]}}]}


def _tool(raw, fin, lid="x/1"):
    return {"name": "search_legislation_sections", "args": {"legislation_id": lid},
            "raw_result": raw, "final_result": fin}


ADDS = [r"Widget Code 1950"]


def test_an_addition_absent_from_the_raw_text_is_found():
    doc = _doc(_tool("Section 1) A gadget.", "Summary: under the Widget Code 1950 ..."))
    assert len(sp.added_slots(doc, ADDS, [])) == 1


def test_a_name_already_in_the_raw_text_is_not_an_addition():
    doc = _doc(_tool("See the Widget Code 1950. Section 1) A gadget.", "The Widget Code 1950 ..."))
    assert sp.added_slots(doc, ADDS, []) == []


def test_a_retrieval_of_the_named_instrument_itself_is_excluded():
    # Its raw text is the instrument's sections, which carry no title.
    doc = _doc(_tool("Section 1) A widget.", "The Widget Code 1950 ...", lid="code/1950/1"))
    assert sp.added_slots(doc, ADDS, ["code/1950/1"]) == []


def test_an_unsummarised_result_is_ignored():
    doc = _doc(_tool("Widget", "Widget"))
    assert sp.added_slots(doc, ADDS, []) == []


def test_count_reads_the_rubric_and_exits_0(tmp_path, capsys):
    d = tmp_path / "runs"
    d.mkdir()
    (d / "9999_rep1.json").write_text(json.dumps(_doc(
        _tool("Section 1) A gadget.", "Under the Widget Code 1950 ..."))), encoding="utf-8")
    rub = tmp_path / "r.json"
    rub.write_text(json.dumps({"9999": {"summary_adds": ADDS}}), encoding="utf-8")
    assert sp.main(["--rubric", str(rub), "count", "--dir", str(d)]) == 0
    assert "with a rubric addition absent from the raw text: 1" in capsys.readouterr().out
