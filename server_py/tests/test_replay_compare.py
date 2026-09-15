"""Tests for `replay_report compare` — the wave-over-wave instrument (P1.5).

`compare` is how every re-baseline from P1.5 onward reads: a directory of runs
on the old code against a directory on the new. It computes **no metric of its
own** — every number is summed straight out of `analyse_run`, which
`test_replay_tooling.py` already pins — so what needs guarding here is not the
arithmetic but the *denominator*.

The trap these tests exist for
------------------------------
The Wave 0 baseline holds **65** run files: an n=1 pass over 41 sessions, plus
24 targeted repetitions on the 12 sessions a single draw did not settle
(Invariant 4). A Wave 1 sweep holds **41**. Comparing the two directories whole
measures the 24 extra repetitions as if they were a regression — over the real
Wave 0 data that inflates every "before" figure by roughly half (2,354 searches
against 1,531; 180 bad links against 88). BASELINE.md's published totals are the
rep-1 pass, so rep 1 is the like-for-like scope and `compare` defaults to it.

`--all-reps` is kept for deliberate whole-corpus reads, and says in its own help
text that the denominators will differ.
"""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import replay_report as rr  # noqa: E402

# The run/tool builders are reused rather than copied: they are already pinned
# by test_replay_tooling, and a second copy would drift from the shape
# `analyse_run` actually consumes.
from test_replay_tooling import _run, _tool  # noqa: E402


def _wiped_run(session_id, rep, n_searches):
    """A run whose every search is emptied by the filters — the B2 shape."""
    import json

    doc = _run(tools=[
        _tool(
            "search_legislation",
            args={"query": f"q{i}"},
            final_result=json.dumps({"results": [], "total": 0}),
            api_response={"results": [{"id": j} for j in range(20)], "total": 97},
        )
        for i in range(n_searches)
    ])
    doc["session_id"] = session_id
    doc["rep"] = rep
    return doc


def _write(tmp_path, name, docs):
    import json

    d = tmp_path / name
    d.mkdir()
    for doc in docs:
        (d / f"{doc['session_id']}_rep{doc['rep']}.json").write_text(
            json.dumps(doc), encoding="utf-8"
        )
    return d


def _capture(capsys, before, after, all_reps=False):
    argv = ["compare", "--before", str(before), "--after", str(after)]
    if all_reps:
        argv.append("--all-reps")
    assert rr.main(argv) == 0
    return capsys.readouterr().out


def _metric(out, label):
    """(before, after, change) for one metric row, parsed not substring-matched.

    A loose `"2" in line` assertion would pass on almost any output, which is the
    failure mode this whole instrument exists to avoid."""
    line = next(l for l in out.splitlines() if l.startswith(label))
    rest = line[len(label):]
    change = rest.split("<-")[0].strip().split("   ")[-1].strip()
    nums = rest.split("<-")[0].split()
    return int(nums[0]), int(nums[1]), change


# --- the denominator ---------------------------------------------------------


def test_extra_repetitions_in_the_before_dir_are_excluded_by_default(tmp_path, capsys):
    """The Wave 0 shape: 1 session at n=3 on the before side, n=1 on the after.

    Counting all three reps would report 6 wiped searches against 2 and make a
    fix that removed a third of them look like it removed none.
    """
    before = _write(tmp_path, "before", [
        _wiped_run("6354", 1, 2),
        _wiped_run("6354", 2, 2),
        _wiped_run("6354", 3, 2),
    ])
    after = _write(tmp_path, "after", [_wiped_run("6354", 1, 2)])

    out = _capture(capsys, before, after)

    assert "rep 1 only (like for like)" in out
    assert "1 vs 1 run(s)" in out
    # 2 wiped before, 2 after — no change, which is the truth. Counting all
    # three reps would have said 6 -> 2 and invented a 67% improvement.
    before_n, after_n, change = _metric(out, "  filters removed EVERYTHING")
    assert (before_n, after_n, change) == (2, 2, "=")


def test_all_reps_counts_every_run_and_is_opt_in(tmp_path, capsys):
    before = _write(tmp_path, "before", [
        _wiped_run("6354", 1, 2),
        _wiped_run("6354", 2, 2),
        _wiped_run("6354", 3, 2),
    ])
    after = _write(tmp_path, "after", [_wiped_run("6354", 1, 2)])

    out = _capture(capsys, before, after, all_reps=True)

    assert "ALL reps" in out
    assert "3 vs 1 run(s)" in out


# --- the comparison itself ---------------------------------------------------


def test_a_directory_compared_with_itself_reports_no_change(tmp_path, capsys):
    """The strongest self-check available: same data both sides, every delta '='.

    Run against the real Wave 0 directory this also reproduces BASELINE.md's
    published totals exactly (1531 searches, 351 wiped, 88/376 links).
    """
    docs = [_wiped_run("6354", 1, 2), _wiped_run("6382", 1, 3)]
    d1 = _write(tmp_path, "d1", docs)
    d2 = _write(tmp_path, "d2", docs)

    out = _capture(capsys, d1, d2)

    body = out.split("--- per session")[0]
    metric_lines = [
        l for l in body.splitlines()
        if l.strip() and l[0] != "-" and ("=" in l or "<-" in l)
    ]
    assert metric_lines, "expected metric rows"
    for line in metric_lines:
        change = line.split("   ")[-1].split("<-")[0].strip()
        assert change in ("=", ""), f"unchanged data reported a delta: {line!r}"


def test_a_fix_that_empties_no_searches_shows_as_a_fall_to_zero(tmp_path, capsys):
    """P1.1's expected signature: 5 wiped searches before, 0 after."""
    import json

    before = _write(tmp_path, "before", [_wiped_run("6354", 1, 5)])
    clean = _run(tools=[_tool(
        "search_legislation",
        args={"query": "q"},
        final_result=json.dumps({"results": [{"id": i} for i in range(5)], "total": 97}),
        api_response={"results": [{"id": i} for i in range(20)], "total": 97},
    )])
    clean["session_id"], clean["rep"] = "6354", 1
    after = _write(tmp_path, "after", [clean])

    out = _capture(capsys, before, after)

    before_n, after_n, change = _metric(out, "  filters removed EVERYTHING")
    assert (before_n, after_n) == (5, 0)
    assert change == "-5 (-100%)"


def test_sessions_present_on_only_one_side_are_called_out(tmp_path, capsys):
    """A sweep that skipped a session must not silently shrink the denominator."""
    before = _write(tmp_path, "before", [
        _wiped_run("6354", 1, 2), _wiped_run("6382", 1, 2),
    ])
    after = _write(tmp_path, "after", [_wiped_run("6354", 1, 2)])

    out = _capture(capsys, before, after)

    assert "only in BEFORE: 6382" in out
    assert "1 session(s) in common" in out


def test_a_run_on_the_wrong_model_is_flagged_on_the_after_side(tmp_path, capsys):
    """A replay on an unpinned model measures a different system (CLAUDE.md
    records model choice as the dominant variable), so it must never be read as
    a result."""
    after_doc = _wiped_run("6354", 1, 2)
    after_doc["model_mismatch"] = ["moonshotai/kimi-k3"]
    before = _write(tmp_path, "before", [_wiped_run("6354", 1, 2)])
    after = _write(tmp_path, "after", [after_doc])

    out = _capture(capsys, before, after)

    assert "model other than the pin" in out
    assert "moonshotai/kimi-k3" in out


def test_per_session_rows_show_both_sides_so_a_headline_cannot_hide_a_swap(
    tmp_path, capsys
):
    """P1.5's instruction: read session by session. A bucket total that falls
    while one session gets worse must still show that session getting worse."""
    before = _write(tmp_path, "before", [
        _wiped_run("6354", 1, 10), _wiped_run("6382", 1, 1),
    ])
    after = _write(tmp_path, "after", [
        _wiped_run("6354", 1, 1), _wiped_run("6382", 1, 6),
    ])

    out = _capture(capsys, before, after)

    per = out.split("--- per session (before -> after) ---")[1]
    assert "10/10->1/1" in per
    assert "1/1->6/6" in per


# --- the title-year false positive (found mid-P1.5, 2026-09-15) ---------------
#
# `PROVISION_LABEL` matches "regulations" + digits, so the NAME of every SI ever
# cited read as a provision reference: "The X Regulations 2013" became
# "regulation 2013" and the checker demanded `/regulation/2013`. Over the Wave 0
# baseline that was 73 of the 88 links the report called wrong — it inflated B14
# roughly six-fold, and flagged links that were correct.


def _answer_run(answer):
    doc = _run(answer=answer)
    doc["session_id"], doc["rep"] = "6340", 1
    return doc


def test_an_si_cited_by_title_is_not_a_provision_reference():
    """The exact false positive: a correct Act-level link to a named SI."""
    doc = _answer_run(
        "See [The Grant-Aided Secondary Schools (Scotland) Grant Amendment "
        "Regulations 1979 - SI 1979/766]"
        "(http://www.legislation.gov.uk/id/uksi/1979/766)."
    )
    assert rr.analyse_run(doc).bad_links == []


def test_a_correct_provision_link_is_not_flagged_because_of_its_title_year():
    """`/regulation/2` is right; the label's "Regulations 2020" must not demand
    `/regulation/2020`. This shape was counted as a defect 73 times."""
    doc = _answer_run(
        "[The Health Protection (Coronavirus) Regulations 2020, regulation 2]"
        "(http://www.legislation.gov.uk/id/uksi/2020/791/regulation/2)"
    )
    assert rr.analyse_run(doc).bad_links == []


def test_the_real_provision_is_still_checked_when_a_title_year_precedes_it():
    """Title first, provision second — the checker must walk past the title and
    still catch a link that misses its provision."""
    doc = _answer_run(
        "[The Sale of Tobacco Regulations 2013, regulation 2]"
        "(http://www.legislation.gov.uk/id/ssi/2013/85)"
    )
    bad = rr.analyse_run(doc).bad_links
    assert len(bad) == 1
    assert bad[0].expected_segment == "/regulation/2"


def test_a_genuine_bad_provision_link_is_still_caught():
    """The defect P1.4 fixes: a section-labelled link to the contents page."""
    doc = _answer_run(
        "[section 117 of the Education (Scotland) Act 1962]"
        "(http://www.legislation.gov.uk/id/ukpga/1962/47)"
    )
    bad = rr.analyse_run(doc).bad_links
    assert len(bad) == 1
    assert bad[0].expected_segment == "/section/117"


def test_year_like_numbers_are_recognised_and_ordinary_ones_are_not():
    assert rr._is_title_year("1979") is True
    assert rr._is_title_year("2020") is True
    assert rr._is_title_year("117") is False   # the largest section in the corpus
    assert rr._is_title_year("2") is False
    assert rr._is_title_year("12A") is False   # provision numbers carry suffixes


def test_totals_ignore_sessions_missing_from_one_side(tmp_path, capsys):
    """A sweep that skipped a session must not make every metric look better.

    Before this, totals were summed over each directory whole, so a missing
    "after" session removed its wiped searches from the after-column and read as
    an improvement of exactly that size."""
    before = _write(tmp_path, "before", [
        _wiped_run("6354", 1, 5), _wiped_run("6382", 1, 5),
    ])
    # 6382 never ran on the after side.
    after = _write(tmp_path, "after", [_wiped_run("6354", 1, 5)])

    out = _capture(capsys, before, after)

    assert "only in BEFORE: 6382" in out
    # 5 -> 5 over the one common session, NOT 10 -> 5.
    before_n, after_n, change = _metric(out, "  filters removed EVERYTHING")
    assert (before_n, after_n, change) == (5, 5, "=")


# --- the halt detector (widened 2026-09-15, P1.5) -----------------------------
#
# The original HALT_PARAPHRASE caught 9 of the 14 real disclosures in the Wave 0
# baseline. That is the dangerous direction for P2.1, whose acceptance asserts
# the ABSENCE of halt language: a blind detector marks the row green while the
# halt still reaches the lawyer. These are the verbatim strings it missed.


import pytest  # noqa: E402


@pytest.mark.parametrize("text", [
    "The research agent was unable to complete the search for this query as it "
    "exceeded its processing limits (timed out).",
    'The research agent timed out while searching for further definitions of "shop".',
    "The research agent timed out while attempting to find the correct provision.",
    "The research agent was unable to complete this request as the search exceeded "
    "the maximum permitted steps.",
    "Research Step 2 (examining the controlled drug status) was halted by the system "
    "prior to completion.",
    "A broader search for statutory definitions was halted due to system limitations.",
    "the agent exceeded its operational limits (timed out)",
    "[Research halted: exceeded 20 tool-call steps]",
    "the research process was halted prior to completion",
])
def test_real_halt_disclosures_are_detected(text):
    assert rr.HALT_PARAPHRASE.search(text), f"missed a real halt disclosure: {text!r}"


@pytest.mark.parametrize("text", [
    # Ordinary legal prose that must not read as a halt.
    "The time limit for appeal under section 20 is 21 days from the decision.",
    "The Act imposes a statutory limit on the number of directors.",
    "Section 5 sets out the maximum penalty of level 3 on the standard scale.",
    "The limit of liability is prescribed by regulation 4.",
    "The council halted the development under a stop notice.",
    "The search returned no results for the Victims and Witnesses (Scotland) Act 2014.",
])
def test_ordinary_legal_prose_is_not_read_as_a_halt(text):
    assert not rr.HALT_PARAPHRASE.search(text), f"false positive on: {text!r}"


def test_a_halt_the_answer_never_mentions_is_counted_separately():
    """The case the plan does not name: the worker halted, the answer is a normal
    report, and the lawyer is given no signal that it is incomplete. Invariant 1
    requires a disclosure to be TRUE; no disclosure at all is worse."""
    doc = _run(
        answer="The Act applies throughout Scotland and section 3 sets out the duty. " * 6,
        report="[Research halted: exceeded 20 tool-call steps]",
    )
    sig = rr.analyse_run(doc)
    assert sig.halt_in_worker_report == 1
    assert sig.halt_language_in_answer == 0
    assert sig.halts_undisclosed == 1


def test_a_disclosed_halt_is_not_counted_as_undisclosed():
    doc = _run(
        answer="The research process was halted prior to completion, so no findings "
               "are available for that step.",
        report="[Research halted: exceeded 20 tool-call steps]",
    )
    sig = rr.analyse_run(doc)
    assert sig.halt_language_in_answer == 1
    assert sig.halts_undisclosed == 0


def test_an_empty_answer_after_a_halt_is_b13_not_an_undisclosed_halt():
    """An empty body has no room for a disclosure. It is B13/P4.2, a different
    defect with a different fix, and double-booking it here would inflate both."""
    doc = _run(answer="", report="[Research halted: exceeded 20 tool-call steps]", cost=0.4)
    sig = rr.analyse_run(doc)
    assert sig.halts_undisclosed == 0
    assert sig.turns_billed_but_empty == 1
