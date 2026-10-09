"""P4.24 (B8), batch 12 D: a Sources-rail entry titled with a bare id gets its title in code.

`utils/rail_titles.py` (pure), `made_under_store.titles_for` / `majority_act_titles`
(the record, no database until it is loaded), `agent_core.title_rail_sources`
and its wiring: `run_worker_agent` carries out the titles its lookups returned,
and the Manager and Deep Research paths title the rail after P4.3's lever R.
Nothing is invented: an entry with no exact title keeps its id. Synthetic ids
and titles only ("Widget Order 1901", `ssi/1901/3`).
"""
import asyncio
import json

import pytest

import src.database as db
import src.services.made_under_store as store
from src.agent.agent_core import (
    process_user_request,
    run_deep_research,
    run_worker_agent,
    title_rail_sources,
)
from src.agent.provider_factory import set_request_provider_config
from src.utils import rail_titles as rt

ID_URL = "https://www.legislation.gov.uk/id/"


def _src(lid, title=None, kept=True, url=None, **kw):
    return {"_lid": lid, "kind": "Statute", "title": title or lid, "cite": lid,
            "url": "" if url is None else url, "_kept": kept, **kw}


def _entry(lid, url=""):
    """A rail entry as the rail holds it: public keys, titled with its id."""
    return {"kind": "Statute", "title": lid, "cite": lid, "url": url, "n": 1}


# --- the pure helpers --------------------------------------------------------------------

@pytest.mark.parametrize("title, lid", [
    ("ssi/1901/3", "ssi/1901/3"), ("eur/1901/3", "eur/1901/3"),
    ("ukpga/Edw7/1/9", "ukpga/Edw7/1/9"), (" ssi/1901/3 ", "ssi/1901/3"),
    ("Widget Order 1901", ""), ("ssi/1901/3, s.2", ""), ("x ssi/1901/3", ""), ("ssi/1901", ""),
    ("", ""), (None, ""),
])
def test_bare_id(title, lid):
    assert rt.bare_id(title) == lid


def test_id_url_only_for_an_id():
    assert rt.id_url("ssi/1901/3") == ID_URL + "ssi/1901/3"
    assert rt.id_url("Widget Order 1901") == ""


@pytest.mark.parametrize("title, out", [
    ("Widget Order 1901", "Widget Order 1901"), ("  Widget Order 1901 ", "Widget Order 1901"),
    ("", ""), (None, ""), ("ssi/1901/3", ""), ("A Very Long Widget Title 1901 …", ""),
    # an instrument title names a year: a section heading LEX once returned as a title does not
    ("Short title, commencement, and extent.", ""), ("Widget Order 19011", ""),
    ("Widget Order 21901", ""),
    ("Widget Order (No. 2) 2026", "Widget Order (No. 2) 2026"),
])
def test_exact_title(title, out):
    assert rt.exact_title(title) == out


def test_in_turn_titles_first_real_title_then_lookups():
    retrieved = [_src("ssi/1901/3"),                                  # titled by its id: skipped
                 _src("ssi/1901/3", "Widget Order 1901"),
                 _src("ssi/1901/3", "Widget Order 1901 (later)"),     # the first one wins
                 _src("ssi/1901/4", "Gadget Order 1901")]
    lookups = {"ssi/1901/4": "Gadget Order 1901 (lookup)",            # a source's title wins
               "ssi/1901/5": "Sprocket Order 1901",
               "ssi/1901/6": "ssi/1901/6", "ssi/1901/7": "Cut short 1901 …"}
    assert rt.in_turn_titles(retrieved, lookups) == {
        "ssi/1901/3": "Widget Order 1901", "ssi/1901/4": "Gadget Order 1901",
        "ssi/1901/5": "Sprocket Order 1901"}


def test_untitled_ids_are_what_the_record_is_asked_for():
    rail = [_entry("ssi/1901/3"), _entry("ssi/1901/4"), _entry("ssi/1901/4"),
            {"title": "Widget Order 1901", "url": "u"}]
    retrieved = [_src("ssi/1901/3", "Widget Order 1901")]
    assert rt.untitled_ids(rail, retrieved) == ["ssi/1901/4"]
    assert rt.untitled_ids(rail, retrieved, {"ssi/1901/4": "Gadget Order 1901"}) == []


def test_fill_prefers_the_turn_then_the_record_and_invents_nothing():
    rail = [_entry("ssi/1901/3"), _entry("ssi/1901/4", url="http://x/ssi/1901/4"),
            _entry("ssi/1901/5"), {"kind": "SI", "title": "Cog Order 1901", "url": ""}]
    retrieved = [_src("ssi/1901/3", "Widget Order 1901")]
    record = {"ssi/1901/3": "Record Widget Title 1901", "ssi/1901/4": "Gadget Order 1901"}
    out, titled, urled = rt.fill_rail(rail, retrieved, record)
    assert [e["title"] for e in out] == ["Widget Order 1901", "Gadget Order 1901",
                                         "ssi/1901/5", "Cog Order 1901"]
    # the URL from the id, only where there was none and only for an id-titled entry
    assert [e["url"] for e in out] == [ID_URL + "ssi/1901/3", "http://x/ssi/1901/4",
                                       ID_URL + "ssi/1901/5", ""]
    assert (titled, urled) == (2, 2)
    assert out[3] is rail[3]                        # a titled entry is passed through untouched
    assert rail[0]["title"] == "ssi/1901/3"         # the input is never mutated
    assert {k for k in out[0]} == {k for k in rail[0]}


def test_a_record_title_cut_short_is_not_used():
    out, titled, _ = rt.fill_rail([_entry("ssi/1901/3")], [], {"ssi/1901/3": "Widget Order 1901 …"})
    assert out[0]["title"] == "ssi/1901/3" and titled == 0


def test_lookup_titles_fill_too():
    out, titled, _ = rt.fill_rail([_entry("eur/1901/3")], [], {}, {"eur/1901/3": "Widget Regulation 1901"})
    assert out[0]["title"] == "Widget Regulation 1901" and titled == 1


# --- the record --------------------------------------------------------------------------

def test_majority_act_title():
    rows = [("ukpga/1901/1", "Widget Act 1901", 9), ("ukpga/1901/1", "Widgets Act 1901", 2),
            ("ukpga/1901/2", "Gadget Act 1901", 3), ("ukpga/1901/2", "Gadgets Act 1901", 3),
            ("ukpga/1901/3", "Sprocket Act 1901", 1), (None, "Cog Act 1901", 5),
            ("ukpga/1901/4", "", 5)]
    assert store.majority_act_titles(rows) == {"ukpga/1901/1": "Widget Act 1901",
                                               "ukpga/1901/3": "Sprocket Act 1901"}


class _Session:
    """A stand-in for one database session: answers the two queries by their table."""

    def __init__(self, inst, powers, calls):
        self.inst, self.powers, self.calls = inst, powers, calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt, params):
        sql = str(stmt)
        self.calls.append((sql.split("FROM ")[1].split()[0], sorted(params["ids"])))
        rows = (self.inst if "made_under_instruments" in sql else self.powers)
        ids = set(params["ids"])
        res = [r for r in rows if r[0] in ids]

        class _R:
            def all(self_inner):
                return res
        return _R()


def _fake_db(monkeypatch, inst, powers):
    calls = []
    monkeypatch.setattr(db, "async_session_maker", lambda: _Session(inst, powers, calls))
    monkeypatch.setitem(store._STATE, "available", True)
    return calls


def test_titles_for_touches_no_database_until_the_record_is_loaded(monkeypatch):
    touched = []

    def boom():
        touched.append(1)                   # recorded: the fail-soft below would swallow a raise
        raise RuntimeError("database touched")
    monkeypatch.setattr(db, "async_session_maker", boom)
    monkeypatch.setitem(store._STATE, "available", False)
    assert asyncio.run(store.titles_for(["ssi/1901/3"])) == {}
    assert touched == []


def test_titles_for_with_no_ids_touches_no_database(monkeypatch):
    calls = _fake_db(monkeypatch, [], [])
    assert asyncio.run(store.titles_for(["", None])) == {}
    assert calls == []


def test_titles_for_instruments_then_acts(monkeypatch):
    inst = [("ssi/1901/3", "The Widget Order 1901"), ("ssi/1901/9", "")]
    powers = [("ukpga/1901/1", "Widget Act 1901", 7), ("ukpga/1901/1", "Widgets Act 1901", 1),
              ("ssi/1901/3", "Not an Act title", 50)]
    calls = _fake_db(monkeypatch, inst, powers)
    got = asyncio.run(store.titles_for(["ssi/1901/3", "/ukpga/1901/1/", "ssi/1901/9"]))
    assert got == {"ssi/1901/3": "The Widget Order 1901", "ukpga/1901/1": "Widget Act 1901"}
    # the Acts are asked for only the ids the instruments did not title
    assert calls == [("made_under_instruments", ["ssi/1901/3", "ssi/1901/9", "ukpga/1901/1"]),
                     ("made_under_powers", ["ssi/1901/9", "ukpga/1901/1"])]


def test_titles_for_skips_the_act_query_when_every_id_is_titled(monkeypatch):
    calls = _fake_db(monkeypatch, [("ssi/1901/3", "The Widget Order 1901")], [])
    assert asyncio.run(store.titles_for(["ssi/1901/3"])) == {"ssi/1901/3": "The Widget Order 1901"}
    assert [c[0] for c in calls] == ["made_under_instruments"]


def test_titles_for_never_raises(monkeypatch):
    def broken():
        raise RuntimeError("no database")
    monkeypatch.setattr(db, "async_session_maker", broken)
    monkeypatch.setitem(store._STATE, "available", True)
    assert asyncio.run(store.titles_for(["ssi/1901/3"])) == {}


# --- title_rail_sources ------------------------------------------------------------------

def test_title_rail_sources_asks_the_record_only_for_what_the_turn_cannot_title(monkeypatch):
    asked = []

    async def fake(ids):
        asked.append(list(ids))
        return {"ssi/1901/4": "Gadget Order 1901"}
    monkeypatch.setattr(store, "titles_for", fake)
    rail = [_entry("ssi/1901/3"), _entry("ssi/1901/4")]
    out = asyncio.run(title_rail_sources(rail, [_src("ssi/1901/3", "Widget Order 1901")]))
    assert [e["title"] for e in out] == ["Widget Order 1901", "Gadget Order 1901"]
    assert asked == [["ssi/1901/4"]]
    asked.clear()
    asyncio.run(title_rail_sources([_entry("ssi/1901/3")], [_src("ssi/1901/3", "Widget Order 1901")]))
    assert asked == []


def test_title_rail_sources_keeps_an_empty_rail_and_fails_soft(monkeypatch):
    assert asyncio.run(title_rail_sources([], [])) == []

    async def broken(ids):
        raise RuntimeError("boom")
    monkeypatch.setattr(store, "titles_for", broken)
    rail = [_entry("ssi/1901/3")]
    assert asyncio.run(title_rail_sources(rail, [])) is rail


# --- the wiring ----------------------------------------------------------------------------

def _lookup(lid, title=None):
    d = {"tool": "lookup_legislation", "legislation_id": lid, "label": lid,
         "status": "held" if title else "not_held"}
    if title:
        d["title"] = title
    return json.dumps(d)


@pytest.mark.asyncio
async def test_run_worker_agent_hands_on_its_lookups_titles(monkeypatch):
    from src.agent import agent_shared

    set_request_provider_config({
        "_provider": "openrouter", "_research_mode": "legislation_only",
        "_chat_mode": "research", "model": "test-model", "_tool_memo_enabled": False,
    })

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        if name == "lookup_legislation":
            n = args.get("number")
            return _lookup(f"ssi/1901/{n}", "Widget Order 1901" if n == 3 else None)
        # Only a lookup's own result is read: another tool's result is never parsed as one.
        return _lookup("ssi/1901/9", "Not A Lookup Title")

    async def chat_loop(messages, model, cancel_event, num_ctx, tools, executor,
                        on_chunk=None, emit_tool_details=False, timing_collector=None,
                        worker_call=False):
        await executor("lookup_legislation", {"legislation_type": "ssi", "year": 1901, "number": 3})
        await executor("lookup_legislation", {"legislation_type": "ssi", "year": 1901, "number": 4})
        await executor("search_legislation", {"query": "widget"})
        return {"role": "assistant", "content": "Nothing on point."}

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    try:
        result = await run_worker_agent(chat_loop, lambda *a, **k: None, "q", "test-model", None, 0)
    finally:
        set_request_provider_config({})
    assert result["retrieved_titles"] == {"ssi/1901/3": "Widget Order 1901"}


def _worker_result(sources, titles):
    return {"content": "Nothing on point.", "searches": [],
            "sources": [{**{k: v for k, v in s.items() if not k.startswith("_")}, "n": i + 1}
                        for i, s in enumerate(sources)],
            "retrieved_sources": sources, "retrieved_titles": titles}


@pytest.mark.asyncio
async def test_the_manager_path_titles_the_rail(monkeypatch):
    monkeypatch.setitem(store._STATE, "available", False)          # no record: the turn titles it
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "model": "test-model", "_tool_memo_enabled": False,
                                 "_chat_mode": "conversational"})
    results = iter([_worker_result([_src("ssi/1901/3")], {}),
                    _worker_result([], {"ssi/1901/3": "Widget Order 1901"})])

    async def worker(*a, **kw):
        return next(results)

    async def manager(messages, model, cancel_event, num_ctx, tools, tool_executor,
                      on_chunk=None, **kw):
        await tool_executor("delegate_research", {"query": "q"})
        await tool_executor("delegate_research", {"query": "q2"})
        return {"role": "assistant", "content": "Nothing on point."}

    try:
        result = await process_user_request(manager, worker, [{"role": "user", "content": "q"}],
                                            "test-model", None, None, 0)
    finally:
        set_request_provider_config({})
    assert [(s["title"], s["url"]) for s in result["sources"]] == [
        ("Widget Order 1901", ID_URL + "ssi/1901/3")]


@pytest.mark.asyncio
async def test_the_deep_research_path_titles_the_rail(monkeypatch):
    monkeypatch.setitem(store._STATE, "available", False)
    plan = {"scope_note": "", "steps": [{"id": 1, "title": "A", "detail": "a"},
                                        {"id": 2, "title": "B", "detail": "b"}]}
    results = iter([_worker_result([_src("ssi/1901/3")], {}),
                    _worker_result([], {"ssi/1901/3": "Widget Order 1901"})])

    async def run_worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                         emit_tool_details=False, timing_collector=None,
                         tool_memo=None, retrieved_urls=None):
        return next(results)

    async def synthesis(messages, model, cancel_event, num_ctx, tools, tool_executor,
                        on_chunk=None, **kw):
        return {"role": "assistant", "content": "Report."}

    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "model": "test-model", "_tool_memo_enabled": False})
    try:
        result = await run_deep_research(synthesis, run_worker, plan,
                                         [{"role": "user", "content": "q"}], "test-model", None, None, 0)
    finally:
        set_request_provider_config({})
    assert [s["title"] for s in result["sources"]] == ["Widget Order 1901"]


def test_a_search_hit_titled_by_a_heading_is_not_used_but_the_record_is():
    """The stored case: LEX titled an old Act's search hit with a section heading."""
    retrieved = [_src("ukpga/Edw7/1-2/9", "Short title, commencement, and extent.")]
    rail = [_entry("ukpga/Edw7/1-2/9")]
    assert rt.untitled_ids(rail, retrieved) == ["ukpga/Edw7/1-2/9"]
    out, titled, _ = rt.fill_rail(rail, retrieved, {"ukpga/Edw7/1-2/9": "Widget Act 1901"})
    assert out[0]["title"] == "Widget Act 1901" and titled == 1
