"""P3.7 (bucket B5): `lookup_legislation`, the held/absent test.

A ranked keyword search cannot say an instrument is not held: absence from its
top 5 of a median 141 matches is not absence from the corpus. `/legislation/
lookup` can. Three states, because a 200 does not mean the text is held
(`ssi/2025/119` is a record with no text): held, held without text, not held.
And a fourth, `lookup_failed`, that must never read as a negative.

The instruments here are the ones the row is about, and their live states were
checked at Session 24's pre-flight and again in Session 25: `ssi/2025/377` and
`ssi/2026/170` 404 on lookup; `ssi/2025/119` is 200 on lookup and 404 on
`/legislation/section/lookup`; `asp/2025/2` is 200 on both.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.agent_core import run_worker_agent  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.agent.tools import executor  # noqa: E402
from src.agent.tools.schemas import WORKER_TOOLS, get_worker_tools  # noqa: E402
from src.services.local_prompt_cache import CACHEABLE_TOOLS  # noqa: E402
from src.utils.instrument_lookup import (  # noqa: E402
    LOOKUP_TOOL,
    citation_label,
    extract_instrument_citations,
    lookup_args,
    lookup_brief_block,
)
from src.utils.search_scope import (  # noqa: E402
    _lookup_footer_clause,
    answer_scope_footer,
    lookup_scope_footer,
    record_lookup,
    strip_scope_blocks,
    worker_scope_block,
)
from src.utils.stopwatch import _PHASE1_SEARCH_TOOLS, _PHASE2_RETRIEVAL_TOOLS  # noqa: E402

RECORD_119 = {
    "id": "http://www.legislation.gov.uk/id/ssi/2025/119",
    "uri": "http://www.legislation.gov.uk/id/ssi/2025/119",
    "title": "The Example (Commencement No. 1) Regulations 2025",
    "description": "These Regulations bring sections 2 and 9 of the Act into force on 10 May 2025.",
    "category": "secondary", "type": "ssi", "year": 2025, "number": 119,
    "number_of_provisions": 6, "text": "",
}
RECORD_ASP = dict(RECORD_119, id="http://www.legislation.gov.uk/id/asp/2025/2",
                  uri="http://www.legislation.gov.uk/id/asp/2025/2", title="An Example Act 2025",
                  type="asp", number=2, category="primary", description="")


# --- the citation a brief names ------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Check SSI 2025/377 for commencement.", [("ssi", 2025, 377)]),
    ("the regulations (SSI 2025/377 (C. 28))", [("ssi", 2025, 377)]),
    ("S.S.I. 2025 No. 377", [("ssi", 2025, 377)]),
    ("Scottish Statutory Instrument 2026/170", [("ssi", 2026, 170)]),
    # How a stored Manager brief wrote it (`wave3_p35` 6409 r1 t9).
    ("Scottish Statutory Instrument (SSI) 2025/377, which", [("ssi", 2025, 377)]),
    ("Statutory Instrument (S.I.) 2020/1234", [("uksi", 2020, 1234)]),
    ("the Act (2025 asp 2) and SSI 2025/119", [("asp", 2025, 2), ("ssi", 2025, 119)]),
    ("asp 2025/2", [("asp", 2025, 2)]),
    ("SI 2020/1234 and S.I. 2019/5", [("uksi", 2020, 1234), ("uksi", 2019, 5)]),
    ("WSI 2021/10", [("wsi", 2021, 10)]),
    ("ids ssi/2025/377 and ukpga/2010/15", [("ssi", 2025, 377), ("ukpga", 2010, 15)]),
    ("the Equality Act 2010 c. 15", [("ukpga", 2010, 15)]),
    # No type, so no lookup: it could be an SSI, an SI or a WSI.
    ("and how about 2025/377?", []),
    # "(C. 28)" is a commencement-order series number, not a chapter.
    ("Regulations 2025 (C. 28)", []),
    ("no instrument here", []),
])
def test_citations_are_parsed_by_type_year_and_number(text, expected):
    assert extract_instrument_citations(text) == expected


def test_citations_are_deduplicated_in_order_and_capped():
    text = "SSI 2025/377, ssi/2025/377, SSI 2025/119, " + ", ".join(
        f"SSI 2024/{n}" for n in range(1, 10))
    got = extract_instrument_citations(text)
    assert got[:2] == [("ssi", 2025, 377), ("ssi", 2025, 119)]
    assert len(got) == 5


def test_the_tool_arguments_and_the_label():
    assert lookup_args({"legislation_type": "SSI", "year": "2025", "number": 377}) == \
        ("ssi", 2025, 377)
    assert lookup_args({"legislation_id": "ssi/2025/377"}) == ("ssi", 2025, 377)
    assert lookup_args({"legislation_id": "http://www.legislation.gov.uk/id/asp/2025/2"}) == \
        ("asp", 2025, 2)
    for bad in ({"legislation_type": "ssix", "year": 2025, "number": 1},
                {"legislation_type": "ssi", "year": 2025},
                {"legislation_id": "the SSI"}, None):
        assert lookup_args(bad) is None
    assert citation_label(("ssi", 2025, 377)) == "SSI 2025/377"
    assert citation_label(("asp", 2025, 2)) == "2025 asp 2"
    assert citation_label(("eur", 2016, 679)) == "eur/2016/679"


# --- the executor: three states, and a failure that is not a negative ---------

def _lex(monkeypatch, lookup, sections=None):
    """Stub `_request_with_retry` with (status, body) per endpoint, recording
    the calls made."""
    asked = []

    async def fake(client, method, url, *, name="", **kwargs):
        asked.append((url.rsplit("/legislation", 1)[-1], kwargs.get("json")))
        status, body = sections if url.endswith("/section/lookup") else lookup
        if isinstance(status, Exception):
            raise status
        return httpx.Response(status, json=body, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)
    return asked


def _run(args):
    return json.loads(asyncio.run(executor.execute_worker_tool(LOOKUP_TOOL, args)))


def test_not_held_is_a_404_the_api_calls_not_found(monkeypatch):
    asked = _lex(monkeypatch, (404, {"detail": "Legislation not found: ssi 2025 No. 377"}))
    got = _run({"legislation_type": "ssi", "year": 2025, "number": 377})
    assert got["status"] == "not_held"
    assert got["legislation_id"] == "ssi/2025/377" and got["label"] == "SSI 2025/377"
    assert "url" not in got
    # The API takes an INTEGER number, and no text check follows a 404.
    assert asked == [("/lookup", {"legislation_type": "ssi", "year": 2025, "number": 377})]


def test_a_stub_is_held_without_text(monkeypatch):
    asked = _lex(monkeypatch, (200, RECORD_119),
                 (404, {"detail": "No sections found for legislation ID: ssi/2025/119"}))
    got = _run({"legislation_type": "ssi", "year": 2025, "number": 119})
    assert got["status"] == "held_without_text" and got["text_held"] is False
    assert got["url"] == "https://www.legislation.gov.uk/id/ssi/2025/119"
    assert "into force on 10 May 2025" in got["description"]
    assert asked[1] == ("/section/lookup", {"legislation_id": "ssi/2025/119", "limit": 1})


def test_a_held_instrument_is_held_with_text(monkeypatch):
    _lex(monkeypatch, (200, RECORD_ASP), (200, [{"text": "Section 1) ...", "uri": "x"}]))
    got = _run({"legislation_id": "asp/2025/2"})
    assert got["status"] == "held" and got["text_held"] is True
    assert got["title"] == "An Example Act 2025"


@pytest.mark.parametrize("lookup", [
    (500, {"detail": "boom"}),
    (422, {"detail": [{"msg": "bad"}]}),
    # A route 404 (an endpoint moved) is not the API's "Legislation not found:
    # <id>". Read as not-held, it would say every instrument is absent.
    (404, {"detail": "Not Found"}),
    (httpx.ConnectTimeout("slow"), None),
])
def test_a_lookup_that_did_not_complete_is_never_a_negative(monkeypatch, lookup):
    _lex(monkeypatch, lookup)
    got = _run({"legislation_type": "ssi", "year": 2025, "number": 377})
    assert got["status"] == "lookup_failed"
    assert "says nothing" in got["note"]


def test_a_route_404_on_the_text_check_leaves_the_text_question_open(monkeypatch):
    _lex(monkeypatch, (200, RECORD_ASP), (404, {"detail": "Not Found"}))
    got = _run({"legislation_type": "asp", "year": 2025, "number": 2})
    assert got["status"] == "held" and got["text_held"] is None


def test_a_held_instrument_whose_text_check_failed_is_held_with_the_question_open(monkeypatch):
    _lex(monkeypatch, (200, RECORD_ASP), (503, {"detail": "busy"}))
    got = _run({"legislation_type": "asp", "year": 2025, "number": 2})
    assert got["status"] == "held" and got["text_held"] is None


def test_invalid_arguments_are_refused_without_a_call(monkeypatch):
    asked = _lex(monkeypatch, (404, {}))
    got = _run({"legislation_type": "nonsense", "year": 2025, "number": 1})
    assert got["status"] == "invalid" and asked == []


# --- the Worker's brief: routed in code before round 1 -------------------------

def _outcome(status, lid="ssi/2025/377", label="SSI 2025/377", **kw):
    return json.dumps({"tool": LOOKUP_TOOL, "legislation_id": lid, "label": label,
                       "status": status, **kw})


def test_the_brief_block_states_each_outcome_in_sentences():
    block = lookup_brief_block([
        _outcome("not_held"),
        _outcome("held_without_text", "ssi/2025/119", "SSI 2025/119", title="T [x]",
                 description="brings s.2 into force [on 10 May 2025]."),
        _outcome("held", "asp/2025/2", "2025 asp 2", title="An Act"),
        _outcome("lookup_failed", "ssi/2026/1", "SSI 2026/1"),
    ])
    assert "SSI 2025/377: NOT HELD" in block and "not an error in the citation" in block
    assert "SSI 2025/119 (T (x)): HELD WITHOUT TEXT" in block and "never as not found" in block
    assert "under legislation_id asp/2025/2. Check that this title is the instrument" in block
    assert "SSI 2026/1" not in block             # a failed lookup says nothing
    assert "\n-" not in block and "\n*" not in block   # sentences, not bullets
    # It is a tool block: an echo of it never reaches the lawyer.
    assert strip_scope_blocks("Answer." + block)[0] == "Answer."
    assert lookup_brief_block([_outcome("lookup_failed")]) == ""


def test_the_same_number_under_two_types_is_said_to_be_two_instruments():
    """`uksi/2026/170` is held and is an unrelated planning instrument; the SSI
    the lawyer meant is not held. A brief unsure of the type names both."""
    block = lookup_brief_block([
        _outcome("not_held", "ssi/2026/170", "SSI 2026/170"),
        _outcome("held", "uksi/2026/170", "SI 2026/170", title="The Planning Order 2026"),
    ])
    assert "SSI 2026/170 and SI 2026/170 share a year and number but are different " \
           "instruments: never present one as the other." in block
    assert "Check that this title is the instrument the question is about" in block


def _worker(monkeypatch, brief, lex_by_id, research_mode="legislation_only"):
    """Run the Worker with a fake loop that records its brief; LEX answers by id."""
    set_request_provider_config({"_provider": "openrouter", "_research_mode": research_mode,
                                 "model": "test-model"})
    seen = {}

    async def fake(client, method, url, *, name="", **kwargs):
        body = kwargs.get("json") or {}
        lid = body.get("legislation_id") or "{legislation_type}/{year}/{number}".format(**body)
        lookup, sections = lex_by_id[lid]
        status, payload = sections if url.endswith("/section/lookup") else lookup
        return httpx.Response(status, json=payload, request=httpx.Request(method, url))

    monkeypatch.setattr(executor, "_request_with_retry", fake)

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None,
                   **kw):
        seen["brief"] = messages[1]["content"]
        seen["tools"] = [t["function"]["name"] for t in tools]
        return {"role": "assistant", "content": "Report."}

    result = asyncio.run(run_worker_agent(loop, lambda *a, **k: None, brief, "test-model",
                                          None, 0))
    return seen, result


NOT_FOUND = ((404, {"detail": "Legislation not found: ssi 2025 No. 377"}), None)
STUB = ((200, RECORD_119), (404, {"detail": "No sections found for legislation ID: x"}))


def test_the_worker_is_handed_the_lookup_of_every_instrument_its_brief_names(monkeypatch):
    seen, result = _worker(monkeypatch, "What does SSI 2025/377 do? Compare SSI 2025/119.",
                           {"ssi/2025/377": NOT_FOUND, "ssi/2025/119": STUB})
    assert seen["brief"].startswith("What does SSI 2025/377 do? Compare SSI 2025/119.")
    assert "SSI 2025/377: NOT HELD" in seen["brief"]
    assert "HELD WITHOUT TEXT" in seen["brief"]
    assert LOOKUP_TOOL in seen["tools"]
    # The step's record carries both, so the Manager's block and the footer can.
    looked = {e["legislation_id"]: e["status"] for e in result["searches"]
              if e.get("tool") == "lookup"}
    assert looked == {"ssi/2025/377": "not_held", "ssi/2025/119": "held_without_text"}
    assert "Looked up by number" in result["content"]


def test_a_brief_with_no_numbered_instrument_is_untouched(monkeypatch):
    seen, _ = _worker(monkeypatch, "Is the Example Act 2025 in force?", {})
    assert seen["brief"] == "Is the Example Act 2025 in force?"


def test_a_case_law_worker_is_not_routed(monkeypatch):
    seen, _ = _worker(monkeypatch, "Cases on SSI 2025/377?", {"ssi/2025/377": NOT_FOUND},
                      research_mode="case_law_only")
    assert seen["brief"] == "Cases on SSI 2025/377?"
    assert LOOKUP_TOOL not in seen["tools"]


def test_a_failed_routed_lookup_leaves_the_brief_as_it_was(monkeypatch):
    seen, result = _worker(monkeypatch, "SSI 2025/377?",
                           {"ssi/2025/377": ((503, {"detail": "busy"}), None)})
    assert seen["brief"] == "SSI 2025/377?"
    assert not [e for e in result["searches"] if e.get("tool") == "lookup"]


def test_a_memo_served_lookup_is_still_recorded_for_its_step(monkeypatch):
    """P2.9's lesson: a memo hit is still the step's retrieval. A second
    delegation naming the same instrument is served from the memo, and without
    this its block and the lawyer's footer would not say it was looked up."""
    from src.agent.agent_shared import run_worker_tool

    set_request_provider_config({"_provider": "openrouter",
                                 "_research_mode": "legislation_only", "model": "m"})
    asked = _lex(monkeypatch, (404, {"detail": "Legislation not found: ssi 2025 No. 377"}))
    memo, logs = {}, ([], [])
    args = {"legislation_type": "ssi", "year": 2025, "number": 377}
    for log in logs:
        asyncio.run(run_worker_tool(LOOKUP_TOOL, dict(args), "q", lambda *a, **k: None, "m",
                                    tool_memo=memo, search_log=log))
    assert len(asked) == 1                       # the second was a memo hit
    for log in logs:
        assert [e["status"] for e in log if e.get("tool") == "lookup"] == ["not_held"]


# --- the agent that writes the answer, and the lawyer -------------------------

def _log(*outcomes):
    log = []
    for o in outcomes:
        record_lookup(log, LOOKUP_TOOL, {}, o)
    return log


def test_only_a_definite_outcome_is_recorded():
    log = _log(_outcome("not_held"), _outcome("lookup_failed", "ssi/2026/1"),
               json.dumps({"tool": LOOKUP_TOOL, "status": "invalid"}), "not json")
    assert [e["legislation_id"] for e in log] == ["ssi/2025/377"]
    record_lookup(log, "search_legislation", {}, _outcome("not_held", "ssi/2026/170"))
    assert len(log) == 1


def test_a_lookup_only_step_does_not_ask_for_search_terms_it_never_had():
    block = worker_scope_block(_log(_outcome("not_held")))
    assert "SSI 2025/377 NOT HELD" in block
    assert "No ranked search was run in this step" in block
    assert "search terms above" not in block


def test_a_searching_step_keeps_its_closing_rule():
    log = _log(_outcome("not_held"))
    log.insert(0, {"tool": "search_legislation", "query": "x", "shown": 5, "matched": 100})
    block = worker_scope_block(log)
    assert "search terms above" in block and "Looked up by number" in block


def test_the_footer_states_not_held_and_stub_and_is_silent_on_held():
    searched = [{"tool": "search_legislation", "query": "q", "shown": 5, "matched": 9}]
    log = searched + _log(_outcome("not_held"),
                          _outcome("held_without_text", "ssi/2025/119", "SSI 2025/119"),
                          _outcome("held", "asp/2025/2", "2025 asp 2"))
    footer = answer_scope_footer(log)
    assert ("SSI 2025/377 was looked up by its number and is not held in this index; that "
            "is a gap in the index, not a sign that the citation is wrong.") in footer
    assert "SSI 2025/119 was looked up by its number: this index holds its record" in footer
    assert "asp 2" not in footer
    assert answer_scope_footer(searched + _log(_outcome("held", "asp/2025/2", "2025 asp 2"))) \
        == answer_scope_footer(searched)


def test_a_turn_that_only_looked_up_still_tells_the_lawyer():
    only = _log(_outcome("not_held"))
    assert answer_scope_footer(only) == ""
    line = lookup_scope_footer(only)
    assert line.startswith("\n\n*Search scope: no ranked search of the legislation index")
    assert "SSI 2025/377 was looked up by its number" in line and line.endswith("*")
    assert lookup_scope_footer(_log(_outcome("held", "asp/2025/2", "2025 asp 2"))) == ""


def test_the_footer_clause_trips_no_detector_and_is_stripped():
    """P2.2's lesson: a product clause must not corrupt the instrument grading
    it. The clause is clear of `NEG_ASSERTED`, and the whole footer is removed
    by `_without_footer` before any prose is graded, lookup-only shape too."""
    from tools.replay_report import LK_FOOTER, NEG_ASSERTED, _without_footer

    clause = _lookup_footer_clause(_log(_outcome("not_held"),
                                        _outcome("held_without_text", "ssi/2025/119",
                                                 "SSI 2025/119")))
    assert not NEG_ASSERTED.search(clause)
    assert LK_FOOTER.search(clause)
    for footer in (answer_scope_footer([{"tool": "search_legislation", "query": "q"}]
                                       + _log(_outcome("not_held"))),
                   lookup_scope_footer(_log(_outcome("not_held")))):
        assert _without_footer("Answer." + footer) == "Answer."


# --- the wiring decisions, each deliberate ------------------------------------

def test_the_tool_is_offered_to_both_legislation_research_types_only():
    assert LOOKUP_TOOL in [t["function"]["name"] for t in WORKER_TOOLS]
    for mode in ("legislation_only", "legislation_and_case_law"):
        assert LOOKUP_TOOL in [t["function"]["name"] for t in get_worker_tools(mode)]
    for mode in ("case_law_only", "parliamentary_records", "westminster_records"):
        assert LOOKUP_TOOL not in [t["function"]["name"] for t in get_worker_tools(mode)]


def test_it_is_neither_a_discovery_search_nor_a_retrieval_nor_cached():
    assert LOOKUP_TOOL not in _PHASE1_SEARCH_TOOLS | _PHASE2_RETRIEVAL_TOOLS
    # Its output is a few hundred characters, never summarised, so the shared
    # summary cache would never engage on it: left out rather than admitted
    # for nothing (the drafting invariant is unaffected).
    assert LOOKUP_TOOL not in CACHEABLE_TOOLS
    assert "search_drafting_guidance" not in CACHEABLE_TOOLS


def test_it_is_not_counted_against_the_discovery_budget():
    """P2.7's budget bounds a ranked search that loops. A lookup cannot page
    through a ranking, and code makes one per numbered instrument before the
    Worker's first round, where no round is in context."""
    from src.utils.discovery_budget import (
        LEGISLATION_DISCOVERY_TOOLS,
        legislation_budget_blocks,
        new_search_budget,
    )

    assert LOOKUP_TOOL not in LEGISLATION_DISCOVERY_TOOLS
    budget = new_search_budget("legislation_only")
    budget["rounds"] = set(range(100))
    assert not legislation_budget_blocks(budget, LOOKUP_TOOL)
