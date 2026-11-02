"""P4.8: the label the Manager's delegation results carry never reaches an answer.

`manager_tool_executor` hands a report back as `[Research Agent Result]` and
the report; in research mode the Manager is told to pass the report through
verbatim, and 7 stored answers opened with the label as well. Removed at the
Manager return; what the Manager receives is unchanged. Sentences synthetic.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.agent_core import (  # noqa: E402
    RESEARCH_RESULT_PREFIX,
    strip_result_label,
    worker_result_for_manager,
)

LABEL = "[Research Agent Result]"


@pytest.mark.parametrize("answer, expected", [
    # The stored shape: the label, a line break, the report.
    (LABEL + "\n1. **Summary Answer (BLUF):**\nThe Order is silent.",
     "1. **Summary Answer (BLUF):**\nThe Order is silent."),
    # Leading whitespace and a blank line after it.
    ("  " + LABEL + "\n\n### 1. Summary Answer (BLUF)\nThe Act applies.",
     "### 1. Summary Answer (BLUF)\nThe Act applies."),
    # In backticks, mid-answer, after a one-line preamble.
    ("Here is the report.\n\n`" + LABEL + "`\nThe Act applies.",
     "Here is the report.\n\nThe Act applies."),
    # Its own line between two lines: the line goes, no blank line is left.
    ("Here is the report.\n" + LABEL + "\nThe Act applies.",
     "Here is the report.\nThe Act applies."),
    # Twice (two delegations passed through).
    (LABEL + "\nStep one.\n\n" + LABEL + "\nStep two.", "Step one.\n\nStep two."),
    # Windows line ending.
    (LABEL + "\r\nThe Act applies.", "The Act applies."),
])
def test_the_label_goes_and_the_report_stays(answer, expected):
    out, n = strip_result_label(answer)
    assert out == expected
    assert n >= 1


@pytest.mark.parametrize("answer", [
    "The Order is silent on gadgets.\n\n\n",
    "",
    # Not this label: the Worker-error containment string, and the bare words
    # (the one stored placeholder, a different failure) are left alone.
    "[Research Agent Error] The research step did not complete.",
    "Here are the findings from the research agent:\n\nResearch Agent Result",
])
def test_an_answer_without_the_label_is_byte_identical(answer):
    assert strip_result_label(answer) == (answer, 0)


def test_what_the_manager_receives_is_unchanged():
    handed = worker_result_for_manager("The Act applies.", {"_chat_mode": "research"})
    assert handed == RESEARCH_RESULT_PREFIX + "The Act applies."


@pytest.fixture
def _research_cfg():
    from src.agent.provider_factory import set_request_provider_config
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "model": "test-model", "_tool_memo_enabled": False, "_chat_mode": "research",
    })
    yield
    set_request_provider_config({})


async def _answer(manager_text, seen=None):
    from src.agent.agent_core import process_user_request

    async def worker(*a, **kw):
        return {"content": "1. **Summary Answer (BLUF):**\nSSI 2017/114 applies.",
                "sources": [], "searches": []}

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        handed = await tool_executor("delegate_research", {"query": "q"})
        if seen is not None:
            seen.append(handed)
        return {"role": "assistant", "content": manager_text}

    return await process_user_request(
        manager, worker, [{"role": "user", "content": "q"}], "test-model", None, None, 0)


@pytest.mark.asyncio
async def test_the_manager_return_removes_a_copied_label(_research_cfg):
    seen = []
    final = await _answer(LABEL + "\n1. **Summary Answer (BLUF):**\nSSI 2017/114 applies.", seen)
    assert LABEL not in final["content"]
    assert final["content"].startswith("1. **Summary Answer (BLUF):**")
    # The Manager was handed the labelled report, as before.
    assert seen and seen[0].startswith(RESEARCH_RESULT_PREFIX)


@pytest.mark.asyncio
async def test_the_label_goes_before_the_opener_strip_reads_the_start(_research_cfg):
    final = await _answer(LABEL + "\nYou are absolutely right to challenge this, and "
                          "SSI 2017/114 applies.")
    assert final["content"].startswith("SSI 2017/114 applies.")


@pytest.mark.asyncio
async def test_an_answer_that_was_the_label_alone_gets_the_research(_research_cfg):
    final = await _answer(LABEL)
    assert LABEL not in final["content"]
    assert final.get("answer_failed") is True
    assert "SSI 2017/114 applies." in final["content"]
