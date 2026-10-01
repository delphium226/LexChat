"""P3.2 (B6): the agreement formula removed from the start of a Manager answer.

Cosmetic by design: the acceptance's position criteria are the model's; this
only stops the register announcing a concession before anything was checked.
Every sentence here is synthetic.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.utils.openers import strip_agreement_opener  # noqa: E402


@pytest.mark.parametrize("answer, expected, kind", [
    # A formula that is the whole sentence goes; the content stays.
    ("You make a very precise point. Section 4 applies to widgets.",
     "Section 4 applies to widgets.", "praise"),
    ("You are absolutely right.\n\nThe Order defines a widget.",
     "The Order defines a widget.", "bare"),
    ("Apologies for that. The Order defines a widget.",
     "The Order defines a widget.", "apology"),
    ("Thank you for pressing on this. The Order defines a widget.",
     "The Order defines a widget.", "thanks"),
    # A formula leading into content loses the formula only.
    ("You are absolutely right to challenge this, and your reading shows a gap.",
     "Your reading shows a gap.", "bare"),
    ("You make a strong textual point: the Order says widget, not gadget.",
     "The Order says widget, not gadget.", "praise"),
    ("You have correctly identified that the Order is silent. More follows.",
     "The Order is silent. More follows.", "praise"),
    # A contrast that answered the dropped concession goes with it.
    ("You raise a fair point. However, the Order is silent.",
     "The Order is silent.", "praise"),
    # Two formulas in a row: two passes.
    ("You are correct, and I apologise for the confusion. The Order is silent.",
     "The Order is silent.", "bare"),
    # A leading link is capitalised inside the bracket.
    ("You make a strong point: [regulation 3](http://x/3) says so.",
     "[Regulation 3](http://x/3) says so.", "praise"),
])
def test_the_formula_goes_and_the_content_stays(answer, expected, kind):
    assert strip_agreement_opener(answer) == (expected, kind)


@pytest.mark.parametrize("answer, expected, kind", [
    # P4.13: the object is the bot's own earlier answer. Each adjective and
    # noun of the widened object list, in both formulas that take an object.
    ("You are correct to challenge my earlier statement. The Order defines a widget.",
     "The Order defines a widget.", "bare"),
    ("You are right to question my previous answer, and the Order is silent.",
     "The Order is silent.", "bare"),
    ("You are absolutely right to push back on my last response. However, the Order "
     "is silent.", "The Order is silent.", "bare"),
    ("You're right to query my original position: the Order says widget.",
     "The Order says widget.", "bare"),
    ("You are correct to challenge my earlier reply. The Order is silent.",
     "The Order is silent.", "bare"),
    ("You are right to challenge my previous assessment. The Order is silent.",
     "The Order is silent.", "bare"),
    ("Thank you for challenging my earlier answer. The Order defines a widget.",
     "The Order defines a widget.", "thanks"),
    ("Thank you for pressing me on my previous statement. The Order is silent.",
     "The Order is silent.", "thanks"),
])
def test_a_challenge_to_my_earlier_answer_goes(answer, expected, kind):
    assert strip_agreement_opener(answer) == (expected, kind)


@pytest.mark.parametrize("answer", [
    # P4.13's object is the bot's OWN earlier answer, named by the listed
    # nouns; anything else, or a clause saying what was challenged, stays.
    "You are right to challenge my earlier statement that section 4 applies. It does not.",
    "You are right to challenge my earlier reading of section 4. It is narrower.",
    "You are right to challenge the earlier statement. The Order is silent.",
    "Thank you for challenging my earlier analysis. The Order is silent.",
    "You are correct that my earlier answer was wrong. The Order is silent.",
])
def test_a_challenge_to_something_else_is_left(answer):
    assert strip_agreement_opener(answer) == (answer, None)


@pytest.mark.parametrize("answer, expected, kind", [
    # P4.16: "highlight" as the bare formula's verb, with each object and the
    # drop, connector, colon and dangling-"However" shapes.
    ("You are correct to highlight this. The Order defines a widget.",
     "The Order defines a widget.", "bare"),
    ("You're absolutely right to highlight that, and the Order is silent.",
     "The Order is silent.", "bare"),
    ("You are right to highlight my earlier statement. However, the Order is silent.",
     "The Order is silent.", "bare"),
    ("You are correct to highlight the point: the Order says widget.",
     "The Order says widget.", "bare"),
    ("You are right to highlight this point — the Order is silent.",
     "The Order is silent.", "bare"),
])
def test_a_highlighting_formula_goes(answer, expected, kind):
    assert strip_agreement_opener(answer) == (expected, kind)


@pytest.mark.parametrize("answer", [
    # P4.16 widens the verb only: a clause saying what was highlighted, an
    # unlisted object, a qualifier, or nothing after the formula, all stay.
    "You are correct to highlight that the Order is silent. More follows.",
    "You are correct to highlight this distinction. The Order is silent.",
    "You are right to highlight this in section 4. The Order is silent.",
    "You are correct to highlight this.",
])
def test_a_highlight_with_content_is_left(answer):
    assert strip_agreement_opener(answer) == (answer, None)


@pytest.mark.parametrize("answer", [
    # Scoped: it says what is agreed, and the acceptance allows it.
    "You are correct that section 4 applies. More follows.",
    # A yes to a yes/no question is an answer (code cannot tell it from a
    # capitulation), so affirm openers are never touched.
    "Yes, that is correct. The Act is partly in force.",
    "Yes, exactly. The Order is silent.",
    # The formula alone, carrying a link or a number: a citation is never lost.
    "You make a very good point about section 4. The Order is silent.",
    "You raise a fair point about [the Order](http://x/1). It is silent.",
    # Nothing left after the formula.
    "You are absolutely right.",
    # No clause to keep.
    "You have correctly identified a significant gap. The Order is silent.",
    # Not an opener at all.
    "The Order defines a widget. You are right to ask.",
    "",
])
def test_left_as_written(answer):
    assert strip_agreement_opener(answer) == (answer, None)


def test_it_never_raises():
    assert strip_agreement_opener(None) == (None, None)


async def _manager_answer(text):
    from src.agent.agent_core import process_user_request

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False, "_chat_mode": "conversational",
    })

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        return {"role": "assistant", "content": text}

    async def worker(*a, **kw):
        raise AssertionError("no delegation expected")

    try:
        return await process_user_request(
            manager, worker, [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    finally:
        set_request_provider_config({})


@pytest.mark.asyncio
async def test_the_answer_seam_removes_the_formula():
    result = await _manager_answer("You are absolutely right to challenge this, and the "
                                   "Order is silent on gadgets.")
    assert result["content"].startswith("The Order is silent on gadgets.")


@pytest.mark.asyncio
async def test_the_answer_seam_leaves_a_scoped_agreement():
    result = await _manager_answer("You are correct that the Order is silent on gadgets.")
    assert result["content"].startswith("You are correct that the Order is silent")
