"""Unit tests for TimingCollector efficiency counters and run_worker_tool's
key derivation / budget-blocked accounting.

Covers the per-bot efficiency fixes:
  - WI-1 phase classification (SP plenary search / retrieval, search_bills)
  - WI-2 composite redundancy key for transcripts (meeting_id:iob_id)
  - WI-3 search-budget-blocked counter
  - WI-4 generic "distinct primary resources retrieved" counter
"""
import pytest

from src.agent.agent_shared import run_worker_tool
from src.utils.stopwatch import TimingCollector

pytestmark_async = pytest.mark.asyncio


# --------------------------------------------------------------------------- #
# WI-1 — phase classification
# --------------------------------------------------------------------------- #

def test_sp_plenary_search_is_phase1():
    tc = TimingCollector("req")
    tc.record_worker_tool("search_scottish_plenary")
    assert tc.phase1_search_calls == 1
    assert tc.phase2_retrieval_calls == 0


def test_search_bills_is_phase1():
    tc = TimingCollector("req")
    tc.record_worker_tool("search_bills")
    assert tc.phase1_search_calls == 1


def test_sp_plenary_retrieval_is_phase2():
    tc = TimingCollector("req")
    tc.record_worker_tool("get_scottish_plenary_debate", "123:456")
    assert tc.phase2_retrieval_calls == 1
    assert tc.phase1_search_calls == 0


def test_get_member_info_unclassified():
    tc = TimingCollector("req")
    tc.record_worker_tool("get_member_info")
    assert tc.phase1_search_calls == 0
    assert tc.phase2_retrieval_calls == 0


# --------------------------------------------------------------------------- #
# WI-2 — composite redundancy key for transcripts
# --------------------------------------------------------------------------- #

def test_different_iob_same_meeting_not_redundant():
    tc = TimingCollector("req")
    tc.record_worker_tool("get_scottish_plenary_debate", "100:1")
    tc.record_worker_tool("get_scottish_plenary_debate", "100:2")
    assert tc.redundant_tool_calls == 0


def test_same_meeting_and_iob_is_redundant():
    tc = TimingCollector("req")
    tc.record_worker_tool("get_scottish_plenary_debate", "100:1")
    tc.record_worker_tool("get_scottish_plenary_debate", "100:1")
    assert tc.redundant_tool_calls == 1


def test_legislation_id_repeat_is_redundant():
    tc = TimingCollector("req")
    tc.record_worker_tool("get_legislation_text", "ukpga-2020-1")
    tc.record_worker_tool("get_legislation_text", "ukpga-2020-1")
    assert tc.redundant_tool_calls == 1


# --------------------------------------------------------------------------- #
# WI-4 — generic distinct-primary-resources-retrieved counter
# --------------------------------------------------------------------------- #

def test_distinct_transcripts_counted():
    tc = TimingCollector("req")
    tc.record_worker_tool("get_scottish_plenary_debate", "100:1")
    tc.record_worker_tool("get_scottish_committee_transcript", "200:5")
    assert tc.distinct_legislation_ids_retrieved == 2


def test_repeat_transcript_not_double_counted():
    tc = TimingCollector("req")
    tc.record_worker_tool("get_scottish_plenary_debate", "100:1")
    tc.record_worker_tool("get_scottish_plenary_debate", "100:1")
    assert tc.distinct_legislation_ids_retrieved == 1
    assert tc.redundant_tool_calls == 1


# --------------------------------------------------------------------------- #
# WI-3 — search-budget-blocked counter
# --------------------------------------------------------------------------- #

def test_budget_blocked_recorder_and_to_dict():
    tc = TimingCollector("req")
    tc.record_search_budget_blocked()
    assert tc.search_budget_blocked == 1
    assert tc.to_dict()["search_budget_blocked"] == 1


@pytestmark_async
async def test_run_worker_tool_budget_blocked_counts_separately():
    tc = TimingCollector("req")
    budget = {"remaining": 0}
    result = await run_worker_tool(
        "search_scottish_plenary",
        {"query": "housing"},
        query="housing",
        chunk_fn=None,
        summarise_model="",
        timing_collector=tc,
        search_budget=budget,
    )
    assert "Search limit reached" in result
    assert tc.search_budget_blocked == 1
    # Blocked calls stay out of the worker/phase counts.
    assert tc.worker_tool_calls == 0
    assert tc.phase1_search_calls == 0
