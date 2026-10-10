"""P4.3 lever R (batch 12 D): the answer seam re-admits a source the answer cites.

V4 (batch 11 C) stopped the Worker seam falling back to the whole accumulator, so
a source reaches the Sources rail only when a Worker report vouches for it. An
answer can cite what no report named: an instrument a code scope block listed,
or one an earlier turn's answer linked. `readmit_answer_sources` puts such a
source back, on the Manager path and the Deep Research path, read against the
answer before the scope footer, by the keep test's token and name branches
(never its excerpt branch), once per instrument, and never on the
parliamentary bots. Also pinned: the longer-title guard's unclosed
"(Commencement" form (`source_naming._LONGER_TITLE`).

Synthetic text only ("Widget Order 1901", `ssi/1901/3`).
"""
import json

import pytest

from src.agent.agent_core import (
    _source_is_named,
    _source_is_used,
    process_user_request,
    readmit_answer_sources,
    retrieved_with_marks,
    run_deep_research,
    run_worker_agent,
)
from src.agent.provider_factory import set_request_provider_config
from src.utils import source_naming as sn
from src.utils.search_scope import answer_scope_footer

LEG = "https://www.legislation.gov.uk/"


def _leg(lid, title=None, kept=False, url=None, **kw):
    """A retrieved legislation source as `run_worker_agent` hands it on."""
    return {"_lid": lid, "kind": "SI", "title": title or lid,
            "url": url if url is not None else LEG + lid, "cite": lid,
            "_kept": kept, **kw}


def _pub(s):
    return {k: v for k, v in s.items() if not k.startswith("_")}


# --- readmit_answer_sources ------------------------------------------------------------

def test_a_source_the_answer_cites_and_no_report_named_is_readmitted():
    src = _leg("ssi/1901/3", "Widget Order 1901")
    out = readmit_answer_sources([], [src], "The Widget Order 1901 applies.", "legislation_only")
    assert out == [_pub(src)]
    assert all(not k.startswith("_") for k in out[0])


@pytest.mark.parametrize("answer", [
    "Made as SSI 1901/3.",                                     # its SI number
    f"See [reg 2]({LEG}ssi/1901/3/regulation/2).",             # its URL
    "The record names ssi/1901/3.",                            # its id
])
def test_every_naming_route_readmits(answer):
    assert readmit_answer_sources([], [_leg("ssi/1901/3", "Widget Order 1901")], answer,
                                  "legislation_only")


def test_a_source_the_answer_does_not_cite_is_not_readmitted():
    assert readmit_answer_sources([], [_leg("ssi/1901/3", "Widget Order 1901")],
                                  "Nothing on point was found.", "legislation_only") == []


def test_retrieval_alone_is_not_citation():
    """The excerpt branch keeps a source at the Worker seam; it never re-admits one."""
    src = _leg("ssi/1901/3", "Widget Order 1901", excerpt="1. Citation ...")
    assert _source_is_used(src, "Nothing on point.")
    assert not _source_is_named(src, "Nothing on point.")
    assert readmit_answer_sources([], [src], "Nothing on point.", "legislation_only") == []


def test_a_kept_source_is_never_readmitted():
    src = _leg("ssi/1901/3", "Widget Order 1901", kept=True)
    rail = [_pub(src)]
    assert readmit_answer_sources(rail, [src], "The Widget Order 1901 applies.",
                                  "legislation_only") == []


def test_an_instrument_already_in_the_rail_under_another_url_is_not_readmitted():
    """A change record's `http://.../id/` URL and a search hit's `https://` URL are one
    instrument: the rail's exact-URL dedupe would list it twice."""
    kept = _leg("ssi/1901/3", "Widget Order 1901", kept=True)
    record = _leg("ssi/1901/3", url="http://www.legislation.gov.uk/id/ssi/1901/3")
    out = readmit_answer_sources([_pub(kept)], [kept, record],
                                 "The Widget Order 1901 (SSI 1901/3) applies.",
                                 "legislation_only")
    assert out == []


def test_one_instrument_retrieved_by_two_delegations_is_readmitted_once():
    a = _leg("ssi/1901/3", url="http://www.legislation.gov.uk/id/ssi/1901/3")
    b = _leg("ssi/1901/3", "Widget Order 1901")
    out = readmit_answer_sources([], [a, b], "Made as SSI 1901/3.", "legislation_only")
    assert out == [_pub(a)]


def test_a_source_with_no_id_already_in_the_rail_by_url_is_not_readmitted():
    case = {"kind": "Case", "title": "Widget Co v Example Ltd", "sub": "[1901] UKSC 1",
            "cite": "[1901] UKSC 1", "url": "https://caselaw.nationalarchives.gov.uk/uksc/1901/1",
            "_kept": False}
    answer = "In Widget Co v Example Ltd [1901] UKSC 1 the duty was strict."
    assert readmit_answer_sources([], [case], answer, "legislation_and_case_law") == [_pub(case)]
    assert readmit_answer_sources([_pub(case)], [case], answer, "legislation_and_case_law") == []


def test_two_cases_with_no_id_are_readmitted_once_each():
    case = {"kind": "Case", "title": "Widget Co v Example Ltd", "sub": "[1901] UKSC 1",
            "cite": "[1901] UKSC 1", "url": "https://caselaw.nationalarchives.gov.uk/uksc/1901/1",
            "_kept": False}
    answer = "In Widget Co v Example Ltd [1901] UKSC 1 the duty was strict."
    assert readmit_answer_sources([], [case, dict(case)], answer,
                                  "legislation_and_case_law") == [_pub(case)]


def test_retrieval_order_is_kept():
    a, b = _leg("ssi/1901/4", "Gadget Order 1901"), _leg("ssi/1901/3", "Widget Order 1901")
    out = readmit_answer_sources([], [a, b], "The Widget Order 1901 and the Gadget Order 1901.",
                                 "legislation_only")
    assert [s["cite"] for s in out] == ["ssi/1901/4", "ssi/1901/3"]


@pytest.mark.parametrize("mode", ["parliamentary_records", "westminster_records"])
def test_not_on_the_parliamentary_bots(mode):
    assert readmit_answer_sources([], [_leg("ssi/1901/3", "Widget Order 1901")],
                                  "The Widget Order 1901 applies.", mode) == []


@pytest.mark.parametrize("mode", ["legislation_only", "case_law_only", "legislation_and_case_law"])
def test_on_every_legislation_bot_research_type(mode):
    assert readmit_answer_sources([], [_leg("ssi/1901/3", "Widget Order 1901")],
                                  "The Widget Order 1901 applies.", mode)


def test_nothing_to_read_or_nothing_retrieved_is_nothing():
    src = _leg("ssi/1901/3", "Widget Order 1901")
    assert readmit_answer_sources([], [src], "", "legislation_only") == []
    assert readmit_answer_sources([], [], "The Widget Order 1901 applies.",
                                  "legislation_only") == []


def test_it_never_raises():
    assert readmit_answer_sources([], [None], "The Widget Order 1901 applies.",
                                  "legislation_only") == []


def test_retrieved_with_marks_marks_by_identity_not_equality():
    a = {"_lid": "ssi/1901/3", "title": "Widget Order 1901"}
    b = dict(a)                                    # equal, but not the kept one
    marked = retrieved_with_marks([a, b], [a])
    assert [m["_kept"] for m in marked] == [True, False]
    assert marked[0]["_lid"] == "ssi/1901/3"       # private keys kept for the seam
    assert "_kept" not in a                        # the accumulator is not mutated


# --- the longer-title guard: an unclosed "(Commencement" --------------------------------

def test_a_title_heading_an_unclosed_commencement_parenthesis_does_not_name_it():
    src = {"_lid": "asp/1901/3", "kind": "Act", "title": "Widget (Scotland) Act 1901"}
    query = 'The index was searched for "Widget (Scotland) Act 1901 (Commencement No. 1".'
    assert not sn.named_in(src, query)
    assert not sn.named_in(src, "Widget (Scotland) Act 1901 (Commencement")
    assert sn.named_in(src, query + " The Widget (Scotland) Act 1901 itself applies.")


def test_the_commencement_guard_needs_the_whole_word():
    src = {"_lid": "asp/1901/3", "kind": "Act", "title": "Widget (Scotland) Act 1901"}
    assert sn.named_in(src, "the Widget (Scotland) Act 1901 (Commencements and savings).")


def test_the_closed_longer_title_guard_still_holds():
    src = {"_lid": "asp/1901/3", "kind": "Act", "title": "Widget (Scotland) Act 1901"}
    assert not sn.named_in(
        src, "the Widget (Scotland) Act 1901 (Consequential Provisions) Order 1902 applies")


# --- the wiring: run_worker_agent, the Manager path, the Deep Research path -------------

def _search():
    return {"results": [
        {"legislation_id": f"ssi/1901/{i}", "title": f"Widget Order 1901 No {i}",
         "url": f"https://www.legislation.gov.uk/ssi/1901/{i}", "text_version": "revised",
         "year": 1901, "extent": ["Scotland"]} for i in (1, 2)],
        "returned": 2, "total": 2, "total_matched": 2, "removed_by_filters": 0}


@pytest.mark.asyncio
async def test_run_worker_agent_hands_on_everything_it_retrieved(monkeypatch):
    from src.agent import agent_shared

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "_chat_mode": "conversational", "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return json.dumps(_search())

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None,
                        worker_call=False):
        await executor("search_legislation", {"query": "widget"})
        return {"role": "assistant", "content": "The Widget Order 1901 No 2 applies."}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        result = await run_worker_agent(chat_loop, lambda *a, **k: None, "q", "test-model",
                                        None, 0)
    finally:
        set_request_provider_config({})
    assert [s["title"] for s in result["sources"]] == ["Widget Order 1901 No 2"]
    assert [(s["_lid"], s["_kept"]) for s in result["retrieved_sources"]] == [
        ("ssi/1901/1", False), ("ssi/1901/2", True)]


def _worker_result(report, retrieved, searches=()):
    return {"content": report, "searches": list(searches),
            "sources": [{**_pub(s), "n": i + 1} for i, s in enumerate(
                [s for s in retrieved if s["_kept"]])],
            "retrieved_sources": retrieved}


async def _manager_turn(answer, retrieved, searches=(), mode="legislation_only"):
    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": mode, "model": "test-model",
        "_tool_memo_enabled": False, "_chat_mode": "conversational",
    })

    async def worker(*a, **kw):
        return _worker_result("Nothing on point was found.", retrieved, searches)

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        return {"role": "assistant", "content": answer}

    try:
        return await process_user_request(manager, worker, [{"role": "user", "content": "q"}],
                                          "test-model", None, None, 0)
    finally:
        set_request_provider_config({})


@pytest.mark.asyncio
async def test_the_manager_path_readmits_a_source_the_answer_cites():
    retrieved = [_leg("ssi/1901/3", "Widget Order 1901"), _leg("ssi/1901/4", "Gadget Order 1901")]
    result = await _manager_turn("The Widget Order 1901 (SSI 1901/3) applies.", retrieved)
    assert [(s["cite"], s["n"]) for s in result["sources"]] == [("ssi/1901/3", 1)]


@pytest.mark.asyncio
async def test_the_manager_path_adds_nothing_the_answer_does_not_cite():
    result = await _manager_turn("Nothing on point.", [_leg("ssi/1901/3", "Widget Order 1901")])
    assert "sources" not in result


@pytest.mark.asyncio
async def test_the_manager_path_does_not_read_the_scope_footer():
    """The footer names what was searched, in code's words; it is appended after."""
    title = "Widget Order 1901"
    searches = [{"tool": "search_legislation", "query": title, "legislation_id": "",
                 "shown": 1, "matched": 1}]
    assert title.lower() in answer_scope_footer(searches, {}).lower()
    result = await _manager_turn("Nothing on point.", [_leg("ssi/1901/3", title)], searches)
    assert title.lower() in result["content"].lower()
    assert "sources" not in result


@pytest.mark.asyncio
async def test_the_manager_path_is_off_on_the_parliamentary_bot():
    result = await _manager_turn("The Widget Order 1901 applies.",
                                 [_leg("ssi/1901/3", "Widget Order 1901")],
                                 mode="parliamentary_records")
    assert "sources" not in result


_PLAN = {"scope_note": "", "steps": [{"id": 1, "title": "Order", "detail": "The order."},
                                     {"id": 2, "title": "Changes", "detail": "Its changes."}]}


async def _dr(report_text, per_step):
    steps = iter(per_step)

    async def run_worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                         emit_tool_details=False, timing_collector=None,
                         tool_memo=None, retrieved_urls=None):
        return _worker_result("f", next(steps))

    async def synthesis(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, **kw):
        return {"role": "assistant", "content": report_text}

    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "model": "test-model", "_tool_memo_enabled": False})
    try:
        return await run_deep_research(synthesis, run_worker, _PLAN,
                                       [{"role": "user", "content": "q"}],
                                       "test-model", None, None, 0)
    finally:
        set_request_provider_config({})


@pytest.mark.asyncio
async def test_the_deep_research_path_readmits_across_steps():
    kept = _leg("ssi/1901/1", "Sprocket Order 1901", kept=True)
    step1 = [kept, _leg("ssi/1901/3", url="http://www.legislation.gov.uk/id/ssi/1901/3")]
    step2 = [_leg("ssi/1901/1", url="http://www.legislation.gov.uk/id/ssi/1901/1"),
             _leg("ssi/1901/4", "Gadget Order 1901")]
    result = await _dr("The Sprocket Order 1901 was changed by ssi/1901/1 and ssi/1901/3.",
                       [step1, step2])
    assert [s["cite"] for s in result["sources"]] == ["ssi/1901/1", "ssi/1901/3"]
    assert [s["n"] for s in result["sources"]] == [1, 2]
