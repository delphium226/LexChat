"""`tools/plan_lint`: one test per check, each on a synthetic plan string.

The plan text is invented (widgets and gadgets); nothing here comes from a session.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import plan_lint as pl  # noqa: E402

ROW_X = "| `[x]` | **P1.1** | **Fix the widget.** Body. **Depends on:** — |"
ROW_OPEN = "| `[ ]` | **P1.2** | **Fix the gadget.** Body. **Depends on:** P1.1 |"
INDEX = [
    "| B1 Widgets | P1.1 (the widget) **done**, P1.2 (the gadget) |",
    "| *(no bucket)* | P1.3 (the sprocket) |",
]
ROW_3 = "| `[ ]` | **P1.3** | **Fix the sprocket.** Body. **Depends on:** — |"


def _plan(rows=None, index=None, order=None, extra=""):
    rows = rows if rows is not None else [ROW_X, ROW_OPEN, ROW_3]
    index = index if index is not None else INDEX
    order = order if order is not None else (
        "**Recommended order as at 2026-01-01 (end of Session 1):** Take P1.2 next. "
        "1 of 3 rows, 0 of 1 buckets.")
    return "\n".join([
        "# Widget plan", "", order, "", "## Ledger", "",
        "### Wave 1 — Widgets", "", "| | ID | Row |", "|---|---|---|", *rows, "",
        extra, "",
        "## Bucket → row index", "", "| Bucket | Rows |", "|---|---|", *index, "",
        "---", "", "## Merging back", "",
    ])


def _msgs(findings, check, level=None):
    return [f.message for f in findings
            if f.check == check and (level is None or f.level == level)]


def test_the_synthetic_plan_is_clean():
    assert pl.lint(_plan().encode("utf-8")) == []


# 1. row shape --------------------------------------------------------------

def test_a_stray_pipe_splits_a_row_and_is_an_error():
    rows = [ROW_X, ROW_OPEN.replace("Body.", "Body `a|b`. More | text."), ROW_3]
    msgs = _msgs(pl.check_row_shape(_plan(rows=rows)), "shape", pl.ERROR)
    assert len(msgs) == 1 and msgs[0].startswith("P1.2")
    assert "5 cells" in msgs[0] and "1 inside a code span, 1 outside" in msgs[0]


def test_an_escaped_pipe_does_not_split_a_row():
    rows = [ROW_X, ROW_OPEN.replace("Body.", r"Body `a\|b`."), ROW_3]
    assert pl.check_row_shape(_plan(rows=rows)) == []


def test_a_duplicate_row_id_is_an_error():
    rows = [ROW_X, ROW_OPEN, ROW_3, ROW_3.replace("`[ ]`", "`[x]`")]
    assert any("id used by 2 rows" in m for m in _msgs(pl.check_row_shape(_plan(rows=rows)),
                                                       "shape"))


def test_a_row_plan_status_cannot_read_is_an_error():
    rows = [ROW_X, ROW_OPEN.replace("**Fix the gadget.**", "Fix the gadget."), ROW_3]
    assert any("plan_status does not read" in m
               for m in _msgs(pl.check_row_shape(_plan(rows=rows)), "shape"))


# 2. index coverage --------------------------------------------------------

def test_a_row_in_no_index_line_is_an_error():
    index = [INDEX[0], "| *(no bucket)* |  |"]
    msgs = _msgs(pl.check_index_coverage(_plan(index=index)), "index", pl.ERROR)
    assert msgs == ["P1.3: in no bucket line and not in the *(no bucket)* line"]


def test_a_row_named_in_two_lines_is_an_error():
    index = [INDEX[0], "| *(no bucket)* | P1.3 (the sprocket), P1.2 (again) |"]
    msgs = _msgs(pl.check_index_coverage(_plan(index=index)), "index", pl.ERROR)
    assert msgs == ["P1.2: named in 2 index lines (B1, *(no bucket)*)"]


def test_a_mention_inside_a_parenthetical_does_not_name_a_row():
    # P1.3 is only mentioned; that is a warning, not coverage and not an error
    index = [INDEX[0], "| *(no bucket)* | P1.1 (see P1.3) |"]
    f = pl.check_index_coverage(_plan(index=index))
    assert any(m.startswith("P1.1: named in 2") for m in _msgs(f, "index", pl.ERROR))
    assert any(m.startswith("P1.3: not named") for m in _msgs(f, "index", pl.WARNING))


def test_a_bucket_parenthetical_naming_another_row_warns_about_closure():
    index = ["| B1 Widgets | P1.1 (the widget; P1.2 folded in) **done** |",
             "| *(no bucket)* | P1.3 (the sprocket), P1.2 (the gadget) |"]
    msgs = _msgs(pl.check_index_coverage(_plan(index=index)), "index", pl.WARNING)
    assert any("closure dependency of B1" in m for m in msgs)


def test_an_index_name_that_is_no_row_is_an_error():
    index = [INDEX[0], "| *(no bucket)* | P1.3 (the sprocket), P9.9 (nothing) |"]
    assert "P9.9: named in the index but no such row" in _msgs(
        pl.check_index_coverage(_plan(index=index)), "index")


# 3. done marks ------------------------------------------------------------

def test_a_ticked_row_without_a_done_mark_is_an_error():
    index = ["| B1 Widgets | P1.1 (the widget), P1.2 (the gadget) |", INDEX[1]]
    assert _msgs(pl.check_done_marks(_plan(index=index)), "done") == [
        "B1: P1.1 is ticked but carries no **done**"]


def test_an_open_row_with_a_done_mark_is_an_error():
    index = ["| B1 Widgets | P1.1 (the widget) **done**, P1.2 (the gadget) **done** |",
             INDEX[1]]
    assert _msgs(pl.check_done_marks(_plan(index=index)), "done") == [
        "B1: P1.2 carries **done** but is open"]


def test_a_bare_entry_is_checked_too():
    index = ["| B1 Widgets | P1.1, P1.2 (the gadget) |", INDEX[1]]
    assert len(pl.check_done_marks(_plan(index=index))) == 1


def test_the_none_convention_flags_every_mark():
    assert len(pl.check_done_marks(_plan(), convention="none")) == 1


# 4. dependencies -----------------------------------------------------------

def test_a_ticked_row_on_an_open_row_warns_unless_the_clause_says_why():
    rows = [ROW_X, ROW_OPEN, ROW_3.replace("`[ ]`", "`[x]`").replace(
        "**Depends on:** —", "**Depends on:** P1.2")]
    plan = _plan(rows=rows).replace("P1.3 (the sprocket)", "P1.3 (the sprocket) **done**")
    msgs = _msgs(pl.check_dependencies(plan), "depends", pl.WARNING)
    assert msgs and msgs[0].startswith("P1.3 is ticked but depends on P1.2 (open)")
    ahead = plan.replace("**Depends on:** P1.2",
                         "**Depends on:** P1.2 (ticked ahead of P1.2: user decision)")
    assert pl.check_dependencies(ahead) == []


def test_an_unknown_dependency_is_an_error():
    rows = [ROW_X, ROW_OPEN.replace("**Depends on:** P1.1", "**Depends on:** P7.7"), ROW_3]
    assert _msgs(pl.check_dependencies(_plan(rows=rows)), "depends", pl.ERROR) == [
        "P1.2: depends on P7.7, which is no row"]


def test_ranges_wildcards_bold_ids_and_related_are_read():
    ids = ["P1.1", "P1.2", "P1.3", "P2.1"]
    assert pl.dependency_ids("P1.1–P1.3", ids) == (["P1.1", "P1.2", "P1.3"], [])
    assert pl.dependency_ids("P1.*", ids) == (["P1.1", "P1.2", "P1.3"], [])
    line = ("| `[ ]` | **P2.1** | **T.** **Depends on:** P1.1, **P1.2** (added) "
            "**Note.** P1.3 |")
    assert pl.depends_clauses(line) == [" P1.1, P1.2 (added) "]
    line = "| `[ ]` | **P2.1** | **T.** **Depends on:** —. Related: P1.3 |"
    assert pl.dependency_ids(pl.depends_clauses(line)[0], ids) == ([], [])


# 5. the top order line's counts ------------------------------------------------

def test_stale_counts_on_the_top_order_line_warn():
    order = ("**Recommended order as at 2026-01-02 (end of Session 2):** "
             "2 of 3 rows, 1 of 1 buckets.")
    msgs = _msgs(pl.check_order_counts(_plan(order=order)), "order", pl.WARNING)
    assert msgs == [
        "top line (**Recommended order as at 2026-01-02 (end of Session 2):) says 2 of 3 "
        "rows; plan_status says 1 of 3",
        "top line (**Recommended order as at 2026-01-02 (end of Session 2):) says 1 of 1 "
        "buckets; plan_status says 0 of 1"]


def test_only_the_top_order_line_is_read():
    older = ("\n\n**Recommended order as at 2025-12-01 (end of Session 0):** "
             "0 of 2 rows, 0 of 1 buckets.")
    plan = _plan().replace("0 of 1 buckets.", "0 of 1 buckets." + older, 1)
    assert pl.check_order_counts(plan) == []


# 6. ** parity -----------------------------------------------------------------

def test_an_odd_bold_count_on_a_row_is_an_error():
    rows = [ROW_X, ROW_OPEN.replace("Body.", "**Body."), ROW_3]
    assert _msgs(pl.check_bold_parity(_plan(rows=rows)), "bold") == [
        "P1.2 (line 12): 7 `**`, odd"]


def test_an_odd_bold_count_in_a_paragraph_is_an_error_and_a_wrapped_pair_is_not():
    assert pl.check_bold_parity(_plan(extra="**Bold that\nwraps.** Fine.")) == []
    msgs = _msgs(pl.check_bold_parity(_plan(extra="**Unclosed\nbold.")), "bold")
    assert len(msgs) == 1 and msgs[0].startswith("paragraph at lines")


def test_the_known_odd_literal_is_excused_on_its_own_row_only():
    lit = pl.ODD_LITERALS["P0.2"]
    row02 = f"| `[x]` | **P0.2** | **Freeze it.** Uses {lit}. **Depends on:** — |"
    assert pl.check_bold_parity(_plan(rows=[row02, ROW_X, ROW_OPEN, ROW_3])) == []
    elsewhere = ROW_OPEN.replace("Body.", f"Body {lit}.")
    assert len(pl.check_bold_parity(_plan(rows=[ROW_X, elsewhere, ROW_3]))) == 1


# 7. encoding ------------------------------------------------------------------

def test_a_cp1252_byte_is_an_error_naming_its_line():
    # cp1252 cannot encode the plan's arrow ("?"), and writes the dash as 0x97
    raw = _plan().replace("Take P1.2 next.", "Take P1.2 next — now.").encode(
        "cp1252", errors="replace")
    msgs = _msgs(pl.check_encoding(raw), "encoding", pl.ERROR)
    assert msgs == [f"not UTF-8: byte 0x97 at offset {raw.index(bytes([0x97]))} (line 3)"]


def test_mixed_line_endings_warn_and_crlf_throughout_does_not():
    crlf = _plan().replace("\n", "\r\n").encode("utf-8")
    assert pl.check_encoding(crlf) == []
    mixed = crlf.replace(b"\r\n", b"\n", 1)
    assert _msgs(pl.check_encoding(mixed), "encoding", pl.WARNING)


# the command ------------------------------------------------------------------

def test_the_command_exits_1_on_an_error_and_0_on_warnings_only(tmp_path, capsys):
    p = tmp_path / "plan.md"
    p.write_bytes(_plan(index=[INDEX[0], "| *(no bucket)* |  |"]).encode("utf-8"))
    assert pl.main(["--plan", str(p)]) == 1
    assert pl.main(["--plan", str(p), "--only", "done,depends"]) == 0
    order = "**Recommended order as at 2026-01-02 (end of Session 2):** 2 of 3 rows."
    p.write_bytes(_plan(order=order).encode("utf-8"))
    assert pl.main(["--plan", str(p)]) == 0
    assert "WARNING [order]" in capsys.readouterr().out
