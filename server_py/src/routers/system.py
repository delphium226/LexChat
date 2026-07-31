"""Machine-to-machine chat endpoint for evaluation harnesses.

`/api/system/chat` runs exactly the same pipeline as `/api/chat` but with
`emit_tool_details=True`, so the caller sees the internal `tool_call`,
`api_call_start` and `api_call_end` events the UI never needs. That is the only
reason this endpoint exists — an eval harness has to see what the agent
retrieved, not just what it answered.

Two things this module deliberately does NOT do:

* **It does not define its own request model.** It imports `ChatRequest` from
  `agent_request`, so its accepted fields are structurally identical to
  `/api/chat`. The previous version declared a three-field model of its own and
  silently dropped `chat_mode`, `research_mode`, every filter and the Deep
  Research plan — an eval run could only ever exercise the defaults
  (`legislation_only` / `research`) no matter what it sent.
* **It does not re-implement the agent orchestration.** Provider resolution,
  config building, queueing and dispatch all go through the same helpers as
  `/api/chat`. Copying that logic is what let this endpoint rot in the first
  place.

Its one addition is the `audit` SSE event: a structured trace of the run
(delegations → tool calls → API calls, with raw and post-summarisation results
side by side), emitted once before `result`. See `utils/audit_trace.py`.
"""

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..agent.agent_shared import describe_agent_error
from ..agent.provider_factory import (
    get_active_provider,
    get_process_user_request_from_context,
    get_provider_config,
    get_request_queue,
    get_run_deep_research_from_context,
    set_request_provider_config,
)
from ..database import async_session_maker
from ..dependencies import get_current_user
from ..models import RequestTiming
from ..utils.audit_trace import AuditCollector, set_audit_collector
from ..utils.stopwatch import TimingCollector
from .agent_request import ChatRequest, build_request_config, resolve_research_mode
from .ai import _load_doc_context, _load_matter_context
from .developer import _read_features

logger = logging.getLogger("app")

router = APIRouter(tags=["System"])


class SystemChatRequest(ChatRequest):
    """Identical to the `/api/chat` body, plus audit-only controls.

    Subclassing rather than redeclaring is the point: a field added to
    `/api/chat` is accepted here automatically and cannot be forgotten.
    """

    # Emit the structured `audit` event. On by default — an eval harness is the
    # only caller, and the trace is the reason to use this endpoint.
    audit: bool = True
    # Truncate long strings in the trace (raw tool results can run to hundreds
    # of KB). 0 = no truncation, which is the useful default for an audit.
    audit_max_field_chars: int = 0


@router.post("/api/system/chat")
async def system_chat_endpoint(
    body: SystemChatRequest, request: Request, user: dict = Depends(get_current_user)
):
    """System-to-system chat. Relays all detailed events plus an `audit` trace."""

    if not body.messages or not body.model:
        raise HTTPException(status_code=400, detail="Missing messages or model")

    # Same guard as /api/chat: executing a Deep Research run needs an approved
    # plan from POST /api/research/plan. Raised as a 400 rather than an SSE
    # error event so a harness checking status codes cannot mistake it for a
    # successful run that happened to research nothing.
    if body.chat_mode == "deep_research" and body.deep_research_plan is None:
        raise HTTPException(
            status_code=400,
            detail="Deep Research execution requires an approved plan (deep_research_plan). "
                   "Call POST /api/research/plan first.",
        )

    cancel_event = asyncio.Event()
    t_request = time.perf_counter()
    request_id = uuid.uuid4().hex[:8]
    timing = TimingCollector(request_id)
    audit = (
        AuditCollector(request_id, max_field_chars=body.audit_max_field_chars)
        if body.audit else None
    )

    async def event_stream():
        try:
            async with async_session_maker() as _cfg_db:
                active_provider = await get_active_provider(_cfg_db)
                provider_config = await get_provider_config(_cfg_db, active_provider)
                features = await _read_features(_cfg_db)
        except Exception as e:
            logger.error(f"[System] Provider resolution failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': 'Service temporarily unavailable. Please try again.'})}\n\n"
            return

        doc_context = await _load_doc_context(body.chat_id) if body.chat_id else ""
        matter_context = await _load_matter_context(body.chat_id) if body.chat_id else ""

        request_config = build_request_config(
            body, provider_config, active_provider, features,
            chat_mode=body.chat_mode or "research",
            doc_context=doc_context,
            matter_context=matter_context,
        )
        set_request_provider_config(request_config)
        # Set on the same context as the provider config, before the agent task
        # is created — asyncio.create_task copies the context, so the collector
        # reaches the whole call tree without threading a parameter through it.
        set_audit_collector(audit)

        resolved_model = provider_config.get("model") or body.model
        request_queue = get_request_queue(
            active_provider, provider_config["max_concurrent_requests"]
        )

        disconnect_task = asyncio.create_task(_watch_disconnect(request, cancel_event))

        try:
            events = asyncio.Queue()

            def on_chunk(data):
                events.put_nowait(data)

            t_queue_entry = time.perf_counter()

            async def run_agent_task():
                timing.record_queue_wait((time.perf_counter() - t_queue_entry) * 1000)
                deep_research = (
                    body.chat_mode == "deep_research" and body.deep_research_plan is not None
                )
                async with async_session_maker() as db_session:
                    if deep_research:
                        run_deep_research = get_run_deep_research_from_context()
                        result = await run_deep_research(
                            body.deep_research_plan.model_dump(),
                            list(body.messages),
                            resolved_model,
                            on_chunk,
                            cancel_event,
                            body.num_ctx or 0,
                            db_session=db_session,
                            emit_tool_details=True,
                            timing_collector=timing,
                        )
                    else:
                        process_user_request = get_process_user_request_from_context()
                        result = await process_user_request(
                            list(body.messages),
                            resolved_model,
                            on_chunk,
                            cancel_event,
                            body.num_ctx or 0,
                            db_session=db_session,
                            emit_tool_details=True,
                            timing_collector=timing,
                        )

                    if isinstance(result, dict):
                        result["provider"] = active_provider
                        result["model"] = resolved_model
                    return result

            def on_queue_waiting(position):
                events.put_nowait({"type": "queue", "position": position})

            agent_task = asyncio.create_task(
                request_queue.enqueue(run_agent_task, on_waiting=on_queue_waiting)
            )

            # Persistent get-task drained via asyncio.wait (which does not cancel
            # it on timeout), so an event delivered exactly as the window elapses
            # is never lost — same pattern as /api/chat.
            get_task = asyncio.ensure_future(events.get())
            try:
                while not agent_task.done():
                    done, _ = await asyncio.wait({get_task}, timeout=0.5)
                    if get_task in done:
                        yield f"data: {json.dumps(get_task.result())}\n\n"
                        get_task = asyncio.ensure_future(events.get())

                if get_task.done():
                    yield f"data: {json.dumps(get_task.result())}\n\n"
                else:
                    get_task.cancel()
                while not events.empty():
                    yield f"data: {json.dumps(events.get_nowait())}\n\n"
            finally:
                if not get_task.done():
                    get_task.cancel()

            result_message = agent_task.result()

            timing.record_total((time.perf_counter() - t_request) * 1000)
            yield f"data: {json.dumps({'type': 'timing', **timing.to_dict()})}\n\n"

            # The audit event goes out BEFORE result so a consumer that stops
            # reading at `result` still has to have seen it.
            if audit is not None:
                audit.record_final(result_message)
                yield f"data: {json.dumps(audit.to_event(config=request_config, timings=timing.to_dict()))}\n\n"

            if result_message:
                yield f"data: {json.dumps({'type': 'result', 'message': result_message})}\n\n"
            else:
                logger.error("[System] Agent returned no result")
                yield f"data: {json.dumps({'type': 'error', 'error': 'The agent completed but returned no response.'})}\n\n"

        except asyncio.CancelledError:
            logger.info("[System] Client disconnected.")
        except Exception as e:
            error_msg = describe_agent_error(e)
            logger.error(f"[System] Chat error: {type(e).__name__}: {error_msg}", exc_info=True)
            # A failed run is still an eval data point — emit whatever trace was
            # gathered before the failure rather than only the error.
            if audit is not None:
                audit.record_error(error_msg)
                try:
                    yield f"data: {json.dumps(audit.to_event(config=request_config, timings=timing.to_dict()))}\n\n"
                except Exception:
                    logger.error("[System] Failed to emit audit trace", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
        finally:
            cancel_event.set()
            disconnect_task.cancel()
            set_audit_collector(None)

            if timing.total_ms == 0:
                timing.record_total((time.perf_counter() - t_request) * 1000)

            # Persist the timing row so eval runs populate the Efficiency and
            # Cache tabs like any other request. Tagged source="eval" so the two
            # traffic types stay separable. No ActivityLog efficiency breach is
            # written: those are operator alerts about live behaviour, and a
            # deliberate eval sweep would flood the activity feed.
            if timing.queue_wait_ms > 0 or timing.llm_calls > 0:
                metrics = timing.to_dict()
                metrics["research_mode"] = resolve_research_mode(body)
                metrics["chat_mode"] = body.chat_mode or "research"
                metrics["provider"] = active_provider
                metrics["model"] = resolved_model
                metrics["source"] = "eval"
                try:
                    async with async_session_maker() as db_save:
                        db_save.add(RequestTiming(**metrics))
                        await db_save.commit()
                except Exception as save_err:
                    logger.error(f"[System] Failed to persist request timing: {save_err}", exc_info=True)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def _watch_disconnect(request: Request, cancel_event: asyncio.Event):
    try:
        while not cancel_event.is_set():
            if await request.is_disconnected():
                cancel_event.set()
                return
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
