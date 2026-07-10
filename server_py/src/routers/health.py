import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import ServiceHealthStatus, AppSetting
from ..services.health_service import perform_health_checks

logger = logging.getLogger("app")

router = APIRouter(tags=["Health"])


class HealthEntry(BaseModel):
    is_healthy: Optional[bool]
    error_message: Optional[str]
    latency_ms: Optional[int]
    checked_at: Optional[str]


class HealthStatusOut(BaseModel):
    database: HealthEntry
    lex_api: HealthEntry
    llm: HealthEntry
    active_llm_provider: str


async def _get_active_provider(db: AsyncSession) -> str:
    try:
        result = await db.execute(select(AppSetting).where(AppSetting.key == "active_provider"))
        setting = result.scalar_one_or_none()
        if setting and setting.value in ("ollama", "openrouter"):
            return setting.value
    except Exception:
        pass
    return "ollama"


@router.get("/api/health/status", response_model=HealthStatusOut)
async def get_latest_health_status(db: AsyncSession = Depends(get_db)):
    """Returns the most recent health record for all tracked services."""
    active_llm = await _get_active_provider(db)
    fixed_services = ["database", "lex_api"]
    results = {}

    try:
        for svc in fixed_services + [active_llm]:
            stmt = (
                select(ServiceHealthStatus)
                .where(ServiceHealthStatus.service_name == svc)
                .order_by(desc(ServiceHealthStatus.checked_at))
                .limit(1)
            )
            res = await db.execute(stmt)
            record = res.scalar_one_or_none()

            entry = (
                {
                    "is_healthy": record.is_healthy,
                    "error_message": record.error_message,
                    "latency_ms": record.latency_ms,
                    "checked_at": record.checked_at.isoformat(),
                }
                if record
                else {
                    "is_healthy": None,
                    "error_message": "No data available yet.",
                    "latency_ms": None,
                    "checked_at": None,
                }
            )

            if svc == active_llm:
                results["llm"] = entry
            else:
                results[svc] = entry

        results["active_llm_provider"] = active_llm

    except Exception as e:
        logger.error(f"[Health] Cannot query status from DB (down?), falling back to live check: {e}")
        from datetime import datetime
        live_results = await perform_health_checks()
        for r in live_results:
            svc = r["service_name"]
            entry = {
                "is_healthy": r["is_healthy"],
                "error_message": r["error_message"],
                "latency_ms": r["latency_ms"],
                "checked_at": datetime.utcnow().isoformat(),
            }
            if svc == active_llm:
                results["llm"] = entry
            else:
                results[svc] = entry
        results["active_llm_provider"] = active_llm

    return results


@router.get("/api/health/history", response_model=list[HealthEntry])
async def get_health_history(service: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Returns the last `limit` health checks for a specific service."""
    try:
        stmt = (
            select(ServiceHealthStatus)
            .where(ServiceHealthStatus.service_name == service)
            .order_by(desc(ServiceHealthStatus.checked_at))
            .limit(limit)
        )
        res = await db.execute(stmt)
        records = res.scalars().all()

        return [
            {
                "is_healthy": r.is_healthy,
                "error_message": r.error_message,
                "latency_ms": r.latency_ms,
                "checked_at": r.checked_at.isoformat(),
            }
            for r in reversed(records)
        ]
    except Exception as e:
        logger.error(f"[Health] Cannot query history from DB: {e}")
        return []


@router.post("/api/health/trigger", response_model=HealthStatusOut)
async def trigger_immediate_health_check(db: AsyncSession = Depends(get_db)):
    """Manually triggers an immediate health check across all services, bypassing the schedule."""
    try:
        await perform_health_checks()
        return await get_latest_health_status(db)
    except Exception as e:
        logger.error(f"[Health] Failed manual health trigger: {e}")
        raise HTTPException(status_code=500, detail="Failed to run health checks.")
