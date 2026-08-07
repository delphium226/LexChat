import logging
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Chat, ProductFeedback, SessionFeedback, User

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

class FeedbackCreate(BaseModel):
    message: str | None = None
    time_saved_hours: float | None = None
    time_without_aila_hours: float | None = None
    confidence: int | None = None
    usability: int | None = None
    verification_hours: float | None = None


class FeedbackOut(BaseModel):
    id: int
    username: str
    message: str | None
    time_saved_hours: float | None
    time_without_aila_hours: float | None
    confidence: int | None
    usability: int | None
    verification_hours: float | None
    created_at: str


class SessionFeedbackCreate(BaseModel):
    chat_id: int | None = None
    message_count: int | None = None
    manual_time_hours: float | None = None
    time_saved_hours: float | None = None
    verification_hours: float | None = None
    session_continuity: str | None = None
    found_right_law: str | None = None
    found_right_law_notes: str | None = None
    right_jurisdiction: str | None = None
    right_jurisdiction_notes: str | None = None
    references_accurate: str | None = None
    references_notes: str | None = None
    refers_incorrectly: str | None = None
    refers_incorrectly_notes: str | None = None
    confidence: int | None = None
    ease_of_use: int | None = None
    ease_of_use_reason: str | None = None
    other_comments: str | None = None
    # Seconds between the user pressing "Finished session" and this form being
    # submitted. An elapsed delta, NOT a client wall-clock timestamp: a skewed
    # client clock would otherwise land in the DB as a wrong (or negative)
    # session end. The server resolves it against its own clock, so only the
    # short local interval has to be right.
    finished_seconds_ago: int | None = None


class SessionFeedbackOut(BaseModel):
    id: int
    username: str
    chat_id: int | None
    chat_title: str | None
    message_count: int | None
    manual_time_hours: float | None
    time_saved_hours: float | None
    verification_hours: float | None
    session_continuity: str | None
    found_right_law: str | None
    found_right_law_notes: str | None
    right_jurisdiction: str | None
    right_jurisdiction_notes: str | None
    references_accurate: str | None
    references_notes: str | None
    refers_incorrectly: str | None
    refers_incorrectly_notes: str | None
    confidence: int | None
    ease_of_use: int | None
    ease_of_use_reason: str | None
    other_comments: str | None
    finished_at: str | None
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


class StatusResponse(BaseModel):
    status: str


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


@router.post("", status_code=201, response_model=StatusResponse)
async def submit_feedback(
    body: FeedbackCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.time_saved_hours is not None and body.time_saved_hours < 0:
        raise HTTPException(status_code=400, detail="time_saved_hours must be non-negative.")
    if body.time_without_aila_hours is not None and body.time_without_aila_hours < 0:
        raise HTTPException(status_code=400, detail="time_without_aila_hours must be non-negative.")
    if body.confidence is not None and not (1 <= body.confidence <= 5):
        raise HTTPException(status_code=400, detail="Confidence must be between 1 and 5.")
    if body.usability is not None and not (1 <= body.usability <= 5):
        raise HTTPException(status_code=400, detail="Usability must be between 1 and 5.")
    if body.verification_hours is not None and body.verification_hours < 0:
        raise HTTPException(status_code=400, detail="verification_hours must be non-negative.")

    message = body.message.strip() if body.message else None
    entry = ProductFeedback(
        user_id=user["id"],
        message=message,
        time_saved_hours=body.time_saved_hours,
        time_without_aila_hours=body.time_without_aila_hours,
        confidence=body.confidence,
        usability=body.usability,
        verification_hours=body.verification_hours,
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
            confidence=fb.confidence,
            usability=fb.usability,
            verification_hours=fb.verification_hours,
            created_at=fb.created_at.isoformat(),
        )
        for fb, username in rows
    ]


# Upper bound on how long the feedback form can plausibly sit open before being
# submitted (2 hours). Anything beyond it is a bad client value, not a lawyer
# still typing, and is rejected rather than silently backdating the session end.
_MAX_FORM_FILL_SECONDS = 2 * 60 * 60

_CONTINUITY_VALUES = {"one_go", "not_one_go"}
_YES_PARTIALLY_NO = {"yes", "partially", "no"}


def _clean(value: str | None) -> str | None:
    """Blank / whitespace-only free text is stored as NULL, not ''."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@router.post("/session", status_code=201, response_model=StatusResponse)
async def submit_session_feedback(
    body: SessionFeedbackCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """End-of-session feedback (the pre-pilot form).

    Every field is optional — the form is long and a lawyer may only want to
    answer part of it — so validation only rejects values that are present and
    out of range.
    """
    for field in ("manual_time_hours", "time_saved_hours", "verification_hours"):
        value = getattr(body, field)
        if value is not None and value < 0:
            raise HTTPException(status_code=400, detail=f"{field} must be non-negative.")
    if body.confidence is not None and not (1 <= body.confidence <= 5):
        raise HTTPException(status_code=400, detail="Confidence must be between 1 and 5.")
    if body.ease_of_use is not None and not (1 <= body.ease_of_use <= 5):
        raise HTTPException(status_code=400, detail="Ease of use must be between 1 and 5.")
    if body.message_count is not None and body.message_count < 0:
        raise HTTPException(status_code=400, detail="message_count must be non-negative.")
    if body.finished_seconds_ago is not None and not (0 <= body.finished_seconds_ago <= _MAX_FORM_FILL_SECONDS):
        raise HTTPException(
            status_code=400,
            detail=f"finished_seconds_ago must be between 0 and {_MAX_FORM_FILL_SECONDS}.",
        )

    for field, allowed in (
        ("session_continuity", _CONTINUITY_VALUES),
        ("found_right_law", _YES_PARTIALLY_NO),
        ("right_jurisdiction", _YES_PARTIALLY_NO),
        ("references_accurate", _YES_PARTIALLY_NO),
        ("refers_incorrectly", _YES_PARTIALLY_NO),
    ):
        value = getattr(body, field)
        if value is not None and value not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"{field} must be one of: {', '.join(sorted(allowed))}.",
            )

    # Only accept a chat_id the caller actually owns — the column is provenance
    # for their own thread, not a handle onto anyone else's.
    chat_id = body.chat_id
    if chat_id is not None:
        owns = await db.execute(
            select(Chat.id).where(Chat.id == chat_id, Chat.user_id == user["id"])
        )
        if owns.scalar_one_or_none() is None:
            chat_id = None

    finished_at = None
    if body.finished_seconds_ago is not None:
        finished_at = datetime.utcnow() - timedelta(seconds=body.finished_seconds_ago)

    entry = SessionFeedback(
        user_id=user["id"],
        chat_id=chat_id,
        finished_at=finished_at,
        message_count=body.message_count,
        manual_time_hours=body.manual_time_hours,
        time_saved_hours=body.time_saved_hours,
        verification_hours=body.verification_hours,
        session_continuity=body.session_continuity,
        found_right_law=body.found_right_law,
        found_right_law_notes=_clean(body.found_right_law_notes),
        right_jurisdiction=body.right_jurisdiction,
        right_jurisdiction_notes=_clean(body.right_jurisdiction_notes),
        references_accurate=body.references_accurate,
        references_notes=_clean(body.references_notes),
        refers_incorrectly=body.refers_incorrectly,
        refers_incorrectly_notes=_clean(body.refers_incorrectly_notes),
        confidence=body.confidence,
        ease_of_use=body.ease_of_use,
        ease_of_use_reason=_clean(body.ease_of_use_reason),
        other_comments=_clean(body.other_comments),
    )
    db.add(entry)
    await db.commit()
    logger.info(f"[Feedback] Session feedback submitted by user id={user['id']} chat_id={chat_id}")
    return {"status": "ok"}


@router.get("/session", response_model=list[SessionFeedbackOut])
async def get_all_session_feedback(
    days: str = "30",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    query = (
        select(SessionFeedback, User.username, Chat.title)
        .join(User, SessionFeedback.user_id == User.id)
        .outerjoin(Chat, SessionFeedback.chat_id == Chat.id)
    )
    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        cutoff = datetime.utcnow() - timedelta(days=days_num)
        query = query.where(SessionFeedback.created_at >= cutoff)
    result = await db.execute(query.order_by(desc(SessionFeedback.created_at)))
    return [
        SessionFeedbackOut(
            id=fb.id,
            username=username,
            chat_id=fb.chat_id,
            chat_title=chat_title,
            message_count=fb.message_count,
            manual_time_hours=fb.manual_time_hours,
            time_saved_hours=fb.time_saved_hours,
            verification_hours=fb.verification_hours,
            session_continuity=fb.session_continuity,
            found_right_law=fb.found_right_law,
            found_right_law_notes=fb.found_right_law_notes,
            right_jurisdiction=fb.right_jurisdiction,
            right_jurisdiction_notes=fb.right_jurisdiction_notes,
            references_accurate=fb.references_accurate,
            references_notes=fb.references_notes,
            refers_incorrectly=fb.refers_incorrectly,
            refers_incorrectly_notes=fb.refers_incorrectly_notes,
            confidence=fb.confidence,
            ease_of_use=fb.ease_of_use,
            ease_of_use_reason=fb.ease_of_use_reason,
            other_comments=fb.other_comments,
            finished_at=fb.finished_at.isoformat() if fb.finished_at else None,
            created_at=fb.created_at.isoformat(),
        )
        for fb, username, chat_title in result.all()
    ]


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


@router.get("/session/durations")
async def get_session_durations(
    days: str = "30",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Session length, one row per thread.

    A session runs from the **first user message** in a thread to whichever end
    signal applies:

    * `finished_button` — the user pressed "Finished session". Authoritative:
      it is an explicit "I am done". Recorded as `finished_at`, the moment of
      the press, not when the completed form arrived.
    * `last_response` — fallback for a thread the user simply navigated away
      from. Systematically an **undercount**, since it stops at the moment the
      assistant finished writing and ignores the time spent reading it.

    Elapsed wall-clock, deliberately not split on idle gaps: a thread resumed
    the next day reports as one long session. `session_continuity` (Q3 of the
    feedback form) is returned per row so that distortion stays visible in the
    numbers rather than being silently smoothed away.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    params: dict = {}
    period_filter = ""
    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        params["cutoff"] = datetime.utcnow() - timedelta(days=days_num)
        period_filter = "WHERE fq.started_at >= :cutoff"

    result = await db.execute(
        text(f"""
            WITH fq AS (
                SELECT chat_id, MIN(created_at) AS started_at, COUNT(*) AS queries
                FROM messages WHERE role = 'user' GROUP BY chat_id
            ),
            la AS (
                SELECT chat_id, MAX(created_at) AS last_response
                FROM messages WHERE role = 'assistant' GROUP BY chat_id
            ),
            fb AS (
                SELECT chat_id,
                       MAX(finished_at) AS finished_at,
                       (ARRAY_AGG(session_continuity ORDER BY created_at DESC))[1] AS session_continuity
                FROM session_feedback WHERE chat_id IS NOT NULL GROUP BY chat_id
            )
            SELECT c.id AS chat_id, c.title, u.username,
                   fq.started_at, fq.queries,
                   la.last_response, fb.finished_at, fb.session_continuity
            FROM fq
            JOIN chats c ON c.id = fq.chat_id
            JOIN users u ON u.id = c.user_id
            LEFT JOIN la ON la.chat_id = fq.chat_id
            LEFT JOIN fb ON fb.chat_id = fq.chat_id
            {period_filter}
            ORDER BY fq.started_at DESC
        """),
        params,
    )

    sessions = []
    for row in result.mappings().all():
        # The button wins when both signals exist — an explicit "I am done"
        # beats an inference. Threads with neither (a question asked but never
        # answered) have no measurable length and are dropped.
        if row["finished_at"] is not None:
            ended_at, signal = row["finished_at"], "finished_button"
        elif row["last_response"] is not None:
            ended_at, signal = row["last_response"], "last_response"
        else:
            continue
        duration = (ended_at - row["started_at"]).total_seconds()
        if duration < 0:
            # Only reachable via clock weirdness; a negative length is never
            # meaningful, so drop rather than pollute the medians.
            continue
        sessions.append({
            "chat_id": row["chat_id"],
            "chat_title": row["title"],
            "username": row["username"],
            "started_at": row["started_at"].isoformat(),
            "ended_at": ended_at.isoformat(),
            "end_signal": signal,
            "duration_seconds": duration,
            "queries": int(row["queries"]),
            "session_continuity": row["session_continuity"],
        })

    def durations(rows):
        return [s["duration_seconds"] for s in rows]

    closed = [s for s in sessions if s["end_signal"] == "finished_button"]
    inferred = [s for s in sessions if s["end_signal"] == "last_response"]
    one_go = [s for s in sessions if s["session_continuity"] == "one_go"]
    not_one_go = [s for s in sessions if s["session_continuity"] == "not_one_go"]
    all_durations = durations(sessions)

    return {
        "days": days,
        "summary": {
            "sessions": len(sessions),
            "closed_properly": len(closed),
            "inferred": len(inferred),
            "median_seconds": _median(all_durations),
            "mean_seconds": (sum(all_durations) / len(all_durations)) if all_durations else None,
            "median_closed": _median(durations(closed)),
            "median_inferred": _median(durations(inferred)),
            "one_go_sessions": len(one_go),
            "median_one_go": _median(durations(one_go)),
            "not_one_go_sessions": len(not_one_go),
            "median_not_one_go": _median(durations(not_one_go)),
            "total_seconds": sum(all_durations),
        },
        "sessions": sessions,
    }


@router.get("/session/compliance")
async def get_session_feedback_compliance(
    days: str = "30",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Who is using the system without filling in the session feedback form.

    The unit is the *thread*, not the calendar week (that is the weekly
    survey's cadence): a lawyer is asked for feedback at the end of each
    session, so the honest denominator is how many threads they actually
    worked in over the period. `last_active` / `last_feedback` are deliberately
    all-time, not period-bounded — for chasing someone, "never" and "five weeks
    ago" are the useful answers, and a period-bounded MAX would render both as
    an indistinguishable blank.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    message_filter = ""
    feedback_filter = ""
    params: dict = {}
    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        params["cutoff"] = datetime.utcnow() - timedelta(days=days_num)
        message_filter = "AND m.created_at >= :cutoff"
        feedback_filter = "AND created_at >= :cutoff"

    activity = await db.execute(
        text(f"""
            SELECT c.user_id,
                   COUNT(*) AS queries,
                   COUNT(DISTINCT m.chat_id) AS threads
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            WHERE m.role = 'user'
              {message_filter}
            GROUP BY c.user_id
        """),
        params,
    )
    activity_by_user = {r.user_id: (int(r.queries), int(r.threads)) for r in activity}

    responses = await db.execute(
        text(f"""
            SELECT user_id, COUNT(*) AS responses
            FROM session_feedback
            WHERE 1 = 1 {feedback_filter}
            GROUP BY user_id
        """),
        params,
    )
    responses_by_user = {r.user_id: int(r.responses) for r in responses}

    # All-time recency, used for the chase list.
    last_active = await db.execute(
        text("""
            SELECT c.user_id, MAX(m.created_at) AS last_at
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            WHERE m.role = 'user'
            GROUP BY c.user_id
        """)
    )
    last_active_by_user = {r.user_id: r.last_at for r in last_active}

    last_feedback = await db.execute(
        text("SELECT user_id, MAX(created_at) AS last_at FROM session_feedback GROUP BY user_id")
    )
    last_feedback_by_user = {r.user_id: r.last_at for r in last_feedback}

    all_users = (await db.execute(select(User).order_by(User.username))).scalars().all()

    rows = []
    for u in all_users:
        queries, threads = activity_by_user.get(u.id, (0, 0))
        submitted = responses_by_user.get(u.id, 0)
        la = last_active_by_user.get(u.id)
        lf = last_feedback_by_user.get(u.id)
        rows.append({
            "user_id": u.id,
            "username": u.username,
            "queries": queries,
            "threads": threads,
            "responses": submitted,
            "last_active": la.isoformat() if la else None,
            "last_feedback": lf.isoformat() if lf else None,
        })

    active = [r for r in rows if r["threads"] > 0]
    return {
        "days": days,
        "totals": {
            "active_users": len(active),
            "responding_users": len([r for r in active if r["responses"] > 0]),
            "threads": sum(r["threads"] for r in rows),
            "responses": sum(r["responses"] for r in rows),
        },
        "users": rows,
    }


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
