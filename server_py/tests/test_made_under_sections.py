"""P3.51: the made-under record, for the sections a section search returned.

Thomas's Q16 (6354): the research relied on s.33 of the Housing (Scotland) Act
1987 and never named the record's ssi/2022/356, made under s.33A, because the
made-under tool runs only when a question asks the made-under question. After
each section search, code now hands the Worker the record's instruments for the
sections the search returned and the lettered sections beside them.

Pinned here: reading the returned sections; the block (listed and counted
families, revoked instruments, the cap, no square brackets, stripped from the
answer); once per family per run; no database until the record is loaded; the
memo; the entries reaching the limb and the footer only for an instrument the
report names; and the P2.3 grader reading the block. Synthetic ids, 1963 or
later (P3.49 treats an earlier id specially).
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import agent_core, agent_shared  # noqa: E402
from src.agent.provider_factory import set_request_provider_config  # noqa: E402
from src.services import made_under_store as store  # noqa: E402
from src.utils import made_under as mu  # noqa: E402
from src.utils import search_scope as ss  # noqa: E402

ACT = "asp/2001/9"
ACT_TITLE = "Widget (Scotland) Act 2001"
COV = {"statement": "Scottish statutory instruments made from 1999 to 2026, as harvested.",
       "label": "Scottish statutory instruments made from 1999 to 2026"}
WHOLE = json.dumps({"state": "wholly", "whole": [{"by": "ssi/2009/1",
                                                  "dates": [{"date": "2009-01-01"}]}]})


def _row(prov, lid, title, rev=None, checked="2026-10-10"):
    return (prov, lid, title, ACT_TITLE, rev, checked)


ROWS = [
    _row("section/33A", "ssi/2022/356", "The Widget (Suspension of Referrals) (Scotland) Order 2022"),
    _row("section/33", "ssi/2002/41", "The Widget (Local Connection) (Scotland) Order 2002",
         rev=json.dumps({"state": "partly"})),
    _row("section/31", "ssi/2002/414", "The Widget (Accommodation) (Scotland) Order 2002"),
    _row("section/32", "ssi/2002/414", "The Widget (Accommodation) (Scotland) Order 2002"),
    _row("section/40", "ssi/2003/7", "The Widget (Revoked) (Scotland) Order 2003", rev=WHOLE),
] + [_row("section/29", f"ssi/20{10 + i}/{50 + i}", f"The Widget (Unsuitable) (Scotland) Order 20{10 + i}")
     for i in range(7)]


def _search(*sections, act=ACT):
    return json.dumps({"results": [
        {"legislation_id": act, "provision_type": "section", "number": None,
         "url": f"http://www.legislation.gov.uk/{act}/section/{s}", "text": "..."}
        for s in sections], "returned": len(sections)})


@pytest.fixture(autouse=True)
def _clean():
    yield
    set_request_provider_config({})


# --- 1. the returned sections ------------------------------------------------


def test_the_returned_sections_are_read_from_the_urls_in_rank_order():
    raw = _search("33", "7", "33A", "22A", "333")
    assert mu.returned_section_families(raw) == (ACT, ["33", "7", "22", "333"])
    mixed = json.loads(_search("5"))
    mixed["results"].append({"url": "http://www.legislation.gov.uk/ukpga/1987/26/section/9"})
    assert mu.returned_section_families(mixed) == (ACT, ["5"])


@pytest.mark.parametrize("raw", ["Error executing tool: 500", "", None, "{}", '{"results": "x"}',
                                 json.dumps({"results": [{"url": "http://x/section/1"}]})])
def test_anything_else_returns_nothing(raw):
    assert mu.returned_section_families(raw) == ("", [])


# --- 2. the block --------------------------------------------------------------


def test_a_small_family_is_listed_by_title_with_its_lettered_sibling():
    block, entries = mu.section_families_block(ACT, ["33"], ROWS, COV)
    assert block.startswith(f"\n\n[{mu.SECTION_FAMILY_HEAD} of the {ACT_TITLE} ({ACT}) and the "
                            "lettered sections beside them")
    assert ("Made under s.33: The Widget (Local Connection) (Scotland) Order 2002 (ssi/2002/41) "
            "(recorded on legislation.gov.uk as revoked in part); made under s.33A: The Widget "
            "(Suspension of Referrals) (Scotland) Order 2022 (ssi/2022/356).") in block
    assert "You MAY state that an instrument named here was made under the section given" in block
    assert "The record covers Scottish statutory instruments made from 1999 to 2026" in block
    assert "does NOT establish that no other instrument was made under these sections" in block
    fam = [e for e in entries if e["tool"] == "made_under"]
    assert fam == [{"tool": "made_under", "source": mu.SECTION_FAMILY_SOURCE, "status": "found",
                    "act_id": ACT, "family": "33", "act": ACT_TITLE,
                    "provision": "section/33, section/33A", "count": 2, "listed": 2,
                    "coverage": COV["label"],
                    "named": [["ssi/2002/41", "The Widget (Local Connection) (Scotland) Order 2002"],
                              ["ssi/2022/356",
                               "The Widget (Suspension of Referrals) (Scotland) Order 2022"]]}]
    assert [(e["legislation_id"], e["stated"]) for e in entries if e["tool"] == "enabling_power"] == [
        ("ssi/2002/41", True), ("ssi/2022/356", True)]


def test_one_instrument_under_two_sections_is_one_line():
    block, entries = mu.section_families_block(ACT, ["31", "32"], ROWS, COV)
    assert "made under s.31:" in block.lower() and "made under s.32:" in block.lower()
    # one family per base; the instrument is named under each
    assert [e["family"] for e in entries if e["tool"] == "made_under"] == ["31", "32"]


def test_a_large_family_is_counted_with_its_earliest_and_latest():
    block, entries = mu.section_families_block(ACT, ["29"], ROWS, COV)
    assert ("Made under s.29: 7 instruments not recorded as revoked in whole, the earliest The "
            "Widget (Unsuitable) (Scotland) Order 2010 (ssi/2010/50), the latest The Widget "
            "(Unsuitable) (Scotland) Order 2016 (ssi/2016/56); find_instruments_made_under lists "
            "them all.") in block
    assert "where only a count is given, call find_instruments_made_under" in block
    assert [e["legislation_id"] for e in entries if e["tool"] == "enabling_power"] == [
        "ssi/2010/50", "ssi/2016/56"]


def test_a_family_revoked_in_whole_is_left_out_and_counted_beside_a_live_one():
    assert mu.section_families_block(ACT, ["40"], ROWS, COV) == ("", [])
    rows = ROWS + [_row("section/33", "ssi/2004/9", "The Widget (Old) (Scotland) Order 2004", rev=WHOLE)]
    block, _ = mu.section_families_block(ACT, ["33"], rows, COV)
    assert "(1 more recorded on legislation.gov.uk as revoked in whole, not listed)" in block
    assert "ssi/2004/9" not in block


def test_families_follow_the_search_rank_and_are_capped():
    rows = [_row(f"section/{n}", f"ssi/2005/{n}", f"The Widget (No. {n}) Order 2005")
            for n in range(1, 10)]
    bases = [str(n) for n in range(9, 0, -1)]
    block, entries = mu.section_families_block(ACT, bases, rows, COV)
    fams = [e["family"] for e in entries if e["tool"] == "made_under"]
    assert fams == bases[: mu.SECTION_FAMILIES_PER_BLOCK]
    assert block.index("s.9:") < block.index("s.8:")
    assert ("3 more of the returned sections have instruments in the record; "
            "find_instruments_made_under lists them.") in block


def test_the_block_is_one_tool_block_the_answer_never_shows():
    rows = ROWS + [_row("section/33", "ssi/2005/1", "The Widget [Bracketed] Order 2005")]
    block, _ = mu.section_families_block(ACT, ["33", "29"], rows,
                                         {"statement": "a class [of] instruments."})
    assert block.count("[") == 1 and block.rstrip().endswith("]")
    assert ss.strip_scope_blocks("The answer." + block)[0] == "The answer."
    assert "\n-" not in block and "\n*" not in block        # sentences, not bullets


def test_a_malformed_flag_costs_only_its_own_mark():
    rows = [_row("section/33", "ssi/2002/41", "The Widget (A) Order 2002", rev='{"state": "wholly", "whole": "x"}'),
            _row("section/33A", "ssi/2022/356", "The Widget (B) Order 2022")]
    block, _ = mu.section_families_block(ACT, ["33"], rows, COV)
    assert "ssi/2002/41" in block and "ssi/2022/356" in block


def test_an_unchecked_instrument_is_listed_without_a_mark():
    rows = [_row("section/33", "ssi/2002/41", "The Widget (A) Order 2002", rev=WHOLE, checked=None)]
    block, _ = mu.section_families_block(ACT, ["33"], rows, COV)
    assert "(ssi/2002/41)." in block and "revoked" not in block.split("(ssi/2002/41)")[0]


def test_no_rows_no_block():
    assert mu.section_families_block(ACT, ["33"], [], COV) == ("", [])
    assert mu.section_families_block(ACT, ["99"], ROWS, COV) == ("", [])


def test_the_block_trips_no_detector_but_the_derivation_lines_it_permits():
    from tools import replay_report as rr

    block, _ = mu.section_families_block(ACT, ["33", "29"], ROWS, COV)
    for s in rr._sentences(block.strip()[1:-1]):
        for name in ("NOT_FOUND", "NEG_ASSERTED", "NEG_BLAMED_INDEX", "NEG_BLAMED_USER",
                     "IN_FORCE_CLAIM"):
            assert not getattr(rr, name).search(s), (name, s)
        assert rr.negcurrency_claim(s) == (None, None), s
        assert not rr._currency_asserted(s), s


# --- 3. the route in run_worker_tool ----------------------------------------


def _fake_rows(calls):
    async def fake(act_id, bases):
        calls.append((act_id, list(bases)))
        return [r for r in ROWS if r[0].split("/")[1].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") in bases], COV
    return fake


def _tool(monkeypatch, raw, log, memo=None, calls=None):
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "model": "m"})

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return raw

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    monkeypatch.setattr(store, "section_family_rows", _fake_rows(calls if calls is not None else []))
    return asyncio.run(agent_shared.run_worker_tool(
        "search_legislation_sections", {"legislation_id": ACT, "query": "duty"}, "brief",
        lambda *a, **k: None, "m", search_log=log, tool_memo=memo))


def test_a_section_search_result_carries_the_block_and_its_entries(monkeypatch):
    log = []
    out = _tool(monkeypatch, _search("33", "7"), log)
    assert f"[{mu.SECTION_FAMILY_HEAD}" in out and "ssi/2022/356" in out
    assert out.index("[" + mu.SECTION_FAMILY_HEAD) > out.index('"returned"')
    assert {(e["tool"], e.get("legislation_id") or e.get("family")) for e in log
            if e.get("source") == mu.SECTION_FAMILY_SOURCE} == {
        ("made_under", "33"), ("enabling_power", "ssi/2002/41"), ("enabling_power", "ssi/2022/356")}


def test_each_family_once_per_run(monkeypatch):
    log, calls = [], []
    _tool(monkeypatch, _search("33", "7"), log, calls=calls)
    out = _tool(monkeypatch, _search("33", "29"), log, calls=calls)
    assert calls == [(ACT, ["33", "7"]), (ACT, ["29"])]
    assert "ssi/2022/356" not in out and "s.29" in out
    out3 = _tool(monkeypatch, _search("33", "29"), log, calls=calls)
    assert mu.SECTION_FAMILY_HEAD not in out3 and len(calls) == 2


def test_a_memo_hit_hands_the_step_its_entries(monkeypatch):
    memo, first, second = {}, [], []
    out1 = _tool(monkeypatch, _search("33"), first, memo=memo)
    out2 = _tool(monkeypatch, _search("33"), second, memo=memo)
    assert out1 == out2
    assert [e for e in second if e.get("source") == mu.SECTION_FAMILY_SOURCE] == \
        [e for e in first if e.get("source") == mu.SECTION_FAMILY_SOURCE]


def test_other_tools_and_failures_get_nothing(monkeypatch):
    assert asyncio.run(agent_shared.made_under_sections_note(
        "search_legislation", _search("33"), [])) == ("", [])

    async def boom(act_id, bases):
        raise RuntimeError("db down")
    monkeypatch.setattr(store, "section_family_rows", boom)
    assert asyncio.run(agent_shared.made_under_sections_note(
        "search_legislation_sections", _search("33"), [])) == ("", [])


def test_no_database_until_the_record_is_loaded(monkeypatch):
    touched = []

    def boom(*a, **k):
        touched.append(1)
        raise AssertionError("database touched")
    import src.database as db
    monkeypatch.setattr(db, "async_session_maker", boom)
    monkeypatch.setitem(store._STATE, "available", False)
    assert asyncio.run(store.section_family_rows(ACT, ["33"])) == ([], {})
    assert touched == []
    # Loaded, but nothing a section number can be: still no query.
    monkeypatch.setitem(store._STATE, "available", True)
    assert asyncio.run(store.section_family_rows(ACT, ["x; drop", "33A"])) == ([], {})
    assert asyncio.run(store.section_family_rows("", ["33"])) == ([], {})
    assert touched == []
    # A real number reaches the query (and a failure there is soft).
    assert asyncio.run(store.section_family_rows(ACT, ["33"])) == ([], {})
    assert touched == [1]


# --- 4. the limb and the footer speak only of what the report names ---------


def _log():
    _block, entries = mu.section_families_block(ACT, ["33", "29"], ROWS, COV)
    return [{"tool": "search_legislation_sections", "legislation_id": ACT}] + entries


@pytest.mark.parametrize("report,kept", [
    ("Made under s.33A, [the 2022 Order](https://www.legislation.gov.uk/ssi/2022/356) ...",
     {"ssi/2022/356"}),
    ("The Suspension Order (SSI 2022/356) partly suspends ...", {"ssi/2022/356"}),
    ("the widget (suspension of referrals) (scotland) order 2022 suspends ...", {"ssi/2022/356"}),
    ("Section 33 governs referrals.", set()),
    ("Compare ssi/2022/3560 and SSI 2022/35.", set()),
])
def test_the_entries_are_kept_only_for_an_instrument_the_report_names(report, kept):
    out = mu.prune_section_family_entries(_log(), report)
    assert {e["legislation_id"] for e in out if e["tool"] == "enabling_power"} == kept
    assert [e["family"] for e in out if e["tool"] == "made_under"] == (["33"] if kept else [])
    assert out[0] == {"tool": "search_legislation_sections", "legislation_id": ACT}


def test_entries_from_other_routes_are_untouched():
    other = {"tool": "enabling_power", "legislation_id": "ssi/2010/50", "stated": True,
             "source": "made_under_record"}
    out = mu.prune_section_family_entries(_log() + [other], "nothing named")
    assert other in out


def test_a_named_instrument_reaches_the_limb_and_the_footer_and_an_unnamed_one_does_not():
    named = mu.prune_section_family_entries(_log(), "The 2022 Order (ssi/2022/356) suspends s.33.")
    assert "Made-under record consulted" in ss._made_under_limb(named)
    assert "ssi/2022/356" in ss._enabling_footer_clause(named)
    assert ss._made_under_footer_clause(named)
    none = mu.prune_section_family_entries(_log(), "Section 33 governs referrals.")
    assert ss._made_under_limb(none) == "" and ss._enabling_footer_clause(none) == ""
    assert ss._made_under_footer_clause(none) == ""


def _worker(monkeypatch, report):
    set_request_provider_config({"_provider": "openrouter", "_research_mode": "legislation_only",
                                 "_chat_mode": "conversational", "model": "m"})

    async def fake_exec(name, args, on_chunk=None, timing_collector=None, worker_call=False):
        return _search("33")

    monkeypatch.setattr(agent_shared, "execute_worker_tool", fake_exec)
    monkeypatch.setattr(store, "section_family_rows", _fake_rows([]))
    seen = {}

    async def loop(messages, model, cancel_event, num_ctx, tools, tool_exec, on_chunk=None, **kw):
        seen["result"] = await tool_exec("search_legislation_sections",
                                         {"legislation_id": ACT, "query": "referrals"})
        return {"role": "assistant", "content": report}

    result = asyncio.run(agent_core.run_worker_agent(loop, lambda *a, **k: None, "brief", "m",
                                                     None, 0))
    return seen, result


def test_run_worker_agent_prunes_before_the_scope_block(monkeypatch):
    seen, result = _worker(monkeypatch, "The 2022 Order (SSI 2022/356) suspends s.33's rules.")
    assert "ssi/2022/356" in seen["result"]
    assert any(e.get("legislation_id") == "ssi/2022/356" for e in result["searches"])
    assert "Made-under record consulted" in result["content"]
    seen, result = _worker(monkeypatch, "Section 33 governs referrals.")
    assert "ssi/2022/356" in seen["result"]                     # the Worker was handed it
    assert not [e for e in result["searches"] if e.get("source") == mu.SECTION_FAMILY_SOURCE]
    assert "Made-under record consulted" not in result["content"]


# --- 5. the P2.3 grader reads the block --------------------------------------


def test_the_derivation_grader_counts_the_block_and_not_the_act():
    from tools.replay_report import retrieved_enabling

    block, _ = mu.section_families_block(ACT, ["33"], ROWS, COV)
    turn = {"audit": {"delegations": [{"tools": [
        {"name": "search_legislation_sections", "raw_result": _search("33"),
         "final_result": '{"results": []}' + block}]}]}}
    got = [lid for lid, _ in retrieved_enabling(turn)]
    assert got == ["ssi/2002/41", "ssi/2022/356"]
