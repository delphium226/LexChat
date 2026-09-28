"""P3.2: the `openers` detector — answers that open by agreeing with the lawyer.

The row (B6) proposes removing agreement openers ("You are absolutely
correct"), which announce a resolution before any reason for it is given. This
pins the detector the rate is quoted from: only the answer's first sentence is
read, a sentence agreeing with a stated proposition is kept apart from a bare
concession, and an acknowledgement ("Thank you for providing the full title")
is not an opener. Every sentence here is synthetic.
"""

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_report as rr  # noqa: E402


def test_bare_concessions():
    for s in ("You are absolutely correct, and I apologise for the oversight.",
              "You are correct.",
              "You're absolutely right.",
              "You are entirely correct to challenge that, and I concede.",
              "**You are absolutely correct:** the section says otherwise.",
              "Yes, you are right — the order was revoked."):
        assert rr.opener_kind(s) == "bare", s


def test_scoped_agreement_is_not_bare():
    assert rr.opener_kind("You are correct that the order was revoked in 2020.") == "scoped"
    assert rr.opener_kind("You are entirely correct in your analysis of s.5.") == "scoped"


def test_praise_affirm_apology_thanks():
    assert rr.opener_kind("You make an excellent point regarding interpretation.") == "praise"
    assert rr.opener_kind("You raise a very sharp point.") == "praise"
    assert rr.opener_kind("You have correctly identified a gap in the scheme.") == "praise"
    assert rr.opener_kind("You have hit on a critical technicality.") == "praise"
    assert rr.opener_kind("Yes, exactly.") == "affirm"
    assert rr.opener_kind("That is correct: the Act applies.") == "affirm"
    assert rr.opener_kind("Apologies for that.") == "apology"
    assert rr.opener_kind("I apologise for the error in my previous answer.") == "apology"
    assert rr.opener_kind("Thank you for pressing this point.") == "thanks"


def test_not_openers():
    for s in ("Thank you for providing the full title.",
              "Correctly read, section 5 applies only to Part 2.",
              "Right of appeal lies under section 12.",
              "You are not correct that the order was revoked.",
              "The research confirms that the section applies.",
              "Under section 40, Ministers may make a scheme. You are correct.",
              ""):
        assert rr.opener_kind(s) is None, s


def test_only_the_first_sentence_is_read_and_footer_ignored():
    ans = ("Section 3 applies. You are absolutely correct about that.\n\n"
           "*Search scope: the legislation index was searched for \"x\".*")
    assert rr.first_sentence(ans) == "Section 3 applies."
    assert rr.opener_kind(ans) is None
    assert rr.first_sentence("## You are correct.\nMore text.") == "You are correct."


def _doc(answers, delegations):
    turns = []
    for a, d in zip(answers, delegations):
        turns.append({"answer": a, "chat_mode": "conversational",
                      "audit": None if d is None else {"delegations": [{}] * d}})
    return {"session_id": "9999", "rep": 1, "turns": turns}


def test_opener_rows_skip_blanks_and_count_delegations():
    rows = rr.opener_rows(_doc(["You are correct.", "", "Section 3 applies.",
                                "Yes, exactly."], [0, 1, 2, None]), "d")
    assert [r["turn"] for r in rows] == [1, 3, 4]
    assert [r["kind"] for r in rows] == ["bare", None, "affirm"]
    assert [r["delegations"] for r in rows] == [0, 2, None]


def test_cmd_openers_runs_and_lists_drops(tmp_path, capsys):
    d = tmp_path / "sweep"
    d.mkdir()
    (d / "9999_rep1.json").write_text(json.dumps(_doc(
        ["You are absolutely correct.", "Thank you for providing the full title."],
        [0, 1])), encoding="utf-8")
    rc = rr.main(["--dir", str(d), "openers", "--list", "--drops"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "sweep" in out and "1 of 1" in out
    assert "'You are absolutely correct.'" in out
    assert "Thank you for providing the full title." in out.split("NOT counted")[1]
