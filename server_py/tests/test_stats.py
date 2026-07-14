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
