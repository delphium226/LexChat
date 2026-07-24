"""Deep Research Phase A — plan drafting endpoint.

POST /api/research/plan runs the planner-only agent (no research tools) and
returns the drafted plan as plain JSON. Execution of an approved plan goes
through the existing POST /api/chat (SSE) with chat_mode="deep_research".
"""
import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..agent.provider_factory import (
    get_active_provider,
    get_draft_research_plan_from_context,
    get_provider_config,
    get_request_queue,
    set_request_provider_config,
)
from ..config import settings
from ..database import async_session_maker
from ..dependencies import get_current_user
from ..utils.stopwatch import TimingCollector

logger = logging.getLogger("app")

router = APIRouter(tags=["Research"])


class ResearchPlanRequest(BaseModel):
    messages: List[dict]
    model: str
    num_ctx: Optional[int] = None
    research_mode: Optional[str] = "legislation_only"
    jurisdiction: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    court: Optional[str] = None
    legislation_type: Optional[str] = None
    current_only: Optional[bool] = False
    record_type: Optional[str] = None
    sessions: Optional[List[int]] = None
    chat_id: Optional[int] = None


@router.post("/api/research/plan")
async def draft_plan(body: ResearchPlanRequest, user: dict = Depends(get_current_user)):
    """Draft a Deep Research plan. Plain JSON (planning is quick — no SSE).

    Returns {"plan": {...}} or {"needs_clarification": true, "question": "..."}.
    """
    if not body.messages or not body.model:
        raise HTTPException(status_code=422, detail="Missing messages or model")

    try:
        async with async_session_maker() as db:
            active_provider = await get_active_provider(db)
            provider_config = await get_provider_config(db, active_provider)
    except Exception as e:
        logger.error(f"[Research] Provider resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please try again.")

    set_request_provider_config({
        **provider_config,
        "_provider": active_provider,
        "_chat_mode": "deep_research",
        "_research_mode": settings.research_mode or body.research_mode or "legislation_only",
        "_jurisdiction": body.jurisdiction or None,
        "_year_from": body.year_from or None,
        "_year_to": body.year_to or None,
        "_date_from": body.date_from or None,
        "_date_to": body.date_to or None,
        "_court": body.court or None,
        "_legislation_type": body.legislation_type or None,
        "_current_only": body.current_only or False,
        "_pt_record_type": body.record_type or None,
        "_pt_sessions": body.sessions or None,
    })

    resolved_model = provider_config.get("model") or body.model
    # The planner is still an LLM call — take a slot on the same per-provider
    # queue as /api/chat (the Ollama cloud endpoint 500s under concurrency).
    request_queue = get_request_queue(
        active_provider, provider_config["max_concurrent_requests"]
    )

    request_id = uuid.uuid4().hex[:8]
    timing = TimingCollector(request_id)
    t_start = time.perf_counter()

    async def run_planner_task():
        draft_research_plan = get_draft_research_plan_from_context()
        return await draft_research_plan(
            list(body.messages), resolved_model, None, body.num_ctx or 0,
            timing_collector=timing,
        )

    try:
        result = await request_queue.enqueue(run_planner_task)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"[Research] Planner failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="The planner failed. Please try again.")

    timing.record_total((time.perf_counter() - t_start) * 1000)
    logger.info(
        "[Research] Plan request %s: %.0fms, %s LLM call(s), cost $%.4f",
        request_id, timing.total_ms, timing.llm_calls, timing.total_cost_usd,
    )

    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])

    return result
