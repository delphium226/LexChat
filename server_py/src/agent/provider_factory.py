"""
Provider factory — resolves the active LLM provider at request time.

The active provider is stored in the AppSetting table (key="active_provider").
Supported values: "ollama" | "openrouter"
"""
import logging
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AppSetting

logger = logging.getLogger("agent")

_SUPPORTED_PROVIDERS = ("ollama", "openrouter")


async def get_active_provider(db: AsyncSession) -> str:
    """Read the active provider from the database. Falls back to 'ollama'."""
    try:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == "active_provider")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value in _SUPPORTED_PROVIDERS:
            return setting.value
    except Exception as e:
        logger.error(f"[ProviderFactory] Failed to read active_provider: {e}")
    return "ollama"


async def set_active_provider(db: AsyncSession, provider: str) -> None:
    """Persist the active provider to the database."""
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "active_provider")
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = provider
    else:
        db.add(AppSetting(key="active_provider", value=provider))
    await db.commit()
    logger.info(f"[ProviderFactory] Active provider set to: {provider}")


async def get_process_user_request(db: AsyncSession) -> Callable:
    """Return the process_user_request function for the active provider."""
    provider = await get_active_provider(db)
    if provider == "openrouter":
        from .openrouter_client import process_user_request
    else:
        from .ollama_client import process_user_request
    return process_user_request


async def get_list_models(db: AsyncSession) -> Callable:
    """Return the list_models function for the active provider."""
    provider = await get_active_provider(db)
    if provider == "openrouter":
        from .openrouter_client import list_models
    else:
        from .ollama_client import list_models
    return list_models
