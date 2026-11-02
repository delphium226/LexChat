"""FIX_PLAN P3.57: a literal string searched for, by code, over a made-under list.

6382 and 6383 ask which of the 37 instruments made under s.95 contain '£'; a
section search ranks by meaning and missed SSI 2025/340 in every stored run.
Pins: the detector (what counts as a literal, and what does not), the matcher,
the per-instrument outcome from a provision list and from legislation.gov.uk's
text, the Worker's block (wording, size bound, strip), the gate through
`run_worker_tool` (a whole list of 40 or fewer, a literal in the brief or the
legal professional's message), byte-identical output where it does not fire,
the memo, the not-read paths, the scope record, the Manager's limb, P3.53's
list-coverage line and the footer. No network: the provision-list read and
legislation.gov.uk's read are served synthetically. Synthetic instruments
("Widget (Scotland) Act 1901", `ssi/1901/N`); the live dry run is in the
gitignored evidence folder (`evidence/seam/s52/p357/`).
"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.agent_shared import run_worker_tool  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.agent.tools import literal_scan as io  # noqa: E402
from src.agent.tools import published_text as ptio  # noqa: E402
from src.services import made_under_store as store  # noqa: E402
from src.utils import literal_scan as ls  # noqa: E402
from src.utils import made_under as mu  # noqa: E402
from src.utils import search_scope as ss  # noqa: E402

TOOL = mu.MADE_UNDER_TOOL
ARGS = {"act": "Widget (Scotland) Act 1901", "section": "95"}
COV = store.coverage({"label": "Scottish statutory instruments made from 1901 to 1905",
                      "harvested_at": "1906-01-01"}, None, 0)
BRIEF = ("Find SSIs made under section 95 of the Widget (Scotland) Act 1901 that contain "
         "the '£' symbol in their text.")
PLAIN = "Find SSIs made under section 95 of the Widget (Scotland) Act 1901."
LEX = "http://www.legislation.gov.uk/"


def _found(n):
    rows = [(f"ssi/1901/{i}", f"The Widget Regulations 1901 No. {i}",
             "Widget (Scotland) Act 1901", "asp/1901/1", "power") for i in range(1, n + 1)]
    return json.dumps(store.build_result("Widget (Scotland) Act 1901", "95", "section/95",
                                         rows, [], COV))


def _row(lid, prov, text):
    return {"uri": f"{LEX}{lid}/{prov}/made", "id": f"{LEX}id/{lid}/{prov}", "text": text,
            "provision_type": "schedule" if prov.startswith("schedule") else "section"}


# Instrument 1 holds '£' twice in regulation 3 and once in Schedule 2; 2 holds
# none; 3 is held without text (legislation.gov.uk's text holds '£' once); the
# rest hold none.
def _lists(lid):
    if lid == "ssi/1901/1":
        return {"status": "ok", "complete": True, "rows": [
            _row(lid, "regulation/1", "These Regulations may be cited as the Widget Regulations."),
            _row(lid, "regulation/3", "The weekly rate is £11.29 [F1 and the lower rate £5]."),
            _row(lid, "schedule/2", "SCHEDULE 2 A grant of £300 is payable."),
        ]}
    if lid == "ssi/1901/3":
        return {"status": "no_text"}
    return {"status": "ok", "complete": True, "rows": [
        _row(lid, "regulation/1", "These Regulations may be cited as the Widget Regulations."),
        _row(lid, "regulation/2", "A widget must be blue."),
    ]}


def _serve(monkeypatch, lists=_lists, published=None, calls=None):
    calls = calls if calls is not None else []

    async def read_list(lid, on_chunk, timing_collector, tool_name):
        calls.append(("list", lid))
        out = lists(lid)
        if isinstance(out, Exception):
            raise out
        return out

    async def read_published(lid, **kw):
        calls.append(("lgu", lid))
        if published is not None:
            return published(lid)
        return {"status": "ok", "version": "made", "url": f"https://www.legislation.gov.uk/{lid}/made",
                "text": "2026 No. 3 The Widget Regulations. 2. The fee is £40."}

    monkeypatch.setattr(io, "_read_list", read_list)
    monkeypatch.setattr(ptio, "read_published_text", read_published)
    return calls


async def _chunk(*a, **k):
    return None


def _run(raw, query=BRIEF, cfg=None, log=None, memo=None, urls=None, budget=None, times=1):
    log = [] if log is None else log

    async def go():
        set_request_provider_config(dict(cfg or {"_test": True}))
        out = None
        with patch("src.agent.agent_shared.execute_worker_tool", new=AsyncMock(return_value=raw)):
            for _ in range(times):
                out = await run_worker_tool(TOOL, dict(ARGS), query, _chunk, "m", search_log=log,
                                            tool_memo=memo, retrieved_urls=urls,
                                            context_budget=budget)
        return out
    return asyncio.run(go()), log


def _expected_without_scan(raw):
    return raw + mu.made_under_note(raw)


# --- (1) the detector -------------------------------------------------------------

@pytest.mark.parametrize("text, want", [
    (BRIEF, "£"),                                                    # 6383's brief
    ("I am looking for scottish statutory instruments, made under the powers in section 95 "
     "of the Social Security (Scotland) act 2018, which feature a £ symbol within their text", "£"),
    ("RESEARCH TASK: Review text of identified SSIs for the £ symbol\n\nExamine the full text.", "£"),
    ("Which of them contain a pound sign?", "£"),
    ("Which of them use the phrase “qualifying week”?", "qualifying week"),
    ('Which of these regulations contain the words "Scottish Ministers"?', "Scottish Ministers"),
    ("Do any of them mention the word carer?", "carer"),
    ("Which of them include the § character?", "§"),
])
def test_the_detector_finds_a_literal(text, want):
    assert ls.detect_literal(text) == want


@pytest.mark.parametrize("text", [
    PLAIN,
    "Which of them set the £300 grant?",                             # an amount, not a literal
    "Which of them set a rate in £ per week?",                       # no symbol word, no cue
    "Where is 'carer' defined in these regulations?",                # P3.34's question
    "Which of these regulations include a definition of 'carer'?",   # P3.34's, with a cue word
    "Which of them include a £300 grant?",                           # an amount, with a cue word
    "Which instruments were made under 'section 95'?",               # a provision
    "Instruments made using 'the Social Security (Scotland) Act 2018'",  # a title
    "Which concern Carer's Allowance and the carers' premium?",      # apostrophes, not quotes
    "",
    None,
])
def test_the_detector_finds_none(text):
    assert ls.detect_literal(text) == ""


def test_the_brief_is_read_before_the_lawyers_message():
    assert ls.detect_literal("Which contain '€'?", "Which contain '£'?") == "€"
    assert ls.detect_literal(PLAIN, "Which contain '£'?") == "£"


# --- (2) the matcher --------------------------------------------------------------

def test_a_word_matches_whole_words_any_case_and_any_spacing():
    rx = ls.literal_pattern("Scottish Ministers")
    assert rx.search("the scottish\n  ministers may")
    assert not rx.search("the Scottish Ministerss")
    rx = ls.literal_pattern("carer")
    assert rx.search("a Carer's grant") and not rx.search("careers") and not rx.search("carers")


def test_a_symbol_matches_beside_digits_and_an_apostrophe_either_way():
    assert len(ls.literal_pattern("£").findall("£0 and £11.29")) == 2
    assert ls.literal_pattern("carer's").search("the carer’s grant")


# --- (3) the outcomes ---------------------------------------------------------------

def test_an_outcome_from_a_provision_list_places_each_match():
    o = ls.outcome_from_rows(_lists("ssi/1901/1")["rows"], "£")
    assert o["status"] == "read" and o["count"] == 3 and o["version"] == "made"
    assert [(p["label"], p["count"]) for p in o["provisions"]] == [("regulation 3", 2),
                                                                   ("schedule 2", 1)]
    assert o["provisions"][0]["url"] == "https://www.legislation.gov.uk/ssi/1901/1/regulation/3"
    assert "[" not in o["provisions"][0]["snippet"] and "(F1" in o["provisions"][0]["snippet"]


def test_an_outcome_with_no_match_is_read_and_zero():
    o = ls.outcome_from_rows(_lists("ssi/1901/2")["rows"], "£")
    assert o["status"] == "read" and o["count"] == 0 and o["provisions"] == []


def test_an_outcome_from_published_text():
    o = ls.outcome_from_text("The fee is £40.", "£", url="http://www.legislation.gov.uk/ssi/1901/3/made",
                             version="made")
    assert o["count"] == 1 and o["source"] == "legislation.gov.uk"
    assert o["provisions"][0]["url"].startswith("https://")
    assert ls.outcome_from_text("", "£")["status"] == "not_read"


# --- (4) through run_worker_tool: it fires ----------------------------------------------

def test_a_literal_over_a_whole_list_hands_the_worker_the_scan(monkeypatch):
    calls = _serve(monkeypatch)
    raw = _found(4)
    urls = set()
    out, log = _run(raw, urls=urls)
    assert out.startswith(_expected_without_scan(raw))
    block = out[len(_expected_without_scan(raw)):]
    assert block.startswith('\n\n[SEARCH SCOPE — text scan by code: the question asks for "£"')
    assert "read the text of 4 of the 4 instruments" in block
    assert "Found in 2:\n- ssi/1901/1 (The Widget Regulations 1901 No. 1): 3 times in 2 provision(s)" in block
    assert "regulation 3 (https://www.legislation.gov.uk/ssi/1901/1/regulation/3)" in block
    assert "- ssi/1901/3 (The Widget Regulations 1901 No. 3): once in legislation.gov.uk's text" in block
    assert "Not found in the text read, 2: ssi/1901/2, ssi/1901/4." in block
    assert "Not read" not in block
    assert block.rstrip().endswith('Do not section-search these instruments for "£": this scan has read them.]')
    assert block.count("[") == 1 and block.count("]") == 1
    assert sorted(calls) == [("lgu", "ssi/1901/3"), ("list", "ssi/1901/1"), ("list", "ssi/1901/2"),
                             ("list", "ssi/1901/3"), ("list", "ssi/1901/4")]
    assert "legislation.gov.uk/ssi/1901/1/regulation/3" in urls
    e = [x for x in log if x["tool"] == ls.SCAN_ENTRY]
    assert e == [{"tool": ls.SCAN_ENTRY, "literal": "£", "listed": 4,
                  "ids": ["ssi/1901/1", "ssi/1901/2", "ssi/1901/3", "ssi/1901/4"],
                  "found": ["ssi/1901/1", "ssi/1901/3"], "absent": ["ssi/1901/2", "ssi/1901/4"],
                  "unread": []}]


def test_the_lawyers_message_alone_can_ask_for_it(monkeypatch):
    _serve(monkeypatch)
    out, _ = _run(_found(4), query=PLAIN,
                  cfg={"_cache_key_query": "which of them feature a £ symbol?"})
    assert "text scan by code" in out


def test_the_scan_is_memoised_and_a_memo_hit_records_it_again(monkeypatch):
    calls = _serve(monkeypatch)
    memo, log = {}, []
    first, _ = _run(_found(4), memo=memo, log=log)
    n = len(calls)
    log2 = []
    again, _ = _run(_found(4), memo=memo, log=log2)
    assert again == first and len(calls) == n
    assert [x for x in log2 if x["tool"] == ls.SCAN_ENTRY] == [x for x in log if x["tool"] == ls.SCAN_ENTRY]


def test_provision_lists_are_read_once_a_request(monkeypatch):
    calls = _serve(monkeypatch)

    async def go():
        set_request_provider_config({"_test": True})
        a = await io.scan_instruments(["ssi/1901/1", "ssi/1901/2"], "£")
        b = await io.scan_instruments(["ssi/1901/1", "ssi/1901/2"], "fee")
        return a, b
    a, b = asyncio.run(go())
    assert calls.count(("list", "ssi/1901/1")) == 1
    assert a["ssi/1901/1"]["count"] == 3 and b["ssi/1901/1"]["count"] == 0


# --- (5) the instruments it could not read -------------------------------------------------

def test_an_instrument_it_could_not_read_is_named_not_counted_absent(monkeypatch):
    def lists(lid):
        return {"status": "failed"} if lid == "ssi/1901/2" else _lists(lid)

    def published(lid):
        return {"status": ptio.pt.LIMIT, "limit": 8}
    _serve(monkeypatch, lists=lists, published=published)
    out, log = _run(_found(4))
    assert "read the text of 2 of the 4 instruments" in out
    assert ("Not read, 2: ssi/1901/2 (the read did not complete); ssi/1901/3 (this request's "
            "limit of legislation.gov.uk reads was reached).") in out
    assert "Not found in the text read, 1: ssi/1901/4." in out
    assert 'Name each instrument under Not read as not checked for "£"' in out
    limb = ss.scan_limb(log)
    assert "2 could not be read (ssi/1901/2, ssi/1901/3)" in limb
    assert "one not read must be named as not checked" in limb
    foot = ss._made_under_footer_clause(log)
    assert foot.endswith('code read the text of 2 (their provisions and schedules as made) and '
                         'searched it for "£"; the other 2 could not be read and were not checked.')


def test_a_read_past_the_deadline_is_not_read(monkeypatch):
    async def slow(lid, *a):
        if lid == "ssi/1901/2":
            await asyncio.sleep(5)
        return _lists(lid)
    _serve(monkeypatch)
    monkeypatch.setattr(io, "_read_list", slow)
    monkeypatch.setattr(io, "SCAN_DEADLINE_S", 0.2)
    out, log = _run(_found(4))
    assert "ssi/1901/2 (no reply in time)" in out


def test_any_failure_leaves_the_result_exactly_as_it_was(monkeypatch):
    monkeypatch.setattr(io, "scan_instruments", AsyncMock(side_effect=RuntimeError("boom")))
    raw = _found(4)
    out, log = _run(raw)
    assert out == _expected_without_scan(raw)
    assert not [x for x in log if x["tool"] == ls.SCAN_ENTRY]


# --- (6) where it does not fire: byte-identical ----------------------------------------------

@pytest.mark.parametrize("raw, query", [
    (_found(4), PLAIN),                                   # no literal
    (_found(41), BRIEF),                                  # a cut list (40 of 41 listed)
    (json.dumps({"tool": TOOL, "status": "act_not_in_record", "count": 0, "instruments": [],
                 "coverage": {"statement": "x."}}), BRIEF),
])
def test_it_does_not_fire_and_nothing_moves(monkeypatch, raw, query):
    calls = _serve(monkeypatch)
    out, log = _run(raw, query=query)
    assert out == _expected_without_scan(raw) and calls == []
    assert not [x for x in log if x["tool"] == ls.SCAN_ENTRY]


def test_a_list_longer_than_forty_is_never_scanned(monkeypatch):
    calls = _serve(monkeypatch)
    d = json.loads(_found(40))
    d["instruments"].append(dict(d["instruments"][0], legislation_id="ssi/1901/41"))
    d["count"] = 41
    out, _ = _run(json.dumps(d))
    assert calls == [] and "text scan by code" not in out


def test_another_tool_is_never_scanned(monkeypatch):
    calls = _serve(monkeypatch)

    async def go():
        set_request_provider_config({"_test": True})
        with patch("src.agent.agent_shared.execute_worker_tool",
                   new=AsyncMock(return_value=json.dumps({"results": []}))):
            return await run_worker_tool("search_legislation_sections",
                                         {"legislation_id": "ssi/1901/1", "query": "£"},
                                         BRIEF, _chunk, "m", search_log=[])
    out = asyncio.run(go())
    assert calls == [] and "text scan" not in out


# --- (7) the block's size -----------------------------------------------------------------

def test_the_block_drops_snippets_then_cuts_the_list_to_fit():
    listed = [f"ssi/1901/{i}" for i in range(1, 41)]
    o = ls.outcome_from_rows([_row("ssi/1901/1", f"regulation/{k}", "x £1 " + "y" * 200)
                              for k in range(1, 9)], "£")
    outcomes = {l: o for l in listed}
    full = ls.scan_block("£", listed, outcomes)
    assert len(full) <= ls.BLOCK_MAX_CHARS
    small = ls.scan_block("£", listed, outcomes, max_chars=3000)
    assert len(small) <= 3000 and "(this list is cut here for length)" in small
    assert small.rstrip().endswith("this scan has read them.]")


def test_the_route_sizes_the_block_within_the_context_budget(monkeypatch):
    _serve(monkeypatch)
    budget = {"used": 249_000, "limit": 250_000}
    out, _ = _run(_found(4), budget=budget)
    block = out[len(_expected_without_scan(_found(4))):]
    assert 0 < len(block) <= 2_000


# --- (8) the Manager's limb, P3.53's line and the footer -----------------------------------------

def _scan_log(n=6, unread=()):
    log = []
    ss.record_made_under(log, _found(n))
    ids = [f"ssi/1901/{i}" for i in range(1, n + 1)]
    outcomes = {l: ({"status": "not_read", "reason": "failed"} if l in unread else
                    {"status": "read", "count": 1 if l.endswith(("/1", "/2")) else 0, "provisions": []})
                for l in ids}
    log.append(ls.scan_entry("£", ids, outcomes))
    return log


def test_the_limb_names_found_absent_and_unread():
    limb = ss.scan_limb(_scan_log(6, unread=("ssi/1901/6",)))
    assert limb.startswith("Text scan by code: of the 6 instruments the made-under record listed, "
                           'code read the text of 5 in full and searched each for "£": found in 2 '
                           "(ssi/1901/1, ssi/1901/2), not found in the text read in 3 (ssi/1901/3, "
                           "ssi/1901/4, ssi/1901/5); 1 could not be read (ssi/1901/6).")


def test_the_worker_block_carries_the_limb_and_the_list_coverage_line():
    block = ss.worker_scope_block(_scan_log(6), {"_chat_mode": "conversational"})
    assert "Text scan by code:" in block
    assert ("List coverage: the made-under record listed 6 instruments, and code read every one "
            'of them in full and searched it for "£" (the text scan).') in block


def test_list_coverage_counts_the_scan_and_prefers_it_on_a_tie():
    log = _scan_log(6)
    for i in (1, 2, 3, 4, 5, 6):
        ss.record_search(log, "search_legislation_sections",
                         {"legislation_id": f"ssi/1901/{i}", "query": "£"}, {"results": [{"url": "x"}]})
    cov = ss.list_coverage(log)
    assert cov["scan"] is True and cov["M"] == 6 and cov["N"] == 6
    cov = ss.list_coverage(_scan_log(6, unread=("ssi/1901/5", "ssi/1901/6")))
    assert cov["M"] == 4 and cov["unsearched"] == ["ssi/1901/5", "ssi/1901/6"]
    assert "could not be read (ssi/1901/5, ssi/1901/6)" in ss._list_coverage_text(cov, "this step")


def test_the_footer_says_it_once():
    foot = ss._made_under_footer_clause(_scan_log(6, unread=("ssi/1901/6",)))
    assert foot.count("could not be read") == 1 and "were searched for" not in foot
    foot = ss._made_under_footer_clause(_scan_log(6))
    assert foot.endswith('code read the text of every one (its provisions and schedules as made) '
                         'and searched it for "£".')


def test_without_a_scan_nothing_in_the_record_moves():
    log = []
    ss.record_made_under(log, _found(6))
    for i in (1, 2, 3):
        ss.record_search(log, "search_legislation_sections",
                         {"legislation_id": f"ssi/1901/{i}", "query": "£"}, {"results": [{"url": "x"}]})
    assert ss.scan_limb(log) == "" and ss.scan_footer(log) == ""
    assert "scan" not in ss.list_coverage(log)
    assert ss._list_coverage_footer(log).startswith(" Of the 6 instruments the made-under record "
                                                    "lists, 3 were searched for")


def test_the_block_is_stripped_from_an_answer_that_echoes_it(monkeypatch):
    _serve(monkeypatch)
    raw = _found(4)
    out, _ = _run(raw)
    block = out[len(_expected_without_scan(raw)):]
    stripped, n = ss.strip_scope_blocks("Answer." + block)
    assert stripped == "Answer." and n >= 1
