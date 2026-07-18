"""Unit + integration tests for D7 local prompt caching.

Covers: canonicalise_query, service round-trip against the test DB (D4 gives
the suite its own Postgres), run_worker_tool wiring (hit skips summarisation,
records local_cache_hits), the local_prompt_cache_enabled flag, and fail-soft
behaviour when the DB is unavailable.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from src.agent.agent_shared import run_worker_tool
from src.agent.provider_factory import set_request_provider_config
from src.services import local_prompt_cache as lpc
from src.utils.stopwatch import TimingCollector


# ---------------------------------------------------------------------------
# canonicalise_query (plan test 1)
# ---------------------------------------------------------------------------

def test_canonicalise_collapses_order_case_stopwords():
    variants = [
        "compensation, disturbance payments",
        "Disturbance payments and compensation",
        "the compensation for disturbance payments",
    ]
    keys = {lpc.canonicalise_query(v) for v in variants}
    assert keys == {"compensation disturbance payments"}


def test_canonicalise_drops_short_tokens_and_dedups():
    assert lpc.canonicalise_query("s.13 of of the Act Act") == "act"


def test_canonicalise_distinct_terms_stay_distinct():
    a = lpc.canonicalise_query("compensation for disturbance")
    b = lpc.canonicalise_query("compensation for severance")
    assert a != b


def test_canonicalise_empty_query():
    assert lpc.canonicalise_query("of a to") == ""


# ---------------------------------------------------------------------------
# Service round-trip against the test DB (plan test 2)
# ---------------------------------------------------------------------------

RAW_DOC = json.dumps({"title": "Land Compensation Act 1961", "sections": ["..."]})


@pytest.mark.asyncio
async def test_service_store_lookup_roundtrip(db_session):
    ch = lpc.content_hash(RAW_DOC)
    await lpc.store(ch, "compensation rules", "the summary", "flash-model", "Land Compensation Act 1961", 12345)

    hit = await lpc.lookup(ch, "compensation rules")
    assert hit == {"summary": "the summary", "chars_in": 12345}

    # Canonicalisation-equivalent wording also hits; hit_count accumulates
    hit2 = await lpc.lookup(ch, "the RULES of compensation")
    assert hit2["summary"] == "the summary"

    row = (await db_session.execute(
        text("SELECT hit_count, last_hit_at, summarise_model FROM local_prompt_cache")
    )).first()
    assert row.hit_count == 2
    assert row.last_hit_at is not None
    assert row.summarise_model == "flash-model"


@pytest.mark.asyncio
async def test_service_miss_on_different_key(db_session):
    ch = lpc.content_hash(RAW_DOC)
    await lpc.store(ch, "compensation rules", "the summary")

    assert await lpc.lookup(lpc.content_hash(RAW_DOC + "x"), "compensation rules") is None
    assert await lpc.lookup(ch, "severance rules") is None


@pytest.mark.asyncio
async def test_service_double_store_is_noop(db_session):
    ch = lpc.content_hash(RAW_DOC)
    await lpc.store(ch, "compensation rules", "first summary")
    await lpc.store(ch, "compensation rules", "second summary")

    count = (await db_session.execute(
        text("SELECT COUNT(*) FROM local_prompt_cache")
    )).scalar()
    assert count == 1
    hit = await lpc.lookup(ch, "compensation rules")
    assert hit["summary"] == "first summary"


# ---------------------------------------------------------------------------
# run_worker_tool wiring (plan tests 3–5)
# ---------------------------------------------------------------------------

# Oversized (> the 10K minimum summarise threshold) raw tool result.
OVERSIZED_RESULT = json.dumps({
    "title": "Acquisition of Land Act 1981",
    "sections": [{"title": "Confirmation", "content": "x" * 20_000}],
})

TOOL_ARGS = {"legislation_id": "ukpga/1981/67", "query": "confirmation procedure"}


async def _noop_chunk(*a, **k):
    return None


def _call(timing, query="confirmation procedure"):
    return run_worker_tool(
        "search_legislation_sections", dict(TOOL_ARGS), query,
        _noop_chunk, "test-model",
        timing_collector=timing,
    )


def _patched_exec_and_summarise():
    return (
        patch(
            "src.agent.agent_shared.execute_worker_tool",
            new=AsyncMock(return_value=OVERSIZED_RESULT),
        ),
        patch(
            "src.agent.agent_shared.summarise_for_query",
            new=AsyncMock(return_value=("SUMMARY OF CONFIRMATION PROCEDURE", False)),
        ),
    )


@pytest.mark.asyncio
async def test_second_identical_request_served_from_cache(db_session):
    p_exec, p_summ = _patched_exec_and_summarise()
    with p_exec, p_summ as mock_summ:
        t1 = TimingCollector("req1")
        first = await _call(t1)

        t2 = TimingCollector("req2")
        second = await _call(t2)

    assert mock_summ.await_count == 1  # second run skipped summarisation
    assert second == first

    # First request: a summarisation, no local hit. Second: the inverse.
    assert t1.summarisation_calls == 1
    assert t1.local_cache_hits == 0
    assert t2.summarisation_calls == 0
    assert t2.local_cache_hits == 1
    assert t2.local_cache_chars_saved == len(OVERSIZED_RESULT)


@pytest.mark.asyncio
async def test_different_query_beyond_canonicalisation_misses(db_session):
    p_exec, p_summ = _patched_exec_and_summarise()
    with p_exec, p_summ as mock_summ:
        await _call(TimingCollector("req1"), query="confirmation procedure")
        await _call(TimingCollector("req2"), query="compensation for severance")
    assert mock_summ.await_count == 2  # exact canonicalised match only


@pytest.mark.asyncio
async def test_flag_off_no_lookup_no_store(db_session):
    """local_prompt_cache_enabled=False → no cache calls, summarise every time."""
    set_request_provider_config({"_local_prompt_cache_enabled": False})
    try:
        p_exec, p_summ = _patched_exec_and_summarise()
        with p_exec, p_summ as mock_summ, \
             patch.object(lpc, "lookup", new=AsyncMock()) as mock_lookup, \
             patch.object(lpc, "store", new=AsyncMock()) as mock_store:
            t = TimingCollector("req1")
            await _call(t)
            await _call(t)
        assert mock_summ.await_count == 2
        mock_lookup.assert_not_awaited()
        mock_store.assert_not_awaited()
        assert t.local_cache_hits == 0
    finally:
        set_request_provider_config({})


# ---------------------------------------------------------------------------
# Phase 1 (D8): degraded / truncated summaries must never be cached
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_degraded_summary_not_stored(db_session):
    """chunk_fn returning None (single-chunk fallback → raw text) must not
    poison the cache; a second identical run re-attempts summarisation."""
    p_exec = patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=OVERSIZED_RESULT),
    )
    # Real summarise_for_query with a chunk_fn that always fails → degraded.
    with p_exec:
        t1 = TimingCollector("req1")
        await _call(t1)

        count = (await db_session.execute(
            text("SELECT COUNT(*) FROM local_prompt_cache")
        )).scalar()
        assert count == 0  # degraded output was not stored

        t2 = TimingCollector("req2")
        await _call(t2)

    # Second run was a miss and re-attempted summarisation — no cache hit.
    assert t2.local_cache_hits == 0
    assert t2.summarisation_calls == 1


@pytest.mark.asyncio
async def test_truncated_summary_not_stored(db_session):
    """A summary still over the threshold is truncated for this request but
    must not be stored (request-specific lossiness)."""
    p_exec = patch(
        "src.agent.agent_shared.execute_worker_tool",
        new=AsyncMock(return_value=OVERSIZED_RESULT),
    )
    p_summ = patch(
        "src.agent.agent_shared.summarise_for_query",
        new=AsyncMock(return_value=("S" * 50_000, False)),  # non-degraded but oversized
    )
    with p_exec, p_summ:
        t = TimingCollector("req1")
        result = await _call(t)

    assert "[Content truncated" in result
    count = (await db_session.execute(
        text("SELECT COUNT(*) FROM local_prompt_cache")
    )).scalar()
    assert count == 0


# ---------------------------------------------------------------------------
# Phase 5 (D8): standard mode keys on the raw user query, not the brief
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_raw_query_keying_hits_across_different_briefs(db_session):
    """Same user question, differently-phrased delegation briefs → same key
    (standard mode sets _cache_key_query to the raw user message)."""
    set_request_provider_config(
        {"_cache_key_query": "What is the confirmation procedure for CPOs?"}
    )
    try:
        p_exec, p_summ = _patched_exec_and_summarise()
        with p_exec, p_summ as mock_summ:
            t1 = TimingCollector("req1")
            await _call(t1, query="research the confirmation procedure under the 1981 Act")
            t2 = TimingCollector("req2")
            await _call(t2, query="confirmation of compulsory purchase orders — procedure")
    finally:
        set_request_provider_config({})

    assert mock_summ.await_count == 1  # second brief hit despite different wording
    assert t2.local_cache_hits == 1

    # The stored row is keyed/recorded against the raw user query
    row = (await db_session.execute(
        text("SELECT query_text FROM local_prompt_cache")
    )).first()
    assert row.query_text == "What is the confirmation procedure for CPOs?"


@pytest.mark.asyncio
async def test_no_cache_key_query_keys_on_brief(db_session):
    """Deep Research (no _cache_key_query) keys on the step brief as before —
    different briefs must not collide."""
    p_exec, p_summ = _patched_exec_and_summarise()
    with p_exec, p_summ as mock_summ:
        await _call(TimingCollector("req1"), query="confirmation procedure")
        await _call(TimingCollector("req2"), query="compensation for severance")
    assert mock_summ.await_count == 2


@pytest.mark.asyncio
async def test_cache_db_failure_is_fail_soft(db_session):
    """A broken DB never breaks the research request — it just always misses."""
    p_exec, p_summ = _patched_exec_and_summarise()

    class _Boom:
        def __call__(self):
            raise RuntimeError("db down")

    with p_exec, p_summ as mock_summ, \
         patch("src.database.async_session_maker", new=_Boom()):
        t = TimingCollector("req1")
        result = await _call(t)

    assert result == "SUMMARY OF CONFIRMATION PROCEDURE"
    assert mock_summ.await_count == 1
    assert t.local_cache_hits == 0
    assert t.summarisation_calls == 1
