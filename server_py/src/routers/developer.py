import logging
import random
import time
from datetime import datetime, timedelta

import httpx
from faker import Faker
from fastapi import APIRouter, Depends, HTTPException
from passlib.hash import bcrypt
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
from ..models import Chat, Message, User

logger = logging.getLogger("app")

fake = Faker()

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
    hashed_password = bcrypt.using(rounds=10).hash("password123")
    users_to_create = 100
    user_ids = []

    # 1. Create users
    for _ in range(users_to_create):
        first = fake.first_name()
        last = fake.last_name()
        username = (
            fake.user_name()[:15].lower().replace(".", "")
            + str(random.randint(100, 999))
        )
        email = fake.email()

        # Check if exists
        existing = await db.execute(
            select(User.id).where(User.username == username)
        )
        row = existing.scalar_one_or_none()
        if row:
            user_ids.append(row)
        else:
            new_user = User(
                username=username,
                password_hash=hashed_password,
                role="user",
                email=email,
            )
            db.add(new_user)
            await db.flush()
            user_ids.append(new_user.id)

    await db.commit()

    # 2. Generate 6 months of history
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=180)

    legal_topics = [
        "Contract Law", "Tort Liability", "GDPR Compliance",
        "Employment Rights", "Property Dispute", "Intellectual Property",
    ]
    model_names = [m["name"] for m in MODEL_LIST]

    total_chats = 0
    total_messages = 0

    current_date = start_date
    while current_date <= end_date:
        for user_id in user_ids:
            # 30% chance of activity per user per week
            if random.random() < 0.3:
                chats_this_week = random.randint(1, 3)

                for _ in range(chats_this_week):
                    chat_date = current_date + timedelta(
                        days=random.randint(0, 6),
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59),
                    )
                    if chat_date > end_date:
                        continue

                    topic = random.choice(legal_topics)
                    model = random.choice(model_names)

                    chat = Chat(
                        user_id=user_id,
                        title=f"{topic} Inquiry",
                        model=model,
                        created_at=chat_date,
                    )
                    db.add(chat)
                    await db.flush()
                    total_chats += 1

                    # User message
                    user_msg = Message(
                        chat_id=chat.id,
                        role="user",
                        content=f"I have a question about {topic}.",
                        created_at=chat_date,
                    )
                    db.add(user_msg)

                    # Assistant message
                    response_date = chat_date + timedelta(seconds=5)
                    rating = None
                    comment = None

                    if random.random() < 0.5:
                        rand = random.random()
                        if rand < 0.1:
                            rating = 1
                        elif rand < 0.2:
                            rating = 2
                        elif rand < 0.4:
                            rating = 3
                        elif rand < 0.7:
                            rating = 4
                        else:
                            rating = 5

                        if random.random() < 0.4:
                            comment = fake.sentence()

                    assistant_msg = Message(
                        chat_id=chat.id,
                        role="assistant",
                        content=f"Here is some information regarding {topic}... [Synthetic Response]",
                        created_at=response_date,
                        rating=rating,
                        feedback_comment=comment,
                    )
                    db.add(assistant_msg)
                    total_messages += 2

        # Advance one week
        current_date += timedelta(days=7)

    await db.commit()

    logger.info(f"[Developer] Seed complete: {len(user_ids)} users, {total_chats} chats, {total_messages} messages")
    return {
        "success": True,
        "message": "Synthetic data generated successfully.",
        "stats": {
            "users": len(user_ids),
            "chats": total_chats,
            "messages": total_messages,
        },
    }


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
