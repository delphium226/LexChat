"""P4.14: a footer the model echoed, followed by P1.6's link note.

The model copies the previous turn's `*Search scope:*` line out of the history.
`strip_answer_footer` removes such an echo only while it is the END of the
text, but `enforce_provision_links` appends its "No provision-level URL" note
after the model's text first, so the echo was no longer trailing when the strip
ran and the lawyer read two scope lines (`wave4_p33_post`, 2 turns). The echo is
now stripped while it is still trailing, on the Manager and the Deep Research
paths.

Pinned alongside `tests/test_case_law_gap.py`: exactly ONE scope line reaches
the lawyer, it is the one computed from this turn's searches, P2.8's
`_earlier_footers` reads it back from the LAST line, and the case-law clause
stays last. Every text here is synthetic.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.agent_core import run_deep_research, run_worker_agent  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.utils.citation_links import PROVISION_FOOTNOTE  # noqa: E402
from src.utils.search_scope import (  # noqa: E402
    CASE_LAW_DOCTRINE_SENTENCE,
    _earlier_footers,
    answer_scope_footer,
)

# A provision link no tool returned, so P1.6 marks it and appends its note.
_UNRETURNED = "[art 4](http://www.legislation.gov.uk/uksi/1901/1/article/4)"
_PROSE = f"The Widget Order 1901 {_UNRETURNED} defines a widget."


def _leg(*queries):
    return [{"tool": "search_legislation", "query": q, "legislation_id": "",
             "shown": 5, "matched": 141} for q in queries]


# What the model copies back: the previous turn's code-emitted line.
_ECHO = answer_scope_footer(_leg("an earlier widget search"), {})


async def _manager_turn(monkeypatch, manager_text, worker_calls):
    from src.agent import agent_shared
    from src.agent.agent_core import process_user_request

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_and_case_law",
        "model": "test-model", "_tool_memo_enabled": False,
        "_chat_mode": "conversational",
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        if name == "search_case_law":
            return json.dumps({"results": [
                {"title": "Alpha v Beta", "ncn": "[2020] EWHC 1", "court": "ewhc",
                 "date": "2020-01-01",
                 "url": "https://caselaw.nationalarchives.gov.uk/ewhc/2020/1"}],
                "total": 1, "query": "q"})
        return json.dumps({"results": [
            {"legislation_id": "uksi/1901/1", "title": "Widget Order 1901",
             "url": "http://www.legislation.gov.uk/id/uksi/1901/1",
             "status": "revised", "year": 1901, "extent": ["Scotland"]}],
            "returned": 1, "total": 141})

    async def worker_chat_loop(messages, model, cancel_event, num_ctx, tools,
                               executor, on_chunk=None, emit_tool_details=False,
                               timing_collector=None, worker_call=False):
        for name, args in worker_calls:
            await executor(name, args)
        return {"role": "assistant", "content": (
            "1. **Summary Answer (BLUF):** The Order defines a widget.\n"
            "2. **References:** None.")}

    async def worker(*a, **kw):
        return await run_worker_agent(
            worker_chat_loop, lambda *x, **y: None, "q", "test-model", None, 0)

    async def manager(messages, model, cancel_event, num_ctx, tools,
                      tool_executor, on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": manager_text}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        return await process_user_request(
            manager, worker, [{"role": "user", "content": "q"}],
            "test-model", None, None, 0)
    finally:
        set_request_provider_config({})


def _assert_one_fresh_line(content, fresh_term):
    assert content.count("*Search scope:") == 1
    assert "an earlier widget search" not in content
    # P1.6's note survives, ahead of the one scope line.
    assert PROVISION_FOOTNOTE in content
    assert content.index(PROVISION_FOOTNOTE) < content.index("*Search scope:")
    # P2.8 reads the line back from the last line, and it is this turn's.
    read = _earlier_footers([{"role": "assistant", "content": content}])
    assert len(read) == 1 and fresh_term in read[0]["terms"]


_LEG_CALL = ("search_legislation", {"query": "widget definition"})
_CL_CALL = ("search_case_law", {"query": "widget case"})


@pytest.mark.asyncio
@pytest.mark.parametrize("manager_text", [
    # The recorded shape: the echo is the end of the model's text.
    _PROSE + _ECHO,
    # The same with the suggestions block after it, which is stripped first.
    _PROSE + _ECHO + "\n\n<suggestions>\nWhat does article 5 say?\n</suggestions>",
])
async def test_an_echo_ahead_of_the_link_note_is_stripped(monkeypatch, manager_text):
    final = await _manager_turn(monkeypatch, manager_text, [_LEG_CALL, _CL_CALL])
    content = final["content"]
    assert content.startswith("The Widget Order 1901")
    _assert_one_fresh_line(content, "widget definition")
    # The case-law clause stays last.
    assert content.endswith(CASE_LAW_DOCTRINE_SENTENCE + "*")


@pytest.mark.asyncio
async def test_prose_after_an_echo_is_never_eaten(monkeypatch):
    """The early strip is the same trailing-only strip: a model paragraph after
    the copied line is answer text, and stays (as `test_search_scope` pins for
    the strip itself)."""
    final = await _manager_turn(
        monkeypatch, _PROSE + _ECHO + "\n\nA later widget paragraph.", [_LEG_CALL])
    assert "A later widget paragraph." in final["content"]


# ---------------------------------------------------------------------------
# Deep Research: the synthesis has the same shape
# ---------------------------------------------------------------------------

_PLAN = {"scope_note": "", "steps": [
    {"id": 1, "title": "Order", "detail": "The Widget Order 1901."},
]}


@pytest.mark.asyncio
async def test_deep_research_strips_an_echo_ahead_of_the_link_note():
    async def run_worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                         emit_tool_details=False, timing_collector=None,
                         tool_memo=None, retrieved_urls=None):
        return {"content": "f1", "sources": [], "searches": _leg("widget order")}

    async def synthesis(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None,
                        worker_call=False):
        return {"role": "assistant", "content": "Integrated report. " + _PROSE + _ECHO}

    result = await run_deep_research(
        synthesis, run_worker, _PLAN, [{"role": "user", "content": "q"}],
        "test-model", None, None, 0,
    )
    content = result["content"]
    assert content.startswith("Integrated report.")
    _assert_one_fresh_line(content, "widget order")
    assert content.endswith(answer_scope_footer(_leg("widget order"), {}))
