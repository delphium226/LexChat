"""Unit tests for the `<suggestions>` block parser (utils/suggestions.py) and
the prompt wiring that produces and suppresses the block."""

import pytest

from src.prompts import CONSULTED_PEER_BLOCK, get_manager_system_prompt
from src.utils.suggestions import MAX_SUGGESTIONS, extract_suggestions


def test_no_block_returns_content_unchanged():
    content = "Section 33 creates the offence.\n\nWhat would you like next?"
    assert extract_suggestions(content) == (content, [])


def test_empty_content():
    assert extract_suggestions("") == ("", [])
    assert extract_suggestions(None) == ("", [])


def test_well_formed_block():
    content = (
        "Section 33 creates the offence.\n\n"
        "<suggestions>\n"
        "What penalties apply under section 33?\n"
        "Has section 33 been considered in case law?\n"
        "</suggestions>"
    )
    clean, items = extract_suggestions(content)
    assert clean == "Section 33 creates the offence."
    assert items == [
        "What penalties apply under section 33?",
        "Has section 33 been considered in case law?",
    ]


def test_bulleted_and_numbered_lines_are_stripped():
    content = (
        "Answer.\n<suggestions>\n"
        "- What penalties apply?\n"
        "* Which court decided it?\n"
        "1. Is it still in force?\n"
        "2) Does it extend to Scotland?\n"
        "</suggestions>"
    )
    _, items = extract_suggestions(content)
    assert items == [
        "What penalties apply?",
        "Which court decided it?",
        "Is it still in force?",
        "Does it extend to Scotland?",
    ]


def test_surrounding_quotes_are_stripped():
    content = '<suggestions>\n"What penalties apply?"\n</suggestions>'
    _, items = extract_suggestions(content)
    assert items == ["What penalties apply?"]


def test_duplicate_lines_deduped_case_insensitively():
    content = (
        "Answer.\n<suggestions>\n"
        "What penalties apply?\n"
        "what PENALTIES apply?\n"
        "Is it in force?\n"
        "</suggestions>"
    )
    _, items = extract_suggestions(content)
    assert items == ["What penalties apply?", "Is it in force?"]


def test_more_than_four_items_capped():
    lines = "\n".join(f"Question number {i}?" for i in range(1, 8))
    clean, items = extract_suggestions(f"Answer.\n<suggestions>\n{lines}\n</suggestions>")
    assert clean == "Answer."
    assert len(items) == MAX_SUGGESTIONS
    assert items[0] == "Question number 1?"


def test_over_long_item_is_dropped_not_truncated():
    long_line = "Why " + ("x" * 200) + "?"
    content = f"Answer.\n<suggestions>\n{long_line}\nShort one?\n</suggestions>"
    _, items = extract_suggestions(content)
    assert items == ["Short one?"]


def test_unterminated_tag_is_stripped_and_parsed():
    content = "Answer body.\n\n<suggestions>\nWhat penalties apply?\nIs it in force?"
    clean, items = extract_suggestions(content)
    assert clean == "Answer body."
    assert items == ["What penalties apply?", "Is it in force?"]


def test_unterminated_tag_alone_leaves_clean_content():
    clean, items = extract_suggestions("Answer body.\n\n<suggestions>")
    assert clean == "Answer body."
    assert items == []


def test_tag_echoed_twice_last_block_wins():
    content = (
        "Here is what I would suggest:\n"
        "<suggestions>\nStale question?\n</suggestions>\n\n"
        "The real answer.\n\n"
        "<suggestions>\nFresh question?\n</suggestions>"
    )
    clean, items = extract_suggestions(content)
    assert items == ["Fresh question?"]
    # Only the last block is removed; the earlier echo is left in the prose,
    # which is a prompt-quality issue rather than something to guess at here.
    assert clean.endswith("The real answer.")


def test_empty_block_yields_no_items_but_strips_markup():
    clean, items = extract_suggestions("Answer.\n<suggestions>\n\n</suggestions>")
    assert clean == "Answer."
    assert items == []


def test_case_insensitive_tag():
    clean, items = extract_suggestions("Answer.\n<SUGGESTIONS>\nWhat next?\n</Suggestions>")
    assert clean == "Answer."
    assert items == ["What next?"]


# ---------------------------------------------------------------------------
# Prompt wiring
# ---------------------------------------------------------------------------

# Every branch of get_manager_system_prompt's dispatch, so a new bot type or a
# refactor to a single return cannot silently lose either half of the wiring.
_MANAGER_PROMPT_CASES = [
    ("legislation_only", {}),                                   # research mode
    ("legislation_and_case_law", {}),
    ("legislation_only", {"_chat_mode": "conversational"}),     # conversational
    ("parliamentary_records", {}),                              # early return
    ("westminster_records", {}),                                # early return
]


@pytest.mark.parametrize("mode,cfg", _MANAGER_PROMPT_CASES)
def test_every_manager_prompt_asks_for_a_suggestions_block(mode, cfg):
    prompt = get_manager_system_prompt(mode, cfg or None)
    assert "<suggestions>" in prompt
    assert "</suggestions>" in prompt


@pytest.mark.parametrize("mode,cfg", _MANAGER_PROMPT_CASES)
def test_consulted_block_appended_on_every_return_path(mode, cfg):
    assert CONSULTED_PEER_BLOCK not in get_manager_system_prompt(mode, cfg or None)
    consulted = get_manager_system_prompt(mode, {**cfg, "_consulted": True})
    assert CONSULTED_PEER_BLOCK in consulted
    # It must be last, so it overrides the follow-up instruction above it.
    assert consulted.rstrip().endswith(CONSULTED_PEER_BLOCK)
