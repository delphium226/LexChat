"""FIX_PLAN P3.38, finding 2 (Session 50): an empty section search triggers a
code lookup, and where the index lacks the instrument or its text, the note says
so and the text code read from legislation.gov.uk follows it.

Why. P3.38 read an instrument's text only on a lookup or a text read, and P3.25's
lookup before a section search stops at five a run. In 6383 t1 the Worker
section-searched 37 instruments for "£"; six came back empty past that cap, so
nothing was read, and the empty search's note said the result was "NOT that the
instrument is unavailable", which let a Worker write that 20 instruments, the
unheld SSI 2026/170 among them, "do not feature the '£' symbol". Over every
stored run no instrument the index holds with text ever returned an empty section
search (5,397 non-empty on 374 ids, 131 empty on 13 ids, disjoint).

Every id, title and provision here is synthetic ("The Widget Order 1901",
`ssi/1901/3`). No test reaches the network: the read is served by
`test_published_text._Server`.
"""
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agent.agent_shared import run_worker_tool
from src.agent.provider_factory import set_request_provider_config
from src.utils import published_text as pt
from src.utils.instrument_lookup import (
    LOOKUP_TOOL,
    MAX_EMPTY_SECTION_LOOKUPS,
    empty_section_lookup,
)
from src.utils.search_scope import (
    empty_section_note,
    is_empty_section_result,
    section_search_note,
    strip_scope_blocks,
)

from .test_published_text import _Server, _doc

LID = "ssi/1901/3"
SECTIONS = "search_legislation_sections"
EMPTY = json.dumps({"results": [], "returned": 0})
FULL = json.dumps({"results": [{"uri": f"http://www.legislation.gov.uk/id/{LID}/article/1",
                                "text": "Widgets shall be blue."}], "returned": 1})
ARGS = {"legislation_id": LID, "query": "£"}
OLD_CLAUSE = "NOT that the instrument is unavailable"


def _lookup(status, lid=LID):
    return json.dumps({"tool": LOOKUP_TOOL, "legislation_id": lid, "label": pt.label_for(lid),
                       "title": "The Widget Order 1901", "status": status})


# ---------------------------------------------------------------------------
# the note and the emptiness test
# ---------------------------------------------------------------------------

def test_the_note_for_an_instrument_the_index_lacks():
    note = empty_section_note(ARGS, "not_held", "SSI 1901/3")
    assert note == (
        '\n\n[SEARCH SCOPE — 0 provisions of ssi/1901/3 matched "£": looked up by its number, '
        "SSI 1901/3 is one this index lacks, so there was nothing of it to search. That says "
        "nothing about what the instrument contains or about whether the citation is accurate, "
        "so do not report the instrument as lacking what this search asked for.]")


def test_the_note_for_an_instrument_held_without_text():
    note = empty_section_note(ARGS, "held_without_text", "SSI 1901/3")
    assert note == (
        '\n\n[SEARCH SCOPE — 0 provisions of ssi/1901/3 matched "£": looked up by its number, '
        "this index holds the record of SSI 1901/3 but none of its text, so there was nothing "
        "of it to search. That says nothing about what the instrument contains, so do not report "
        "the instrument as lacking what this search asked for.]")


@pytest.mark.parametrize("status", ["held", "lookup_failed", "invalid", "", None])
def test_any_other_outcome_has_no_note_of_its_own(status):
    assert empty_section_note(ARGS, status, "SSI 1901/3") == ""


def test_both_notes_are_stripped_from_an_answer_that_echoes_them():
    for status in ("not_held", "held_without_text"):
        note = empty_section_note(ARGS, status, "SSI 1901/3").strip()
        stripped, n = strip_scope_blocks("Answer. " + note + " More.")
        assert n == 1 and note not in stripped


@pytest.mark.parametrize("data,want", [
    ({"results": [], "returned": 0}, True),
    ({"results": []}, True),
    ({"results": [{"text": "x"}], "returned": 1}, False),
    ({"results": [], "error": "boom"}, False),
    ({"returned": 0}, False),
    (None, False),
    ("not json", False),
])
def test_an_empty_result_is_one_with_an_empty_results_list_and_no_error(data, want):
    assert is_empty_section_result(data) is want


# ---------------------------------------------------------------------------
# the lookup helper
# ---------------------------------------------------------------------------

def _runner(status="not_held"):
    calls = []

    async def run(name, args):
        calls.append((name, dict(args)))
        return _lookup(status, f"{args['legislation_type']}/{args['year']}/{args['number']}")
    return run, calls


def test_the_helper_looks_up_once_per_instrument_per_run():
    run, calls = _runner()
    done = {}

    async def go():
        a = await empty_section_lookup(ARGS, done, run)
        b = await empty_section_lookup(ARGS, done, run)
        return a, b
    a, b = asyncio.run(go())
    assert a == b == _lookup("not_held")
    assert calls == [(LOOKUP_TOOL, {"legislation_type": "ssi", "year": 1901, "number": 3})]


def test_the_helper_reuses_a_lookup_the_run_already_made():
    run, calls = _runner()
    out = asyncio.run(empty_section_lookup(ARGS, {}, run, seen={LID: "earlier"}))
    assert out == "earlier" and calls == []


def test_the_helper_is_bounded_per_run():
    run, calls = _runner()

    async def go():
        done = {}
        outs = []
        for n in range(1, MAX_EMPTY_SECTION_LOOKUPS + 3):
            outs.append(await empty_section_lookup({"legislation_id": f"ssi/1901/{n}"}, done, run))
        return outs
    outs = asyncio.run(go())
    assert len(calls) == MAX_EMPTY_SECTION_LOOKUPS
    assert outs[-2:] == [None, None]


@pytest.mark.parametrize("args", [{}, {"legislation_id": ""}, {"legislation_id": "nonsense"}, None])
def test_the_helper_makes_no_call_without_an_instrument_id(args):
    run, calls = _runner()
    assert asyncio.run(empty_section_lookup(args, {}, run)) is None and calls == []


def test_a_held_outcome_is_taken_back_out_of_the_scope_record():
    log = []

    async def run(name, args):
        log.append({"tool": "lookup", "legislation_id": LID, "status": "held"})
        log.append({"tool": "other"})
        return _lookup("held")
    asyncio.run(empty_section_lookup(ARGS, {}, run, log=log))
    assert log == [{"tool": "other"}]


def test_a_not_held_outcome_stays_in_the_scope_record():
    log = []

    async def run(name, args):
        log.append({"tool": "lookup", "legislation_id": LID, "status": "not_held"})
        return _lookup("not_held")
    asyncio.run(empty_section_lookup(ARGS, {}, run, log=log))
    assert log == [{"tool": "lookup", "legislation_id": LID, "status": "not_held"}]


# ---------------------------------------------------------------------------
# the seam: run_worker_tool, with the callback wired as run_worker_agent wires it
# ---------------------------------------------------------------------------

async def _chunk(*a, **k):
    return None


def _seam(monkeypatch, section_raw=EMPTY, lookup_status="not_held", pages=None, log=None,
          memo=None, suffix="", callback=True, seen=None, args=None, preface=(), budget=None):
    """A section search through `run_worker_tool`, the executor answering by tool
    and the read served from `pages`. Returns (result, server, lookups asked)."""
    srv = _Server(pages if pages is not None else {f"{LID}/made/data.xml": (200, _doc())})
    srv.install(monkeypatch)
    log = [] if log is None else log
    asked = []

    async def execute(name, a, *rest, **kw):
        if name == LOOKUP_TOOL:
            asked.append(dict(a))
            return _lookup(lookup_status)
        return section_raw

    async def go():
        set_request_provider_config({"_test": True})
        done = {}

        async def run_tool(name, a, result_suffix=""):
            return await run_worker_tool(name, a, "is a fee in pounds set?", _chunk, "m",
                                         search_log=log, tool_memo=memo,
                                         empty_search_lookup=cb, result_suffix=result_suffix,
                                         context_budget=budget)

        async def cb(a):
            return await empty_section_lookup(a, done, run_tool, log=log, seen=seen)

        with patch("src.agent.agent_shared.execute_worker_tool", new=AsyncMock(side_effect=execute)):
            for name, a in preface:
                await run_tool(name, a)
            return await run_worker_tool(SECTIONS, dict(args or ARGS), "is a fee in pounds set?",
                                         _chunk, "m", search_log=log, tool_memo=memo,
                                         result_suffix=suffix,
                                         empty_search_lookup=cb if callback else None,
                                         context_budget=budget)
    return asyncio.run(go()), srv, asked


def test_an_empty_search_of_an_unheld_instrument_hands_the_worker_its_text(monkeypatch):
    log = []
    out, srv, asked = _seam(monkeypatch, log=log)
    assert asked == [{"legislation_type": "ssi", "year": 1901, "number": 3}]
    assert out.startswith(EMPTY)
    assert "SSI 1901/3 is one this index lacks, so there was nothing of it to search" in out
    assert OLD_CLAUSE not in out
    assert "this index lacks SSI 1901/3 (The Widget Order 1901), so code read its text" in out
    assert "1. (1) This Order may be cited as the Widget Order 1901." in out
    assert out.count(pt.FETCHED_CLOSE) == 1
    assert out.index("there was nothing of it to search") < out.index(pt.FETCHED_OPEN)
    assert [e["status"] for e in log if e["tool"] == "lookup"] == ["not_held"]
    assert [e["status"] for e in log if e["tool"] == pt.PUBLISHED_ENTRY] == [pt.OK]


def test_an_empty_search_of_an_instrument_held_without_text_says_so(monkeypatch):
    out, _, _ = _seam(monkeypatch, lookup_status="held_without_text")
    assert "this index holds the record of SSI 1901/3 but none of its text, so there was " \
           "nothing of it to search" in out
    assert "this index holds the record of SSI 1901/3 (The Widget Order 1901) but none of " \
           "its text, so code read" in out
    assert OLD_CLAUSE not in out


@pytest.fixture
def _over_budget(monkeypatch):
    """Past the budget `run_worker_tool` summarises, which consults the shared
    local prompt cache in the database: stubbed, as test_published_text does,
    because a test's closing event loop would leave that transaction open and
    the session's teardown would wait on its lock (found in Session 50)."""
    monkeypatch.setattr("src.agent.agent_shared.summarise_for_query",
                        AsyncMock(return_value=("Summary: a summary.", False)))
    from src.services import local_prompt_cache as lpc
    monkeypatch.setattr(lpc, "lookup", AsyncMock(return_value=None))
    monkeypatch.setattr(lpc, "store", AsyncMock(return_value=None))
    return {"used": 300_000, "limit": 250_000}


@pytest.mark.parametrize("status,phrase", [
    ("not_held", "SSI 1901/3 is one this index lacks"),
    ("held_without_text", "holds the record of SSI 1901/3 but none of its text, so there was nothing"),
])
def test_past_the_context_budget_the_summarised_lookup_still_decides(monkeypatch, _over_budget,
                                                                    status, phrase):
    """6383 t1 r3 (Session 50): past the Worker's context budget every result is
    summarised, the lookup's JSON included, so its status could not be parsed
    from it; three instruments then kept the old note and got no text. The
    outcome is read from the scope record, written from the raw result."""
    log = []
    out, _, asked = _seam(monkeypatch, lookup_status=status, log=log, budget=_over_budget)
    assert len(asked) == 1
    assert phrase in out and OLD_CLAUSE not in out
    assert pt.FETCHED_OPEN in out  # the text (here its summary) follows the note


def test_past_the_context_budget_a_held_lookup_still_leaves_the_note(monkeypatch, _over_budget):
    out, srv, _ = _seam(monkeypatch, lookup_status="held", budget=_over_budget)
    assert OLD_CLAUSE in out and srv.asked == []


def test_a_held_lookup_leaves_the_note_and_reads_nothing(monkeypatch):
    log = []
    out, srv, asked = _seam(monkeypatch, lookup_status="held", log=log)
    assert len(asked) == 1 and srv.asked == []
    assert out == EMPTY + section_search_note(ARGS, json.loads(EMPTY))
    assert not [e for e in log if e["tool"] == "lookup"]


def test_a_failed_lookup_leaves_the_note(monkeypatch):
    out, srv, _ = _seam(monkeypatch, lookup_status="lookup_failed")
    assert out == EMPTY + section_search_note(ARGS, json.loads(EMPTY)) and srv.asked == []


def test_a_search_that_returned_provisions_makes_no_lookup(monkeypatch):
    out, srv, asked = _seam(monkeypatch, section_raw=FULL)
    assert asked == [] and srv.asked == []
    assert out == FULL + section_search_note(ARGS, json.loads(FULL))


def test_without_the_callback_the_result_is_exactly_as_before(monkeypatch):
    out, srv, asked = _seam(monkeypatch, callback=False)
    assert asked == [] and srv.asked == []
    assert out == EMPTY + section_search_note(ARGS, json.loads(EMPTY))


def test_a_failed_read_still_rewords_the_note_and_says_why_no_text_follows(monkeypatch):
    out, _, _ = _seam(monkeypatch, pages={f"{LID}/made/data.xml": (500, "boom")})
    assert "SSI 1901/3 is one this index lacks" in out
    assert "did not complete (an error)" in out and "This Order may be cited" not in out


def test_a_text_already_handed_in_this_run_is_pointed_back_to_not_repeated(monkeypatch):
    log = []
    # The Worker looked the instrument up itself first, and was handed the text.
    out, srv, asked = _seam(monkeypatch, log=log, preface=[(LOOKUP_TOOL, ARGS)])
    assert len(asked) == 2  # its own lookup, then code's (no memo, no `seen`)
    assert "This Order may be cited" not in out
    assert "code read its text from legislation.gov.uk earlier in this research, and that " \
           "text was handed over there" in out
    assert "SSI 1901/3 is one this index lacks" in out


def test_a_reused_lookup_whose_text_was_handed_is_pointed_back_to(monkeypatch):
    # The run's earlier lookup carried the whole text (its result is in `seen`),
    # and the scope record says it was handed: the empty search gets the line
    # pointing back, in the held-without-text form, never the text again.
    log = [{"tool": pt.PUBLISHED_ENTRY, "legislation_id": LID, "label": "SSI 1901/3",
            "kind": pt.KIND_NO_TEXT, "status": pt.OK, "version": "made"}]
    earlier = _lookup("held_without_text") + pt.published_block(
        LID, pt.KIND_NO_TEXT, {"version": "made"}, body="This Order may be cited.", total_chars=24)
    out, _, asked = _seam(monkeypatch, log=log, seen={LID: earlier})
    assert asked == [] and "This Order may be cited" not in out
    assert "[PROVISION FETCHED BY CODE — this index holds the record of SSI 1901/3 but none of " \
           "its text; code read its text from legislation.gov.uk earlier in this research" in out


def test_a_lookup_the_run_already_made_is_reused(monkeypatch):
    out, _, asked = _seam(monkeypatch, seen={LID: _lookup("held_without_text")})
    assert asked == []
    assert "holds the record of SSI 1901/3 but none of its text, so there was nothing" in out


def test_the_text_is_not_added_twice_where_the_suffix_carries_it(monkeypatch):
    suffix = pt.published_block(LID, pt.KIND_NOT_HELD, {"version": "made"}, body="Text.",
                                total_chars=5)
    out, _, _ = _seam(monkeypatch, suffix=suffix)
    assert out.count(pt.FETCHED_OPEN) == 1 and out.endswith(suffix)
    assert "SSI 1901/3 is one this index lacks" in out


def test_a_failure_in_the_lookup_leaves_the_result_as_it_was(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr("src.agent.agent_shared._empty_search_text", boom)
    out, _, _ = _seam(monkeypatch)
    assert out == EMPTY + section_search_note(ARGS, json.loads(EMPTY))


def test_a_memo_hit_records_the_lookup_and_the_read_for_the_reusing_step(monkeypatch):
    memo, first, second = {}, [], []
    out1, _, asked1 = _seam(monkeypatch, log=first, memo=memo)
    out2, srv2, asked2 = _seam(monkeypatch, log=second, memo=memo)
    assert out1 == out2 and asked2 == [] and srv2.asked == []
    assert [e["status"] for e in second if e["tool"] == "lookup"] == ["not_held"]
    assert [e["status"] for e in second if e["tool"] == pt.PUBLISHED_ENTRY] == [pt.OK]


def test_the_lawyers_footer_and_the_managers_limb_follow_the_lookup(monkeypatch):
    from src.utils.search_scope import _lookup_footer_clause, _lookup_limb
    log = []
    _seam(monkeypatch, log=log)
    assert "SSI 1901/3 was looked up by its number and is not held in this index" in \
        _lookup_footer_clause(log)
    assert "The text of SSI 1901/3 (as made) was read from legislation.gov.uk." in \
        _lookup_footer_clause(log)
    assert "SSI 1901/3 NOT HELD" in _lookup_limb(log)


# ---------------------------------------------------------------------------
# run_worker_agent wires it for both Workers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("chat_mode", ["conversational", "research"])
def test_run_worker_agent_wires_the_lookup_for_both_workers(monkeypatch, chat_mode):
    from src.agent.agent_core import run_worker_agent
    _Server({f"{LID}/made/data.xml": (200, _doc())}).install(monkeypatch)
    set_request_provider_config({"_provider": "openrouter", "model": "test-model",
                                 "_research_mode": "legislation_only", "_chat_mode": chat_mode})
    asked = []

    async def execute(name, a, *rest, **kw):
        if name == LOOKUP_TOOL:
            asked.append(dict(a))
            return _lookup("not_held")
        return EMPTY

    seen = []

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None, **kw):
        seen.append(await tool_exec(SECTIONS, dict(ARGS)))
        return {"role": "assistant", "content": "Report."}

    with patch("src.agent.agent_shared.execute_worker_tool", new=AsyncMock(side_effect=execute)):
        result = asyncio.run(run_worker_agent(loop, lambda *a, **k: None, "Widgets?",
                                              "test-model", None, 0))
    # One lookup whichever Worker: the quick-lookup Worker's P3.25 lookup runs
    # first and the empty search reuses it.
    assert asked == [{"legislation_type": "ssi", "year": 1901, "number": 3}]
    assert "SSI 1901/3 is one this index lacks" in seen[0]
    assert seen[0].count("This Order may be cited") == 1
    assert [e["status"] for e in result["searches"] if e.get("tool") == "lookup"] == ["not_held"]
