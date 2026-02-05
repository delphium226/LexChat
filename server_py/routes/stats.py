from fastapi import APIRouter, HTTPException, Depends
from services.auth import get_current_user
from database import db
from models.auth import UserResponse
import logging

logger = logging.getLogger("lexchat.stats")
router = APIRouter(prefix="/api/stats", tags=["Stats"])

@router.get("/usage")
async def get_usage_stats(days: str = '30', user: UserResponse = Depends(get_current_user)):
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
        
    try:
        date_filter_chats = ""
        date_filter_messages = ""
        date_filter_msg_join = ""
        
        if days != 'all':
            days_num = int(days) if days.isdigit() else 30
            date_filter_chats = f"WHERE created_at > NOW() - INTERVAL '{days_num} days'"
            date_filter_messages = f"WHERE created_at > NOW() - INTERVAL '{days_num} days'"
            date_filter_msg_join = f"WHERE m.created_at > NOW() - INTERVAL '{days_num} days'"

        # 1. KPIs
        total_users = await db.fetch_one("SELECT COUNT(*) FROM users")
        total_chats = await db.fetch_one(f"SELECT COUNT(*) FROM chats {date_filter_chats}")
        total_messages = await db.fetch_one(f"SELECT COUNT(*) FROM messages {date_filter_messages}")
        active_users = await db.fetch_one(f"SELECT COUNT(DISTINCT user_id) FROM chats {date_filter_chats}")
        
        # 2. Daily Activity
        # Postgres date truncation
        daily_activity = await db.fetch_all(f"""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM chats
            {date_filter_chats}
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) ASC
        """)
        
        # 3. Model Distribution
        model_dist = await db.fetch_all(f"""
            SELECT model, COUNT(*) as count
            FROM chats
            {date_filter_chats}
            GROUP BY model
        """)
        
        # 4. Power Users
        power_users = await db.fetch_all(f"""
            SELECT u.username, COUNT(m.id) as msg_count
            FROM users u
            JOIN chats c ON u.id = c.user_id
            JOIN messages m ON c.id = m.chat_id
            {date_filter_msg_join}
            GROUP BY u.username
            ORDER BY msg_count DESC
            LIMIT 5
        """)
        
        return {
            "kpi": {
                "users": total_users['count'],
                "chats": total_chats['count'],
                "messages": total_messages['count'],
                "activeUsers": active_users['count']
            },
            "activity": [dict(row) for row in daily_activity],
            "models": [dict(row) for row in model_dist],
            "topUsers": [dict(row) for row in power_users]
        }
        
    except Exception as e:
        logger.error(f"Error fetching usage stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch usage statistics")
