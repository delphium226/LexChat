"""P4.26: an instrument the answer took from a lookup or a made-under list gets a rail entry.

`lookup_legislation` and `find_instruments_made_under` added no source, so an
instrument the answer named from either had no rail entry unless another tool
retrieved it (600 such instruments in 86 stored turns, none in the stored rail).
`agent_shared._extract_listed_instruments` now collects their instruments (a
lookup: held, with or without text; a made-under list: every instrument listed)
apart from the source accumulator; `run_worker_agent` hands on those no other
tool retrieved as `listed_sources` (`agent_core.listed_only`); and lever R
(`readmit_answer_sources`) reads them after every other retrieved source, so one
reaches the rail only where the ANSWER names it. The Worker seam never keeps
one (a report commonly lists all 40 of a made-under list), and nothing that
reads `retrieved_sources` (P4.23's linker, P3.51's listing, P4.24's titles)
sees them.

Synthetic text only ("Widget Order 1901", `ssi/1901/3`, "Widget (Scotland) Act 1901").
"""
import json

import pytest

from src.agent import agent_shared
from src.agent.agent_core import (
    listed_only,
    process_user_request,
    readmit_answer_sources,
    run_deep_research,
    run_worker_agent,
)
from src.agent.agent_shared import _extract_listed_instruments, run_worker_tool
from src.agent.provider_factory import set_request_provider_config
from src.utils.instrument_lookup import LOOKUP_TOOL
from src.utils.made_under import MADE_UNDER_TOOL

LEG = "https://www.legislation.gov.uk/"
ACT = "Widget (Scotland) Act 1901"


def _lookup(lid="ssi/1901/3", status="held", title="The Widget Order 1901", url=None):
    out = {"tool": LOOKUP_TOOL, "legislation_id": lid, "label": "SSI 1901/3", "status": status}
    if status in ("held", "held_without_text"):
        out.update(title=title, url=url if url is not None else LEG + lid,
                   http_status=200, text_held=status == "held")
    return out


def _made_under(n=3, start=1, title=None):
    insts = [{"legislation_id": f"ssi/1901/{i}",
              "title": title or f"The Widget Order 1901 No {i}",
              "url": f"{LEG}ssi/1901/{i}", "revocation": "none recorded",
              "revocation_status": "none"} for i in range(start, start + n)]
    return {"tool": MADE_UNDER_TOOL, "act": ACT, "section": "95", "provision": "section/95",
            "matched_act": ACT, "status": "found", "count": n, "instruments": insts}


def _listed(*results):
    out: list = []
    for name, data in results:
        _extract_listed_instruments(name, {}, json.dumps(data), out)
    return out


def _pub(s):
    return {k: v for k, v in s.items() if not k.startswith("_")}


# --- _extract_listed_instruments -----------------------------------------------------

@pytest.mark.parametrize("status", ["held", "held_without_text"])
def test_a_held_lookup_lists_its_instrument(status):
    [e] = _listed((LOOKUP_TOOL, _lookup(status=status)))
    assert e == {"_lid": "ssi/1901/3", "kind": "SI", "title": "The Widget Order 1901",
                 "cite": "ssi/1901/3", "url": LEG + "ssi/1901/3"}
    assert "excerpt" not in e, "a lookup did not read the text"


@pytest.mark.parametrize("status", ["not_held", "lookup_failed", "invalid"])
def test_a_lookup_that_does_not_establish_the_instrument_lists_nothing(status):
    assert _listed((LOOKUP_TOOL, _lookup(status=status))) == []


def test_a_lookup_with_no_title_or_url_takes_its_id():
    [e] = _listed((LOOKUP_TOOL, {**_lookup(), "title": None, "url": None}))
    assert e["title"] == "ssi/1901/3"
    assert e["url"] == LEG + "ssi/1901/3"


def test_an_act_lookup_is_an_act():
    [e] = _listed((LOOKUP_TOOL, _lookup("asp/1901/2", title=ACT)))
    assert e["kind"] == "Act"


def test_a_made_under_list_lists_every_instrument_with_what_the_record_says():
    out = _listed((MADE_UNDER_TOOL, _made_under(3)))
    assert [e["_lid"] for e in out] == ["ssi/1901/1", "ssi/1901/2", "ssi/1901/3"]
    assert {e["sub"] for e in out} == {f"recorded as made under section 95 of {ACT}"}
    assert all("excerpt" not in e for e in out)


def test_a_cut_title_is_replaced_by_the_id_for_p424_to_fill():
    [e] = _listed((MADE_UNDER_TOOL, _made_under(1, title="The Widget (Very Long) Order 19…")))
    assert e["title"] == "ssi/1901/1"


@pytest.mark.parametrize("status", ["act_not_in_record", "act_known_section_not_cited"])
def test_a_made_under_result_with_no_list_lists_nothing(status):
    assert _listed((MADE_UNDER_TOOL, {"tool": MADE_UNDER_TOOL, "status": status,
                                      "count": 0, "instruments": []})) == []


def test_one_entry_per_instrument_across_calls():
    out = _listed((MADE_UNDER_TOOL, _made_under(3)), (LOOKUP_TOOL, _lookup("ssi/1901/2")),
                  (MADE_UNDER_TOOL, _made_under(2, start=3)))
    assert [e["_lid"] for e in out] == ["ssi/1901/1", "ssi/1901/2", "ssi/1901/3", "ssi/1901/4"]
    assert out[1]["sub"].startswith("recorded as made under"), "the first entry stands"


@pytest.mark.parametrize("name,raw", [
    ("search_legislation", json.dumps({"results": [{"legislation_id": "ssi/1901/3"}]})),
    (LOOKUP_TOOL, "not json"),
    (LOOKUP_TOOL, json.dumps(["a list"])),
    (MADE_UNDER_TOOL, json.dumps({"status": "found", "instruments": ["x", None, {"title": "t"}]})),
    (MADE_UNDER_TOOL, json.dumps({"status": "found", "instruments": 7})),
    # only a "found" result lists: any other status is not a list, whatever it carries
    (MADE_UNDER_TOOL, json.dumps({**_made_under(1), "status": "act_known_section_not_cited"})),
])
def test_other_tools_and_odd_shapes_list_nothing_and_never_raise(name, raw):
    out: list = []
    _extract_listed_instruments(name, {}, raw, out)
    assert out == []


# --- listed_only and lever R -----------------------------------------------------------

def test_listed_only_leaves_an_instrument_another_tool_retrieved_to_its_own_entry():
    listed = _listed((MADE_UNDER_TOOL, _made_under(3)))
    acc = [{"_lid": "ssi/1901/2", "kind": "SI", "title": "The Widget Order 1901 No 2",
            "url": LEG + "ssi/1901/2", "cite": "ssi/1901/2"}]
    out = listed_only(listed, acc)
    assert [(e["_lid"], e["_kept"]) for e in out] == [("ssi/1901/1", False), ("ssi/1901/3", False)]
    assert listed_only(None, acc) == []        # never raises


def test_only_the_instruments_the_answer_names_of_a_forty_item_list_reach_the_rail():
    listed = listed_only(_listed((MADE_UNDER_TOOL, _made_under(40))), [])
    answer = ("Two instruments were made under section 95: SSI 1901/7 and the "
              "Widget Order 1901 No 12.")
    out = readmit_answer_sources([], listed, answer, "legislation_only")
    assert [e["cite"] for e in out] == ["ssi/1901/7", "ssi/1901/12"]
    assert readmit_answer_sources([], listed, "None was found.", "legislation_only") == []


def test_a_retrieved_source_for_the_same_instrument_wins():
    retrieved = [{"_lid": "ssi/1901/3", "kind": "SI", "title": "The Widget Order 1901",
                  "url": LEG + "ssi/1901/3", "cite": "ssi/1901/3", "sub": "Interpretation",
                  "_kept": False}]
    listed = [{**e, "_kept": False} for e in _listed((MADE_UNDER_TOOL, _made_under(3)))]
    out = readmit_answer_sources([], retrieved + listed, "Made as SSI 1901/3.", "legislation_only")
    assert out == [_pub(retrieved[0])]


# --- the wiring: run_worker_tool, run_worker_agent, the Manager and Deep Research paths --

def _cfg(**kw):
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "_chat_mode": "conversational", "model": "test-model",
                                 "_tool_memo_enabled": False, **kw})


@pytest.mark.asyncio
async def test_run_worker_tool_lists_on_a_memo_hit_too(monkeypatch):
    calls = []

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, **kw):
        calls.append(name)
        return json.dumps(_lookup())

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    _cfg(_tool_memo_enabled=True)
    memo: dict = {}
    first, second, acc = [], [], []
    try:
        for into in (first, second):
            await run_worker_tool(LOOKUP_TOOL, {"legislation_id": "ssi/1901/3"}, "q",
                                  lambda *a, **k: None, "m", source_accumulator=acc,
                                  tool_memo=memo, listed_accumulator=into)
    finally:
        set_request_provider_config({})
    assert calls == [LOOKUP_TOOL], "the second call was a memo hit"
    assert [e["_lid"] for e in first] == [e["_lid"] for e in second] == ["ssi/1901/3"]
    assert acc == [], "a lookup still adds nothing to the accumulator"


@pytest.mark.asyncio
async def test_run_worker_tool_without_a_listed_accumulator_is_unchanged(monkeypatch):
    async def fake_exec(name, args, on_chunk=None, timing_collector=None, **kw):
        return json.dumps(_lookup())

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    _cfg()
    acc: list = []
    try:
        await run_worker_tool(LOOKUP_TOOL, {"legislation_id": "ssi/1901/3"}, "q",
                              lambda *a, **k: None, "m", source_accumulator=acc)
    finally:
        set_request_provider_config({})
    assert acc == []


def _search():
    return {"results": [{"legislation_id": "ssi/1901/2", "title": "The Widget Order 1901 No 2",
                         "url": LEG + "ssi/1901/2", "text_version": "revised", "year": 1901,
                         "extent": ["Scotland"]}],
            "returned": 1, "total": 1, "total_matched": 1, "removed_by_filters": 0}


@pytest.mark.asyncio
async def test_run_worker_agent_hands_on_listed_instruments_apart(monkeypatch):
    async def fake_exec(name, args, on_chunk=None, timing_collector=None, **kw):
        return json.dumps({MADE_UNDER_TOOL: _made_under(3),
                           "search_legislation": _search()}[name])

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, **kw):
        await executor(MADE_UNDER_TOOL, {"act": ACT, "section": "95"})
        await executor("search_legislation", {"query": "widget"})
        # The report names every listed instrument: the Worker seam keeps none of them.
        return {"role": "assistant",
                "content": "Made under s.95: SSI 1901/1, SSI 1901/2 and SSI 1901/3."}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    _cfg()
    try:
        result = await run_worker_agent(chat_loop, lambda *a, **k: None, "q", "test-model",
                                        None, 0)
    finally:
        set_request_provider_config({})
    assert [s["cite"] for s in result["sources"]] == ["ssi/1901/2"]
    assert [s["_lid"] for s in result["retrieved_sources"]] == ["ssi/1901/2"]
    assert [(s["_lid"], s["_kept"]) for s in result["listed_sources"]] == [
        ("ssi/1901/1", False), ("ssi/1901/3", False)]


@pytest.mark.asyncio
async def test_a_worker_with_only_a_lookup_hands_on_no_rail_source(monkeypatch):
    async def fake_exec(name, args, on_chunk=None, timing_collector=None, **kw):
        return json.dumps(_lookup())

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, **kw):
        await executor(LOOKUP_TOOL, {"legislation_id": "ssi/1901/3"})
        return {"role": "assistant", "content": "The Widget Order 1901 is held."}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    _cfg()
    try:
        result = await run_worker_agent(chat_loop, lambda *a, **k: None, "q", "test-model",
                                        None, 0)
    finally:
        set_request_provider_config({})
    assert "sources" not in result and "retrieved_sources" not in result
    assert [s["_lid"] for s in result["listed_sources"]] == ["ssi/1901/3"]


async def _manager_turn(answer, listed, retrieved=(), mode="legislation_only"):
    _cfg(_research_mode=mode)

    async def worker(*a, **kw):
        return {"content": "Report.", "searches": [], "retrieved_sources": list(retrieved),
                "listed_sources": list(listed)}

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
async def test_the_manager_path_lists_an_instrument_the_answer_names():
    listed = listed_only(_listed((MADE_UNDER_TOOL, _made_under(3))), [])
    result = await _manager_turn("The Widget Order 1901 No 2 was made under s.95.", listed)
    assert [(s["cite"], s["n"]) for s in result["sources"]] == [("ssi/1901/2", 1)]
    assert result["sources"][0]["sub"] == f"recorded as made under section 95 of {ACT}"


@pytest.mark.asyncio
async def test_the_manager_path_prefers_another_tool_s_entry_for_the_same_instrument():
    """A search hit from another delegation, not kept there, is the entry that goes in."""
    listed = listed_only(_listed((MADE_UNDER_TOOL, _made_under(3))), [])
    retrieved = [{"_lid": "ssi/1901/2", "kind": "SI", "title": "The Widget Order 1901 No 2",
                  "url": LEG + "ssi/1901/2", "cite": "ssi/1901/2", "meta": "revised",
                  "_kept": False}]
    result = await _manager_turn("Made as SSI 1901/2.", listed, retrieved)
    assert [(s["cite"], s.get("meta"), s.get("sub")) for s in result["sources"]] == [
        ("ssi/1901/2", "revised", None)]


@pytest.mark.asyncio
async def test_a_cut_title_is_restored_before_the_naming_test(monkeypatch):
    """The made-under list cuts a long title; the entry takes its id, and P4.24's fill
    (the made-under record) gives it the full title before lever R reads the answer,
    which names the instrument by its title alone."""
    from src.services import made_under_store

    full = "The Widget (Very Long Title Indeed) (Scotland) Order 1901"
    asked = []

    async def titles_for(ids):
        asked.append(sorted(ids))
        return {"ssi/1901/1": full}

    monkeypatch.setattr(made_under_store, "titles_for", titles_for)
    listed = listed_only(_listed((MADE_UNDER_TOOL, _made_under(1, title=full[:30] + "…"))), [])
    assert listed[0]["title"] == "ssi/1901/1"
    result = await _manager_turn(f"{full} was made under s.95.", listed)
    assert asked and asked[0] == ["ssi/1901/1"]
    assert [(s["cite"], s["title"]) for s in result["sources"]] == [("ssi/1901/1", full)]


@pytest.mark.asyncio
async def test_the_manager_path_lists_nothing_the_answer_does_not_name():
    listed = listed_only(_listed((MADE_UNDER_TOOL, _made_under(3))), [])
    assert "sources" not in await _manager_turn("No instrument was found.", listed)


@pytest.mark.asyncio
async def test_the_manager_path_is_off_on_the_parliamentary_bot():
    listed = listed_only(_listed((LOOKUP_TOOL, _lookup())), [])
    result = await _manager_turn("The Widget Order 1901 applies.", listed,
                                 mode="parliamentary_records")
    assert "sources" not in result


_PLAN = {"scope_note": "", "steps": [{"id": 1, "title": "List", "detail": "The list."},
                                     {"id": 2, "title": "Order", "detail": "The order."}]}


@pytest.mark.asyncio
async def test_the_deep_research_path_lists_across_steps_once():
    per_step = iter([listed_only(_listed((MADE_UNDER_TOOL, _made_under(3))), []),
                     listed_only(_listed((LOOKUP_TOOL, _lookup("ssi/1901/3"))), [])])

    async def run_worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                         emit_tool_details=False, timing_collector=None,
                         tool_memo=None, retrieved_urls=None):
        return {"content": "f", "searches": [], "listed_sources": next(per_step)}

    async def synthesis(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, **kw):
        return {"role": "assistant",
                "content": "SSI 1901/3 and the Widget Order 1901 No 1 were made under s.95."}

    _cfg(_chat_mode="deep_research")
    try:
        result = await run_deep_research(synthesis, run_worker, _PLAN,
                                         [{"role": "user", "content": "q"}],
                                         "test-model", None, None, 0)
    finally:
        set_request_provider_config({})
    assert [s["cite"] for s in result["sources"]] == ["ssi/1901/1", "ssi/1901/3"]
