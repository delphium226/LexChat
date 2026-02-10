from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_admin_user

router = APIRouter(prefix="/api/stats", tags=["Statistics"])


@router.get("/usage")
async def get_usage_stats(
    days: str = "30",
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    # Build date filter clause
    date_filter_chats = ""
    date_filter_messages = ""

    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        interval = f"'{days_num} days'"
        date_filter_chats = f"WHERE created_at > NOW() - INTERVAL {interval}"
        date_filter_messages = f"WHERE created_at > NOW() - INTERVAL {interval}"

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
    power_user_filter = ""
    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        power_user_filter = f"WHERE m.created_at > NOW() - INTERVAL '{days_num} days'"

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
