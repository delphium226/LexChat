"""P4.14's instrument: `python -m tools.footer_echo`. Synthetic text only."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.citation_links import PROVISION_FOOTNOTE  # noqa: E402
from src.utils.search_scope import answer_scope_footer  # noqa: E402
from tools import footer_echo  # noqa: E402


def _leg(q):
    return [{"tool": "search_legislation", "query": q, "legislation_id": "",
             "shown": 5, "matched": 141}]


ECHO = answer_scope_footer(_leg("an earlier widget search"), {})
FRESH = answer_scope_footer(_leg("widget definition"), {})
PROSE = "The Widget Order 1901 defines a widget."
# What the seam stored before P4.14: echo, then P1.6's note, then the real line.
RECORDED = PROSE + ECHO + "\n\n" + PROVISION_FOOTNOTE + FRESH


def test_the_recorded_shape_loses_the_echo_only():
    before = footer_echo.rebuild(RECORDED, p414=False)
    after = footer_echo.rebuild(RECORDED, p414=True)
    assert before.count("*Search scope:") == 2
    assert after == PROSE + "\n\n" + PROVISION_FOOTNOTE + FRESH


def test_an_answer_the_seam_already_handled_is_the_same_both_sides():
    for answer in (PROSE + FRESH, PROSE + "\n\n" + PROVISION_FOOTNOTE + FRESH,
                   PROSE + ECHO + FRESH,
                   # Prose after an echo is answer text, on either side.
                   PROSE + ECHO + "\n\nA later paragraph." + FRESH, PROSE):
        assert footer_echo.rebuild(answer, True) == footer_echo.rebuild(answer, False)


def test_the_command_lists_the_changed_answer(tmp_path, capsys):
    d = tmp_path / "wave9"
    d.mkdir()
    (d / "9999_rep1.json").write_text(json.dumps({
        "session_id": "9999", "rep": 1, "turns": [
            {"chat_mode": "conversational", "answer": RECORDED},
            {"chat_mode": "conversational", "answer": PROSE + FRESH},
        ]}), encoding="utf-8")
    assert footer_echo.main(["--dir", str(d)]) == 0
    out = capsys.readouterr().out
    assert "before P4.14: 1" in out
    assert "after P4.14:  0" in out
    assert "answers P4.14 changes: 1" in out
    assert "9999 r1 t1" in out
