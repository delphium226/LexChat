"""P3.25: the quick-lookup (conversational) Worker is not offered
`get_legislation_text`, and the two things only that tool supplied, an SI's
own recital and `valid_date`, come through `lookup_legislation` instead.

Its prompt said "Do NOT fall back to `get_legislation_text`" while its tool
list offered it: 143 of 1,314 answered conversational turns called it, on the
pinned model. The fix is in code (Invariant 2): the tool list depends on the
chat mode, a call to the withheld tool is answered without running it, and
code looks up each statutory instrument the Worker searches within, so P2.3's
permitted branch (an SI's recital, which 6340 quoted) keeps a source.

Instruments here are synthetic ("Widget Order 1901", `uksi/1901/9`).
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.agent_core import run_worker_agent  # noqa: E402
from src.agent.agent_shared import run_worker_tool  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.agent.tools import executor  # noqa: E402
from src.agent.tools.schemas import (  # noqa: E402
    QUICK_LOOKUP_WITHHELD_TOOLS,
    WORKER_TOOLS,
    get_worker_tools,
    is_quick_lookup_worker,
)
from src.prompts import (  # noqa: E402
    WORKER_SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT_CONVERSATIONAL,
    WORKER_SYSTEM_PROMPT_HYBRID,
    _ENABLING_POWER_RULE,
    _IN_FORCE_RULE,
    get_worker_system_prompt,
)
from src.utils.instrument_lookup import (  # noqa: E402
    LOOKUP_TOOL,
    MAX_SECTION_LOOKUPS,
    lookup_brief_block,
    parse_lookup_result,
    section_search_lookup,
)
from src.utils.search_scope import (  # noqa: E402
    _currency_limb,
    _enabling_limb,
    enabling_power_note,
    lookup_enabling_note,
    record_currency,
    record_enabling_power,
    strip_scope_blocks,
)

GLT = "get_legislation_text"
RECITAL = ("The Secretary of State, in exercise of the powers conferred upon him by "
           "section 4 of the Widget Act 1899 [a], hereby makes the following Order:")
RECORD_SI = {
    "id": "http://www.legislation.gov.uk/id/uksi/1901/9",
    "uri": "http://www.legislation.gov.uk/id/uksi/1901/9",
    "title": "The Widget Order 1901", "description": RECITAL,
    "enactment_date": "1901-03-01", "valid_date": "2024-06-07",
    "category": "secondary", "type": "uksi", "year": 1901, "number": 9,
    "status": "revised", "text": "",
}
RECORD_SSI = dict(RECORD_SI, id="http://www.legislation.gov.uk/id/ssi/1901/3",
                  uri="http://www.legislation.gov.uk/id/ssi/1901/3",
                  title="The Widget (Scotland) Order 1901", type="ssi", number=3,
                  description="This Order makes provision about widgets.")
SECTION_ROWS = [{"uri": "http://www.legislation.gov.uk/id/uksi/1901/9/article/2",
                 "provision_type": "article", "number": "2", "text": "Widgets shall be blue."}]


def _outcome(status, lid="uksi/1901/9", **kw):
    return json.dumps({"tool": LOOKUP_TOOL, "legislation_id": lid, "label": lid,
                       "status": status, **kw})


# --- (1) the tool list depends on the chat mode --------------------------------

@pytest.mark.parametrize("rm", ["legislation_only", "legislation_and_case_law"])
def test_the_quick_lookup_worker_is_not_offered_the_whole_text(rm):
    names = [t["function"]["name"] for t in get_worker_tools(rm, "conversational")]
    assert GLT not in names
    # Everything else the research type offers is still offered.
    assert names == [t["function"]["name"] for t in get_worker_tools(rm) if
                     t["function"]["name"] != GLT]
    assert LOOKUP_TOOL in names and "search_legislation_sections" in names


@pytest.mark.parametrize("rm", ["legislation_only", "legislation_and_case_law",
                                "case_law_only", "parliamentary_records",
                                "westminster_records"])
@pytest.mark.parametrize("cm", [None, "", "research", "deep_research"])
def test_every_other_worker_gets_exactly_the_list_it_had(rm, cm):
    assert json.dumps(get_worker_tools(rm, cm)) == json.dumps(get_worker_tools(rm))
    if rm in ("legislation_only", "legislation_and_case_law"):
        assert GLT in [t["function"]["name"] for t in get_worker_tools(rm, cm)]
    assert get_worker_tools("legislation_only") is WORKER_TOOLS


@pytest.mark.parametrize("rm", ["legislation_only", "legislation_and_case_law",
                                "case_law_only", "parliamentary_records",
                                "westminster_records", "drafting"])
@pytest.mark.parametrize("cm", [None, "", "research", "deep_research", "conversational"])
def test_the_narrowed_list_goes_with_the_quick_lookup_prompt_and_only_with_it(rm, cm):
    cfg = {"_chat_mode": cm} if cm is not None else None
    on_quick_prompt = get_worker_system_prompt(rm, cfg).endswith(
        WORKER_SYSTEM_PROMPT_CONVERSATIONAL)
    assert on_quick_prompt == is_quick_lookup_worker(rm, cm)


def test_the_quick_lookup_prompt_names_no_tool_its_worker_is_not_offered():
    for name in QUICK_LOOKUP_WITHHELD_TOOLS:
        assert name not in WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    # Both route swaps took (a swap whose anchor moved is left undone).
    assert "arrives in a `lookup_legislation` result for some instruments" in \
        WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    assert "(d) the `valid_date` on a `lookup_legislation` result" in \
        WORKER_SYSTEM_PROMPT_CONVERSATIONAL
    # The research Workers keep the rules as they were.
    for prompt in (WORKER_SYSTEM_PROMPT, WORKER_SYSTEM_PROMPT_HYBRID):
        assert _ENABLING_POWER_RULE in prompt and _IN_FORCE_RULE in prompt
    assert f"a `{GLT}` result for some instruments" in _ENABLING_POWER_RULE


# --- (2) the lookup carries valid_date, and the recorders read it -------------

def _lex(monkeypatch, by_path):
    """LEX by endpoint: {"/lookup": (status, body), ...}; records each call."""
    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        path = url.split("/legislation", 1)[-1]
        asked.append(path)
        status, body = by_path[path]
        return httpx.Response(status, json=body, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    return asked


def test_the_lookup_result_carries_valid_date(monkeypatch):
    _lex(monkeypatch, {"/lookup": (200, RECORD_SI), "/section/lookup": (200, SECTION_ROWS)})
    got = json.loads(asyncio.run(executor.execute_worker_tool(
        LOOKUP_TOOL, {"legislation_id": "uksi/1901/9"})))
    assert got["status"] == "held" and got["valid_date"] == "2024-06-07"
    assert got["description"] == RECITAL
    _lex(monkeypatch, {"/lookup": (200, dict(RECORD_SI, valid_date="")),
                       "/section/lookup": (200, SECTION_ROWS)})
    got = json.loads(asyncio.run(executor.execute_worker_tool(
        LOOKUP_TOOL, {"legislation_id": "uksi/1901/9"})))
    assert got["valid_date"] is None


def test_valid_date_is_recorded_from_a_held_lookup_and_only_from_one():
    log = []
    record_currency(log, LOOKUP_TOOL, {}, _outcome("held", valid_date="2024-06-07"))
    assert log == [{"tool": "currency", "kind": "valid_date", "via": LOOKUP_TOOL,
                    "legislation_id": "uksi/1901/9", "valid_date": "2024-06-07"}]
    assert "up to date to: uksi/1901/9 to 2024-06-07" in _currency_limb(log)
    # A stub has no held text for the date to describe; not-held has no record.
    for other in (_outcome("held_without_text", valid_date="2024-06-07"),
                  _outcome("not_held"), _outcome("held", valid_date="June 2024"),
                  _outcome("held")):
        log = []
        record_currency(log, LOOKUP_TOOL, {}, other)
        assert log == []


def test_the_recital_is_recorded_from_a_lookup_and_nothing_without_one():
    log = []
    record_enabling_power(log, LOOKUP_TOOL, {}, _outcome("held", description=RECITAL))
    assert log == [{"tool": "enabling_power", "legislation_id": "uksi/1901/9",
                    "stated": True}]
    assert "retrieved for 1 of 1 instrument(s)" in _enabling_limb(log)
    # A lookup is not a read of the instrument: no recital, no record (the
    # section search records the instrument as looked at); nor for an Act.
    for other in (_outcome("held", description="This Order makes provision about widgets."),
                  _outcome("held", lid="ukpga/1899/2", description=RECITAL),
                  _outcome("not_held", description=RECITAL)):
        log = []
        record_enabling_power(log, LOOKUP_TOOL, {}, other)
        assert log == []


def test_the_lookup_block_quotes_the_recital_names_its_source_and_is_stripped():
    block = lookup_enabling_note(_outcome("held", description=RECITAL))
    assert block.startswith("\n\n[ENABLING POWER — the index record lookup_legislation "
                            "returned for uksi/1901/9 DOES state what uksi/1901/9")
    assert "section 4 of the Widget Act 1899 (a)" in block       # brackets neutralised
    assert "You MAY state the enabling power of uksi/1901/9" in block
    assert strip_scope_blocks("Answer." + block)[0] == "Answer."
    assert lookup_enabling_note(_outcome("held", description="About widgets.")) == ""
    assert lookup_enabling_note("not json") == ""


def test_the_whole_text_block_is_byte_for_byte_what_p23_built():
    text = json.dumps({"legislation": {"description": RECITAL}, "full_text": "Article 1 ..."})
    assert enabling_power_note({"legislation_id": "uksi/1901/9"}, text) == (
        "\n\n[ENABLING POWER — this record DOES state what uksi/1901/9 was made "
        "under, and these words are the only evidence of it you have:\n"
        f'  "{RECITAL.replace("[", "(").replace("]", ")")}"\n'
        "You MAY state the enabling power of uksi/1901/9, citing this text. Do NOT "
        "extend the claim to any other instrument: each one states its own, "
        "and most records do not state it at all.]"
    )


def test_a_lookup_result_carrying_the_block_still_parses_and_still_briefs():
    final = _outcome("held", description=RECITAL, title="The Widget Order 1901") + \
        lookup_enabling_note(_outcome("held", description=RECITAL))
    assert parse_lookup_result(final)["status"] == "held"
    assert "uksi/1901/9 (The Widget Order 1901): HELD" in lookup_brief_block([final])


def test_a_lookup_run_by_the_worker_records_both_and_shows_the_block(monkeypatch):
    set_request_provider_config({"_provider": "openrouter",
                                 "_research_mode": "legislation_only", "model": "m"})
    _lex(monkeypatch, {"/lookup": (200, RECORD_SI), "/section/lookup": (200, SECTION_ROWS)})
    log = []
    final = asyncio.run(run_worker_tool(LOOKUP_TOOL, {"legislation_id": "uksi/1901/9"},
                                        "q", lambda *a, **k: None, "m", search_log=log))
    assert "[ENABLING POWER — the index record lookup_legislation returned" in final
    kinds = {(e["tool"], e.get("kind") or e.get("stated") or e.get("status")) for e in log}
    assert ("enabling_power", True) in kinds
    assert ("currency", "valid_date") in kinds
    assert ("lookup", "held") in kinds


# --- (3) the code lookup on a section-searched SI ------------------------------

def _recorder():
    calls = []

    async def run(name, args):
        calls.append((name, args))
        return _outcome("held", description=RECITAL, valid_date="2024-06-07")
    return calls, run


def test_the_code_lookup_fires_once_for_a_section_searched_si():
    calls, run = _recorder()
    done: set = set()
    args = {"legislation_id": "uksi/1901/9", "query": "widgets"}
    block = asyncio.run(section_search_lookup("search_legislation_sections", args, done, run))
    assert calls == [(LOOKUP_TOOL, {"legislation_type": "uksi", "year": 1901, "number": 9})]
    assert "You MAY state the enabling power of uksi/1901/9" in block
    # Once per run: a second section search of the same instrument does not repeat it.
    assert asyncio.run(section_search_lookup(
        "search_legislation_sections", dict(args, query="colour"), done, run)) == ""
    assert len(calls) == 1


@pytest.mark.parametrize("name,lid", [
    ("search_legislation_sections", "ukpga/1899/2"),     # an Act has no enabling power
    ("search_legislation_sections", "asp/1901/1"),
    ("search_legislation_sections", "not an id"),
    ("search_legislation", "uksi/1901/9"),               # not a search within it
    ("get_legislation_changes", "uksi/1901/9"),
    (LOOKUP_TOOL, "uksi/1901/9"),
])
def test_the_code_lookup_does_not_fire_otherwise(name, lid):
    calls, run = _recorder()
    assert asyncio.run(section_search_lookup(name, {"legislation_id": lid}, set(), run)) == ""
    assert calls == []


def test_the_code_lookup_is_bounded_per_run():
    calls, run = _recorder()
    done: set = set()
    for n in range(1, MAX_SECTION_LOOKUPS + 3):
        asyncio.run(section_search_lookup("search_legislation_sections",
                                          {"legislation_id": f"ssi/1901/{n}"}, done, run))
    assert len(calls) == MAX_SECTION_LOOKUPS


def test_an_si_without_a_recital_is_looked_up_but_shows_the_worker_nothing():
    async def run(name, args):
        return _outcome("held", lid="ssi/1901/3", description="About widgets.")
    assert asyncio.run(section_search_lookup(
        "search_legislation_sections", {"legislation_id": "ssi/1901/3"}, set(), run)) == ""


def _worker(monkeypatch, chat_mode, calls_to_make, lex):
    """Run the Worker with a fake loop that makes `calls_to_make` and keeps the
    results; LEX answers by endpoint."""
    set_request_provider_config({"_provider": "openrouter", "model": "test-model",
                                 "_research_mode": "legislation_only",
                                 "_chat_mode": chat_mode})
    asked = _lex(monkeypatch, lex)
    seen = {"results": []}

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None,
                   **kw):
        seen["tools"] = [t["function"]["name"] for t in tools]
        for name, args in calls_to_make:
            seen["results"].append(await tool_exec(name, args))
        return {"role": "assistant", "content": "Report."}

    result = asyncio.run(run_worker_agent(loop, lambda *a, **k: None, "Widgets?",
                                          "test-model", None, 0))
    return seen, asked, result


LEX_SI = {"/lookup": (200, RECORD_SI), "/section/lookup": (200, SECTION_ROWS),
          "/section/search": (200, SECTION_ROWS)}
SECTION_CALL = ("search_legislation_sections", {"legislation_id": "uksi/1901/9",
                                                "query": "widgets"})


def test_the_quick_lookup_worker_gets_the_recital_with_its_section_search(monkeypatch):
    seen, asked, result = _worker(monkeypatch, "conversational", [SECTION_CALL], LEX_SI)
    assert GLT not in seen["tools"]
    assert asked == ["/lookup", "/section/lookup", "/section/search"]
    assert "[ENABLING POWER — the index record lookup_legislation returned for " \
           "uksi/1901/9" in seen["results"][0]
    recorded = result["searches"]
    assert {"tool": "enabling_power", "legislation_id": "uksi/1901/9",
            "stated": True} in recorded
    assert [e["valid_date"] for e in recorded if e.get("kind") == "valid_date"] == \
        ["2024-06-07"]
    # A route to the recital and the date, not P3.7's held/absent test: its
    # HELD outcome does not put "Looked up by number" on the report.
    assert not [e for e in recorded if e.get("tool") == "lookup"]
    assert "Looked up by number" not in result["content"]


def test_a_code_lookup_that_finds_a_stub_is_kept_for_the_report_and_footer(monkeypatch):
    stub = dict(LEX_SI, **{"/section/lookup": (404, {"detail": "No sections found for x"}),
                           "/section/search": (200, [])})
    _, _, result = _worker(monkeypatch, "conversational", [SECTION_CALL], stub)
    assert [e["status"] for e in result["searches"] if e.get("tool") == "lookup"] == \
        ["held_without_text"]
    assert not [e for e in result["searches"] if e.get("kind") == "valid_date"]


def test_a_lookup_the_worker_asks_for_itself_is_still_recorded_when_held(monkeypatch):
    _, _, result = _worker(monkeypatch, "conversational",
                           [(LOOKUP_TOOL, {"legislation_id": "uksi/1901/9"})], LEX_SI)
    assert [e["status"] for e in result["searches"] if e.get("tool") == "lookup"] == ["held"]


@pytest.mark.parametrize("chat_mode", ["research", "deep_research", ""])
def test_a_research_worker_section_search_runs_exactly_as_before(monkeypatch, chat_mode):
    seen, asked, result = _worker(monkeypatch, chat_mode, [SECTION_CALL], LEX_SI)
    assert GLT in seen["tools"]
    assert asked == ["/section/search"]
    assert "[ENABLING POWER — the index" not in seen["results"][0]
    assert not [e for e in result["searches"] if e.get("tool") == "lookup"]


def test_a_withheld_tool_called_anyway_is_not_run(monkeypatch):
    seen, asked, _ = _worker(monkeypatch, "conversational",
                             [(GLT, {"legislation_id": "uksi/1901/9"})], LEX_SI)
    assert asked == []
    got = json.loads(seen["results"][0])
    assert got["run"] is False and "not offered in quick-lookup mode" in got["note"]
    assert "results" not in got


def test_a_failed_code_lookup_leaves_the_section_search_as_it_was(monkeypatch):
    lex = dict(LEX_SI, **{"/lookup": (503, {"detail": "busy"})})
    seen, asked, result = _worker(monkeypatch, "conversational", [SECTION_CALL], lex)
    assert asked[-1] == "/section/search"
    assert "[ENABLING POWER — the index" not in seen["results"][0]
    assert not [e for e in result["searches"] if e.get("kind") == "valid_date"]


# --- the graders read the new route ---------------------------------------------

def _turn(raw):
    return {"audit": {"delegations": [{"tools": [
        {"name": LOOKUP_TOOL, "args": {}, "raw_result": raw}]}]}}


def test_derivations_reads_a_recital_on_a_lookup_record():
    """P2.3's grader: a claim the product now permits from a lookup is
    supported, not unverified."""
    from tools.replay_report import retrieved_enabling

    got = retrieved_enabling(_turn(_outcome("held", description=RECITAL)))
    assert [lid for lid, _ in got] == ["uksi/1901/9"]
    assert retrieved_enabling(_turn(_outcome("held", description="About widgets."))) == []


def test_negcurrency_reads_a_held_lookups_valid_date():
    from tools.replay_report import negcurrency_evidence

    ev = negcurrency_evidence(_turn(_outcome("held", valid_date="2024-06-07",
                                             title="The Widget Order 1901")))
    assert ev["valid_dates"] == [("uksi/1901/9", "2024-06-07")]
    assert ev["titles"]["uksi/1901/9"] == "The Widget Order 1901"
    stub = negcurrency_evidence(_turn(_outcome("held_without_text", valid_date="2024-06-07")))
    assert stub["valid_dates"] == []


# --- the seam tools build the same list the product does ------------------------

def test_the_seam_tools_offer_the_quick_lookup_worker_the_product_list():
    from tools.seam_replay import worker_tools_for

    conv = {"_research_mode": "legislation_only", "_chat_mode": "conversational"}
    assert GLT not in [t["function"]["name"] for t in worker_tools_for(get_worker_tools, conv)]
    research = dict(conv, _chat_mode="research")
    assert worker_tools_for(get_worker_tools, research) is WORKER_TOOLS

    def old_signature(research_mode):           # a revision before P3.25
        return ["old", research_mode]
    assert worker_tools_for(old_signature, conv) == ["old", "legislation_only"]
