import logging
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import bindparam, select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Chat, ProductFeedback, SessionFeedback, User

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

# The operator's own login. Its threads are smoke tests, demos and support
# reproductions, not legal research, so they are excluded from every pre-pilot
# read — the responses, the session-length timings and the compliance roster
# alike. Otherwise a demo thread that was never fed back on drags the medians
# and the coverage percentage around, and the operator sits permanently at the
# top of "who to chase" reading "Never".
#
# Applies to the whole /api/feedback/session/* family. Anything added here must
# hold for all three, or the tab starts showing numbers that cannot be
# reconciled against each other.
EXCLUDED_USERNAMES = ("admin",)

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

# Session length is elapsed wall-clock with no idle-gap splitting, so a thread
# picked up after lunch — or the next morning — reads as one enormous session.
# Past this point (4h) the extra time is breaks, not work, and it is credited
# as 4h rather than at face value.
#
# CAPPED, NOT EXCLUDED, and the distinction is the whole design. Dropping the
# long sessions would delete the genuine ones alongside the artefacts, turn
# "Total time" into an undercount of unknown size, and pull those threads out
# of the session-length population while leaving them in the accuracy and
# confidence charts — the same irreconcilable-denominators problem the tab was
# just cleaned up to avoid. A capped session keeps its row and its duration is
# a floor on the truth, which is a failure mode you can state on screen.
#
# 4h is an ASSUMPTION, not a measurement: office-hours users, one thread per
# research question, and Q3 exists at all because breaks were expected. The
# endpoint therefore also returns an `uncapped` block so the tab can show what
# the numbers would have been without it — retune or remove this constant from
# what that line says once real traffic has accumulated.
_MAX_CREDITED_SECONDS = 4 * 60 * 60


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
    """The responses behind every statistic on the admin tab.

    Nothing stops a lawyer pressing "Finished session" twice on one thread, and
    a second form is treated as a **correction**: the latest response per
    (user, thread) is returned and the earlier ones are held back. Without this
    a lawyer who resubmits is counted twice in the accuracy shares and the
    confidence averages, silently carrying double weight in the pre-pilot's
    headline numbers.

    Superseded rows are filtered from the READ ONLY — never deleted, and the
    POST is left free to insert. `session_feedback` is an audit record of how
    each piece of research went (the same reasoning that makes `chat_id` SET
    NULL rather than CASCADE), so the history stays queryable in the database
    even though the tab reports one answer per thread.

    Forms with no `chat_id` are exempt: there is no thread to supersede them
    against, so each is a distinct response and all of them are returned.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    query = (
        select(SessionFeedback, User.username, Chat.title)
        .join(User, SessionFeedback.user_id == User.id)
        .outerjoin(Chat, SessionFeedback.chat_id == Chat.id)
        .where(User.username.notin_(EXCLUDED_USERNAMES))
    )
    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        cutoff = datetime.utcnow() - timedelta(days=days_num)
        query = query.where(SessionFeedback.created_at >= cutoff)
    result = await db.execute(query.order_by(desc(SessionFeedback.created_at)))

    # Newest first, so the first row seen for a thread is the one that stands.
    # Done in Python rather than as a window function because the rows are all
    # materialised here anyway, and a DISTINCT ON would have to special-case
    # the NULL chat_ids — Postgres treats NULLs as equal for that purpose, so
    # it would collapse a user's untethered forms into one.
    seen_threads: set[tuple[int, int]] = set()
    latest = []
    for fb, username, chat_title in result.all():
        if fb.chat_id is not None:
            key = (fb.user_id, fb.chat_id)
            if key in seen_threads:
                continue
            seen_threads.add(key)
        latest.append((fb, username, chat_title))

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
        for fb, username, chat_title in latest
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
    """Session length, one row per **thread that got a feedback form**.

    A session runs from the **first user message** in a thread to whichever end
    signal applies:

    * `finished_button` — the user pressed "Finished session". Authoritative:
      it is an explicit "I am done". Recorded as `finished_at`, the moment of
      the press, not when the completed form arrived.
    * `last_response` — fallback for a form that arrived without a
      `finished_seconds_ago` delta, so the press itself was never timed.
      Systematically an **undercount**, since it stops at the moment the
      assistant finished writing and ignores the time spent reading it.

    The `fb` join is INNER, so a thread with no feedback row is not measured at
    all. That is a deliberate narrowing: an abandoned thread has no end signal
    but the last answer, which is both the weakest measurement here and by far
    the most common, and it used to dominate the medians on this tab. Every
    number the tab shows now describes the same population — the sessions a
    lawyer actually reported on.

    Elapsed wall-clock, deliberately not split on idle gaps, but capped at
    `_MAX_CREDITED_SECONDS`: a thread resumed the next day would otherwise
    report as one enormous session and drag the mean and the total with it.
    Each row carries both `duration_seconds` (capped, what the tab renders)
    and `elapsed_seconds` (raw), and the summary is mirrored by an `uncapped`
    block so the size of the correction stays legible rather than being
    applied silently. `session_continuity` (Q3) is returned per row for the
    same reason.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    params: dict = {"excluded": list(EXCLUDED_USERNAMES)}
    conditions = ["u.username NOT IN :excluded"]
    if days != "all":
        days_num = int(days) if days.isdigit() else 30
        params["cutoff"] = datetime.utcnow() - timedelta(days=days_num)
        conditions.append("fq.started_at >= :cutoff")
    where_clause = "WHERE " + " AND ".join(conditions)

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
            -- One row per thread, so a resubmitted form is a correction here
            -- too, matching GET /session. `session_continuity` takes the
            -- latest answer; `finished_at` deliberately takes MAX rather than
            -- the latest row's value, because a correction submitted without
            -- pressing the button carries a NULL that would throw away a good
            -- measurement and demote the session to an inferred one.
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
            JOIN fb ON fb.chat_id = fq.chat_id
            LEFT JOIN la ON la.chat_id = fq.chat_id
            {where_clause}
            ORDER BY fq.started_at DESC
        """).bindparams(bindparam("excluded", expanding=True)),
        params,
    )

    sessions = []
    for row in result.mappings().all():
        # The button wins when both signals exist — an explicit "I am done"
        # beats an inference. Threads with neither (a form submitted with no
        # timed press, on a thread the assistant never answered) have no
        # measurable length and are dropped.
        if row["finished_at"] is not None:
            ended_at, signal = row["finished_at"], "finished_button"
        elif row["last_response"] is not None:
            ended_at, signal = row["last_response"], "last_response"
        else:
            continue
        elapsed = (ended_at - row["started_at"]).total_seconds()
        if elapsed < 0:
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
            "duration_seconds": min(elapsed, _MAX_CREDITED_SECONDS),
            "elapsed_seconds": elapsed,
            "capped": elapsed > _MAX_CREDITED_SECONDS,
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
    elapsed_durations = [s["elapsed_seconds"] for s in sessions]

    return {
        "days": days,
        "cap_seconds": _MAX_CREDITED_SECONDS,
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
        # What the numbers above would have been with no cap. This is the tab
        # answering the question we cannot run against the live DB: if the
        # capped and uncapped medians agree and `capped_sessions` is ~0, the
        # cap is doing nothing and can go. If the uncapped mean is a multiple
        # of the uncapped median, the skew was real and the cap is earning its
        # place. Rendered as one small line under the tiles, not as tiles.
        "uncapped": {
            "capped_sessions": sum(1 for s in sessions if s["capped"]),
            "median_seconds": _median(elapsed_durations),
            "mean_seconds": (sum(elapsed_durations) / len(elapsed_durations)) if elapsed_durations else None,
            "total_seconds": sum(elapsed_durations),
            "longest_seconds": max(elapsed_durations) if elapsed_durations else None,
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

    `EXCLUDED_USERNAMES` is filtered out here too, so the roster matches the
    statistics above it: there is nobody to chase about a smoke test, and an
    operator account permanently reading "Never" is noise at the top of a list
    sorted by how much feedback is missing.

    Two counts per user, and the distinction is the whole point of the chase
    list. `responses` is forms submitted; `threads_covered` is how many of the
    threads they worked in this period have a form against them. Only the
    second can answer "what is missing" — three forms on one thread is three
    responses but one thread covered, and a form with no `chat_id` (submitted
    outside a thread, or against a thread the caller did not own) is a response
    that covers nothing. Chasing on `responses`, as this did, reports a lawyer
    with three untouched threads as fully up to date, and lets the coverage
    percentage exceed 100.

    `threads_covered` deliberately does not date-filter the feedback side: the
    denominator is already bounded by thread activity in the period, and the
    question being asked is "does this thread have feedback", which is a
    property of the thread rather than of the window.
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

    # Threads worked in this period that have at least one form against them.
    # Joining through the period's own threads is what bounds this by `threads`
    # and keeps coverage at or below 100% — counting distinct chat_ids straight
    # out of session_feedback would also pick up feedback left on threads that
    # were started before the window.
    covered = await db.execute(
        text(f"""
            WITH active AS (
                SELECT c.user_id, m.chat_id
                FROM messages m
                JOIN chats c ON m.chat_id = c.id
                WHERE m.role = 'user'
                  {message_filter}
                GROUP BY c.user_id, m.chat_id
            )
            SELECT a.user_id, COUNT(DISTINCT sf.chat_id) AS threads_covered
            FROM active a
            JOIN session_feedback sf ON sf.chat_id = a.chat_id
            GROUP BY a.user_id
        """),
        params,
    )
    covered_by_user = {r.user_id: int(r.threads_covered) for r in covered}

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

    all_users = (
        await db.execute(
            select(User)
            .where(User.username.notin_(EXCLUDED_USERNAMES))
            .order_by(User.username)
        )
    ).scalars().all()

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
            "threads_covered": covered_by_user.get(u.id, 0),
            "last_active": la.isoformat() if la else None,
            "last_feedback": lf.isoformat() if lf else None,
        })

    active = [r for r in rows if r["threads"] > 0]
    return {
        "days": days,
        "totals": {
            "active_users": len(active),
            # Engagement, not coverage: has this lawyer submitted the form at
            # all. Deliberately still keyed on `responses`, so someone whose
            # only form was submitted outside a thread counts as having
            # responded — they did. How much of their work is actually reviewed
            # is what `threads_covered` is for, and the two are allowed to
            # disagree.
            "responding_users": len([r for r in active if r["responses"] > 0]),
            "threads": sum(r["threads"] for r in rows),
            "responses": sum(r["responses"] for r in rows),
            "threads_covered": sum(r["threads_covered"] for r in rows),
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
