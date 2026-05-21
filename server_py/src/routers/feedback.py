import logging
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import ProductFeedback, User

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

VALID_RESEARCH_SUCCESS = {"Always", "Most of the time", "About half the time", "Rarely", "Never"}


class FeedbackCreate(BaseModel):
    message: str | None = None
    time_saved_hours: float | None = None
    time_without_aila_hours: float | None = None
    research_success: str | None = None
    confidence: int | None = None


class FeedbackOut(BaseModel):
    id: int
    username: str
    message: str | None
    time_saved_hours: float | None
    time_without_aila_hours: float | None
    research_success: str | None
    confidence: int | None
    created_at: str


class MessageRatingOut(BaseModel):
    id: int
    rating: int
    feedback_comment: str | None
    response: str
    query: str | None
    username: str
    chat_title: str | None
    created_at: str


def _week_bounds(weeks_ago: int) -> tuple[datetime, datetime]:
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(weeks=weeks_ago)
    end = start + timedelta(days=6)
    return (
        datetime.combine(start, time.min),
        datetime.combine(end, time(23, 59, 59, 999999)),
    )


def _week_label(weeks_ago: int) -> str:
    if weeks_ago == 0:
        return "This week"
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(weeks=weeks_ago)
    end = start + timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {end.strftime('%b')}"
    return f"{start.day} {start.strftime('%b')}–{end.day} {end.strftime('%b')}"


@router.post("", status_code=201)
async def submit_feedback(
    body: FeedbackCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.time_saved_hours is not None and body.time_saved_hours < 0:
        raise HTTPException(status_code=400, detail="time_saved_hours must be non-negative.")
    if body.time_without_aila_hours is not None and body.time_without_aila_hours < 0:
        raise HTTPException(status_code=400, detail="time_without_aila_hours must be non-negative.")
    if body.research_success is not None and body.research_success not in VALID_RESEARCH_SUCCESS:
        raise HTTPException(status_code=400, detail="Invalid research_success value.")
    if body.confidence is not None and not (1 <= body.confidence <= 5):
        raise HTTPException(status_code=400, detail="Confidence must be between 1 and 5.")

    message = body.message.strip() if body.message else None
    entry = ProductFeedback(
        user_id=user["id"],
        message=message,
        time_saved_hours=body.time_saved_hours,
        time_without_aila_hours=body.time_without_aila_hours,
        research_success=body.research_success,
        confidence=body.confidence,
    )
    db.add(entry)
    await db.commit()
    logger.info(f"[Feedback] Submitted by user id={user['id']}")
    return {"status": "ok"}


@router.get("", response_model=list[FeedbackOut])
async def get_all_feedback(
    days: str = "30",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    query = select(ProductFeedback, User.username).join(User, ProductFeedback.user_id == User.id)
    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        cutoff = datetime.utcnow() - timedelta(days=days_num)
        query = query.where(ProductFeedback.created_at >= cutoff)
    result = await db.execute(query.order_by(desc(ProductFeedback.created_at)))
    rows = result.all()
    return [
        FeedbackOut(
            id=fb.id,
            username=username,
            message=fb.message,
            time_saved_hours=fb.time_saved_hours,
            time_without_aila_hours=fb.time_without_aila_hours,
            research_success=fb.research_success,
            confidence=fb.confidence,
            created_at=fb.created_at.isoformat(),
        )
        for fb, username in rows
    ]


@router.get("/message-ratings", response_model=list[MessageRatingOut])
async def get_message_ratings(
    days: str = "30",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    date_filter = ""
    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        date_filter = f"AND m.created_at >= NOW() - INTERVAL '{days_num} days'"

    result = await db.execute(
        text(f"""
            SELECT
                m.id,
                m.rating,
                m.feedback_comment,
                m.content AS response,
                m.created_at,
                u.username,
                c.title AS chat_title,
                (
                    SELECT um.content
                    FROM messages um
                    WHERE um.chat_id = m.chat_id
                      AND um.role = 'user'
                      AND um.created_at < m.created_at
                    ORDER BY um.created_at DESC
                    LIMIT 1
                ) AS query
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            JOIN users u ON c.user_id = u.id
            WHERE m.rating IS NOT NULL AND m.role = 'assistant'
            {date_filter}
            ORDER BY m.created_at DESC
        """)
    )
    rows = result.mappings().all()
    return [
        MessageRatingOut(
            id=row["id"],
            rating=row["rating"],
            feedback_comment=row["feedback_comment"],
            response=row["response"],
            query=row["query"],
            username=row["username"],
            chat_title=row["chat_title"],
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]


@router.get("/compliance")
async def get_survey_compliance(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    # Build 4 calendar week boundaries (index 0 = current week)
    weeks = []
    for i in range(4):
        start, end = _week_bounds(i)
        weeks.append({
            "label": _week_label(i),
            "start": start,
            "end": end,
            "is_current": i == 0,
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
        })

    oldest_start = weeks[-1]["start"]

    # Query: user message counts per user per week in one pass
    query_rows = await db.execute(
        text("""
            SELECT c.user_id,
                SUM(CASE WHEN m.created_at >= :w0s AND m.created_at <= :w0e THEN 1 ELSE 0 END) AS w0,
                SUM(CASE WHEN m.created_at >= :w1s AND m.created_at <= :w1e THEN 1 ELSE 0 END) AS w1,
                SUM(CASE WHEN m.created_at >= :w2s AND m.created_at <= :w2e THEN 1 ELSE 0 END) AS w2,
                SUM(CASE WHEN m.created_at >= :w3s AND m.created_at <= :w3e THEN 1 ELSE 0 END) AS w3
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            WHERE m.role = 'user'
              AND m.created_at >= :oldest
            GROUP BY c.user_id
        """),
        {
            "w0s": weeks[0]["start"], "w0e": weeks[0]["end"],
            "w1s": weeks[1]["start"], "w1e": weeks[1]["end"],
            "w2s": weeks[2]["start"], "w2e": weeks[2]["end"],
            "w3s": weeks[3]["start"], "w3e": weeks[3]["end"],
            "oldest": oldest_start,
        },
    )
    query_counts = {row.user_id: [int(row.w0), int(row.w1), int(row.w2), int(row.w3)] for row in query_rows}

    # Query: feedback submissions per user per week
    fb_rows = await db.execute(
        text("""
            SELECT user_id,
                MAX(CASE WHEN created_at >= :w0s AND created_at <= :w0e THEN 1 ELSE 0 END) AS w0,
                MAX(CASE WHEN created_at >= :w1s AND created_at <= :w1e THEN 1 ELSE 0 END) AS w1,
                MAX(CASE WHEN created_at >= :w2s AND created_at <= :w2e THEN 1 ELSE 0 END) AS w2,
                MAX(CASE WHEN created_at >= :w3s AND created_at <= :w3e THEN 1 ELSE 0 END) AS w3
            FROM product_feedback
            WHERE created_at >= :oldest
            GROUP BY user_id
        """),
        {
            "w0s": weeks[0]["start"], "w0e": weeks[0]["end"],
            "w1s": weeks[1]["start"], "w1e": weeks[1]["end"],
            "w2s": weeks[2]["start"], "w2e": weeks[2]["end"],
            "w3s": weeks[3]["start"], "w3e": weeks[3]["end"],
            "oldest": oldest_start,
        },
    )
    submitted = {row.user_id: [bool(row.w0), bool(row.w1), bool(row.w2), bool(row.w3)] for row in fb_rows}

    # Get all users ordered by username
    all_users_result = await db.execute(select(User).order_by(User.username))
    all_users = all_users_result.scalars().all()

    user_rows = []
    for u in all_users:
        counts = query_counts.get(u.id, [0, 0, 0, 0])
        subs = submitted.get(u.id, [False, False, False, False])
        user_rows.append({
            "user_id": u.id,
            "username": u.username,
            "weeks": [
                {"query_count": counts[i], "survey_submitted": subs[i]}
                for i in range(4)
            ],
        })

    return {
        "weeks": [
            {
                "label": w["label"],
                "start_date": w["start_date"],
                "end_date": w["end_date"],
                "is_current": w["is_current"],
            }
            for w in weeks
        ],
        "users": user_rows,
    }
