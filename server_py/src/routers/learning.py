import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.learning import get_relevant_examples
from ..database import get_db
from ..dependencies import get_admin_user

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/learning", tags=["Learning"])


class TestQuery(BaseModel):
    query: str


@router.get("/feedback")
async def get_feedback(
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("""
        SELECT
            m.id,
            m.content AS assistant_response,
            m.rating,
            m.feedback_comment,
            m.created_at,
            c.title AS chat_title,
            u.username
        FROM messages m
        JOIN chats c ON m.chat_id = c.id
        JOIN users u ON c.user_id = u.id
        WHERE m.rating IS NOT NULL
        ORDER BY m.created_at DESC
        LIMIT 100
    """))
    rows = [dict(row._mapping) for row in result]
    # Serialize datetimes
    for row in rows:
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
    return rows


@router.get("/stats")
async def get_stats(
    days: str = "30",
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    date_filter = ""
    params = {}

    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        date_filter = "AND m.created_at > NOW() - INTERVAL :days_interval"
        params["days_interval"] = f"{days_num} days"

    # Use parameterised interval via string interpolation for the interval
    # (Postgres doesn't support parameterised intervals natively)
    sql = f"""
        SELECT
            DATE(m.created_at) AS date,
            c.model,
            AVG(m.rating) AS avg_rating,
            COUNT(*) AS feedback_count
        FROM messages m
        JOIN chats c ON m.chat_id = c.id
        WHERE m.rating IS NOT NULL
        {"AND m.created_at > NOW() - INTERVAL '" + str(int(days) if days.isdigit() else 30) + " days'" if days != "all" else ""}
        GROUP BY DATE(m.created_at), c.model
        ORDER BY date ASC
    """

    result = await db.execute(text(sql))
    rows = [dict(row._mapping) for row in result]
    for row in rows:
        if row.get("date"):
            row["date"] = row["date"].isoformat()
        if row.get("avg_rating") is not None:
            row["avg_rating"] = float(row["avg_rating"])
        if row.get("feedback_count") is not None:
            row["feedback_count"] = int(row["feedback_count"])
    return rows


@router.post("/test")
async def test_retrieval(
    body: TestQuery,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.query:
        raise HTTPException(status_code=400, detail="Query required")

    results = await get_relevant_examples(body.query, db)
    logger.info(f"[Learning] Test retrieval for query {body.query!r}: {len(results)} examples returned")
    return results
