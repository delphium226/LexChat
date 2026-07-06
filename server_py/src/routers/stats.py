from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_admin_user

router = APIRouter(prefix="/api/stats", tags=["Statistics"])


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


@router.get("/usage")
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


@router.get("/performance")
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


@router.get("/cost")
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
