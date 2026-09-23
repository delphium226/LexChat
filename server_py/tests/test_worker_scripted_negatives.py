"""P4.6 (B5): no Worker prompt scripts a negative about the whole database.

Three research-Worker prompt lines told the model what to say when a search
fell short, and each said it about the corpus: *"The available database does
not contain information on this specific issue."*, *"… before concluding
nothing exists"* and *"No reported case law directly addresses this specific
issue in the National Archives database."* The model said them verbatim. In
the stored sweeps most of them came from a legislation Worker that had been
sent a case-law question and made no search at all, so the claim was about a
tool set, not even about a search. The truth is about the searches made, and
that is what the prompts now script (Thomas's wording, FIX_PLAN P4.6).
"""

import pytest

from src import prompts
from src.prompts import get_worker_system_prompt

OLD_LINES = (
    "The available database does not contain",
    "before concluding nothing exists",
    "No reported case law directly addresses this specific issue",
    # The case-law Worker's PHASE 4 restated the same verdict in its own words.
    "No directly relevant case law was found in the National Archives Find Case Law "
    "database for this query",
    # ...and its STOP RULE gave the model the inference to draw.
    "wasted effort if the database does not contain",
)

WORKER_CONSTANTS = (
    "WORKER_SYSTEM_PROMPT",
    "WORKER_SYSTEM_PROMPT_CASE_LAW",
    "WORKER_SYSTEM_PROMPT_HYBRID",
    "WORKER_SYSTEM_PROMPT_CONVERSATIONAL",
    "PARLIAMENT_WORKER_SYSTEM_PROMPT",
    "WESTMINSTER_WORKER_SYSTEM_PROMPT",
)

MODES = ("legislation_only", "case_law_only", "legislation_and_case_law",
         "parliamentary_records", "westminster_records")
CHAT_MODES = ("research", "conversational", "deep_research")


@pytest.mark.parametrize("name", WORKER_CONSTANTS)
def test_no_worker_constant_scripts_a_corpus_negative(name):
    text = getattr(prompts, name)
    for line in OLD_LINES:
        assert line not in text, f"{name} still carries {line!r}"


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("chat_mode", CHAT_MODES)
def test_no_built_worker_prompt_scripts_a_corpus_negative(mode, chat_mode):
    """What the Worker is actually sent, through the product's builder, in
    every research type and chat mode (a filter block included)."""
    text = get_worker_system_prompt(mode, {"_chat_mode": chat_mode,
                                           "_jurisdiction": "scotland"})
    for line in OLD_LINES:
        assert line not in text, f"{mode}/{chat_mode} still carries {line!r}"


def test_the_legislation_worker_is_scripted_about_the_search():
    text = prompts.WORKER_SYSTEM_PROMPT
    # Thomas's wording, both lines.
    assert "The material retrieved in this search does not establish the answer." in text
    assert "before reporting that these searches found no relevant material" in text
    # The shape the stored sweeps actually produced: a case-law question sent
    # to the legislation Worker, which has no case-law tool.
    assert "Your tools search legislation only" in text
    assert "say that it was not searched in this research, not that it was not found" in text
    # The honest negative survives (Invariant 1): the rule scopes it, it does
    # not forbid it, and the no-training-data rule is kept.
    assert "DO NOT attempt to fill gaps with internal training data." in text


def test_the_case_law_worker_is_scripted_about_the_search():
    text = prompts.WORKER_SYSTEM_PROMPT_CASE_LAW
    assert ("These searches of the National Archives Find Case Law database did not "
            "return a judgment that addresses this issue.") in text
    assert "Never state or imply that no case law exists on the point" in text
    # PHASE 4 points back at the one statement rather than scripting a second.
    assert "say so as YOUR MANDATE sets out" in text
    assert "coverage limitation" in text


def test_the_lines_that_never_carried_the_negative_are_untouched():
    """The hybrid and quick-lookup Workers carried none of the three lines
    (P0.6's check), so this row gives them nothing: a structural change to
    the quick-lookup prompt has cost links before (Session 14)."""
    for name in ("WORKER_SYSTEM_PROMPT_HYBRID", "WORKER_SYSTEM_PROMPT_CONVERSATIONAL"):
        text = getattr(prompts, name)
        assert "The material retrieved in this search" not in text
        assert "Your tools search legislation only" not in text
