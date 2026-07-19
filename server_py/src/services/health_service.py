import asyncio
import logging
import time
from datetime import datetime
import httpx

from sqlalchemy import select
from ..database import async_session_maker
from ..models import ServiceHealthStatus, AppSetting
from ..config import settings

logger = logging.getLogger("app")

async def check_database() -> dict:
    start_time = time.time()
    try:
        async with async_session_maker() as session:
            await session.execute(select(1))
            latency = int((time.time() - start_time) * 1000)
            return {"service_name": "database", "is_healthy": True, "error_message": None, "latency_ms": latency}
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {"service_name": "database", "is_healthy": False, "error_message": str(e), "latency_ms": latency}

async def check_ollama() -> dict:
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            response.raise_for_status()
            latency = int((time.time() - start_time) * 1000)
            return {"service_name": "ollama", "is_healthy": True, "error_message": None, "latency_ms": latency}
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {"service_name": "ollama", "is_healthy": False, "error_message": str(e), "latency_ms": latency}

async def check_openrouter(base_url: str, api_key: str | None) -> dict:
    start_time = time.time()
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/models", headers=headers)
            # Any HTTP response means the service is reachable; treat 200 as healthy
            latency = int((time.time() - start_time) * 1000)
            is_healthy = response.status_code == 200
            error = None if is_healthy else f"HTTP {response.status_code}"
            return {"service_name": "openrouter", "is_healthy": is_healthy, "error_message": error, "latency_ms": latency}
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {"service_name": "openrouter", "is_healthy": False, "error_message": str(e), "latency_ms": latency}

async def _get_active_llm_check():
    """Return (provider_name, check_coroutine) based on the active provider in DB."""
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(AppSetting).where(AppSetting.key == "active_provider")
            )
            setting = result.scalar_one_or_none()
            active = setting.value if setting else "ollama"

            if active == "openrouter":
                cfg_result = await session.execute(
                    select(AppSetting).where(AppSetting.key == "provider.openrouter")
                )
                cfg_setting = cfg_result.scalar_one_or_none()
                import json
                cfg = json.loads(cfg_setting.value) if cfg_setting else {}
                base_url = cfg.get("base_url") or settings.openrouter_base_url
                api_key = cfg.get("api_key") or settings.openrouter_api_key
                return "openrouter", check_openrouter(base_url, api_key)

    except Exception as e:
        logger.error(f"[Health] Failed to read active provider for health check: {e}", exc_info=True)

    return "ollama", check_ollama()

async def perform_health_checks():
    _, llm_check = await _get_active_llm_check()

    results = await asyncio.gather(
        check_database(),
        llm_check,
        check_lex_api()
    )

    try:
        async with async_session_maker() as session:
            for res in results:
                status = ServiceHealthStatus(
                    service_name=res["service_name"],
                    is_healthy=res["is_healthy"],
                    error_message=res["error_message"],
                    latency_ms=res["latency_ms"],
                    checked_at=datetime.utcnow()
                )
                session.add(status)
            await session.commit()
    except Exception as db_err:
        logger.error(f"[Health] Failed to write health checks to DB: {db_err}", exc_info=True)

    return results

async def check_lex_api() -> dict:
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(settings.lex_api_url)
            latency = int((time.time() - start_time) * 1000)
            return {"service_name": "lex_api", "is_healthy": True, "error_message": None, "latency_ms": latency}
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {"service_name": "lex_api", "is_healthy": False, "error_message": str(e), "latency_ms": latency}

async def background_health_loop(interval_seconds: int = 60):
    logger.info(f"[Health] Background check loop started (interval: {interval_seconds}s)")
    try:
        while True:
            await perform_health_checks()
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("[Health] Background check loop stopped.")
