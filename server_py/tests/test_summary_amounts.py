"""P3.58: a money amount the summariser wrote that its source does not hold.

Measured over every stored summarised result (6,784 distinct, Session 52,
`evidence/seam/s52/p358/`): 7 amounts in 5 summaries the source does not hold
in any form, every one the summariser's ('£151' twice in formulas SSI 2024/173
does not contain, in 2 runs; '£300' from its knowledge of another instrument,
in 3); every other amount the first reader missed was the source's in another
written form. What this file pins:

1. the amounts read;
2. an amount the source holds in ANOTHER written form is held (each form met
   in the stored summaries), and an amount the question holds;
3. what goes: the one-line list item, or the sentence;
4. what stays: a heading, an item with nested lines, a passage carrying a held
   amount or citation, everything else byte for byte;
5. fail-soft and idempotent;
6. the wiring: through `check_summary_citations`, at every return of
   `summarise_for_query` and on a local-cache hit (P3.45's seam).

Fixtures are synthetic (the Widget Regulations, ssi/1901/3).
"""

import asyncio
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import summarisation as summ  # noqa: E402
from src.agent.agent_shared import run_worker_tool  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.services import local_prompt_cache as lpc  # noqa: E402
from src.utils import summary_amounts as sa  # noqa: E402
from src.utils.summary_amounts import AmountIndex, find_amounts, unsourced_amounts  # noqa: E402
from src.utils.summary_citations import strip_unsourced_citations  # noqa: E402


def _src(text: str) -> str:
    """A section search result as the executor returns it (JSON)."""
    return json.dumps({"results": [{"legislation_id": "ssi/1901/3", "text": text}]})


def _amounts(records):
    return [(r["citation"], r["action"]) for r in records if r.get("kind") == "amount"]


# ---------------------------------------------------------------------------
# 1. amounts read
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,pence", [
    ("the grant is £151.", "15100"),
    ("a cap of £1,510.00 a year", "151000"),
    ("a fund of £1.5 million", "150000000"),
    ("up to GBP 40 in total", "4000"),
    ("a fee of 151 pounds", "15100"),
    ("a charge of 50 pence", "50"),
    ("a charge of 50p a mile", "50"),
    ("a fine of three hundred pounds", "30000"),
    ("a levy of fifty pence", "50"),
])
def test_amounts_read(text, pence):
    found = find_amounts(text)
    assert [str(a.pence.normalize()) for a in found] == [str(Decimal(pence).normalize())]


@pytest.mark.parametrize("text", [
    "see s.5p of the Act",          # no amount
    "paragraph 5p.",                 # a page or paragraph reference
    "regulation 151 applies",        # a bare number
    "1.5 per cent",
])
def test_no_amount_is_read_where_none_is_written(text):
    assert find_amounts(text) == []


# ---------------------------------------------------------------------------
# 2. held in another written form
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("summary,source", [
    ("£237.55", "the amount is£237∙55;"),                       # bullet operator point
    ("£3.48", "reduced by £3-48, in the case of a man"),         # hyphen point
    ("£2.9", "and by £2:9 in the case of a woman"),              # colon point
    ("£40,000", "less than EUR 40 000 £40 000 shall be"),         # space thousands
    ("£235.00", "Weekly Rate £ Yearly Rate £ 100235.0012,26290211.50"),   # cells run together
    ("£12,262", "Weekly Rate £ Yearly Rate £ 100235.0012,26290211.50"),
    ("£250", "falls between EUR 100 and EUR 250"),               # another currency
    ("£473.99", "not less than £273.00 but less than £474.00"),  # a penny below
    ("£585", "but less than £586"),                              # a pound below
    ("£1.5 million", "a fund of £1,500,000"),                    # scale written out
    ("£0.50", "a charge of 50 pence"),                           # pence
    ("three hundred pounds", "a fine of three hundred pounds"),  # words
    ("£1,000", "a cap of £1000"),
])
def test_an_amount_the_source_holds_in_another_form_is_held(summary, source):
    assert unsourced_amounts(f"The rate is {summary}.", _src(source)) == []


def test_an_amount_the_source_does_not_hold_is_unheld():
    got = unsourced_amounts("C = £151 per week.", _src("C is the weekly amount in regulation 3."))
    assert [a.text for a in got] == ["£151"]


def test_a_figure_is_not_held_by_a_neighbouring_amount_beyond_a_step():
    # £151 is a pound and a penny from neither £149 nor £153
    assert len(unsourced_amounts("£151", _src("between £149 and £153"))) == 1


def test_a_pound_step_is_only_for_a_whole_pound_amount():
    # £151.50 is a pound from £150.50, but only a whole-pound amount takes that step
    assert len(unsourced_amounts("£151.50", _src("a fee of £150.50"))) == 1
    assert unsourced_amounts("£151.51", _src("a fee of £151.50")) == []


def test_an_amount_the_question_holds_is_held():
    raw = _src("C is the weekly amount in regulation 3.")
    assert unsourced_amounts("C = £151.", raw, "Is the figure of £151 in force?") == []


def test_a_whole_number_amount_is_held_by_its_digits_anywhere():
    """Errs towards held: the figure's digits in the source keep it."""
    idx = AmountIndex(_src("Table 1 (£): 151"))
    assert idx.held(find_amounts("£151")[0])


# ---------------------------------------------------------------------------
# 3. what goes
# ---------------------------------------------------------------------------

RAW = _src("Regulation 2 substitutes a new formula: (A + B - C) x 52 / D, "
           "where D is the number of weeks. The fee is £20.")


def test_a_one_line_item_whose_first_sentence_carries_the_amount_goes():
    summary = ("*   **Regulation 2:** substitutes a new formula.\n"
               "*   *Note:* the 1900 Regulations set the grant at £300, since uprated.\n"
               "*   **Regulation 3:** the fee is £20.")
    out, rec = strip_unsourced_citations(summary, RAW)
    assert out == ("*   **Regulation 2:** substitutes a new formula.\n"
                   "*   **Regulation 3:** the fee is £20.")
    assert _amounts(rec) == [("£300", "item")]


def test_a_quoted_formula_line_goes_and_its_neighbours_stay():
    summary = ("*   **Regulation 2:** substitutes a new formula:\n"
               "    > **A** = the net earnings...\n"
               "    > **C** = **£151**\n"
               "    > **D** = the number of weeks...")
    out, rec = strip_unsourced_citations(summary, RAW)
    assert out == ("*   **Regulation 2:** substitutes a new formula:\n"
                   "    > **A** = the net earnings...\n"
                   "    > **D** = the number of weeks...")
    assert _amounts(rec) == [("£151", "sentence")]


def test_in_prose_the_sentence_goes():
    summary = "Regulation 2 substitutes a new formula. It divides by £151 each week. D is weeks."
    out, rec = strip_unsourced_citations(summary, RAW)
    assert out == "Regulation 2 substitutes a new formula. D is weeks."
    assert _amounts(rec) == [("£151", "sentence")]


def test_an_amount_in_a_later_sentence_of_an_item_takes_that_sentence_only():
    summary = "*   **Regulation 2:** substitutes a new formula. It divides by £151."
    out, _ = strip_unsourced_citations(summary, RAW)
    assert out == "*   **Regulation 2:** substitutes a new formula."


# ---------------------------------------------------------------------------
# 4. what stays
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("summary", [
    "### Grants of £151",                                          # a heading
    "**The £151 grant**",                                          # a bold label line
    "*   Grant of £151:\n    *   Regulation 2 substitutes a new formula.",   # nested lines
    "*   Regulation 2 sets £151 against the fee of £20.",           # a held amount beside it
    "Regulation 2 sets £151 as in Widget Co v Gadget Ltd [1901] UKSC 3.",   # a held citation
])
def test_a_passage_it_must_not_take_stays(summary):
    raw = _src("Regulation 2 substitutes a formula. The fee is £20. "
               "Widget Co v Gadget Ltd [1901] UKSC 3.")
    out, rec = strip_unsourced_citations(summary, raw)
    assert out == summary and _amounts(rec) == []


def test_a_summary_whose_amounts_are_all_held_is_unchanged_byte_for_byte():
    summary = "*  The fee is **£20** ;  \n\n\nnothing else  \n"
    assert strip_unsourced_citations(summary, RAW) == (summary, [])


# ---------------------------------------------------------------------------
# 5. fail-soft and idempotent
# ---------------------------------------------------------------------------

def test_the_amount_check_is_idempotent():
    summary = "Regulation 2 substitutes a new formula. It divides by £151 each week.\n*   £300 grant."
    once, _ = strip_unsourced_citations(summary, RAW)
    assert strip_unsourced_citations(once, RAW) == (once, [])


def test_an_error_in_the_amount_reader_removes_nothing(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(sa, "find_amounts", boom)
    summary = "It divides by £151 each week."
    assert unsourced_amounts(summary, RAW) == []
    assert strip_unsourced_citations(summary, RAW) == (summary, [])


# ---------------------------------------------------------------------------
# 6. the wiring
# ---------------------------------------------------------------------------

HELD = "Regulation 2 substitutes a new formula."
INVENTED = "*   *Note:* the grant is set at £300 elsewhere."


def _chunk_returning(text):
    async def chunk_fn(t, q, m, timing_collector=None):
        return text
    return chunk_fn


def test_a_fresh_summary_loses_an_invented_amount():
    out, degraded = asyncio.run(summ.summarise_for_query(
        RAW, "formula", "m", chunk_fn=_chunk_returning(HELD + "\n" + INVENTED)))
    assert out == HELD and degraded is False


def test_a_consolidated_summary_is_checked(monkeypatch):
    monkeypatch.setattr(summ, "SUMMARISE_CHUNK_CHARS", 40)
    text = "Regulation 2 substitutes a new formula. " + "y" * 60

    async def chunk_fn(t, q, m, timing_collector=None):
        return HELD + " It divides by £151."
    out, _ = asyncio.run(summ.summarise_for_query(text, "q", "m", chunk_fn=chunk_fn))
    assert "£151" not in out and out.startswith(HELD)


def test_the_wrapper_counts_amounts_apart(caplog):
    with caplog.at_level(logging.INFO, logger="agent"):
        out = summ.check_summary_citations(HELD + "\n" + INVENTED, RAW, "q")
    assert out == HELD
    assert "and 0 case name(s) and 1 amount(s)" in caplog.text
    assert "removed 0 case citation(s)" in caplog.text


@pytest.fixture
def _worker_config():
    set_request_provider_config({
        "_research_mode": "legislation_only",
        "_tool_memo_enabled": False,
        "_local_prompt_cache_enabled": False,
    })
    yield
    set_request_provider_config({})


async def _noop_chunk(*a, **k):
    return None


def _run_tool(raw, cache_on, chunk_fn=_noop_chunk):
    with patch("src.agent.agent_shared.execute_worker_tool",
               new=AsyncMock(return_value=raw)), \
         patch("src.agent.agent_shared.get_request_provider_config",
               return_value={"_research_mode": "legislation_only",
                             "_local_prompt_cache_enabled": cache_on}), \
         patch("src.agent.provider_factory.get_summarise_threshold", return_value=120):
        # RAW (about 190 characters) is summarised; the summary (87) is not cut
        return asyncio.run(run_worker_tool(
            "search_case_law", {"query": "formula"}, "formula", chunk_fn, "test-model"))


def test_a_fresh_summary_reaches_the_worker_checked(_worker_config):
    out = _run_tool(RAW, cache_on=False, chunk_fn=_chunk_returning(HELD + "\n" + INVENTED))
    assert out.startswith(HELD) and "£300" not in out


def test_a_local_cache_hit_is_checked_too(_worker_config):
    with patch.object(lpc, "lookup", new=AsyncMock(return_value={
            "summary": "Cached: " + HELD + "\n" + INVENTED, "chars_in": 3000})):
        out = _run_tool(RAW, cache_on=True)
    assert out.startswith("Cached: " + HELD) and "£300" not in out
