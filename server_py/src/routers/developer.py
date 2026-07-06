import json
import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.provider_factory import (
    get_active_provider,
    get_provider_config,
    save_provider_config,
    set_active_provider,
)
from ..config import MODEL_LIST, settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models import ActivityLog, AppSetting, Chat, Message, ProductFeedback, RequestTiming, ServiceHealthStatus, User
from ..services.synthetic_data import generate_synthetic_data

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/developer", tags=["Developer"])


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


@router.get("/provider-config")
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


@router.post("/provider-config")
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


@router.post("/active-provider")
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


@router.get("/openrouter-models")
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


@router.post("/seed")
async def seed_data(db: AsyncSession = Depends(get_db)):
    """Generate 100 synthetic users with 6 months of chat history."""
    return await generate_synthetic_data(db)


@router.post("/reset")
async def reset_database(db: AsyncSession = Depends(get_db)):
    """Delete all data except the admin user."""
    await db.execute(delete(Message))
    await db.execute(delete(Chat))
    await db.execute(text("DELETE FROM users WHERE username != 'admin'"))
    await db.commit()

    logger.warning("[Developer] Database reset: all messages, chats, and non-admin users deleted")
    return {
        "success": True,
        "message": "Database reset successfully. Only admin user remains.",
    }


@router.post("/clear-usage")
async def clear_usage_data(db: AsyncSession = Depends(get_db)):
    """Delete all chats and messages, keeping all user accounts."""
    await db.execute(delete(Message))
    await db.execute(delete(Chat))
    await db.commit()

    logger.warning("[Developer] Usage data cleared: all chats and messages deleted")
    return {
        "success": True,
        "message": "Usage data cleared. All chats and messages have been deleted.",
    }


@router.post("/clear-performance")
async def clear_performance_data(db: AsyncSession = Depends(get_db)):
    """Delete all request timing records."""
    await db.execute(delete(RequestTiming))
    await db.commit()

    logger.warning("[Developer] Performance data cleared: all request_timings deleted")
    return {
        "success": True,
        "message": "Performance data cleared. All timing records have been deleted.",
    }


@router.post("/clear-feedback")
async def clear_feedback_data(db: AsyncSession = Depends(get_db)):
    """Delete all product feedback surveys and clear message ratings/comments."""
    await db.execute(delete(ProductFeedback))
    await db.execute(
        text("UPDATE messages SET rating = NULL, feedback_comment = NULL WHERE rating IS NOT NULL OR feedback_comment IS NOT NULL")
    )
    await db.commit()

    logger.warning("[Developer] Feedback data cleared: product_feedback deleted, message ratings nulled")
    return {
        "success": True,
        "message": "User feedback cleared. All surveys and message ratings have been deleted.",
    }


# -----------------------------------------------------------------------
# Feature flags
# -----------------------------------------------------------------------

_FEATURES_KEY = "features"
_DEFAULT_FEATURES = {"matters_enabled": True}


async def _read_features(db: AsyncSession) -> dict:
    result = await db.execute(select(AppSetting).where(AppSetting.key == _FEATURES_KEY))
    row = result.scalar_one_or_none()
    if not row:
        return dict(_DEFAULT_FEATURES)
    try:
        return json.loads(row.value)
    except (json.JSONDecodeError, ValueError):
        return dict(_DEFAULT_FEATURES)


@router.get("/features")
async def get_features(db: AsyncSession = Depends(get_db)):
    """Return current feature flag settings."""
    return await _read_features(db)


class FeaturesUpdate(BaseModel):
    matters_enabled: bool


@router.post("/features")
async def save_features(body: FeaturesUpdate, db: AsyncSession = Depends(get_db)):
    """Persist feature flag settings."""
    data = {"matters_enabled": body.matters_enabled}
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
# Activity log
# -----------------------------------------------------------------------

@router.get("/activity-log")
async def get_activity_log(
    days: str = "7",
    limit: int = 500,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a unified activity feed for the admin activity log screen."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")

    outer_date_filter = ""
    if days != "all":
        days_num = int(days) if days.isdigit() else 7
        outer_date_filter = f"WHERE created_at >= NOW() - INTERVAL '{days_num} days'"

    query = text(f"""
        SELECT event_type, username, description, created_at FROM (

            SELECT event_type, username, description, created_at
            FROM activity_log

            UNION ALL

            SELECT
                'QUERY' AS event_type,
                u.username,
                LEFT(m.content, 300) AS description,
                m.created_at
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            JOIN users u ON c.user_id = u.id
            WHERE m.role = 'user'

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

    result = await db.execute(query, {"limit": limit})
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
