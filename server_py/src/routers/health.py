import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import ServiceHealthStatus
from ..services.health_service import perform_health_checks

logger = logging.getLogger("app")

router = APIRouter(tags=["Health"])

@router.get("/api/health/status")
async def get_latest_health_status(db: AsyncSession = Depends(get_db)):
    """Returns the most recent health record for all tracked services."""
    services = ["database", "ollama", "lex_api"]
    results = {}
    
    try:
        for svc in services:
            stmt = select(ServiceHealthStatus).where(ServiceHealthStatus.service_name == svc).order_by(desc(ServiceHealthStatus.checked_at)).limit(1)
            res = await db.execute(stmt)
            record = res.scalar_one_or_none()
            
            if record:
                results[svc] = {
                    "is_healthy": record.is_healthy,
                    "error_message": record.error_message,
                    "latency_ms": record.latency_ms,
                    "checked_at": record.checked_at.isoformat()
                }
            else:
                results[svc] = {
                    "is_healthy": None, 
                    "error_message": "No data available yet.",
                    "latency_ms": None,
                    "checked_at": None
                }
    except Exception as e:
        logger.error(f"[Health] Cannot query status from DB (down?), falling back to live check: {e}")
        from datetime import datetime
        live_results = await perform_health_checks()
        for r in live_results:
            results[r["service_name"]] = {
                "is_healthy": r["is_healthy"],
                "error_message": r["error_message"],
                "latency_ms": r["latency_ms"],
                "checked_at": datetime.utcnow().isoformat()
            }
            
    return results

@router.get("/api/health/history")
async def get_health_history(service: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Returns the last `limit` health checks for a specific service."""
    try:
        stmt = select(ServiceHealthStatus).where(ServiceHealthStatus.service_name == service).order_by(desc(ServiceHealthStatus.checked_at)).limit(limit)
        res = await db.execute(stmt)
        records = res.scalars().all()
        
        # Return reversed so chronological for charts
        return [
            {
                "is_healthy": r.is_healthy,
                "error_message": r.error_message,
                "latency_ms": r.latency_ms,
                "checked_at": r.checked_at.isoformat()
            } for r in reversed(records)
        ]
    except Exception as e:
        logger.error(f"[Health] Cannot query history from DB: {e}")
        return []

@router.post("/api/health/trigger")
async def trigger_immediate_health_check(db: AsyncSession = Depends(get_db)):
    """Manually triggers an immediate health check across all services, bypassing the schedule."""
    # We await the check directly. The inner logic logs to DB.
    try:
        results = await perform_health_checks()
        # Convert results to a dict mapping service name -> status for immediate frontend rendering
        formatted = {}
        for r in results:
            formatted[r["service_name"]] = {
                "is_healthy": r["is_healthy"],
                "error_message": r["error_message"],
                "latency_ms": r["latency_ms"],
                "checked_at": r["checked_at"].isoformat() if "checked_at" in r else None # The function doesn't return dates but the router can construct it or we can just refetch
            }
        
        # It's better to refetch down below to get exact timestamps that were saved
        return await get_latest_health_status(db)
    
    except Exception as e:
        logger.error(f"[Health] Failed manual health trigger: {e}")
        # Even if DB fails, the live check completed and we have `formatted` data
        # Let's return the `formatted` live data instead of failing out
        if 'formatted' in locals():
            from datetime import datetime
            now = datetime.utcnow().isoformat()
            for k in formatted:
                formatted[k]["checked_at"] = now
            return formatted
        raise HTTPException(status_code=500, detail="Failed to run health checks.")
