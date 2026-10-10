"""P4.22: the answer cleaner strips a block, not a sentence's mention of one.

`strip_scope_blocks` used to delete every bracketed tool-block tag wherever it
stood, so a Worker that wrote "does not contain an `[ENABLING POWER]` block"
reached the lawyer as "does not contain an `` block" (three stored answers).
Code never writes a bare tag; a bare tag inside a sentence now becomes its own
words, and a bare tag used as a label is deleted as before. Synthetic text only.
"""
import pytest

from src.utils.search_scope import strip_scope_blocks

NAMES = ["SEARCH SCOPE", "ENABLING POWER", "CHANGE RECORD", "CURRENCY",
         "PINPOINTS TO KEEP", "SECTION OUTLINE", "PROVISION FETCHED BY CODE"]


def _s(text):
    return strip_scope_blocks(text)[0]


# --- a mention inside a sentence keeps its words ------------------------------

@pytest.mark.parametrize("name", NAMES)
def test_an_inline_mention_becomes_its_words(name):
    out = _s(f"The Widget Order 1901 does not contain an [{name}] block.")
    assert out == f"The Widget Order 1901 does not contain an {name.lower()} block."


@pytest.mark.parametrize("name", NAMES)
def test_a_backticked_inline_mention_loses_its_backticks(name):
    out = _s(f"None of the records contain an `[{name}]` block or preamble.")
    assert out == f"None of the records contain an {name.lower()} block or preamble."
    assert "`" not in out


def test_the_stored_shapes_read_as_sentences():
    cases = {
        "as no [ENABLING POWER] block was retrieved for either instrument.":
            "as no enabling power block was retrieved for either instrument.",
        "if it provides an explicit `[ENABLING POWER]` block quoting the preamble.":
            "if it provides an explicit enabling power block quoting the preamble.",
        "does not include an enabling power recital (an `[ENABLING POWER]` block).":
            "does not include an enabling power recital (an enabling power block).",
    }
    for src, want in cases.items():
        assert _s(src) == want


def test_a_mention_after_an_opening_bracket_or_comma_is_inline():
    assert _s("Nothing was stated ([ENABLING POWER] absent).") == \
        "Nothing was stated (enabling power absent)."
    assert _s("The text, [ENABLING POWER], was read.") == \
        "The text, enabling power, was read."


def test_a_mention_before_closing_punctuation_or_a_line_end_is_inline():
    assert _s("No preamble came with the [ENABLING POWER].") == \
        "No preamble came with the enabling power."
    assert _s("No preamble (none in the [ENABLING POWER]) was read.") == \
        "No preamble (none in the enabling power) was read."
    assert _s("No preamble came with the [ENABLING POWER]") == \
        "No preamble came with the enabling power"
    assert _s("No preamble came with the [ENABLING POWER]\nNext line.") == \
        "No preamble came with the enabling power\nNext line."


def test_a_lower_case_tag_is_matched():
    assert _s("There was no [enabling power] block.") == "There was no enabling power block."


def test_a_mention_is_counted():
    out, n = strip_scope_blocks("There was no [ENABLING POWER] block.")
    assert n == 1 and out == "There was no enabling power block."


# --- a label is deleted, cleanly ---------------------------------------------

def test_a_label_at_line_start_is_deleted_with_its_space():
    out = _s("Intro.\n\n*[ENABLING POWER] Coverage note: the record covers 1999 to 2026.*")
    assert out == "Intro.\n\n*Coverage note: the record covers 1999 to 2026.*"


def test_a_label_after_a_sentence_end_is_deleted():
    assert _s("The record was read. [ENABLING POWER] The preamble is absent.") == \
        "The record was read. The preamble is absent."


def test_a_label_before_a_capital_is_deleted_even_after_a_word():
    assert _s("The record shows [ENABLING POWER] The preamble is absent.") == \
        "The record shows The preamble is absent."


def test_a_backticked_label_leaves_no_empty_code_span():
    out = _s("`[ENABLING POWER]` Coverage note: none.")
    assert out == "Coverage note: none."


def test_a_tag_before_a_link_is_not_turned_into_words():
    out = _s("See [Currency](https://www.legislation.gov.uk/ssi/1901/3) for it.")
    assert "currency(" not in out.lower()


# --- unchanged: blocks, closers, and what the strip never touched ------------

def test_a_code_written_block_is_still_stripped_whole():
    block = ("\n\n[ENABLING POWER — this record does NOT state what ssi/1901/3 was made "
             "under. Say the enabling power could not be verified.]")
    out, n = strip_scope_blocks("The answer." + block)
    assert out == "The answer." and n == 1


def test_a_stray_closer_is_still_stripped():
    out = _s("Some text [/CURRENCY] more text.")
    assert "[/" not in out and "currency" not in out.lower()


def test_a_block_named_in_full_inline_is_still_stripped():
    out = _s("It said [CHANGE RECORD — the record lists 3 changes] and stopped.")
    assert "CHANGE RECORD" not in out and "change record" not in out


def test_schedules_and_annexes_bare_is_left_alone():
    text = "The [SCHEDULES AND ANNEXES] note was read."
    assert _s(text) == text


def test_a_one_sided_backtick_does_not_raise():
    out = _s("There was no `[ENABLING POWER] block.")
    assert "[ENABLING POWER]" not in out
