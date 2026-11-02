"""P3.57 follow-up: a text scan's result stands over a later ranked section search.

`wave5_p357` 6382 (Deep Research), 3 of 3: step 1's scan by code read all 37
instruments made under s.95 and found '£' in 20, SSI 2025/340 among them. Step 2
was handed the 20 ids but not the scan, section-searched each for "£", got no
'£' provision of 2025/340 back (the summary said the symbol "is not present"),
and reported it as not containing '£'; the synthesis called it a discrepancy.
Now code tells each later reader what the scan read: the later step's brief
(`step_handover.scan_handover_line`), a section search of a scanned instrument
for the scanned string (`literal_scan.search_scan_note`), and the synthesis
(`literal_scan.scan_synthesis_note`). Without a scan, nothing moves.

Every instrument here is synthetic.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.agent_core import (  # noqa: E402
    _build_step_brief,
    build_synthesis_messages,
    run_deep_research,
)
from src.agent.agent_shared import run_worker_tool  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.utils import literal_scan as ls  # noqa: E402
from src.utils import step_handover as SH  # noqa: E402
from src.utils.instrument_lookup import extract_instrument_citations  # noqa: E402
from src.utils.search_scope import strip_scope_blocks  # noqa: E402
from tools import seam_replay  # noqa: E402

from tests.test_literal_scan import BRIEF, TOOL, ARGS, _found, _serve, _chunk  # noqa: E402

SECTIONS = "search_legislation_sections"
# A ranked section search of instrument 1 that returns none of its '£' provisions.
RANKED = json.dumps({"results": [{"legislation_id": "ssi/1901/1", "title": "reg. 1",
                                  "url": "http://www.legislation.gov.uk/ssi/1901/1/regulation/1/made",
                                  "text": "These Regulations may be cited as the Widget Regulations."}]})
ENTRY = {"tool": ls.SCAN_ENTRY, "literal": "£", "listed": 4,
         "ids": ["ssi/1901/1", "ssi/1901/2", "ssi/1901/3", "ssi/1901/4"],
         "found": ["ssi/1901/1", "ssi/1901/3"], "absent": ["ssi/1901/2", "ssi/1901/4"],
         "unread": []}


def _request(calls, cfg=None):
    """Run each `(tool, args, raw)` through run_worker_tool under ONE request
    config, as one request's steps do. Returns the results and the config."""
    cfg = cfg if cfg is not None else {"_test": True, "_chat_mode": "deep_research"}

    async def go():
        set_request_provider_config(cfg)
        outs = []
        for name, args, raw in calls:
            with patch("src.agent.agent_shared.execute_worker_tool",
                       new=AsyncMock(return_value=raw)):
                outs.append(await run_worker_tool(name, dict(args), BRIEF, _chunk, "m",
                                                  search_log=[]))
        return outs
    return asyncio.run(go()), cfg


def _search(lid, query="£"):
    return (SECTIONS, {"legislation_id": lid, "query": query}, RANKED)


def _note(out):
    i = out.find("[SEARCH SCOPE — text scan by code, ssi/")
    return out[i:] if i >= 0 else ""


# --- (c) the section search of a scanned instrument -------------------------------------

def test_a_later_search_of_an_instrument_the_scan_found_it_in_is_told_so(monkeypatch):
    _serve(monkeypatch)
    (_, out), cfg = _request([(TOOL, ARGS, _found(4)), _search("ssi/1901/1")])
    note = _note(out)
    assert note.startswith(
        "[SEARCH SCOPE — text scan by code, ssi/1901/1: earlier in this research code read the "
        'whole text of ssi/1901/1 (every provision and schedule as made) and searched it for "£". '
        "Found 3 times in 2 provisions; regulation 3 "
        "(https://www.legislation.gov.uk/ssi/1901/1/regulation/3): ")
    assert 'That result stands: ssi/1901/1 contains "£".' in note
    assert 'do not report ssi/1901/1 as not containing "£"' in note
    assert note.endswith('do not section-search it for "£" again.]')
    assert note.count("[") == 1 and note.count("]") == 1
    assert len(cfg[ls.STORE_KEY]) == 1


def test_one_the_scan_did_not_find_it_in_is_told_that(monkeypatch):
    _serve(monkeypatch)
    (_, out), _ = _request([(TOOL, ARGS, _found(4)), _search("ssi/1901/2")])
    note = _note(out)
    assert "It is not there. That result stands: you MAY state that ssi/1901/2 does not contain" in note
    assert "never that no later amendment inserts it" in note
    assert "Found" not in note


def test_one_read_from_legislation_gov_uk_is_told_too(monkeypatch):
    _serve(monkeypatch)
    (_, out), _ = _request([(TOOL, ARGS, _found(4)), _search("http://www.legislation.gov.uk/id/ssi/1901/3")])
    assert "Found once in legislation.gov.uk's text; https://www.legislation.gov.uk/ssi/1901/3/made:" in _note(out)


def test_an_instrument_the_scan_could_not_read_gets_no_note(monkeypatch):
    def lists(lid):
        return {"status": "failed"} if lid == "ssi/1901/4" else {"status": "ok", "complete": True, "rows": [
            {"uri": f"http://www.legislation.gov.uk/{lid}/regulation/1/made", "text": "No symbol."}]}
    _serve(monkeypatch, lists=lists)
    (_, out), _ = _request([(TOOL, ARGS, _found(4)), _search("ssi/1901/4")])
    assert _note(out) == ""


@pytest.mark.parametrize("query, fires", [
    ("£", True), ("£ amount rate", True), ("pound sign", True), ("the £ symbol", True),
    ("commencement", False), ("weekly rate", False),
])
def test_only_a_search_for_the_scanned_string_gets_it(monkeypatch, query, fires):
    _serve(monkeypatch)
    (_, out), _ = _request([(TOOL, ARGS, _found(4)), _search("ssi/1901/1", query)])
    assert bool(_note(out)) is fires


def test_without_a_scan_a_section_search_is_unchanged(monkeypatch):
    _serve(monkeypatch)
    (plain,), _ = _request([_search("ssi/1901/1")])
    (_, after), _ = _request([(TOOL, {"act": "Widget (Scotland) Act 1901", "section": "95"},
                               _found(41)), _search("ssi/1901/1")])  # a list cut at 40: no scan
    assert "text scan by code" not in plain
    assert after == plain


def test_another_tool_of_a_scanned_instrument_gets_no_note(monkeypatch):
    _serve(monkeypatch)
    text = json.dumps({"legislation_id": "ssi/1901/1", "text": "The rate is £5."})
    (_, out), _ = _request([(TOOL, ARGS, _found(4)),
                            ("get_legislation_text", {"legislation_id": "ssi/1901/1"}, text)])
    assert _note(out) == ""


def test_the_store_needs_a_request_config():
    ls.remember_scan({}, "£", {"ssi/1901/1": {"status": "read", "count": 1}})
    ls.remember_scan(None, "£", {"ssi/1901/1": {"status": "read", "count": 1}})
    assert ls.search_scan_note(SECTIONS, {"legislation_id": "ssi/1901/1", "query": "£"}, {}) == ""


def test_the_note_is_stripped_if_a_report_echoes_it(monkeypatch):
    _serve(monkeypatch)
    (_, out), _ = _request([(TOOL, ARGS, _found(4)), _search("ssi/1901/1")])
    clean, _ = strip_scope_blocks("Report.\n\n" + _note(out))
    assert "text scan by code" not in clean


# --- (a) the later step's brief ---------------------------------------------------------

STEP = {"title": "Review the identified SSIs for the £ symbol",
        "detail": "Examine the text of the SSIs identified in the previous step."}
PLAN = {"scope_note": "Widget SSIs.", "steps": [{"title": "Find them", "detail": ""}, STEP]}
Q = "Which Widget SSIs feature a £ symbol?"
REPORT = "## Findings\n- [Widget 1](https://www.legislation.gov.uk/ssi/1901/1)\n"


def test_the_scan_line_wording_and_place():
    brief = _build_step_brief(STEP, PLAN, Q, [REPORT], [ENTRY])
    parts = brief.split("\n\n")
    assert parts[-3].startswith(SH.HANDOVER_LABEL)
    assert parts[-2] == (
        "EARLIER STEPS' TEXT SCAN: an earlier step's code read the whole text of 4 of the 4 "
        "instruments the made-under record listed (every provision and schedule as made) and "
        'searched each one for "£": found in 2 (ssi/1901/1, ssi/1901/3); not found in the text '
        "read in 2 (ssi/1901/2, ssi/1901/4). That result stands for each instrument it read, so "
        'this task need not and should not section-search them for "£": a section search ranks '
        'provisions by meaning, and one that does not return "£" does not show that an '
        'instrument lacks it. Where this task asks which of them contain "£", take it from '
        "this scan.")
    assert parts[-1].startswith("CONTEXT:")


def test_the_scan_line_names_what_it_could_not_read():
    e = dict(ENTRY, absent=["ssi/1901/2"], unread=["ssi/1901/4"])
    line = SH.scan_handover_line([e])
    assert "whole text of 3 of the 4" in line
    assert "; not read, 1 (ssi/1901/4). That result" in line


def test_without_a_scan_the_brief_is_unchanged():
    others = [{"tool": "search_legislation_sections", "legislation_id": "ssi/1901/1", "query": "£"},
              {"tool": "made_under", "status": "found", "ids": ENTRY["ids"]}]
    assert (_build_step_brief(STEP, PLAN, Q, [REPORT], others)
            == _build_step_brief(STEP, PLAN, Q, [REPORT], []) == _build_step_brief(STEP, PLAN, Q, [REPORT]))
    assert SH.scan_handover_line(None) == "" and SH.scan_handover_line([{"tool": ls.SCAN_ENTRY}]) == ""


def test_the_scan_line_is_invisible_to_the_lookup_extractor():
    brief = _build_step_brief(STEP, PLAN, Q, [], [ENTRY])
    assert extract_instrument_citations(brief)
    assert extract_instrument_citations(SH.without_handover_line(brief)) == []


@pytest.fixture
def _dr_cfg():
    set_request_provider_config({"_provider": "ollama", "_chat_mode": "deep_research",
                                 "_research_mode": "legislation_only", "model": "m"})
    yield
    set_request_provider_config({})


@pytest.mark.asyncio
async def test_run_deep_research_hands_later_steps_the_scan_and_the_synthesis_its_note(_dr_cfg):
    briefs, synth = [], []

    async def worker(query, model, cancel_event, num_ctx, parent_on_chunk=None,
                     emit_tool_details=False, timing_collector=None, tool_memo=None,
                     retrieved_urls=None):
        briefs.append(query)
        return {"content": REPORT, "sources": [],
                "searches": [dict(ENTRY)] if len(briefs) == 1 else []}

    async def synthesis(messages, *a, **k):
        synth.append(messages)
        return {"role": "assistant", "content": "Report."}

    plan = {"scope_note": "Widgets.", "steps": [PLAN["steps"][0], STEP, dict(STEP, title="Third")]}
    await run_deep_research(synthesis, worker, plan, [{"role": "user", "content": Q}],
                            "m", None, None, 0)
    assert SH.SCAN_HANDOVER_LABEL not in briefs[0]
    assert all(SH.SCAN_HANDOVER_LABEL + " an earlier step's code" in b for b in briefs[1:])
    assert "[SEARCH SCOPE — text scan by code, across every step:" in synth[0][1]["content"]


# --- (b) the synthesis ------------------------------------------------------------------

FINDINGS = [{"title": "One", "detail": "", "content": "Found."}]


def test_the_synthesis_note_wording():
    body = build_synthesis_messages(Q, PLAN, FINDINGS, searches=[ENTRY])[1]["content"]
    i = body.find("\n\n[SEARCH SCOPE — text scan by code, across every step:")
    assert i >= 0
    note = body[i:]
    assert ('It found "£" in 2 (ssi/1901/1, ssi/1901/3) and not in the text read of 2 '
            "(ssi/1901/2, ssi/1901/4).") in note
    assert "never that the instrument lacks it" in note
    assert note.endswith("do not present such a step's report as a discrepancy or a "
                         "conflicting finding.]")
    assert note.count("[") == 1 and note.count("]") == 1
    assert "text scan by code" not in strip_scope_blocks("Answer." + note)[0]


def test_no_scan_or_nothing_found_adds_no_synthesis_note():
    plain = build_synthesis_messages(Q, PLAN, FINDINGS)
    assert build_synthesis_messages(Q, PLAN, FINDINGS, searches=[]) == plain
    none_found = dict(ENTRY, found=[], absent=ENTRY["ids"])
    body = build_synthesis_messages(Q, PLAN, FINDINGS, searches=[none_found])[1]["content"]
    assert "text scan by code, across" not in body


# --- the seam tool reads the scan back from a stored result ------------------------------

@pytest.mark.parametrize("unread", [False, True])
def test_seam_replay_reads_the_scan_entry_back_from_a_stored_block(unread):
    ids = ENTRY["ids"]
    outcomes = {"ssi/1901/1": {"status": "read", "count": 2, "provisions": [
                    {"label": "regulation 3", "url": "https://x/ssi/1901/1/regulation/3", "count": 2,
                     "snippet": "£5"}]},
                "ssi/1901/2": {"status": "read", "count": 0, "provisions": []},
                "ssi/1901/3": {"status": "read", "count": 1, "provisions": [
                    {"label": "its text", "url": "https://x", "count": 1, "snippet": "£1"}]},
                "ssi/1901/4": ({"status": "not_read", "reason": "failed"} if unread
                               else {"status": "read", "count": 0, "provisions": []})}
    block = ls.scan_block("£", ids, outcomes)
    raw = json.dumps({"instruments": [{"legislation_id": i} for i in ids]})
    assert seam_replay.scan_entry_from_block(raw + block, ids) == ls.scan_entry("£", ids, outcomes)
    turn = {"audit": {"delegations": [{"tools": [
        {"name": TOOL, "raw_result": _found(4), "final_result": _found(4) + block}]}]}}
    got = seam_replay.scan_searches_from(turn)
    assert got[-1] == ls.scan_entry("£", ids, outcomes)
    assert seam_replay.scan_searches_from({"audit": {"delegations": [{"tools": [
        {"name": TOOL, "raw_result": _found(4), "final_result": _found(4)}]}]}}) == []
