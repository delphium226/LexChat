"""Response-shape tests for the dynamic /api/stats endpoints.

These lock the exact key set each handler builds so the newly-added
`response_model` on each endpoint cannot silently drop a key, and so an
all-NULL / empty-data row can't 500. Each endpoint is exercised twice:
once against an empty DB (the COALESCE / empty-array paths) and once with a
seeded row (the row-mapping models).
"""
import pytest
from sqlalchemy import text

from src.models import Chat, Message, RequestTiming, User

pytestmark = pytest.mark.asyncio


async def _seed_timing_row(db, **overrides):
    """Insert one request_timings row with sensible non-zero defaults."""
    fields = dict(
        request_id="req0001",
        total_ms=1234.0,
        queue_wait_ms=10.0,
        llm_calls=3,
        llm_total_ms=900.0,
        llm_ttft_first_ms=120.0,
        lex_api_calls=2,
        lex_api_total_ms=300.0,
        total_cost_usd=0.05,
        manager_delegations=1,
        worker_tool_calls=4,
        phase1_search_calls=1,
        phase2_retrieval_calls=3,
        distinct_legislation_ids_retrieved=3,
        redundant_tool_calls=1,
        summarisation_calls=2,
        summarisation_chars_in=1000,
        summarisation_chars_out=400,
        truncation_events=0,
        sources_extracted=5,
        sources_kept=3,
        source_filter_fallback=0,
        max_turns_halted=0,
    )
    fields.update(overrides)
    db.add(RequestTiming(**fields))
    await db.commit()


async def _seed_chat_with_assistant_message(db, admin):
    """Insert a chat + an assistant message with a cost + rating."""
    chat = Chat(user_id=admin.id, title="t", model="m", provider="ollama")
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    db.add(Message(
        chat_id=chat.id, role="assistant", content="answer",
        model="m", provider="ollama", cost_usd=0.02, rating=4,
    ))
    db.add(Message(chat_id=chat.id, role="user", content="a question about housing"))
    await db.commit()
    return chat


# --------------------------------------------------------------------------- #
# /usage
# --------------------------------------------------------------------------- #

async def test_usage_empty(client, admin_token):
    r = await client.get("/api/stats/usage", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"kpi", "activity", "models", "topUsers"}
    assert set(body["kpi"]) == {"users", "chats", "messages", "activeUsers"}
    assert body["activity"] == [] and body["models"] == [] and body["topUsers"] == []


async def test_usage_seeded(client, admin_token, db_session, seed_admin):
    await _seed_chat_with_assistant_message(db_session, seed_admin)
    r = await client.get("/api/stats/usage", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["kpi"]["users"] >= 1
    assert set(body["activity"][0]) == {"date", "count"}
    assert set(body["models"][0]) == {"model", "count"}
    assert set(body["topUsers"][0]) == {"username", "msg_count"}


# --------------------------------------------------------------------------- #
# /performance
# --------------------------------------------------------------------------- #

async def test_performance_empty(client, admin_token):
    r = await client.get("/api/stats/performance", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"kpi", "daily", "llmDistribution", "slowest"}
    assert set(body["kpi"]) == {
        "totalRequests", "avgTotalMs", "p95TotalMs", "avgLlmCalls", "avgLexCalls",
        "avgLlmMs", "avgLexMs", "avgTtftMs", "avgQueueMs",
    }


async def test_performance_seeded(client, admin_token, db_session):
    await _seed_timing_row(db_session)
    r = await client.get("/api/stats/performance", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["kpi"]["totalRequests"] == 1
    assert set(body["daily"][0]) == {
        "date", "avgTotalMs", "avgLlmMs", "avgLexMs", "avgQueueMs", "avgTtftMs", "requestCount",
    }
    assert set(body["llmDistribution"][0]) == {"llmCalls", "count"}
    assert set(body["slowest"][0]) == {
        "requestId", "totalMs", "llmCalls", "llmMs", "lexCalls", "lexMs", "ttftMs", "createdAt",
    }


# --------------------------------------------------------------------------- #
# /cost
# --------------------------------------------------------------------------- #

async def test_cost_empty(client, admin_token):
    r = await client.get("/api/stats/cost", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"kpi", "daily", "perUser", "priciest"}
    assert set(body["kpi"]) == {"paidRequests", "totalCost", "avgCost", "maxCost"}


async def test_cost_seeded(client, admin_token, db_session, seed_admin):
    await _seed_timing_row(db_session)
    await _seed_chat_with_assistant_message(db_session, seed_admin)
    r = await client.get("/api/stats/cost", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["kpi"]["paidRequests"] == 1
    assert set(body["daily"][0]) == {"date", "dailyCost", "paidCount", "label"}
    assert set(body["perUser"][0]) == {"username", "totalCost", "queryCount"}
    assert set(body["priciest"][0]) == {"requestId", "costUsd", "totalMs", "llmCalls", "createdAt"}


# --------------------------------------------------------------------------- #
# /efficiency
# --------------------------------------------------------------------------- #

async def test_efficiency_empty(client, admin_token):
    r = await client.get("/api/stats/efficiency", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"kpi", "indicators", "thresholds", "researchMode", "daily", "worst"}
    assert set(body["kpi"]) == {
        "totalRequests", "avgDelegations", "avgWorkerTools", "avgPhase1", "avgPhase2",
        "avgDistinctRetrieved", "avgSummCalls", "avgTruncations", "avgFanout", "summCompression",
        "avgBudgetBlocked",
    }
    # indicators are static (5 bands on the legislation profile) even with no data;
    # thresholds is the selected profile dict
    assert len(body["indicators"]) == 5
    assert set(body["indicators"][0]) == {"key", "label", "value", "unit", "target", "status"}
    assert isinstance(body["thresholds"], dict)
    assert body["researchMode"] == "legislation"
    assert body["daily"] == [] and body["worst"] == []


async def test_efficiency_seeded(client, admin_token, db_session):
    await _seed_timing_row(db_session)
    r = await client.get("/api/stats/efficiency", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["kpi"]["totalRequests"] == 1
    assert set(body["daily"][0]) == {
        "date", "avgDelegations", "avgFanout", "avgRedundant", "avgWorkerTools", "requestCount",
    }
    assert set(body["worst"][0]) == {
        "requestId", "delegations", "workerTools", "phase2", "redundant",
        "extracted", "kept", "truncations", "fanout", "budgetBlocked", "createdAt",
    }


async def test_efficiency_parliamentary_profile(client, admin_token, db_session, monkeypatch):
    """On a parliament-bot process the endpoint selects the parliamentary profile:
    a budget-exhaustion indicator appears, researchMode reflects the mode, and
    fan-out is computed against distinct retrievals (not sources_kept)."""
    from src.config import settings

    monkeypatch.setattr(settings, "research_mode", "parliamentary_records")
    # Fan-out here is phase2 / distinct_retrieved = 4 / 2 = 2.0 (NOT 4 / 20 = 0.2).
    await _seed_timing_row(
        db_session,
        phase2_retrieval_calls=4,
        distinct_legislation_ids_retrieved=2,
        sources_kept=20,
        search_budget_blocked=1,
    )
    r = await client.get("/api/stats/efficiency", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["researchMode"] == "parliamentary_records"
    keys = {ind["key"] for ind in body["indicators"]}
    assert "budget_exhaustion" in keys
    assert body["kpi"]["avgFanout"] == 2.0
    assert body["worst"][0]["budgetBlocked"] == 1


# --------------------------------------------------------------------------- #
# /cache
# --------------------------------------------------------------------------- #

CACHE_KPI_KEYS = {
    "deepResearchRequests", "memoHits", "memoHitRequests", "cachedPromptTokens",
    "cacheDiscountUsd", "cacheHitRequests", "openrouterEligibleRequests", "totalCostUsd",
    "localCacheHits", "localCacheHitRequests", "localCacheHitRate", "localCacheCharsSaved",
}


async def test_cache_empty(client, admin_token):
    r = await client.get("/api/stats/cache", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"kpi", "daily", "recentHits", "localCache", "localCacheTop", "flags"}
    assert set(body["kpi"]) == CACHE_KPI_KEYS
    assert body["kpi"]["memoHits"] == 0
    # 0-denominator case: no hits AND no summarisations → rate is 0, not an error
    assert body["kpi"]["localCacheHits"] == 0
    assert body["kpi"]["localCacheHitRate"] == 0
    assert body["daily"] == [] and body["recentHits"] == []
    assert body["localCache"] == {
        "entries": 0, "distinctDocuments": 0, "totalHitsServed": 0, "oldestEntry": None,
    }
    assert body["localCacheTop"] == []
    # Flags default ON when no features row exists
    assert body["flags"] == {
        "prompt_caching_enabled": True,
        "tool_memo_enabled": True,
        "local_prompt_cache_enabled": True,
    }


async def test_cache_seeded(client, admin_token, db_session):
    # A deep-research request with memo hits, and a paid request with a
    # provider cache hit; a third plain row must not appear in recentHits.
    await _seed_timing_row(
        db_session, request_id="req_memo", chat_mode="deep_research",
        memo_hits=3, total_cost_usd=0.0,
    )
    await _seed_timing_row(
        db_session, request_id="req_or",
        cached_prompt_tokens=1500, cache_discount_usd=0.0042, total_cost_usd=0.10,
    )
    await _seed_timing_row(db_session, request_id="req_plain", total_cost_usd=0.0)

    r = await client.get("/api/stats/cache", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    kpi = body["kpi"]
    assert kpi["deepResearchRequests"] == 1
    assert kpi["memoHits"] == 3
    assert kpi["memoHitRequests"] == 1
    assert kpi["cachedPromptTokens"] == 1500
    assert kpi["cacheDiscountUsd"] == pytest.approx(0.0042)
    assert kpi["cacheHitRequests"] == 1
    assert kpi["openrouterEligibleRequests"] == 1
    assert kpi["totalCostUsd"] == pytest.approx(0.10)

    assert len(body["daily"]) == 1  # all three rows share today's date
    assert set(body["daily"][0]) == {
        "date", "memoHits", "localCacheHits", "cachedPromptTokens",
        "cacheDiscountUsd", "totalCostUsd",
    }
    assert body["daily"][0]["memoHits"] == 3

    hits = body["recentHits"]
    assert {h["requestId"] for h in hits} == {"req_memo", "req_or"}
    assert set(hits[0]) == {
        "createdAt", "requestId", "chatMode", "memoHits",
        "localCacheHits", "localCacheCharsSaved",
        "cachedPromptTokens", "cacheDiscountUsd", "totalCostUsd",
    }


async def test_cache_timeframe_filter(client, admin_token, db_session):
    """A row older than the window is excluded; days=all includes it."""
    await _seed_timing_row(db_session, request_id="req_old", memo_hits=2, chat_mode="deep_research")
    await db_session.execute(text(
        "UPDATE request_timings SET created_at = NOW() - INTERVAL '40 days' "
        "WHERE request_id = 'req_old'"
    ))
    await db_session.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}
    r = await client.get("/api/stats/cache?days=30", headers=headers)
    assert r.json()["kpi"]["memoHits"] == 0

    r = await client.get("/api/stats/cache?days=all", headers=headers)
    body = r.json()
    assert body["kpi"]["memoHits"] == 2
    assert body["recentHits"][0]["requestId"] == "req_old"


async def test_cache_echoes_flag_state(client, admin_token, db_session):
    import json as _json
    from src.models import AppSetting
    db_session.add(AppSetting(key="features", value=_json.dumps({
        "matters_enabled": True,
        "prompt_caching_enabled": False,
        "tool_memo_enabled": True,
    })))
    await db_session.commit()
    r = await client.get("/api/stats/cache", headers={"Authorization": f"Bearer {admin_token}"})
    # local_prompt_cache_enabled was not in the saved JSON → reported at its default
    assert r.json()["flags"] == {
        "prompt_caching_enabled": False,
        "tool_memo_enabled": True,
        "local_prompt_cache_enabled": True,
    }


async def test_cache_requires_admin(client, user_token):
    r = await client.get("/api/stats/cache", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 403


async def test_cache_openrouter_eligible_uses_provider_column(client, admin_token, db_session):
    """provider='openrouter' counts as eligible even at zero cost (free-tier
    model); provider IS NULL falls back to the old total_cost_usd > 0 proxy;
    provider='ollama' is excluded regardless of cost."""
    await _seed_timing_row(db_session, request_id="req_or_free", provider="openrouter", total_cost_usd=0.0)
    await _seed_timing_row(db_session, request_id="req_legacy", provider=None, total_cost_usd=0.10)
    await _seed_timing_row(db_session, request_id="req_ollama", provider="ollama", total_cost_usd=0.0)

    r = await client.get("/api/stats/cache", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["kpi"]["openrouterEligibleRequests"] == 2


async def test_cache_purge_local(client, admin_token, db_session):
    """DELETE /api/stats/cache/local empties the table and reports the count."""
    from src.services import local_prompt_cache as lpc
    await lpc.store(lpc.content_hash("doc-a"), "query one", "summary a")
    await lpc.store(lpc.content_hash("doc-b"), "query two", "summary b")

    r = await client.delete(
        "/api/stats/cache/local", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r.status_code == 200
    assert r.json() == {"deleted": 2}

    count = (await db_session.execute(
        text("SELECT COUNT(*) FROM local_prompt_cache")
    )).scalar()
    assert count == 0


async def test_cache_purge_local_requires_admin(client, user_token):
    r = await client.delete(
        "/api/stats/cache/local", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert r.status_code == 403


# --------------------------------------------------------------------------- #
# /cache — local prompt cache (D7)
# --------------------------------------------------------------------------- #

async def test_cache_local_hit_rate_seeded(client, admin_token, db_session):
    """rate = hits / (hits + summarisations): 3 hits, 2+1 summarisations → 0.5."""
    await _seed_timing_row(
        db_session, request_id="req_lc1", local_cache_hits=3,
        local_cache_chars_saved=60_000, summarisation_calls=2,
    )
    await _seed_timing_row(db_session, request_id="req_lc2", summarisation_calls=1)

    r = await client.get("/api/stats/cache", headers={"Authorization": f"Bearer {admin_token}"})
    kpi = r.json()["kpi"]
    assert kpi["localCacheHits"] == 3
    assert kpi["localCacheHitRequests"] == 1
    assert kpi["localCacheHitRate"] == pytest.approx(0.5)
    assert kpi["localCacheCharsSaved"] == 60_000
    assert r.json()["daily"][0]["localCacheHits"] == 3


async def test_cache_local_only_row_appears_in_recent_hits(client, admin_token, db_session):
    """A request with only local cache hits (no memo, no provider tokens) is listed."""
    await _seed_timing_row(
        db_session, request_id="req_local_only",
        local_cache_hits=1, local_cache_chars_saved=25_000,
        memo_hits=0, cached_prompt_tokens=0,
    )
    r = await client.get("/api/stats/cache", headers={"Authorization": f"Bearer {admin_token}"})
    hits = r.json()["recentHits"]
    assert [h["requestId"] for h in hits] == ["req_local_only"]
    assert hits[0]["localCacheHits"] == 1
    assert hits[0]["localCacheCharsSaved"] == 25_000


async def test_cache_local_top_ordering_and_filter(client, admin_token, db_session):
    """localCacheTop is hit_count DESC and excludes never-hit entries."""
    from src.models import LocalPromptCache
    for i, hit_count in enumerate([0, 5, 2]):
        db_session.add(LocalPromptCache(
            content_hash=f"ch{i}", query_hash="qh", query_text=f"query {i}",
            summary="s", doc_name=f"Doc {i}", chars_in=1000 * (i + 1),
            hit_count=hit_count,
        ))
    await db_session.commit()

    r = await client.get("/api/stats/cache", headers={"Authorization": f"Bearer {admin_token}"})
    body = r.json()
    top = body["localCacheTop"]
    assert [t["docName"] for t in top] == ["Doc 1", "Doc 2"]  # 5 hits, then 2; Doc 0 excluded
    assert top[0]["hitCount"] == 5
    assert top[0]["charsIn"] == 2000
    # Content stats are timeframe-independent and count all three entries
    assert body["localCache"]["entries"] == 3
    assert body["localCache"]["distinctDocuments"] == 3
    assert body["localCache"]["totalHitsServed"] == 7
    assert body["localCache"]["oldestEntry"] is not None
