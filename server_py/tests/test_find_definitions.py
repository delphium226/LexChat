"""FIX_PLAN P3.34: `find_definitions`, one corpus-wide search for where a term is defined.

No network: the executor's `_request_with_retry` and the summariser are stubbed.
The rows are synthetic, in the shape `/legislation/section/search` returns
(`notes/batch13_G.md`); the live check is in the gitignored evidence folder.
"""
import asyncio
import json

import httpx
import pytest

from src.agent import agent_shared
from src.agent.agent_shared import run_worker_tool
from src.agent.tools import executor
from src.agent.tools.schemas import (
    QUICK_LOOKUP_WITHHELD_TOOLS,
    get_worker_tools,
    withheld_tool_result,
)
from src.utils import definitions as D
from src.utils import search_scope as ss
from src.utils.discovery_budget import (
    LEGISLATION_DISCOVERY_TOOLS,
    legislation_stop_message,
)

TOOL = D.DEFINITIONS_TOOL
LEX = "http://www.legislation.gov.uk/id/"


def _row(lid, text, prov="section/2", extent=None):
    return {"legislation_id": LEX + lid, "uri": f"{LEX}{lid}/{prov}", "id": f"{LEX}{lid}/{prov}",
            "title": "Interpretation", "text": text, "extent": extent if extent is not None else [],
            "provision_type": prov.split("/")[0], "number": 2}


# --- (1) the filter: the quoted term followed by a defining verb ---------------

@pytest.mark.parametrize("text", [
    '“shop” means any premises where a trade is carried on',
    '"shop" includes any premises',
    "'Shop' means a shop as defined by the Shops Act 1912",
    "‘shop’ means a place of retail sale",                       # EU annex quotes
    '"shop" has the meaning given in section 2 of the 1950 Act',
    '"shop" has the same meaning as in the Shops Act 1950.',
    '“shop” (except in Schedule 2) means any premises',
    '“shop” (“siop”) means any premises',                         # bilingual
    '"shop," and "shop assistant" have respectively the same meanings as in the 1912 Act',
    'the expressions "local authority," "shop" and "shop assistant" have respectively '
    'the same meanings as in the Shops Act, 1912',
    '“shop”, in relation to premises, means a building',
    '"shops" means retail premises',                              # plural
    '"shop" refers to premises used for retail sale',
    '"shop" shall be construed as including a kiosk',
])
def test_a_definition_of_the_term_is_kept(text):
    assert D.defining_match(text, "shop")


@pytest.mark.parametrize("text", [
    'a shop means nothing here',                                  # not quoted
    '“shop premises” means premises to which the 1963 Act applies',  # a longer term
    'the word "shop" appears in this Act. "place" means x',
    'in the definition of "shop", for "premises" substitute "building"; "x" means y',
    '"shop" were omitted and "place" means x',
    '',
])
def test_anything_else_is_not(text):
    assert not D.defining_match(text, "shop")


@pytest.mark.parametrize("term,text", [
    ("acquiring authority", '“acquiring authority” means a Minister'),
    ("acquiring authority", '"acquiring\n authority" means a Minister'),  # a line break
    ("dwelling-house", '“dwelling‑house” means a house'),                 # another hyphen
    ("occupier's interest", "“occupier’s interest” means the interest"),  # curly apostrophe
    ("occupier's interest", "\"occupier's interest\" includes a lease"),
])
def test_multi_word_hyphen_and_apostrophe_terms(term, text):
    assert D.defining_match(text, term)


def test_a_longer_term_is_found_apart_and_the_bare_term_is_not_one():
    text = ('"shop" means a building; "shop assistant" means a person employed in a shop; '
            '"large shop" means a shop over 280 square metres.')
    phrases = [p for p, _ in D.longer_term_matches(text, "shop")]
    assert phrases == ["shop assistant", "large shop"]
    # Straight quotes on either side of other words never join into one phrase.
    assert D.longer_term_matches("'sheriff substitute'; the term 'shop' shall include x",
                                 "shop") == []


def test_the_query_is_the_measured_one():
    assert D.definitions_query(" “shop” ") == '"shop" means'


# --- (2) the result ---------------------------------------------------------

def _rows():
    return [
        _row("ukpga/1950/28", 'In this Act— "shop" means any premises where retail trade is '
             'carried on; "retail trade" includes the business of a barber.', "section/74"),
        _row("ukpga/1950/28", '"shop" includes a kiosk.', "section/75"),
        _row("asp/2007/13", '“shop” means any premises within a building', "section/7",
             ["Scotland"]),
        _row("ukpga/1994/20", '“shop” means any premises where there is carried on a trade',
             "schedule/1", ["England", "Wales"]),
        _row("nisr/2012/246", '“shop” means any premises', "regulation/2"),
        _row("ssi/2013/85", 'In this regulation “duty free shop” means an export shop.',
             "regulation/2"),
        _row("[UNCLEAR: no document reference provided]", '"shop" has the same meaning as in '
             'the Shops Act 1912.', "section/15"),
        _row("uksi/2010/863", "this row mentions a shop but defines nothing", "regulation/3"),
    ]


def test_one_entry_per_instrument_in_the_order_returned():
    d = D.build_result(_rows(), "shop")
    ids = [e["legislation_id"] for e in d["definitions"]]
    assert ids == ["ukpga/1950/28", "asp/2007/13", "ukpga/1994/20", "nisr/2012/246",
                   "[UNCLEAR: no document reference provided]"]
    assert d["count"] == d["listed"] == 5 and d["rows_read"] == 8
    first = d["definitions"][0]
    assert first["definition"].startswith('"shop" means any premises where retail trade')
    assert "retail trade\" includes" not in first["definition"]       # cut at the next one
    assert first["url"].endswith("ukpga/1950/28/section/74")
    assert first["provision"] == "section 74"
    assert first["also_defined_in"] == [LEX + "ukpga/1950/28/section/75"]


def test_extent_is_stated_or_not_stated():
    by = {e["legislation_id"]: e for e in D.build_result(_rows(), "shop")["definitions"]}
    assert by["asp/2007/13"]["extent"] == "Scotland"
    assert by["ukpga/1994/20"]["extent"] == "England, Wales"
    assert by["ukpga/1950/28"]["extent"] == "not stated"


def test_longer_terms_are_listed_apart_with_no_completeness_claim():
    d = D.build_result(_rows(), "shop")
    assert [x["term"] for x in d["longer_terms"]] == ["duty free shop"]
    assert d["longer_terms_count"] == 1
    assert "ssi/2013/85" not in [e["legislation_id"] for e in d["definitions"]]
    assert "not searched for, so never present them as complete" in D.definitions_note(
        json.dumps(d))


def test_an_unclear_reference_carries_no_link():
    d = D.build_result(_rows(), "shop")
    unclear = d["definitions"][-1]
    assert unclear["reference_unclear"] is True and "url" not in unclear
    assert d["reference_unclear"] == 1
    assert "reference_unclear" in D.definitions_note(json.dumps(d))


def test_a_jurisdiction_filter_applies_in_and_keeps_not_stated():
    d = D.build_result(_rows(), "shop", jurisdiction="scotland")
    ids = [e["legislation_id"] for e in d["definitions"]]
    assert "asp/2007/13" in ids and "ukpga/1950/28" in ids     # stated, and not stated
    assert "ukpga/1994/20" not in ids                          # stated England, Wales
    assert "nisr/2012/246" not in ids                          # its id says NI
    assert d["removed_by_filters"] == 2
    assert d["jurisdiction"] == "Scotland"
    assert d["extent_not_stated"] == 2
    note = D.definitions_note(json.dumps(d))
    assert "The Scotland filter applies" in note and "marked 'not stated'" in note
    # A UK-wide statement applies in Scotland (P1.1's "applies in" rule).
    uk = [_row("ukpga/2016/12", '“shop” means any premises', "schedule/5", ["United Kingdom"])]
    assert D.build_result(uk, "shop", jurisdiction="scotland")["count"] == 1


def test_a_type_filter_applies_by_id():
    d = D.build_result(_rows(), "shop", legislation_type="secondary")
    assert [e["legislation_id"] for e in d["definitions"]] == ["nisr/2012/246"]


def test_the_list_is_capped_and_counted():
    rows = [_row(f"uksi/2000/{i}", f'"shop" means premises number {i}') for i in range(1, 61)]
    d = D.build_result(rows, "shop")
    assert d["count"] == 60 and d["listed"] == D.MAX_LISTED == 40
    note = D.definitions_note(json.dumps(d))
    assert "Only 40 of the 60 are listed here" in note


def test_the_result_stays_under_its_bound_with_long_clauses():
    long = " ".join(["premises"] * 400)
    rows = [_row(f"uksi/2000/{i}", f'"shop" means {long}; "shop worker" means {long}')
            for i in range(1, 61)]
    d = D.build_result(rows, "shop")
    out = json.dumps(d, ensure_ascii=False) + D.definitions_note(json.dumps(d))
    assert len(out) <= D.DEFINITIONS_WHOLE_CHARS
    assert all(len(e["definition"]) <= D.CLAUSE_CHARS + 2 for e in d["definitions"])
    assert d["count"] == 60


def test_odd_input_never_raises():
    for rows in (None, {}, {"results": None}, [None, 3, "x"], {"detail": "boom"}):
        d = D.build_result(rows, "shop")
        assert d["count"] == 0 and d["definitions"] == []


# --- (3) the block: permits what was kept, names the edge, never "all" --------

def test_the_found_block():
    note = D.definitions_note(json.dumps(D.build_result(_rows(), "shop")))
    assert note.startswith("\n\n[SEARCH SCOPE — definitions search:")
    assert note.count("[") == 1 and note.count("]") == 1
    assert "one search, not a census" in note
    assert "never say that no other legislation defines it" in note
    assert "all definitions" not in note.lower()
    # It is removed whole from anything a legal professional reads.
    stripped, n = ss.strip_scope_blocks("Answer." + note)
    assert n == 1 and stripped.strip() == "Answer."


def test_the_empty_block_forbids_a_negative_about_the_law():
    note = D.definitions_note(json.dumps(D.build_result([_row("uksi/1/1", "nothing")], "shop")))
    assert "NOT evidence that no legislation defines the term" in note
    note = D.definitions_note(json.dumps(D.build_result([], "shop")))
    assert "it returned no provisions" in note


def test_no_block_for_anything_else():
    assert D.definitions_note("Error executing tool: boom") == ""
    assert D.definitions_note(json.dumps({"tool": "find_instruments_made_under"})) == ""


# --- (4) the executor: one corpus-wide call --------------------------------------

def _lex(monkeypatch, rows, cfg=None):
    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        asked.append((url, kwargs.get("json")))
        return httpx.Response(200, json=rows, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    monkeypatch.setattr(executor, "get_request_provider_config", lambda: dict(cfg or {}))
    return asked


def test_the_executor_sends_one_search_with_no_legislation_id(monkeypatch):
    asked = _lex(monkeypatch, _rows())
    d = json.loads(asyncio.run(executor.execute_worker_tool(TOOL, {"term": "shop"})))
    assert len(asked) == 1
    url, payload = asked[0]
    assert url.endswith("/legislation/section/search")
    assert payload == {"query": '"shop" means', "size": 300}
    assert d["count"] == 5


def test_the_user_filters_win_over_the_model_argument(monkeypatch):
    asked = _lex(monkeypatch, _rows(), {"_jurisdiction": "scotland", "_year_from": 1990})
    d = json.loads(asyncio.run(executor.execute_worker_tool(
        TOOL, {"term": "shop", "jurisdiction": "england_and_wales"})))
    assert asked[0][1] == {"query": '"shop" means', "size": 300, "year_from": 1990}
    assert d["jurisdiction"] == "Scotland"


def test_the_model_argument_applies_without_a_user_filter(monkeypatch):
    _lex(monkeypatch, _rows())
    d = json.loads(asyncio.run(executor.execute_worker_tool(
        TOOL, {"term": "shop", "jurisdiction": "scotland"})))
    assert d["jurisdiction"] == "Scotland"
    d = json.loads(asyncio.run(executor.execute_worker_tool(
        TOOL, {"term": "shop", "jurisdiction": "mars"})))
    assert "jurisdiction" not in d


def test_no_term_is_no_call(monkeypatch):
    asked = _lex(monkeypatch, _rows())
    d = json.loads(asyncio.run(executor.execute_worker_tool(TOOL, {"term": " "})))
    assert asked == [] and d["error"]


# --- (5) run_worker_tool: never summarised, recorded, memoised ---------------

@pytest.fixture
def _pipeline(monkeypatch):
    state = {"summarised": 0, "payload": ""}

    async def fake_execute(name, args, on_chunk=None, timing_collector=None):
        return state["payload"]

    async def fake_summarise(text, query, model, **kw):
        state["summarised"] += 1
        return "[summary]", False

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_execute)
    monkeypatch.setattr(agent_shared, "summarise_for_query", fake_summarise)
    monkeypatch.setattr("src.agent.provider_factory.get_summarise_threshold", lambda: 1_000)
    monkeypatch.setattr("src.agent.provider_factory.get_request_provider_config",
                        lambda: {"_local_prompt_cache_enabled": False})
    return state


def _big():
    rows = [_row(f"uksi/2000/{i}", f'"shop" means premises of class {i} ' + "x " * 100)
            for i in range(1, 41)]
    return json.dumps(D.build_result(rows, "shop"), ensure_ascii=False)


def _call(**kw):
    return asyncio.run(run_worker_tool(TOOL, {"term": "shop"}, "q", chunk_fn=None,
                                       summarise_model="m", **kw))


def test_never_summarised_over_the_threshold_or_the_budget(_pipeline):
    _pipeline["payload"] = _big()
    assert len(_pipeline["payload"]) > 1_000
    budget = {"used": 249_000, "limit": 250_000}
    out = _call(context_budget=budget)
    assert _pipeline["summarised"] == 0
    assert out.startswith(_pipeline["payload"])
    assert out[len(_pipeline["payload"]):] == D.definitions_note(_pipeline["payload"])
    assert budget["used"] == 249_000 + len(out)


def test_the_last_resort_cap_does_not_cut_it(monkeypatch):
    from src.agent import provider_factory as pf
    monkeypatch.setattr(pf, "get_summarise_threshold", lambda: 8_000)
    big = "y" * (D.DEFINITIONS_WHOLE_CHARS - 10)
    assert pf.cap_tool_result(TOOL, big) == big
    assert pf.get_tool_result_threshold("search_legislation") == 8_000


def test_recorded_and_sources_extracted(_pipeline):
    _pipeline["payload"] = json.dumps(D.build_result(_rows(), "shop"))
    log, sources, urls = [], [], set()
    _call(search_log=log, source_accumulator=sources, retrieved_urls=urls)
    entry = [e for e in log if e.get("tool") == ss.DEFINITIONS_ENTRY]
    assert entry and entry[0]["term"] == "shop" and entry[0]["count"] == 5
    assert entry[0]["rows"] == 8 and entry[0]["longer"] == 1
    lids = [s["_lid"] for s in sources]
    assert "ukpga/1950/28" in lids
    assert not any("UNCLEAR" in x for x in lids)          # no link, no rail entry
    assert all(not s.get("excerpt") for s in sources)
    assert "legislation.gov.uk/ukpga/1950/28/section/74" in urls


def test_a_memo_hit_records_the_search_too(_pipeline):
    _pipeline["payload"] = json.dumps(D.build_result(_rows(), "shop"))
    memo = {}
    first, second = [], []
    a = _call(tool_memo=memo, search_log=first)
    b = _call(tool_memo=memo, search_log=second)
    assert a == b
    assert [e["tool"] for e in second] == [e["tool"] for e in first]
    assert any(e["tool"] == ss.DEFINITIONS_ENTRY for e in second)


def test_an_error_is_recorded_as_not_ok_with_no_block(_pipeline):
    _pipeline["payload"] = "Error executing tool: boom"
    log = []
    out = _call(search_log=log)
    assert out == "Error executing tool: boom"
    assert log == [{"tool": ss.DEFINITIONS_ENTRY, "ok": False, "term": "shop"}]


# --- (6) the discovery budget ------------------------------------------------

def test_charged_as_a_discovery_search():
    assert TOOL in LEGISLATION_DISCOVERY_TOOLS


def test_the_search_legislation_stop_is_unchanged_and_the_definitions_one_names_it():
    b = {"limit": 8}
    old = legislation_stop_message(b)
    assert old == legislation_stop_message(b, "search_legislation")
    assert "Do not call search_legislation again in this step." in old
    assert "find_definitions" not in old
    new = legislation_stop_message(b, TOOL)
    assert "Do not call search_legislation or find_definitions again" in new
    log = []
    ss.record_budget_stop(log, TOOL, {"term": "shop"}, b)
    assert log[0]["query"] == "shop"


# --- (7) the scope record: limb and footer, and nothing when it did not run ----

def _defs_log(**over):
    log = []
    d = D.build_result(_rows(), "shop", **over)
    ss.record_definitions(log, TOOL, {"term": "shop"}, json.dumps(d))
    return log


SEARCH = {"tool": "search_legislation", "query": "Shops Act 1950", "shown": 5, "matched": 40}
SECTION = {"tool": "search_legislation_sections", "query": "definition of shop",
           "legislation_id": "ukpga/1950/28"}


def test_the_limb_says_what_was_searched_and_that_it_is_not_a_census():
    block = ss.worker_scope_block(_defs_log())
    assert 'Definitions search run (one search of all legislation in the index): for "shop" 5 ' \
        'instrument(s) define the term in quotation marks among the 8 provisions it read' in block
    assert "it is not a census" in block
    assert "No ranked search was run in this step" not in block


def test_the_limb_and_block_are_unchanged_without_it():
    # Every other line is the same, the limb added (a step that searched
    # already gets the currency limb; a lookup-only step is the next test).
    for log in ([SEARCH], [SEARCH, SECTION], [SECTION]):
        with_defs = ss.worker_scope_block(log + _defs_log())
        without = ss.worker_scope_block(log)
        limb = ss._definitions_limb(_defs_log())
        assert with_defs.replace("\n" + limb, "") == without


def test_a_lookup_only_step_with_it_is_a_searched_step():
    lookup = [{"tool": "lookup", "status": "not_held", "legislation_id": "ssi/2025/1",
               "label": "SSI 2025/1"}]
    assert "No ranked search was run in this step" in ss.worker_scope_block(lookup)
    block = ss.worker_scope_block(lookup + _defs_log())
    assert "No ranked search was run in this step" not in block
    assert "NONE of this can establish that something does not exist" in block


def test_the_footer_clause_on_each_footer_and_only_when_it_ran():
    defs = _defs_log()
    clause = ss._definitions_footer_clause(defs)
    assert clause.startswith(' All legislation in the index was also searched once for '
                             'provisions defining "shop"')
    fresh = ss.answer_scope_footer([SEARCH] + defs)
    assert clause in fresh and fresh.replace(clause, "") == ss.answer_scope_footer([SEARCH])
    sec = ss.section_scope_footer([SECTION] + defs)
    assert clause in sec and sec.replace(clause, "") == ss.section_scope_footer([SECTION])
    assert ss._definitions_footer_clause([SEARCH, SECTION]) == ""


def test_a_turn_whose_only_search_was_the_definitions_search_gets_a_footer():
    defs = _defs_log()
    footer = ss.section_scope_footer(defs)
    assert footer.startswith('\n\n*Search scope: for this reply all legislation in the index '
                             'was searched once for provisions defining "shop"')
    assert footer.endswith("*") and footer.count("\n") == 2
    # Not the carried line, which would say no search was run for this reply.
    earlier = [{"role": "assistant", "content": "A.\n\n" + ss.answer_scope_footer([SEARCH])}]
    assert ss.carried_scope_footer(earlier, defs) == ""
    assert ss.carried_scope_footer(earlier, []) != ""
    # A footer copied back by the model is stripped like any other.
    assert ss.strip_answer_footer("Answer." + footer) == "Answer."


def test_the_footer_words_trip_no_negative_detector():
    from tools.replay_report import NEG_ASSERTED
    for log in (_defs_log(), _defs_log(jurisdiction="scotland")):
        assert not NEG_ASSERTED.search(ss._definitions_footer_clause(log))
    none = []
    ss.record_definitions(none, TOOL, {}, json.dumps(D.build_result([], "shop")))
    assert "not the same as the term being undefined in law" in \
        ss._definitions_footer_clause(none)


def test_recording_is_self_gated_and_never_raises():
    log = []
    ss.record_definitions(log, "search_legislation", {}, json.dumps(D.build_result([], "x")))
    ss.record_definitions(None, TOOL, {}, "x")
    assert log == []
    for odd in (None, 3, "[", {"tool": TOOL, "count": "many"}):
        ss.record_definitions(log, TOOL, {}, odd)


def test_the_currency_limb_speaks_on_a_definitions_only_step():
    assert ss._currency_limb(_defs_log())


# --- (8) wiring: the research Workers only -----------------------------------

def _names(tools):
    return [t["function"]["name"] for t in tools]


@pytest.mark.parametrize("rm", ["legislation_only", "legislation_and_case_law"])
@pytest.mark.parametrize("cm", [None, "", "research", "deep_research"])
def test_offered_to_the_research_workers(rm, cm):
    assert TOOL in _names(get_worker_tools(rm, cm))


@pytest.mark.parametrize("rm", ["legislation_only", "legislation_and_case_law"])
def test_not_offered_to_the_quick_lookup_worker(rm):
    assert TOOL not in _names(get_worker_tools(rm, "conversational"))
    assert TOOL in QUICK_LOOKUP_WITHHELD_TOOLS
    assert json.loads(withheld_tool_result(TOOL))["run"] is False


@pytest.mark.parametrize("rm", ["case_law_only", "parliamentary_records", "westminster_records"])
@pytest.mark.parametrize("cm", [None, "research", "conversational", "deep_research"])
def test_not_offered_elsewhere(rm, cm):
    assert TOOL not in _names(get_worker_tools(rm, cm))


def test_the_prompt_line_is_in_the_research_prompts_only():
    from src import prompts as p
    assert p.WORKER_SYSTEM_PROMPT.count(p._DEFINITIONS_TOOL_LINE) == 1
    assert p.WORKER_SYSTEM_PROMPT_HYBRID.count(p._DEFINITIONS_TOOL_LINE) == 1
    for other in (p.WORKER_SYSTEM_PROMPT_CONVERSATIONAL, p.WORKER_SYSTEM_PROMPT_CASE_LAW,
                  p.PARLIAMENT_WORKER_SYSTEM_PROMPT, p.WESTMINSTER_WORKER_SYSTEM_PROMPT):
        assert TOOL not in other


def test_phase_one_and_the_cache_allowlist():
    from src.services.local_prompt_cache import CACHEABLE_TOOLS
    from src.utils.stopwatch import _PHASE1_SEARCH_TOOLS
    assert TOOL in _PHASE1_SEARCH_TOOLS and TOOL in CACHEABLE_TOOLS
