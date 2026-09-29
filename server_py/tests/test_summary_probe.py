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


# ---- P3.16: `glosses`, interpretation a summary adds that its raw text lacks ----

RAW = json.dumps({"results": [
    {"legislation_id": "widget/1901/3", "text": "Section 1) A sprocket is a wheel with teeth."},
    {"legislation_id": "widget/1901/3", "text": "Section 2) A widget is a small gadget. The grant is made under section 4 of this Order."},
    {"legislation_id": "widget/1901/3", "text": "Section 5) Every widget must be marked."},
]})


def _gloss_tool(fin, raw=RAW, name="search_legislation_sections"):
    return {"name": name, "args": {"legislation_id": "widget/1901/3"}, "raw_result": raw,
            "final_result": fin, "summarised": True}


def test_a_parenthetical_gloss_the_raw_text_lacks_is_found():
    # Every word is in the raw text; the run of words round the marker is not.
    gs = sp.glosses_in(RAW, "* **Section 2:** Widgets (including sprockets by definition) must be marked.")
    assert [g["marker"] for g in gs] == ["by definition"]


def test_a_gloss_in_the_raw_text_itself_is_not_counted():
    raw = json.dumps({"text": "Section 9) A cog is, by definition, a sprocket for all purposes."})
    assert sp.glosses_in(raw, "Section 9: a cog is, by definition, a sprocket for all purposes.") == []


def test_a_title_that_expands_an_id_in_the_raw_text_is_not_a_gloss():
    fin = "The grant is made under section 4, i.e. the Widget Order 1901."
    assert sp.glosses_in(RAW, fin) == []
    # The same words where the raw text's id is of another year are counted.
    other = RAW.replace("widget/1901/3", "widget/1902/3")
    assert [g["marker"] for g in sp.glosses_in(other, fin)] == ["i.e."]


def test_a_note_about_the_summary_is_not_a_gloss_but_a_gloss_from_absence_is():
    note = "The provided text did not include the Gadget Act 1950; therefore, it is not summarised here."
    assert sp.glosses_in(RAW, note) == []
    absence = "The text does not mention cogs, suggesting cogs are outside the Order altogether."
    assert [g["marker"] for g in sp.glosses_in(RAW, absence)] == ["suggesting"]


def test_statutory_suggests_and_effectively_as_manner_are_not_glosses():
    assert sp.glosses_in(RAW, "Ministers act if information suggests a widget is unmarked.") == []
    assert sp.glosses_in(RAW, "The grant must be used economically, efficiently and effectively.") == []
    assert sp.glosses_in(RAW, "Grants are made under section 4, effectively creating a sprocket monopoly.")


def test_a_marker_in_a_code_appended_block_is_not_the_summariser_s():
    fin = ("Section 5 requires every widget to be marked.\n\n[SEARCH SCOPE — 3 provision(s); "
           "a provision not returned may therefore still be in it.]")
    assert sp.glosses_in(RAW, fin) == []


def test_a_marker_opening_its_sentence_is_windowed_from_its_own_sentence():
    s = "Section 5 applies to every widget. Therefore, sprockets are widgets."
    a = s.index("Therefore")
    lo, hi = sp._window(s, a, a + len("Therefore"))
    assert s[lo:hi].strip().startswith("Therefore, sprockets are widgets")


def test_an_id_given_a_title_of_another_year_is_found():
    assert [x["id"] for x in sp.id_title_mismatches("Inserted by the Widget Act 1902 (widget/1905/3).")] \
        == ["widget/1905/3"]
    assert sp.id_title_mismatches("Inserted by the Widget Act 1905 (widget/1905/3).") == []
    assert [x["title_year"] for x in sp.id_title_mismatches("Amended by widget/1905/3 (the Widget Act 1902).")] \
        == ["1902"]


def test_glosses_counts_legislation_and_only_lists_case_law(tmp_path, capsys):
    d = tmp_path / "runs"
    d.mkdir()
    gloss = "Widgets (including sprockets by definition) must be marked."
    (d / "9999_rep1.json").write_text(json.dumps(_doc(
        _gloss_tool(gloss), _gloss_tool(gloss, name="get_case_law_text"),
        _gloss_tool("Section 5 requires every widget to be marked."))), encoding="utf-8")
    assert sp.main(["glosses", "--dir", str(d), "--list"]) == 0
    out = capsys.readouterr().out
    assert "summaries of legislation read: 2" in out and "GLOSSES: 1 (in 1 run-file turns)" in out
    assert "marker matches there (listed, NOT counted" in out and "): 1" in out
    assert "  GLOSS runs 9999_rep1 t1 search_legislation_sections [by definition" in out
    assert "  CASE  runs 9999_rep1 t1 get_case_law_text" in out
