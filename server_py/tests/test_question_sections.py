"""P3.52 Fix 1: provisions ranked, by code, against the lawyer's own words.

After the quick-lookup Worker's FIRST `search_legislation` of a run, code runs
one `search_legislation_sections` per Act in that result (at most three) with
the lawyer's latest message as the query, and appends the top three provisions
of each to that result. Q17's own words put s.38 of the Transport (Scotland)
Act 2001 third in that Act's section search, where the Worker's own queries
mostly never search the 2001 Act's sections (7 of 16 runs).

Pinned here: the gate (conversational, legislation research types, enough
words, the run's first search only); what the block holds and where it sits
(before the NEXT STEP nudge); that the code calls are charged to no budget,
add nothing to the Sources rail, are recorded as code section searches and
make their shown URLs retrieved URLs; the request memo; fail-soft paths; and
the size bound below P1.8's.

Every Act here other than Q17's is synthetic. No test reaches the network:
LEX is `executor._request_with_retry`, replaced.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import agent_core  # noqa: E402
from src.agent.agent_core import run_worker_agent  # noqa: E402
from src.agent.agent_shared import run_worker_tool  # noqa: E402
from src.agent.provider_factory import TOOL_RESULT_HEADROOM, set_request_provider_config  # noqa: E402
from src.agent.summarisation import SUMMARISE_THRESHOLD_CHARS  # noqa: E402
from src.agent.tools import executor  # noqa: E402
from src.utils import question_sections as qs  # noqa: E402
from src.utils.citation_links import harvest_legislation_urls  # noqa: E402
from src.utils.discovery_budget import new_search_budget  # noqa: E402
from src.utils.search_scope import worker_scope_block  # noqa: E402

Q17 = "What provision enables Scottish Ministers to establish a national bus fare cap scheme?"
A2001, A2005, SI = "asp/2001/2", "asp/2005/12", "ssi/2006/107"
U = "http://www.legislation.gov.uk/id"


def _search(*ids):
    return json.dumps({"results": [
        {"legislation_id": i, "title": {A2001: "Transport (Scotland) Act 2001",
                                        A2005: "Transport (Scotland) Act 2005"}.get(i, f"Title {i}"),
         "url": f"{U}/{i}", "text_version": "revised", "year": 2001, "extent": ["Scotland"]}
        for i in ids], "total": 106, "returned": len(ids), "total_matched": 106})


def _rows(lid, numbers):
    return [{"legislation_id": f"{U}/{lid}", "provision_type": "section", "number": n,
             "title": f"Heading {n}", "uri": f"{U}/{lid}/section/{n or '33A'}",
             "text": f"Section {n or '33A'}) **Heading {n}**\n\n1) The Scottish Ministers may do {n}."}
            for n in numbers]


SECTIONS = {
    A2001: _rows(A2001, ["68", "41", "38", "3C", "70"]),
    A2005: _rows(A2005, ["40", "10", "41", "42"]),
}


@pytest.fixture(autouse=True)
def _clean_request_state():
    yield
    set_request_provider_config({})


@pytest.fixture
def lex(monkeypatch):
    """The fake LEX: section searches answered from SECTIONS, every call kept."""
    seen = {"calls": [], "fail": set(), "delay": 0.0}

    async def fake(client, method, url, *, name="", **kwargs):
        body = kwargs.get("json") or {}
        seen["calls"].append((url, dict(body)))
        if seen["delay"]:
            await asyncio.sleep(seen["delay"])
        lid = body.get("legislation_id")
        if lid in seen["fail"]:
            return httpx.Response(500, json={"detail": "boom"}, request=httpx.Request(method, url))
        return httpx.Response(200, json=SECTIONS.get(lid, []), request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    return seen


def _cfg(**over):
    cfg = {"_provider": "openrouter", "_research_mode": "legislation_only",
           "_chat_mode": "conversational", "_cache_key_query": Q17,
           "_local_prompt_cache_enabled": False}
    cfg.update(over)
    set_request_provider_config(cfg)
    return cfg


def _tool(monkeypatch, raw, query=Q17, **kw):
    """run_worker_tool on a search_legislation whose executor returns `raw`
    (the code section searches still go through the real executor)."""
    from src.agent import agent_shared
    real = agent_shared.execute_worker_tool

    async def exec_(name, args, on_chunk=None, timing_collector=None):
        if name == "search_legislation":
            return raw
        return await real(name, args, on_chunk=on_chunk, timing_collector=timing_collector)

    monkeypatch.setattr(agent_shared, "execute_worker_tool", exec_)
    state = {"log": [], "urls": set(), "sources": [], "budget": {"used": 0, "limit": 250_000},
             "search_budget": new_search_budget("legislation_only")}
    state.update(kw.pop("state", {}))
    out = asyncio.run(run_worker_tool(
        "search_legislation", {"query": "bus fares"}, "the brief", lambda *a, **k: None, "m",
        search_log=state["log"], retrieved_urls=state["urls"], source_accumulator=state["sources"],
        context_budget=state["budget"], search_budget=state["search_budget"],
        question_sections_query=query, **kw))
    return out, state


# --- 1. the gate -------------------------------------------------------------


@pytest.mark.parametrize("research_mode", ["legislation_only", "legislation_and_case_law"])
def test_a_conversational_legislation_question_is_the_query(research_mode):
    assert qs.question_query(Q17, research_mode, "conversational") == Q17


@pytest.mark.parametrize("research_mode,chat_mode", [
    ("legislation_only", "research"), ("legislation_only", "deep_research"),
    ("legislation_only", None), ("case_law_only", "conversational"),
    ("parliamentary_records", "conversational"), ("westminster_records", "conversational"),
    ("drafting", "conversational"),
])
def test_nowhere_else(research_mode, chat_mode):
    assert qs.question_query(Q17, research_mode, chat_mode) == ""


@pytest.mark.parametrize("question", [None, "", "   ", 7, "and Wales?", "This is not correct.",
                                      "SSI 2025/119", "Is the Scotland Act 1998 in force?"])
def test_no_message_or_too_few_words_is_no_query(question):
    assert qs.question_query(question, "legislation_only", "conversational") == ""


def test_a_long_message_is_cut_at_a_word():
    q = ("ministers grant buses fares " * 100).strip() + " tail"
    got = qs.question_query(q, "legislation_only", "conversational")
    assert len(got) <= qs.MAX_QUERY_CHARS and got.endswith(("ministers", "grant", "buses", "fares"))
    assert q.startswith(got) and q[len(got)] == " "


# --- 2. the pieces -----------------------------------------------------------


def test_acts_only_in_order_at_most_three_each_once():
    raw = _search(SI, A2005, "ukpga/2005/14", A2005, A2001, "asp/2019/17")
    assert [a for a, _ in qs.acts_in(raw)] == [A2005, "ukpga/2005/14", A2001]
    assert qs.acts_in(_search(SI)) == []
    assert qs.acts_in("Error executing tool: 500") == []


@pytest.mark.parametrize("row,label", [
    ({"provision_type": "section", "number": "38", "url": f"{U}/{A2001}/section/38"}, "s.38"),
    ({"provision_type": "section", "number": None, "url": f"{U}/ukpga/1987/26/section/33A"}, "s.33A"),
    ({"provision_type": "schedule", "number": "2", "url": f"{U}/{A2001}/schedule/2"}, "Sch. 2"),
    ({"provision_type": "", "number": None, "url": f"{U}/{A2001}"}, ""),
])
def test_the_label(row, label):
    assert qs.provision_label(row) == label


def test_top_three_with_the_heading_line_taken_off_the_opening():
    got = qs.top_provisions(json.dumps({"results": [
        dict(r, url=r["uri"]) for r in SECTIONS[A2001]]}))
    assert [p["label"] for p in got] == ["s.68", "s.41", "s.38"]
    assert got[2]["opening"] == "1) The Scottish Ministers may do 38."
    assert got[2]["url"] == f"{U}/{A2001}/section/38"


def test_the_opening_is_cut_at_a_word():
    long = {"results": [{"url": "u", "title": "H", "text": "x " * 400}]}
    assert len(qs.top_provisions(json.dumps(long))[0]["opening"]) <= qs.OPENING_CHARS + 2


def test_the_block_wording():
    block = qs.render_block([(A2001, "Transport (Scotland) Act 2001", [
        {"label": "s.38", "heading": "Grants to bus service operators",
         "url": f"{U}/{A2001}/section/38", "opening": "1) The Scottish Ministers may make grants."}])])
    assert block == (
        "\n\n[PROVISIONS RANKED AGAINST THE LAWYER'S OWN WORDS — after this search, code "
        "searched within the Act below, using the lawyer's latest message as written as the "
        "query, and lists the provisions the index ranked first. The index ranks by meaning, "
        "not by what a provision does: none of these is established as relevant to the "
        "question, and a provision not listed is not established as irrelevant. Before citing "
        "one, read it in full (search_legislation_sections) and cite it for what its own words "
        "provide.]\n"
        "Transport (Scotland) Act 2001 (asp/2001/2):\n"
        "  - s.38 Grants to bus service operators — "
        "http://www.legislation.gov.uk/id/asp/2001/2/section/38 — "
        "\"1) The Scottish Ministers may make grants.\"\n"
        "[/PROVISIONS RANKED AGAINST THE LAWYER'S OWN WORDS]")
    assert qs.render_block([(A2001, "T", [])]) == ""


def test_the_worst_case_block_is_well_below_p18s_bound():
    prov = {"label": "s.9999ZZ", "heading": "h" * qs._HEADING_CHARS + " …",
            "url": "http://www.legislation.gov.uk/id/ukpga/Edw7/4/31/section/9999ZZ" + "x" * 40,
            "opening": "o" * qs.OPENING_CHARS + " …"}
    block = qs.render_block([(f"ukpga/2000/{i}", "t" * qs._TITLE_CHARS, [prov] * qs.PER_ACT)
                             for i in range(qs.MAX_ACTS)])
    assert len(block) < 6_000 < SUMMARISE_THRESHOLD_CHARS + TOOL_RESULT_HEADROOM


# --- 3. run_worker_tool --------------------------------------------------------


def test_the_block_follows_the_first_search_and_the_imperative_stays_last(monkeypatch, lex):
    _cfg()
    out, st = _tool(monkeypatch, _search(SI, A2005, A2001))
    head, _, tail = out.partition(qs.BLOCK_OPEN)
    assert tail, "no block"
    assert "Transport (Scotland) Act 2005 (asp/2005/12):" in tail
    assert f"- s.38 Heading 38 — {U}/{A2001}/section/38" in tail
    assert "section/3C" not in tail and "section/42" not in tail          # top three only
    assert tail.index(qs.BLOCK_CLOSE) < tail.index("[NEXT STEP:")
    assert out.rstrip().endswith("]") and out.rfind("[NEXT STEP:") > out.rfind(qs.BLOCK_CLOSE)
    # one call per Act, the SI not searched, the lawyer's words as the query
    sec = [b for u, b in lex["calls"] if u.endswith("/legislation/section/search")]
    assert sorted(b["legislation_id"] for b in sec) == [A2001, A2005]
    assert all(b["query"] == Q17 and b["size"] == 10 for b in sec)


def test_what_the_code_calls_leave_alone_and_what_they_record(monkeypatch, lex):
    _cfg()
    plain, st0 = _tool(monkeypatch, _search(A2005, A2001), query="")
    out, st = _tool(monkeypatch, _search(A2005, A2001))
    start = out.index("\n\n" + qs.BLOCK_OPEN)
    end = out.index(qs.BLOCK_CLOSE) + len(qs.BLOCK_CLOSE)
    assert out[:start] + out[end:] == plain           # the block is the only change
    # no budget: P3.1's per-instrument section rounds untouched
    assert ({k: v for k, v in st["search_budget"].items() if k != "id"}
            == {k: v for k, v in st0["search_budget"].items() if k != "id"})
    assert not st["search_budget"].get("section_rounds")
    # nothing added to the Sources rail
    assert st["sources"] == st0["sources"]
    # the scope record: two code section searches, after the search itself
    code = [e for e in st["log"] if e.get("by_code") == qs.ENTRY_SOURCE]
    assert [(e["tool"], e["legislation_id"], e["shown"]) for e in code] == [
        ("search_legislation_sections", A2005, 3), ("search_legislation_sections", A2001, 3)]
    assert [e for e in st["log"] if not e.get("by_code")] == st0["log"]
    # the URLs the block shows are retrieved, the ones it does not are not
    shown = [f"{U}/{A2005}/section/{n}" for n in ("40", "10", "41")] + [
        f"{U}/{A2001}/section/{n}" for n in ("68", "41", "38")]
    assert st["urls"] - st0["urls"] == harvest_legislation_urls(
        json.dumps({"results": [{"url": u} for u in shown]}))
    assert not any("section/3C" in u or "section/42" in u for u in st["urls"])
    # the context budget is charged with the whole result, block included
    assert st["budget"]["used"] == len(out) > st0["budget"]["used"]


def test_the_manager_block_says_code_searched_within_those_acts(monkeypatch, lex):
    _cfg()
    _, st = _tool(monkeypatch, _search(A2005, A2001))
    assert "Searched within 2 instrument(s) for specific provisions: asp/2005/12, asp/2001/2" \
        in worker_scope_block(st["log"])


def test_without_a_query_no_call_is_made(monkeypatch, lex):
    _cfg()
    out, _ = _tool(monkeypatch, _search(A2005, A2001), query="")
    assert qs.BLOCK_OPEN not in out
    assert lex["calls"] == []


def test_a_result_with_no_act_gets_no_block(monkeypatch, lex):
    _cfg()
    out, st = _tool(monkeypatch, _search(SI))
    plain, _ = _tool(monkeypatch, _search(SI), query="")
    assert out == plain and lex["calls"] == []


def test_a_failed_section_search_drops_that_act_only(monkeypatch, lex):
    _cfg()
    lex["fail"].add(A2005)
    out, st = _tool(monkeypatch, _search(A2005, A2001))
    assert "(asp/2001/2):" in out and "(asp/2005/12):" not in out
    assert "within the Act below" in out


def test_every_section_search_failing_leaves_the_result_unchanged(monkeypatch, lex):
    _cfg()
    lex["fail"].update({A2005, A2001})
    out, st = _tool(monkeypatch, _search(A2005, A2001))
    set_request_provider_config({})
    _cfg()
    plain, st0 = _tool(monkeypatch, _search(A2005, A2001), query="")
    assert out == plain and st["log"] == st0["log"]


def test_a_slow_index_leaves_no_block(monkeypatch, lex):
    _cfg()
    monkeypatch.setattr(qs, "TIMEOUT_S", 0.05)
    lex["delay"] = 0.5
    out, _ = _tool(monkeypatch, _search(A2005, A2001))
    assert qs.BLOCK_OPEN not in out


def test_an_error_in_the_block_code_leaves_the_result_unchanged(monkeypatch, lex):
    _cfg()
    monkeypatch.setattr(qs, "render_block", lambda per_act: 1 / 0)
    out, _ = _tool(monkeypatch, _search(A2005, A2001))
    plain, _ = _tool(monkeypatch, _search(A2005, A2001), query="")
    assert out == plain


def test_no_block_past_the_context_budget(monkeypatch, lex):
    _cfg()
    out, _ = _tool(monkeypatch, _search(A2005, A2001),
                   state={"budget": {"used": 249_000, "limit": 250_000}})
    assert qs.BLOCK_OPEN not in out


def test_memoised_per_request(monkeypatch, lex):
    _cfg()
    first, _ = _tool(monkeypatch, _search(A2005, A2001))
    again, _ = _tool(monkeypatch, _search(A2001, A2005))
    sec = [b for u, b in lex["calls"] if u.endswith("/legislation/section/search")]
    assert len(sec) == 2 and qs.BLOCK_OPEN in again


def test_a_memo_hit_restores_the_record_and_the_urls(monkeypatch, lex):
    _cfg()
    memo = {}
    out, st = _tool(monkeypatch, _search(A2005, A2001), tool_memo=memo)
    out2, st2 = _tool(monkeypatch, _search(A2005, A2001), tool_memo=memo)
    assert out2 == out
    assert [e for e in st2["log"] if e.get("by_code")] == [e for e in st["log"] if e.get("by_code")]
    assert st["urls"] <= st2["urls"]


# --- 4. run_worker_agent: the first search of a quick-lookup run ---------------


def _agent(monkeypatch, *, calls, research_mode="legislation_only", chat_mode="conversational",
           question=Q17, parallel=False):
    cfg = {"_provider": "openrouter", "_research_mode": research_mode, "_chat_mode": chat_mode,
           "model": "test-model"}
    if question is not None:
        cfg["_cache_key_query"] = question
    set_request_provider_config(cfg)
    seen = []

    async def spy(name, args, query, *a, **kw):
        seen.append((name, kw.get("question_sections_query", "")))
        return json.dumps({"results": [], "returned": 0})

    monkeypatch.setattr(agent_core, "run_worker_tool", spy)

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None, **kw):
        if parallel:
            await asyncio.gather(*(asyncio.create_task(tool_exec(n, a)) for n, a in calls))
        else:
            for n, a in calls:
                await tool_exec(n, a)
        return {"role": "assistant", "content": "Report."}

    asyncio.run(run_worker_agent(loop, lambda *a, **k: None, "the brief", "test-model", None, 0))
    return seen


SEARCH = ("search_legislation", {"query": "bus fares"})
SECTION = ("search_legislation_sections", {"query": "fares", "legislation_id": A2001})


def test_only_the_first_search_of_the_run_carries_the_lawyers_words(monkeypatch):
    seen = _agent(monkeypatch, calls=[SECTION, SEARCH, SEARCH, SECTION])
    assert [q for n, q in seen if n == "search_legislation"] == [Q17, ""]
    assert all(q == "" for n, q in seen if n != "search_legislation")


def test_of_a_parallel_round_only_the_first_created_search_carries_it(monkeypatch):
    seen = _agent(monkeypatch, calls=[SEARCH, SEARCH, SEARCH], parallel=True)
    assert [q for _, q in seen] == [Q17, "", ""]


@pytest.mark.parametrize("kw", [
    {"chat_mode": "research"}, {"chat_mode": "deep_research"},
    {"research_mode": "case_law_only"}, {"question": None}, {"question": "and Wales?"},
    {"research_mode": "legislation_and_case_law", "chat_mode": "research"},
])
def test_never_elsewhere(monkeypatch, kw):
    seen = _agent(monkeypatch, calls=[SEARCH, SEARCH], **kw)
    assert all(q == "" for _, q in seen)


def test_a_legislation_and_case_law_conversational_run_gets_it(monkeypatch):
    seen = _agent(monkeypatch, calls=[SEARCH], research_mode="legislation_and_case_law")
    assert seen == [("search_legislation", Q17)]
