"""Deep Research Phase A — plan drafting endpoint.

POST /api/research/plan runs the planner-only agent (no research tools) and
returns the drafted plan as plain JSON. Execution of an approved plan goes
through the existing POST /api/chat (SSE) with chat_mode="deep_research".
"""
import logging
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException

from ..agent.agent_shared import describe_agent_error
from ..agent.provider_factory import (
    get_active_provider,
    get_draft_research_plan_from_context,
    get_provider_config,
    get_request_queue,
    set_request_provider_config,
)
from ..database import async_session_maker
from ..dependencies import get_current_user
from ..utils.stopwatch import TimingCollector
from .agent_request import ResearchPlanRequest, build_request_config
from .developer import _read_features

logger = logging.getLogger("app")

router = APIRouter(tags=["Research"])

# Provider statuses a retry will not cure: the account needs an administrator.
_PROVIDER_ACCOUNT_STATUSES = {401, 402, 403}


def planner_provider_error(exc: httpx.HTTPStatusError) -> HTTPException:
    """The planner's answer to a provider HTTP error (TODO B6).

    Every such error used to reach the lawyer as "The planner failed. Please try
    again." — advice to retry when the provider's account was out of credit,
    and no hint of a rate limit when one was the cause. The detail names the
    provider's status through describe_agent_error, never the provider's raw
    body. A provider 401 is returned as 502, not passed through: the client
    logs the user out on a 401 from this server.
    """
    status = exc.response.status_code
    reason = f"The planner could not run: {describe_agent_error(exc)}."
    if status in _PROVIDER_ACCOUNT_STATUSES:
        return HTTPException(status_code=502, detail=(
            f"{reason} The AI provider declined the request for this service's "
            "account (for example, its credit or payment needs attention), so "
            "trying again will not help. Please tell your administrator."
        ))
    if status == 429:
        return HTTPException(status_code=503, detail=(
            f"{reason} The AI provider is limiting the rate of requests. "
            "Please try again in a few minutes."
        ))
    return HTTPException(status_code=503, detail=(
        f"{reason} The AI provider is unavailable or returned an error. "
        "Please try again later."
    ))


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
            features = await _read_features(db)
    except Exception as e:
        logger.error(f"[Research] Provider resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please try again.")

    # Planning is always deep_research, so chat_mode is fixed rather than read
    # off the body. The cache/memo flags in the shared config are inert here
    # (the planner runs no research tools) but cost nothing and keep the key
    # set identical across the three endpoints.
    set_request_provider_config(build_request_config(
        body, provider_config, active_provider, features,
        chat_mode="deep_research",
    ))

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
    except httpx.HTTPStatusError as e:
        logger.error(f"[Research] Planner failed: {describe_agent_error(e)}")
        raise planner_provider_error(e)
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
