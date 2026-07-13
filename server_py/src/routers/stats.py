from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import EFFICIENCY_THRESHOLDS
from ..database import get_db
from ..dependencies import get_admin_user

router = APIRouter(prefix="/api/stats", tags=["Statistics"])


# --------------------------------------------------------------------------- #
# Response models (inline, per-router). Each enumerates EVERY key its handler
# builds so response_model filters nothing; nullable-uncertain columns are
# Optional so a NULL row can't 500.
# --------------------------------------------------------------------------- #

# --- /usage ---
class UsageKpi(BaseModel):
    users: int
    chats: int
    messages: int
    activeUsers: int


class ActivityPoint(BaseModel):
    date: str
    count: int


class ModelCount(BaseModel):
    model: Optional[str] = None  # chats.model is nullable
    count: int


class TopUser(BaseModel):
    username: str
    msg_count: int


class UsageResponse(BaseModel):
    kpi: UsageKpi
    activity: List[ActivityPoint]
    models: List[ModelCount]
    topUsers: List[TopUser]


# --- /performance ---
class PerformanceKpi(BaseModel):
    totalRequests: int
    avgTotalMs: int
    p95TotalMs: int
    avgLlmCalls: float
    avgLexCalls: float
    avgLlmMs: int
    avgLexMs: int
    avgTtftMs: int
    avgQueueMs: int


class PerformanceDaily(BaseModel):
    date: str
    avgTotalMs: int
    avgLlmMs: int
    avgLexMs: int
    avgQueueMs: int
    avgTtftMs: int
    requestCount: int


class LlmDistPoint(BaseModel):
    llmCalls: int
    count: int


class SlowestRow(BaseModel):
    requestId: str
    totalMs: int
    llmCalls: int
    llmMs: int
    lexCalls: int
    lexMs: int
    ttftMs: int
    createdAt: str


class PerformanceResponse(BaseModel):
    kpi: PerformanceKpi
    daily: List[PerformanceDaily]
    llmDistribution: List[LlmDistPoint]
    slowest: List[SlowestRow]


# --- /cost ---
class CostKpi(BaseModel):
    paidRequests: int
    totalCost: float
    avgCost: float
    maxCost: float


class CostDaily(BaseModel):
    date: str
    dailyCost: float
    paidCount: int
    label: str


class CostPerUser(BaseModel):
    username: str
    totalCost: float
    queryCount: int


class PriciestRow(BaseModel):
    requestId: str
    costUsd: float
    totalMs: int
    llmCalls: int
    createdAt: str


class CostResponse(BaseModel):
    kpi: CostKpi
    daily: List[CostDaily]
    perUser: List[CostPerUser]
    priciest: List[PriciestRow]


# --- /efficiency ---
class EfficiencyKpi(BaseModel):
    totalRequests: int
    avgDelegations: float
    avgWorkerTools: float
    avgPhase1: float
    avgPhase2: float
    avgDistinctRetrieved: float
    avgSummCalls: float
    avgTruncations: float
    avgFanout: float
    summCompression: float


class EfficiencyIndicator(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    target: str
    status: str


class EfficiencyDaily(BaseModel):
    date: str
    avgDelegations: float
    avgFanout: float
    avgRedundant: float
    avgWorkerTools: float
    requestCount: int


class EfficiencyWorst(BaseModel):
    requestId: str
    delegations: int
    workerTools: int
    phase2: int
    redundant: int
    extracted: int
    kept: int
    truncations: int
    fanout: float
    createdAt: str


class EfficiencyResponse(BaseModel):
    kpi: EfficiencyKpi
    indicators: List[EfficiencyIndicator]
    # EFFICIENCY_THRESHOLDS is an arbitrary config dict — modelled as free-form
    # rather than enumerated so tuning it never requires touching this schema.
    thresholds: Dict[str, Any]
    daily: List[EfficiencyDaily]
    worst: List[EfficiencyWorst]


def _band(value, warn_at, bad_at, higher_is_worse=True):
    """Classify a value into 'ok' | 'warn' | 'bad' against two cut points."""
    if value is None:
        return "ok"
    if higher_is_worse:
        if value >= bad_at:
            return "bad"
        if value >= warn_at:
            return "warn"
        return "ok"
    # lower is worse (e.g. source precision)
    if value <= bad_at:
        return "bad"
    if value <= warn_at:
        return "warn"
    return "ok"


def _round_ms(val):
    return round(float(val)) if val is not None else 0


def _days_num(days: str):
    """Coerce the user-supplied days param to a safe int (None = no filter).

    Every SQL date-window interpolation in this module goes through this
    single point, so only a literal integer can ever reach the query text.
    """
    if days == "all":
        return None
    return int(days) if days.isdigit() else 30


def _date_filter(days: str, col: str = "created_at", keyword: str = "WHERE") -> str:
    """Return a date-window clause ('' when days == 'all')."""
    n = _days_num(days)
    if n is None:
        return ""
    return f"{keyword} {col} > NOW() - INTERVAL '{n} days'"


@router.get("/usage", response_model=UsageResponse)
async def get_usage_stats(
    days: str = "30",
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    # Build date filter clause
    date_filter_chats = _date_filter(days)
    date_filter_messages = _date_filter(days)

    # KPI counts
    total_users = await db.execute(text("SELECT COUNT(*) AS count FROM users"))
    total_chats = await db.execute(text(f"SELECT COUNT(*) AS count FROM chats {date_filter_chats}"))
    total_messages = await db.execute(text(f"SELECT COUNT(*) AS count FROM messages {date_filter_messages}"))
    active_users = await db.execute(text(f"SELECT COUNT(DISTINCT user_id) AS count FROM chats {date_filter_chats}"))

    # Daily activity
    daily_activity = await db.execute(text(f"""
        SELECT DATE(created_at) AS date, COUNT(*) AS count
        FROM chats
        {date_filter_chats}
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) ASC
    """))

    # Model distribution
    model_dist = await db.execute(text(f"""
        SELECT model, COUNT(*) AS count
        FROM chats
        {date_filter_chats}
        GROUP BY model
    """))

    # Power users
    power_user_filter = _date_filter(days, col="m.created_at")

    power_users = await db.execute(text(f"""
        SELECT u.username, COUNT(m.id) AS msg_count
        FROM users u
        JOIN chats c ON u.id = c.user_id
        JOIN messages m ON c.id = m.chat_id
        {power_user_filter}
        GROUP BY u.username
        ORDER BY msg_count DESC
        LIMIT 5
    """))

    return {
        "kpi": {
            "users": int(total_users.scalar()),
            "chats": int(total_chats.scalar()),
            "messages": int(total_messages.scalar()),
            "activeUsers": int(active_users.scalar()),
        },
        "activity": [
            {"date": row.date.isoformat(), "count": int(row.count)}
            for row in daily_activity
        ],
        "models": [
            {"model": row.model, "count": int(row.count)}
            for row in model_dist
        ],
        "topUsers": [
            {"username": row.username, "msg_count": int(row.msg_count)}
            for row in power_users
        ],
    }


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance_stats(
    days: str = "30",
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Return query timing statistics for the Performance dashboard."""
    date_filter = _date_filter(days)

    # --- KPI aggregates ---
    kpi_result = await db.execute(text(f"""
        SELECT
            COUNT(*)                                                    AS total_requests,
            COALESCE(AVG(total_ms), 0)                                  AS avg_total_ms,
            COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP
                     (ORDER BY total_ms), 0)                            AS p95_total_ms,
            COALESCE(AVG(llm_calls), 0)                                 AS avg_llm_calls,
            COALESCE(AVG(lex_api_calls), 0)                             AS avg_lex_calls,
            COALESCE(AVG(llm_total_ms), 0)                              AS avg_llm_ms,
            COALESCE(AVG(lex_api_total_ms), 0)                          AS avg_lex_ms,
            COALESCE(AVG(llm_ttft_first_ms), 0)                         AS avg_ttft_ms,
            COALESCE(AVG(queue_wait_ms), 0)                             AS avg_queue_ms
        FROM request_timings
        {date_filter}
    """))
    kpi_row = kpi_result.mappings().first()

    # --- Daily breakdown for charts ---
    daily_result = await db.execute(text(f"""
        SELECT
            DATE(created_at)                                AS date,
            ROUND(AVG(total_ms)::numeric, 0)               AS avg_total_ms,
            ROUND(AVG(llm_total_ms)::numeric, 0)           AS avg_llm_ms,
            ROUND(AVG(lex_api_total_ms)::numeric, 0)       AS avg_lex_ms,
            ROUND(AVG(queue_wait_ms)::numeric, 0)          AS avg_queue_ms,
            ROUND(AVG(llm_ttft_first_ms)::numeric, 0)      AS avg_ttft_ms,
            COUNT(*)                                        AS request_count
        FROM request_timings
        {date_filter}
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) ASC
    """))

    # --- LLM calls distribution ---
    dist_result = await db.execute(text(f"""
        SELECT llm_calls, COUNT(*) AS count
        FROM request_timings
        {date_filter}
        GROUP BY llm_calls
        ORDER BY llm_calls ASC
    """))

    # --- Slowest 10 requests ---
    slowest_result = await db.execute(text(f"""
        SELECT
            request_id,
            ROUND(total_ms::numeric, 0)         AS total_ms,
            llm_calls,
            ROUND(llm_total_ms::numeric, 0)     AS llm_ms,
            lex_api_calls,
            ROUND(lex_api_total_ms::numeric, 0) AS lex_ms,
            ROUND(llm_ttft_first_ms::numeric, 0) AS ttft_ms,
            created_at
        FROM request_timings
        {date_filter}
        ORDER BY total_ms DESC
        LIMIT 10
    """))

    return {
        "kpi": {
            "totalRequests": int(kpi_row["total_requests"]),
            "avgTotalMs": _round_ms(kpi_row["avg_total_ms"]),
            "p95TotalMs": _round_ms(kpi_row["p95_total_ms"]),
            "avgLlmCalls": round(float(kpi_row["avg_llm_calls"]), 1),
            "avgLexCalls": round(float(kpi_row["avg_lex_calls"]), 1),
            "avgLlmMs": _round_ms(kpi_row["avg_llm_ms"]),
            "avgLexMs": _round_ms(kpi_row["avg_lex_ms"]),
            "avgTtftMs": _round_ms(kpi_row["avg_ttft_ms"]),
            "avgQueueMs": _round_ms(kpi_row["avg_queue_ms"]),
        },
        "daily": [
            {
                "date": row["date"].isoformat(),
                "avgTotalMs": _round_ms(row["avg_total_ms"]),
                "avgLlmMs": _round_ms(row["avg_llm_ms"]),
                "avgLexMs": _round_ms(row["avg_lex_ms"]),
                "avgQueueMs": _round_ms(row["avg_queue_ms"]),
                "avgTtftMs": _round_ms(row["avg_ttft_ms"]),
                "requestCount": int(row["request_count"]),
            }
            for row in daily_result.mappings()
        ],
        "llmDistribution": [
            {"llmCalls": int(row["llm_calls"]), "count": int(row["count"])}
            for row in dist_result.mappings()
        ],
        "slowest": [
            {
                "requestId": row["request_id"],
                "totalMs": _round_ms(row["total_ms"]),
                "llmCalls": int(row["llm_calls"]),
                "llmMs": _round_ms(row["llm_ms"]),
                "lexCalls": int(row["lex_api_calls"]),
                "lexMs": _round_ms(row["lex_ms"]),
                "ttftMs": _round_ms(row["ttft_ms"]),
                "createdAt": row["created_at"].isoformat(),
            }
            for row in slowest_result.mappings()
        ],
    }


@router.get("/cost", response_model=CostResponse)
async def get_cost_stats(
    days: str = "30",
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Return OpenRouter cost statistics derived from request_timings and messages."""
    date_filter = _date_filter(days)

    # Date filter for the messages join (uses table alias, appends to existing WHERE)
    msg_date_filter = _date_filter(days, col="m.created_at", keyword="AND")

    # --- KPI ---
    kpi_result = await db.execute(text(f"""
        SELECT
            COUNT(*) FILTER (WHERE total_cost_usd > 0)              AS paid_requests,
            COALESCE(SUM(total_cost_usd), 0)                        AS total_cost,
            COALESCE(AVG(total_cost_usd) FILTER
                     (WHERE total_cost_usd > 0), 0)                 AS avg_cost,
            COALESCE(MAX(total_cost_usd), 0)                        AS max_cost
        FROM request_timings
        {date_filter}
    """))
    kpi_row = kpi_result.mappings().first()

    # --- Daily spend ---
    daily_result = await db.execute(text(f"""
        SELECT
            DATE(created_at)                                        AS date,
            COALESCE(SUM(total_cost_usd), 0)                        AS daily_cost,
            COUNT(*) FILTER (WHERE total_cost_usd > 0)              AS paid_count
        FROM request_timings
        {date_filter}
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) ASC
    """))

    # --- Cost by user (from messages, assistant only) ---
    per_user_result = await db.execute(text(f"""
        SELECT
            u.username,
            COALESCE(SUM(m.cost_usd), 0)   AS total_cost,
            COUNT(m.id)                     AS query_count
        FROM messages m
        JOIN chats c ON m.chat_id = c.id
        JOIN users u ON c.user_id = u.id
        WHERE m.role = 'assistant' AND m.cost_usd > 0
        {msg_date_filter}
        GROUP BY u.username
        ORDER BY total_cost DESC
        LIMIT 10
    """))

    # --- Most expensive individual requests ---
    priciest_result = await db.execute(text(f"""
        SELECT
            request_id,
            ROUND(total_cost_usd::numeric, 6)   AS cost_usd,
            ROUND(total_ms::numeric, 0)          AS total_ms,
            llm_calls,
            created_at
        FROM request_timings
        WHERE total_cost_usd > 0
        {_date_filter(days, keyword="AND")}
        ORDER BY total_cost_usd DESC
        LIMIT 10
    """))

    def _usd(v):
        return round(float(v), 6) if v is not None else 0.0

    return {
        "kpi": {
            "paidRequests": int(kpi_row["paid_requests"]),
            "totalCost": _usd(kpi_row["total_cost"]),
            "avgCost": _usd(kpi_row["avg_cost"]),
            "maxCost": _usd(kpi_row["max_cost"]),
        },
        "daily": [
            {
                "date": row["date"].isoformat(),
                "dailyCost": _usd(row["daily_cost"]),
                "paidCount": int(row["paid_count"]),
                "label": f"{row['date'].day} {row['date'].strftime('%b')}",
            }
            for row in daily_result.mappings()
        ],
        "perUser": [
            {
                "username": row["username"],
                "totalCost": _usd(row["total_cost"]),
                "queryCount": int(row["query_count"]),
            }
            for row in per_user_result.mappings()
        ],
        "priciest": [
            {
                "requestId": row["request_id"],
                "costUsd": _usd(row["cost_usd"]),
                "totalMs": _round_ms(row["total_ms"]),
                "llmCalls": int(row["llm_calls"]),
                "createdAt": row["created_at"].isoformat(),
            }
            for row in priciest_result.mappings()
        ],
    }


@router.get("/efficiency", response_model=EfficiencyResponse)
async def get_efficiency_stats(
    days: str = "30",
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Return Manager→Worker loop efficiency metrics + derived health indicators.

    Answers "is the agent algorithm performing correctly?" — delegate once,
    search minimally, retrieve focused Acts once each, no fan-out/duplication,
    summarise only when needed, cite what was retrieved.
    """
    date_filter = _date_filter(days)
    # Efficiency indicators describe the Manager→Worker loop, so scope to
    # *research* requests (delegated at least once). This excludes pure-chat
    # turns and pre-instrumentation rows (both have manager_delegations = 0),
    # which would otherwise drag every average toward zero.
    research_filter = (
        f"{date_filter} AND manager_delegations > 0" if date_filter
        else "WHERE manager_delegations > 0"
    )

    # Per-request fan-out and precision ratios are computed in SQL so avg/p95
    # reflect per-request behaviour, not a ratio-of-averages.
    kpi_result = await db.execute(text(f"""
        SELECT
            COUNT(*)                                                        AS total_requests,
            COALESCE(AVG(manager_delegations), 0)                           AS avg_delegations,
            COALESCE(AVG(worker_tool_calls), 0)                             AS avg_worker_tools,
            COALESCE(AVG(phase1_search_calls), 0)                           AS avg_phase1,
            COALESCE(AVG(phase2_retrieval_calls), 0)                        AS avg_phase2,
            COALESCE(AVG(distinct_legislation_ids_retrieved), 0)            AS avg_distinct_retrieved,
            COALESCE(SUM(redundant_tool_calls), 0)                          AS sum_redundant,
            COALESCE(SUM(worker_tool_calls), 0)                             AS sum_worker_tools,
            COALESCE(AVG(redundant_tool_calls), 0)                          AS avg_redundant,
            COALESCE(AVG(summarisation_calls), 0)                           AS avg_summ_calls,
            COALESCE(AVG(truncation_events), 0)                             AS avg_truncations,
            COALESCE(SUM(max_turns_halted), 0)                              AS halt_count,
            COALESCE(SUM(source_filter_fallback), 0)                        AS fallback_count,
            COALESCE(AVG(phase2_retrieval_calls::float
                     / GREATEST(sources_kept, 1)), 0)                       AS avg_fanout,
            COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP
                     (ORDER BY phase2_retrieval_calls::float
                      / GREATEST(sources_kept, 1)), 0)                      AS p95_fanout,
            COALESCE(AVG(CASE WHEN summarisation_chars_in > 0
                     THEN summarisation_chars_out::float
                          / summarisation_chars_in END), 0)                 AS avg_compression
        FROM request_timings
        {research_filter}
    """))
    k = kpi_result.mappings().first()

    total = int(k["total_requests"]) or 0
    avg_delegations = round(float(k["avg_delegations"]), 2)
    sum_worker = float(k["sum_worker_tools"]) or 1.0
    redundant_rate = round(float(k["sum_redundant"]) / sum_worker, 3)
    avg_fanout = round(float(k["avg_fanout"]), 2)
    p95_fanout = round(float(k["p95_fanout"]), 2)
    halt_rate = round(int(k["halt_count"]) / total, 3) if total else 0.0
    fallback_rate = round(int(k["fallback_count"]) / total, 3) if total else 0.0
    compression = round(float(k["avg_compression"]), 2)

    # Derived health indicators with red/amber/green bands.
    indicators = [
        {
            "key": "delegation_efficiency",
            "label": "Delegation efficiency",
            "value": avg_delegations,
            "unit": "avg delegations/query",
            "target": "≈1.0",
            "status": _band(avg_delegations, 1.05, 1.15),
        },
        {
            "key": "fanout_ratio",
            "label": "Phase-2 fan-out (p95)",
            "value": p95_fanout,
            "unit": "retrievals / kept source",
            "target": "≤3",
            "status": _band(p95_fanout, 2.0, 3.0),
        },
        {
            "key": "redundant_rate",
            "label": "Redundant-call rate",
            "value": redundant_rate,
            "unit": "redundant / tool calls",
            "target": "≈0",
            "status": _band(redundant_rate, 0.05, 0.10),
        },
        {
            "key": "halt_rate",
            "label": "Max-turns halt rate",
            "value": halt_rate,
            "unit": "% of queries",
            "target": "0",
            "status": _band(halt_rate, 0.001, 0.02),
        },
        {
            "key": "fallback_rate",
            "label": "Source-filter fallback rate",
            "value": fallback_rate,
            "unit": "% of queries",
            "target": "low",
            "status": _band(fallback_rate, 0.1, 0.25),
        },
    ]

    # Daily trend for charts.
    daily_result = await db.execute(text(f"""
        SELECT
            DATE(created_at)                                             AS date,
            ROUND(AVG(manager_delegations)::numeric, 2)                  AS avg_delegations,
            ROUND(AVG(phase2_retrieval_calls::float
                  / GREATEST(sources_kept, 1))::numeric, 2)             AS avg_fanout,
            ROUND(AVG(redundant_tool_calls)::numeric, 2)                 AS avg_redundant,
            ROUND(AVG(worker_tool_calls)::numeric, 2)                    AS avg_worker_tools,
            COUNT(*)                                                     AS request_count
        FROM request_timings
        {research_filter}
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) ASC
    """))

    # Worst offenders — highest fan-out / redundancy, for drill-down.
    worst_result = await db.execute(text(f"""
        SELECT
            request_id,
            manager_delegations,
            worker_tool_calls,
            phase2_retrieval_calls,
            redundant_tool_calls,
            sources_extracted,
            sources_kept,
            truncation_events,
            ROUND((phase2_retrieval_calls::float
                  / GREATEST(sources_kept, 1))::numeric, 2)             AS fanout,
            created_at
        FROM request_timings
        {research_filter}
        ORDER BY redundant_tool_calls DESC,
                 (phase2_retrieval_calls::float / GREATEST(sources_kept, 1)) DESC,
                 manager_delegations DESC
        LIMIT 10
    """))

    return {
        "kpi": {
            "totalRequests": total,
            "avgDelegations": avg_delegations,
            "avgWorkerTools": round(float(k["avg_worker_tools"]), 1),
            "avgPhase1": round(float(k["avg_phase1"]), 1),
            "avgPhase2": round(float(k["avg_phase2"]), 1),
            "avgDistinctRetrieved": round(float(k["avg_distinct_retrieved"]), 1),
            "avgSummCalls": round(float(k["avg_summ_calls"]), 1),
            "avgTruncations": round(float(k["avg_truncations"]), 2),
            "avgFanout": avg_fanout,
            "summCompression": compression,
        },
        "indicators": indicators,
        "thresholds": EFFICIENCY_THRESHOLDS,
        "daily": [
            {
                "date": row["date"].isoformat(),
                "avgDelegations": float(row["avg_delegations"]),
                "avgFanout": float(row["avg_fanout"]),
                "avgRedundant": float(row["avg_redundant"]),
                "avgWorkerTools": float(row["avg_worker_tools"]),
                "requestCount": int(row["request_count"]),
            }
            for row in daily_result.mappings()
        ],
        "worst": [
            {
                "requestId": row["request_id"],
                "delegations": int(row["manager_delegations"]),
                "workerTools": int(row["worker_tool_calls"]),
                "phase2": int(row["phase2_retrieval_calls"]),
                "redundant": int(row["redundant_tool_calls"]),
                "extracted": int(row["sources_extracted"]),
                "kept": int(row["sources_kept"]),
                "truncations": int(row["truncation_events"]),
                "fanout": float(row["fanout"]),
                "createdAt": row["created_at"].isoformat(),
            }
            for row in worst_result.mappings()
        ],
    }
