"""P3.52: the quick-lookup Worker is told the legislation searches rank by meaning.

Thomas's Q17 (13 October, from 6345): s.38 of the Transport (Scotland) Act 2001
was never found. Probed live (Session 47): the question's own words put s.38 at
rank 3 of the Act's section search and the 2001 Act at rank 3 of the Act-level
search; the Worker's quoted OR queries reached neither (0 of 5 Act-level queries
from today's code returned the Act, 4 of 4 written under this line did). Seam:
its first query was a quoted OR list in 6 of 6 draws before the line, a plain
sentence in 6 of 6 after.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.prompts import (  # noqa: E402
    WORKER_SYSTEM_PROMPT_CONVERSATIONAL,
    _LEGISLATION_QUERY_WORDING,
    get_worker_system_prompt,
)


def test_the_quick_lookup_worker_carries_the_line():
    built = get_worker_system_prompt("legislation_only", {"_chat_mode": "conversational"})
    assert _LEGISLATION_QUERY_WORDING in WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    assert _LEGISLATION_QUERY_WORDING in built
    # In Phase 1, where the first search is written.
    assert built.index("PHASE 1 — DISCOVER") < built.index(_LEGISLATION_QUERY_WORDING) \
        < built.index("PHASE 2 — RETRIEVE")


def test_the_line_says_what_the_probe_found():
    line = _LEGISLATION_QUERY_WORDING
    assert "rank results by meaning, not by matching words" in line
    assert "plain sentence" in line
    assert "not as quoted phrases joined by OR or AND" in line
    assert "Unless you are searching for an Act by its exact title" in line
    assert "a power to make grants on conditions" in line
    assert "say which kind of power each provision you cite is" in line


def test_the_example_is_not_the_question_it_was_built_for():
    """The line must not hand the Worker Q17's answer."""
    lowered = _LEGISLATION_QUERY_WORDING.lower()
    for word in ("bus", "fare", "transport (scotland)", "section 38", "s.38"):
        assert word not in lowered, word
