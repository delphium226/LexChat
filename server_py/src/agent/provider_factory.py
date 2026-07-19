"""
Provider factory — resolves the active LLM provider and its config at request time.

Storage: AppSetting table
  key="active_provider"          value="ollama" | "openrouter"
  key="provider.ollama"          value=JSON config blob
  key="provider.openrouter"      value=JSON config blob

Per-request config is carried via a ContextVar so the full call chain
(chat_loop, summarise, worker agent) can read it without signature changes.
"""
import asyncio
import json
import logging
from contextvars import ContextVar
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AppSetting
from ..utils.queue import RequestQueue

logger = logging.getLogger("agent")

_SUPPORTED_PROVIDERS = ("ollama", "openrouter")

# ---------------------------------------------------------------------------
# Per-request context var
# ---------------------------------------------------------------------------
# Holds the fully-resolved provider config for the current request, including
# the special "_provider" key for routing decisions.
_provider_config_ctx: ContextVar[dict] = ContextVar("provider_config", default={})


def set_request_provider_config(config: dict) -> None:
    _provider_config_ctx.set(config)


def get_request_provider_config() -> dict:
    return _provider_config_ctx.get({})


# ---------------------------------------------------------------------------
# Default configs (used when no DB entry exists yet)
# ---------------------------------------------------------------------------

def _build_defaults(provider: str) -> dict:
    """Return .env-seeded defaults for a provider."""
    from ..config import MODEL_LIST, OPENROUTER_MODEL_LIST, settings

    if provider == "ollama":
        return {
            "base_url": settings.ollama_base_url,
            "api_key": settings.ollama_api_key or "",
            "model": MODEL_LIST[0]["name"] if MODEL_LIST else "",
            "summarisation_model": "",
            "temperature": settings.ollama_temperature,
            "max_summarise_concurrency": 1,
            "max_concurrent_requests": 3,
        }
    else:  # openrouter
        return {
            "base_url": settings.openrouter_base_url,
            "api_key": settings.openrouter_api_key or "",
            "model": OPENROUTER_MODEL_LIST[0]["name"] if OPENROUTER_MODEL_LIST else "",
            "summarisation_model": "",
            "temperature": settings.ollama_temperature,
            "max_summarise_concurrency": 5,
            "max_concurrent_requests": 10,
        }


# ---------------------------------------------------------------------------
# Active provider
# ---------------------------------------------------------------------------

async def get_active_provider(db: AsyncSession) -> str:
    """Return the active provider name.

    A genuine DB error is re-raised rather than swallowed: silently defaulting
    to "ollama" on a transient failure would misroute the request to the wrong
    provider (wrong model, wrong key) and answer as if nothing was wrong. The
    caller (chat/consult endpoints) already surfaces the exception to the client
    so the user gets a clear error and can retry.  Only a missing or unrecognised
    setting falls back to the "ollama" default.
    """
    try:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == "active_provider")
        )
    except Exception as e:
        logger.error(f"[ProviderFactory] Failed to read active_provider: {e}", exc_info=True)
        raise
    setting = result.scalar_one_or_none()
    if setting and setting.value in _SUPPORTED_PROVIDERS:
        return setting.value
    return "ollama"


async def set_active_provider(db: AsyncSession, provider: str) -> None:
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


# ---------------------------------------------------------------------------
# Per-provider config (JSON blob in AppSetting)
# ---------------------------------------------------------------------------

async def get_provider_config(db: AsyncSession, provider: str) -> dict:
    """Return fully resolved config for a provider (DB overrides .env defaults)."""
    config = _build_defaults(provider)
    try:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == f"provider.{provider}")
        )
        setting = result.scalar_one_or_none()
        if setting:
            db_config = json.loads(setting.value)
            config.update(db_config)
    except Exception as e:
        logger.error(f"[ProviderFactory] Failed to read provider config for {provider}: {e}", exc_info=True)
    config["_model_context_length"] = _resolve_model_context_length(provider, config)
    return config


def _resolve_model_context_length(provider: str, config: dict):
    """Return the configured model's context length in tokens, or None if unknown.

    Checks the curated static lists first, then (for OpenRouter) the WARM dynamic
    model-list cache. It never triggers a fetch, so config resolution adds no
    network I/O to the request hot path — critical on the internet-restricted
    target. If the cache is cold the caller falls back to the default summarise
    threshold until /api/models warms it.
    """
    from ..config import MODEL_LIST, OPENROUTER_MODEL_LIST

    model_name = config.get("model", "")
    if not model_name:
        return None

    model_list = OPENROUTER_MODEL_LIST if provider == "openrouter" else MODEL_LIST
    entry = next((m for m in model_list if m["name"] == model_name), None)
    if entry:
        return entry["contextLengthKB"] * 1024

    if provider == "openrouter":
        try:
            from .openrouter_client import peek_cached_context_length
            return peek_cached_context_length(model_name, config)
        except Exception as e:
            logger.warning(
                f"[ProviderFactory] Could not resolve context length for '{model_name}': {e}"
            )
    return None


async def save_provider_config(db: AsyncSession, provider: str, data: dict) -> None:
    """Persist provider config as a JSON blob. Validates keys."""
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    allowed_keys = {"base_url", "api_key", "model", "summarisation_model", "temperature",
                    "max_summarise_concurrency", "max_concurrent_requests"}
    clean = {k: v for k, v in data.items() if k in allowed_keys}

    result = await db.execute(
        select(AppSetting).where(AppSetting.key == f"provider.{provider}")
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = json.dumps(clean)
    else:
        db.add(AppSetting(key=f"provider.{provider}", value=json.dumps(clean)))
    await db.commit()
    logger.info(f"[ProviderFactory] Saved config for provider: {provider}")


# ---------------------------------------------------------------------------
# Request queue cache — one queue per (provider, concurrency) pair
# ---------------------------------------------------------------------------
_queue_cache: dict[tuple, RequestQueue] = {}


def get_request_queue(provider: str, concurrency: int) -> RequestQueue:
    """Return a cached RequestQueue for this provider/concurrency pair.
    If concurrency changed, the old queue is retired and a new one created.
    In-flight requests on the old queue complete normally.
    """
    key = (provider, concurrency)
    if key not in _queue_cache:
        # Evict stale queues for this provider
        for k in list(_queue_cache):
            if k[0] == provider:
                del _queue_cache[k]
        _queue_cache[key] = RequestQueue(concurrency=concurrency)
        logger.info(f"[ProviderFactory] Created RequestQueue for {provider} (concurrency={concurrency})")
    return _queue_cache[key]


# ---------------------------------------------------------------------------
# Summarisation semaphore cache — one semaphore per (provider, concurrency)
# ---------------------------------------------------------------------------
_semaphore_cache: dict[tuple, asyncio.Semaphore] = {}


def get_summarise_semaphore(provider: str, concurrency: int) -> asyncio.Semaphore:
    """Return a cached asyncio.Semaphore for summarisation concurrency.
    Recreated if concurrency value changes.
    """
    key = (provider, concurrency)
    if key not in _semaphore_cache:
        for k in list(_semaphore_cache):
            if k[0] == provider:
                del _semaphore_cache[k]
        _semaphore_cache[key] = asyncio.Semaphore(concurrency)
        logger.info(f"[ProviderFactory] Created summarise semaphore for {provider} (concurrency={concurrency})")
    return _semaphore_cache[key]


# ---------------------------------------------------------------------------
# Shared async helper (single definition lives in summarisation.py)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Client function accessors (DB-based)
# ---------------------------------------------------------------------------

async def get_process_user_request(db: AsyncSession) -> Callable:
    provider = await get_active_provider(db)
    if provider == "openrouter":
        from .openrouter_client import process_user_request
    else:
        from .ollama_client import process_user_request
    return process_user_request


async def get_list_models(db: AsyncSession) -> Callable:
    provider = await get_active_provider(db)
    if provider == "openrouter":
        cfg = await get_provider_config(db, "openrouter")
        from .openrouter_client import make_list_models
        return make_list_models(cfg)
    from .ollama_client import list_models
    return list_models


# ---------------------------------------------------------------------------
# Context-based function accessors (no DB session — read from ContextVar)
# ---------------------------------------------------------------------------

def get_active_chat_loop() -> Callable:
    """Return the chat_loop for the active provider from the current request context."""
    provider = _provider_config_ctx.get({}).get("_provider", "ollama")
    if provider == "openrouter":
        from .openrouter_client import chat_loop
    else:
        from .ollama_client import chat_loop
    return chat_loop


def get_process_user_request_from_context() -> Callable:
    """Return process_user_request for the active provider from the current request context.

    Reads the provider from the ContextVar set at request start — avoids a second
    DB round-trip inside run_agent_task and eliminates the TOCTOU race where the
    active provider could change between config resolution and function dispatch.
    """
    provider = _provider_config_ctx.get({}).get("_provider", "ollama")
    if provider == "openrouter":
        from .openrouter_client import process_user_request
    else:
        from .ollama_client import process_user_request
    return process_user_request


def get_draft_research_plan_from_context() -> Callable:
    """Return draft_research_plan (Deep Research Phase A) for the active provider
    from the current request context. Same pattern as
    get_process_user_request_from_context."""
    provider = _provider_config_ctx.get({}).get("_provider", "ollama")
    if provider == "openrouter":
        from .openrouter_client import draft_research_plan
    else:
        from .ollama_client import draft_research_plan
    return draft_research_plan


def get_run_deep_research_from_context() -> Callable:
    """Return run_deep_research (Deep Research Phase B) for the active provider
    from the current request context."""
    provider = _provider_config_ctx.get({}).get("_provider", "ollama")
    if provider == "openrouter":
        from .openrouter_client import run_deep_research
    else:
        from .ollama_client import run_deep_research
    return run_deep_research


def get_summarise_threshold() -> int:
    """Return the char threshold above which a tool result is summarised.

    Scales with the active model's context window: 10% of total context chars,
    clamped to [10_000, 200_000].  The context length is resolved at request
    start by get_provider_config (static lists first, then the dynamic
    OpenRouter model list) and carried in the request config as
    "_model_context_length" (tokens).  Falls back to SUMMARISE_THRESHOLD_CHARS
    only when the model's context length could not be resolved at all.

    The threshold is based on the main model's context (the Worker accumulates
    results in that context), not the summarisation model.
    """
    from ..config import MODEL_LIST, OPENROUTER_MODEL_LIST
    from .summarisation import SUMMARISE_THRESHOLD_CHARS

    cfg = _provider_config_ctx.get({})
    if not cfg:
        return SUMMARISE_THRESHOLD_CHARS

    context_tokens = cfg.get("_model_context_length")
    if not context_tokens:
        # Legacy path: config set without get_provider_config enrichment
        provider = cfg.get("_provider", "ollama")
        model_name = cfg.get("model", "")
        model_list = OPENROUTER_MODEL_LIST if provider == "openrouter" else MODEL_LIST
        entry = next((m for m in model_list if m["name"] == model_name), None)
        if entry is None:
            return SUMMARISE_THRESHOLD_CHARS
        context_tokens = entry["contextLengthKB"] * 1024

    # ~4 chars/token
    context_chars = context_tokens * 4
    return max(10_000, min(int(context_chars * 0.10), 200_000))


def get_summarise_model() -> str:
    """Return the configured summarisation model, falling back to the main model.

    Used wherever summarisation calls need to resolve the correct model without
    knowing whether a separate summarisation_model has been configured.
    """
    cfg = _provider_config_ctx.get({})
    return cfg.get("summarisation_model") or cfg.get("model", "")


def get_active_summarise_for_query() -> Callable:
    """Return a bound summarise_for_query for the active provider.

    Returns summarise_for_query with the provider-specific chunk_fn pre-bound
    so callers don't need to know about it.
    """
    import functools
    from .summarisation import summarise_for_query
    provider = _provider_config_ctx.get({}).get("_provider", "ollama")
    if provider == "openrouter":
        from .openrouter_client import _summarise_chunk
    else:
        from .ollama_client import _summarise_chunk
    return functools.partial(summarise_for_query, chunk_fn=_summarise_chunk)
