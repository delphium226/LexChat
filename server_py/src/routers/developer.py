import json
import logging
import time
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.provider_factory import (
    get_active_provider,
    get_provider_config,
    save_provider_config,
    set_active_provider,
)
from ..config import MODEL_LIST, settings
from ..database import get_db
from ..dependencies import get_admin_user, get_current_user
from ..models import (
    ActivityLog,
    AppSetting,
    Chat,
    Document,
    LocalPromptCache,
    Message,
    ProductFeedback,
    RequestTiming,
    ServiceHealthStatus,
    SessionFeedback,
    User,
)

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/developer", tags=["Developer"])

# Admin-only sub-router: every route registered here inherits the admin check,
# so admin is the DEFAULT for developer endpoints and a newly-added one cannot
# accidentally ship unauthenticated. Only genuinely all-user reads (GET /features,
# GET /activity-log) stay on `router` with a lighter dependency.
# Included into `router` at the bottom of this module.
admin_router = APIRouter(dependencies=[Depends(get_admin_user)])


# -----------------------------------------------------------------------
# Provider configuration
# -----------------------------------------------------------------------

_PROVIDER_META = {
    "ollama": {
        "name": "Ollama (Local)",
        "model_list": [{"name": m["name"], "context_kb": m["contextLengthKB"]} for m in MODEL_LIST],
    },
    "openrouter": {
        "name": "OpenRouter",
        "model_list": [],  # fetched dynamically via /openrouter-models
    },
}

# Simple in-process cache for OpenRouter model list: (base_url, api_key) -> (timestamp, models)
_or_models_cache: dict = {}
_OR_CACHE_TTL = 300  # seconds


class ProviderConfigSave(BaseModel):
    provider: str
    config: dict


class ActiveProviderUpdate(BaseModel):
    active_provider: str


@admin_router.get("/provider-config")
async def get_provider_config_endpoint(db: AsyncSession = Depends(get_db)):
    """Return active provider and full config for all providers."""
    active = await get_active_provider(db)

    providers = []
    for pid, meta in _PROVIDER_META.items():
        cfg = await get_provider_config(db, pid)
        providers.append({
            "id": pid,
            "name": meta["name"],
            "model_list": meta["model_list"],
            "config": cfg,
        })

    return {"active_provider": active, "providers": providers}


@admin_router.post("/provider-config")
async def save_provider_config_endpoint(
    body: ProviderConfigSave,
    db: AsyncSession = Depends(get_db),
):
    """Save settings for a specific provider."""
    try:
        await save_provider_config(db, body.provider, body.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(f"[Developer] Provider config saved for {body.provider!r}")
    return {"success": True}


@admin_router.post("/active-provider")
async def set_active_provider_endpoint(
    body: ActiveProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Switch the active LLM provider (takes effect immediately for all users)."""
    try:
        await set_active_provider(db, body.active_provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(f"[Developer] Active provider switched to {body.active_provider!r}")
    return {"success": True, "active_provider": body.active_provider}


@admin_router.get("/openrouter-models")
async def get_openrouter_models(db: AsyncSession = Depends(get_db)):
    """Fetch available models from OpenRouter dynamically (5-minute cache)."""
    cfg = await get_provider_config(db, "openrouter")
    base_url = (cfg.get("base_url") or settings.openrouter_base_url).rstrip("/")
    api_key = cfg.get("api_key") or settings.openrouter_api_key

    if not api_key:
        raise HTTPException(status_code=400, detail="OpenRouter API key not configured.")

    cache_key = (base_url, api_key)
    now = time.time()
    cached = _or_models_cache.get(cache_key)
    if cached and now - cached[0] < _OR_CACHE_TTL:
        return {"models": cached[1]}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter returned {e.response.status_code}.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach OpenRouter: {e}")

    models = []
    for m in data.get("data", []):
        ctx_length = m.get("context_length")
        models.append({
            "name": m["id"],
            "context_kb": (ctx_length // 1000) if ctx_length else None,
        })
    models.sort(key=lambda m: m["name"])

    _or_models_cache[cache_key] = (now, models)
    return {"models": models}


@admin_router.get("/users-export")
async def export_users(db: AsyncSession = Depends(get_db)):
    """Return all user accounts as a CSV string (name, email, role) for copy/paste."""
    result = await db.execute(select(User).order_by(User.username))
    users = result.scalars().all()

    def _csv_field(value) -> str:
        s = "" if value is None else str(value)
        if any(ch in s for ch in [',', '"', '\n', '\r']):
            return '"' + s.replace('"', '""') + '"'
        return s

    lines = ["name,email,role"]
    for u in users:
        lines.append(
            ",".join([_csv_field(u.username), _csv_field(u.email), _csv_field(u.role)])
        )
    csv = "\r\n".join(lines)

    return {"csv": csv, "count": len(users)}


# -----------------------------------------------------------------------
# Data clearing (Danger Zone)
# -----------------------------------------------------------------------

# One scope per data domain the Admin Portal dashboards read from. The Danger
# Zone renders a checkbox per scope; a "pilot reset" is simply all of them
# ticked. Deliberately covered by NO scope, so they always survive: users,
# app_settings (provider config + feature flags), peer_bots, matters /
# matter_notes, and the crawled SP corpus (sp_committee_items,
# sp_plenary_items, sp_video_captions).
DATA_SCOPES: dict[str, str] = {
    "chats": "Chats & messages",
    "performance": "Performance timings",
    "feedback": "Feedback & ratings",
    "activity": "Activity log",
    "health": "Service health history",
    "cache": "Local prompt cache",
}

# Fixed execution order, applied regardless of the order scopes arrive in.
# `feedback` MUST run before `chats`: session_feedback.chat_id is ON DELETE SET
# NULL, so deleting chats first leaves orphan feedback rows behind and the
# outcome would depend on which boxes were ticked in which order.
_CLEAR_ORDER = ["feedback", "chats", "performance", "activity", "health", "cache"]

_CONFIRM_PHRASE = "DELETE"


class ClearDataRequest(BaseModel):
    scopes: List[str]
    confirm: str = ""


async def _count(db: AsyncSession, model) -> int:
    result = await db.execute(select(func.count()).select_from(model))
    return int(result.scalar() or 0)


@admin_router.get("/data-counts")
async def get_data_counts(db: AsyncSession = Depends(get_db)):
    """Row counts behind each Danger Zone scope, so the UI can show what a clear would destroy."""
    rated_messages = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Message)
                .where((Message.rating.isnot(None)) | (Message.feedback_comment.isnot(None)))
            )
        ).scalar()
        or 0
    )
    surveys = await _count(db, ProductFeedback)
    sessions = await _count(db, SessionFeedback)

    chats = await _count(db, Chat)
    messages = await _count(db, Message)
    documents = await _count(db, Document)

    return {
        "scopes": DATA_SCOPES,
        "counts": {
            "chats": chats,
            "performance": await _count(db, RequestTiming),
            "feedback": surveys + sessions + rated_messages,
            "activity": await _count(db, ActivityLog),
            "health": await _count(db, ServiceHealthStatus),
            "cache": await _count(db, LocalPromptCache),
        },
        # Secondary rows a scope takes with it — surfaced so the cascade is
        # disclosed in the UI rather than discovered afterwards.
        "details": {
            "chats": {"chats": chats, "messages": messages, "documents": documents},
            "feedback": {"surveys": surveys, "sessions": sessions, "rated_messages": rated_messages},
        },
    }


@admin_router.post("/clear-data")
async def clear_data(body: ClearDataRequest, db: AsyncSession = Depends(get_db)):
    """Delete the selected data domains. Users, settings and the crawled corpus are never touched."""
    if body.confirm != _CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f"Confirmation phrase must be exactly '{_CONFIRM_PHRASE}'.",
        )

    requested = set(body.scopes)
    unknown = sorted(requested - set(DATA_SCOPES))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown scope(s): {', '.join(unknown)}")
    if not requested:
        raise HTTPException(status_code=400, detail="Select at least one thing to delete.")

    deleted: dict[str, int] = {}

    for scope in _CLEAR_ORDER:
        if scope not in requested:
            continue

        if scope == "feedback":
            n = (await db.execute(delete(ProductFeedback))).rowcount or 0
            n += (await db.execute(delete(SessionFeedback))).rowcount or 0
            n += (
                await db.execute(
                    text(
                        "UPDATE messages SET rating = NULL, feedback_comment = NULL "
                        "WHERE rating IS NOT NULL OR feedback_comment IS NOT NULL"
                    )
                )
            ).rowcount or 0
        elif scope == "chats":
            # messages.chat_id and documents.chat_id are ON DELETE CASCADE, but
            # delete messages explicitly so the reported count is honest.
            n = (await db.execute(delete(Message))).rowcount or 0
            n += (await db.execute(delete(Chat))).rowcount or 0
        elif scope == "performance":
            n = (await db.execute(delete(RequestTiming))).rowcount or 0
        elif scope == "activity":
            n = (await db.execute(delete(ActivityLog))).rowcount or 0
        elif scope == "health":
            n = (await db.execute(delete(ServiceHealthStatus))).rowcount or 0
        elif scope == "cache":
            n = (await db.execute(delete(LocalPromptCache))).rowcount or 0

        deleted[scope] = n

    await db.commit()

    summary = ", ".join(f"{DATA_SCOPES[s]}: {n}" for s, n in deleted.items())
    logger.warning(f"[Developer] Data cleared — {summary}")
    return {
        "success": True,
        "deleted": deleted,
        "message": f"Deleted {sum(deleted.values())} rows across {len(deleted)} data set(s).",
    }


# -----------------------------------------------------------------------
# Feature flags
# -----------------------------------------------------------------------

_FEATURES_KEY = "features"
_DEFAULT_FEATURES = {
    "matters_enabled": True,
    "prompt_caching_enabled": True,
    "tool_memo_enabled": True,
    "local_prompt_cache_enabled": True,
    "research_mode_enabled": True,
    "deep_research_mode_enabled": True,
    "drafting_mode_enabled": True,
    "suggested_questions_enabled": True,
    # Feedback instruments — both default OFF and are switched on per
    # deployment. The weekly survey and the end-of-session pre-pilot form ask
    # different things and are not meant to run at the same time.
    "weekly_survey_enabled": False,
    "session_feedback_enabled": False,
}


async def _read_features(db: AsyncSession) -> dict:
    result = await db.execute(select(AppSetting).where(AppSetting.key == _FEATURES_KEY))
    row = result.scalar_one_or_none()
    if not row:
        return dict(_DEFAULT_FEATURES)
    try:
        # Merge over defaults so a features JSON saved before a flag existed
        # still reports that flag at its default value.
        return {**_DEFAULT_FEATURES, **json.loads(row.value)}
    except (json.JSONDecodeError, ValueError):
        return dict(_DEFAULT_FEATURES)


@router.get("/features")
async def get_features(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Return current feature flag settings (read by all authenticated users)."""
    return await _read_features(db)


class FeaturesUpdate(BaseModel):
    matters_enabled: bool
    # Defaulted so an old client POST body (matters_enabled only) stays valid.
    prompt_caching_enabled: bool = True
    tool_memo_enabled: bool = True
    local_prompt_cache_enabled: bool = True
    research_mode_enabled: bool = True
    deep_research_mode_enabled: bool = True
    drafting_mode_enabled: bool = True
    suggested_questions_enabled: bool = True
    weekly_survey_enabled: bool = False
    session_feedback_enabled: bool = False


@admin_router.post("/features")
async def save_features(
    body: FeaturesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Persist feature flag settings."""
    data = {
        "matters_enabled": body.matters_enabled,
        "prompt_caching_enabled": body.prompt_caching_enabled,
        "tool_memo_enabled": body.tool_memo_enabled,
        "local_prompt_cache_enabled": body.local_prompt_cache_enabled,
        "research_mode_enabled": body.research_mode_enabled,
        "deep_research_mode_enabled": body.deep_research_mode_enabled,
        "drafting_mode_enabled": body.drafting_mode_enabled,
        "suggested_questions_enabled": body.suggested_questions_enabled,
        "weekly_survey_enabled": body.weekly_survey_enabled,
        "session_feedback_enabled": body.session_feedback_enabled,
    }
    result = await db.execute(select(AppSetting).where(AppSetting.key == _FEATURES_KEY))
    row = result.scalar_one_or_none()
    if row:
        row.value = json.dumps(data)
    else:
        db.add(AppSetting(key=_FEATURES_KEY, value=json.dumps(data)))
    await db.commit()
    logger.info(f"[Developer] Features updated: {data}")
    return {"success": True, "features": data}


# -----------------------------------------------------------------------
# Parliamentary data refresh (parliament bot only)
# -----------------------------------------------------------------------

# Holyrood sessions offered in the refresh dropdown (most-recent first). Windows
# are resolved crawler-side from the authoritative SP_SESSIONS map. Older sessions
# (1–5) are largely un-crawled, so a refresh there is a first ingest.
_REFRESH_SESSIONS = [
    {"id": "all", "label": "All sessions"},
    {"id": "7", "label": "Session 7 (2026– )"},
    {"id": "6", "label": "Session 6 (2021–2026)"},
    {"id": "5", "label": "Session 5 (2016–2021)"},
    {"id": "4", "label": "Session 4 (2011–2016)"},
    {"id": "3", "label": "Session 3 (2007–2011)"},
    {"id": "2", "label": "Session 2 (2003–2007)"},
    {"id": "1", "label": "Session 1 (1999–2003)"},
]


def _is_parliamentary() -> bool:
    return (settings.research_mode or "").strip() == "parliamentary_records"


class ParliamentRefreshRequest(BaseModel):
    session: str


@admin_router.get("/parliament-refresh")
async def get_parliament_refresh():
    """Report whether this bot supports data refresh and the last refresh status.

    `research_mode` lets the admin UI show the refresh panel only on a
    parliament bot; `sessions` populates the dropdown; `status` reflects the
    most recent (or in-flight) manual refresh.
    """
    from ..services.parliament_crawler import get_refresh_status

    return {
        "research_mode": settings.research_mode or "",
        "supported": _is_parliamentary(),
        "sessions": _REFRESH_SESSIONS,
        "status": get_refresh_status(),
    }


@admin_router.post("/parliament-refresh")
async def trigger_parliament_refresh(body: ParliamentRefreshRequest):
    """Kick off a background re-crawl of one Holyrood session's data.

    Fire-and-forget: launches the crawler's refresh as an asyncio task and
    returns immediately. Progress is polled via GET /parliament-refresh. Only
    valid on a bot running in parliamentary_records mode.
    """
    if not _is_parliamentary():
        raise HTTPException(
            status_code=400,
            detail="Data refresh is only available on a bot in parliamentary_records mode.",
        )

    from ..services.parliament_crawler import get_refresh_status, refresh_session_data

    valid_ids = {s["id"] for s in _REFRESH_SESSIONS}
    if body.session not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Unknown session: {body.session!r}")

    status = get_refresh_status()
    if status.get("running"):
        raise HTTPException(status_code=409, detail="A refresh is already running.")

    import asyncio

    asyncio.create_task(refresh_session_data(body.session))
    logger.info(f"[Developer] Parliamentary data refresh triggered for session {body.session!r}")
    return {"success": True, "session": body.session}


# -----------------------------------------------------------------------
# Activity log
# -----------------------------------------------------------------------

class ActivityLogEntry(BaseModel):
    event_type: str
    username: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None


# How much of a message body the QUERY / RESPONSE rows carry. Longer than the
# other event descriptions because the point of those two rows is to read the
# question and the answer against each other; the modal collapses anything long
# behind a "Show more" toggle. Overruns get an ellipsis appended so a truncated
# answer is visibly truncated rather than looking like a short one.
_MESSAGE_EXCERPT_CHARS = 2000

# Assistant content is stored raw, so it can still carry the model's
# <think>/<thinking> reasoning block (the chat UI strips it at render time).
# Stripped here too — otherwise the excerpt would be all reasoning and no answer.
_THINKING_RE = r'<think(ing)?>.*?</think(ing)?>'


@router.get("/activity-log", response_model=List[ActivityLogEntry])
async def get_activity_log(
    days: str = "7",
    limit: int = 500,
    event_types: str = "",
    username: str = "",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a unified activity feed for the admin activity log screen.

    QUERY and RESPONSE are the two halves of an exchange — the user's message
    and the assistant's reply to it. They are separate rows rather than one
    paired row so the existing type filter can show or hide either half; being
    seconds apart, an answer sorts immediately above the question it answers.

    Event-type and user filtering are applied in SQL (in the outer query,
    before the LIMIT) so a narrowed view does not lose older records to the
    row cap — the LIMIT applies to the already-filtered set.
    """
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    params: dict = {"limit": limit}
    conditions: list[str] = []

    if days != "all":
        days_num = int(days) if days.isdigit() else 7
        conditions.append(f"created_at >= NOW() - INTERVAL '{days_num} days'")

    types = [t.strip() for t in event_types.split(",") if t.strip()]
    if types:
        conditions.append("event_type = ANY(:event_types)")
        params["event_types"] = types

    if username:
        conditions.append("username = :username")
        params["username"] = username

    outer_date_filter = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params["thinking_re"] = _THINKING_RE

    query = text(f"""
        SELECT event_type, username, description, created_at FROM (

            SELECT event_type, username, description, created_at
            FROM activity_log

            UNION ALL

            SELECT
                'QUERY' AS event_type,
                u.username,
                CASE WHEN char_length(q.body) > {_MESSAGE_EXCERPT_CHARS}
                    THEN LEFT(q.body, {_MESSAGE_EXCERPT_CHARS}) || '…'
                    ELSE q.body END AS description,
                m.created_at
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            JOIN users u ON c.user_id = u.id
            CROSS JOIN LATERAL (SELECT btrim(m.content, E' \\t\\r\\n') AS body) q
            WHERE m.role = 'user'

            UNION ALL

            SELECT
                'RESPONSE' AS event_type,
                u.username,
                CASE WHEN char_length(r.body) > {_MESSAGE_EXCERPT_CHARS}
                    THEN LEFT(r.body, {_MESSAGE_EXCERPT_CHARS}) || '…'
                    ELSE r.body END AS description,
                m.created_at
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            JOIN users u ON c.user_id = u.id
            CROSS JOIN LATERAL (
                SELECT btrim(regexp_replace(m.content, :thinking_re, '', 'gis'), E' \\t\\r\\n') AS body
            ) r
            WHERE m.role = 'assistant'

            UNION ALL

            SELECT
                'SURVEY' AS event_type,
                u.username,
                CONCAT_WS(' · ',
                    CASE WHEN pf.confidence IS NOT NULL
                        THEN CONCAT('Confidence: ', pf.confidence, '/5') END,
                    CASE WHEN pf.usability IS NOT NULL
                        THEN CONCAT('Usability: ', pf.usability, '/5') END,
                    CASE WHEN pf.message IS NOT NULL AND pf.message <> ''
                        THEN CONCAT('"', LEFT(pf.message, 150), '"') END
                ) AS description,
                pf.created_at
            FROM product_feedback pf
            JOIN users u ON pf.user_id = u.id

            UNION ALL

            SELECT
                'SURVEY' AS event_type,
                u.username,
                CONCAT_WS(' · ',
                    'End of session',
                    CASE WHEN sf.found_right_law IS NOT NULL
                        THEN CONCAT('Right law: ', sf.found_right_law) END,
                    CASE WHEN sf.right_jurisdiction IS NOT NULL
                        THEN CONCAT('Jurisdiction: ', sf.right_jurisdiction) END,
                    CASE WHEN sf.references_accurate IS NOT NULL
                        THEN CONCAT('References: ', sf.references_accurate) END,
                    CASE WHEN sf.refers_incorrectly IS NOT NULL
                        THEN CONCAT('Referred incorrectly: ', sf.refers_incorrectly) END,
                    CASE WHEN sf.confidence IS NOT NULL
                        THEN CONCAT('Confidence: ', sf.confidence, '/5') END,
                    CASE WHEN sf.ease_of_use IS NOT NULL
                        THEN CONCAT('Ease: ', sf.ease_of_use, '/5') END,
                    CASE WHEN sf.other_comments IS NOT NULL AND sf.other_comments <> ''
                        THEN CONCAT('"', LEFT(sf.other_comments, 150), '"') END
                ) AS description,
                sf.created_at
            FROM session_feedback sf
            JOIN users u ON sf.user_id = u.id

            UNION ALL

            SELECT
                'FEEDBACK' AS event_type,
                u.username,
                CONCAT('★', m.rating,
                    CASE WHEN m.feedback_comment IS NOT NULL AND m.feedback_comment <> ''
                        THEN CONCAT(' — ', LEFT(m.feedback_comment, 200))
                        ELSE '' END
                ) AS description,
                m.created_at
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            JOIN users u ON c.user_id = u.id
            WHERE m.rating IS NOT NULL AND m.role = 'assistant'

            UNION ALL

            SELECT
                'ERROR' AS event_type,
                sh.service_name AS username,
                sh.error_message AS description,
                sh.checked_at AS created_at
            FROM service_health_logs sh
            WHERE sh.is_healthy = false

        ) combined
        {outer_date_filter}
        ORDER BY created_at DESC
        LIMIT :limit
    """)

    result = await db.execute(query, params)
    rows = result.mappings().all()
    return [
        {
            "event_type": row["event_type"],
            "username": row["username"],
            "description": row["description"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


# Mount the admin-only routes onto the main router. Defined last so every
# @admin_router endpoint above is registered before it is included. The admin
# routes inherit the /api/developer prefix and the router-level admin dependency.
router.include_router(admin_router)
