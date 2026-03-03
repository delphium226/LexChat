import asyncio
import logging
import time
from datetime import datetime
import httpx

from sqlalchemy import select
from ..database import async_session_maker
from ..models import ServiceHealthStatus
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

async def check_lex_api() -> dict:
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # We just ping the base URL for health
            response = await client.get(settings.lex_api_url)
            # Accept 200 or 401/403 as "service is up but maybe needs auth"
            # Actually LEX API root often returns 404 or something, let's just make sure it connects
            # A connection error would throw an exception
            latency = int((time.time() - start_time) * 1000)
            return {"service_name": "lex_api", "is_healthy": True, "error_message": None, "latency_ms": latency}
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {"service_name": "lex_api", "is_healthy": False, "error_message": str(e), "latency_ms": latency}

async def perform_health_checks():
    # Run all checks concurrently
    results = await asyncio.gather(
        check_database(),
        check_ollama(),
        check_lex_api()
    )
    
    # Save to database
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
        logger.error(f"Failed to write health checks to DB: {db_err}")

    return results

async def background_health_loop(interval_seconds: int = 60):
    logger.info(f"Background health check loop started (interval: {interval_seconds}s)")
    try:
        while True:
            await perform_health_checks()
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Background health check loop stopped.")
