import asyncio
import json
import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..agent.provider_factory import (
    get_active_provider,
    get_list_models,
    get_process_user_request_from_context,
    get_provider_config,
    get_request_queue,
    get_run_deep_research_from_context,
    set_request_provider_config,
)
from ..config import MAX_TOTAL_DOC_CHARS, evaluate_efficiency_breaches, settings
from ..database import async_session_maker
from ..dependencies import get_current_user
from ..models import ActivityLog, Chat, Document, Matter, RequestTiming
from ..utils.stopwatch import TimingCollector
from .developer import _read_features

logger = logging.getLogger("app")

router = APIRouter(tags=["AI"])


class ModelInfo(BaseModel):
    name: str
    context_length: int
    provider: str
    active: bool


@router.get("/api/models", response_model=List[ModelInfo])
async def get_models(user: dict = Depends(get_current_user)):
    async with async_session_maker() as db:
        active_provider = await get_active_provider(db)
        provider_config = await get_provider_config(db, active_provider)
        list_models = await get_list_models(db)
    models = await list_models()
    active_model = provider_config.get("model")
    marked = False
    for m in models:
        m["active"] = (m["name"] == active_model)
        if m["active"]:
            marked = True
    if models and not marked:
        models[0]["active"] = True
    return models


class ResearchPlanStep(BaseModel):
    """One approved Deep Research plan step (user-editable, so validated here)."""
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    detail: str = Field("", max_length=4000)


class DeepResearchPlan(BaseModel):
    """The approved plan sent back for execution. Each step is a full worker
    run (real cost), so the step count is hard-capped server-side."""
    scope_note: str = Field("", max_length=2000)
    steps: List[ResearchPlanStep] = Field(..., min_length=1, max_length=8)


class ChatRequest(BaseModel):
    messages: List[dict]
    model: str
    num_ctx: Optional[int] = None
    chat_mode: Optional[str] = "research"
    research_mode: Optional[str] = "legislation_only"
    jurisdiction: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    court: Optional[str] = None
    legislation_type: Optional[str] = None
    current_only: Optional[bool] = False
    # Parliamentary-mode filters (parliament bot only)
    record_type: Optional[str] = None
    chat_id: Optional[int] = None
    # Deep Research execution: the user-approved plan (chat_mode="deep_research")
    deep_research_plan: Optional[DeepResearchPlan] = None


@router.post("/api/chat")
async def chat_endpoint(body: ChatRequest, request: Request, user: dict = Depends(get_current_user)):
    """Main chat endpoint with SSE streaming, agent system, and queue."""

    if not body.messages or not body.model:
        return StreamingResponse(
            _error_stream("Missing messages or model"),
            media_type="text/event-stream",
        )

    if body.chat_mode == "deep_research" and body.deep_research_plan is None:
        return StreamingResponse(
            _error_stream("Deep Research execution requires an approved plan (deep_research_plan)."),
            media_type="text/event-stream",
        )

    cancel_event = asyncio.Event()
    t_request = time.perf_counter()
    request_id = uuid.uuid4().hex[:8]
    timing = TimingCollector(request_id)

    async def event_stream():
        # Resolve provider config once — set context var for the full call chain.
        # get_active_provider re-raises on DB error (rather than silently defaulting
        # to the wrong provider), so this happens before the main try/finally — a
        # failure here must still emit a clean SSE error event, not a broken stream.
        try:
            async with async_session_maker() as _cfg_db:
                active_provider = await get_active_provider(_cfg_db)
                provider_config = await get_provider_config(_cfg_db, active_provider)
                features = await _read_features(_cfg_db)
        except Exception as e:
            logger.error(f"[AI] Provider resolution failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': 'Service temporarily unavailable. Please try again.'})}\n\n"
            return

        doc_context = await _load_doc_context(body.chat_id) if body.chat_id else ""
        matter_context = await _load_matter_context(body.chat_id) if body.chat_id else ""

        set_request_provider_config({
            **provider_config,
            "_provider": active_provider,
            "_chat_mode": body.chat_mode or "research",
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
            "_doc_context": doc_context,
            "_matter_context": matter_context,
            # Local-cache key source (D8 Phase 5): in standard mode the cache
            # keys on the RAW user query, not the LLM-paraphrased delegation
            # brief (which varies per model/run and makes cross-user hits
            # luck). Deep Research must NOT set this — each step's approved
            # plan text is the right key; steps with different intents must
            # not collide.
            "_cache_key_query": (
                "" if body.chat_mode == "deep_research"
                else next(
                    (m.get("content", "") for m in reversed(body.messages)
                     if m.get("role") == "user"),
                    "",
                )
            ),
            "_prompt_caching_enabled": features.get("prompt_caching_enabled", True),
            "_tool_memo_enabled": features.get("tool_memo_enabled", True),
            "_local_prompt_cache_enabled": features.get("local_prompt_cache_enabled", True),
        })
        # Always use the server-side configured model — the frontend may be stale
        # (e.g. user switched provider via Dev tab without refreshing the page).
        resolved_model = provider_config.get("model") or body.model
        request_queue = get_request_queue(
            active_provider, provider_config["max_concurrent_requests"]
        )

        # Detect client disconnect
        disconnect_task = asyncio.create_task(_watch_disconnect(request, cancel_event))

        # "Taking longer than usual" warning, emitted once after 5 minutes
        warning_sent = False

        try:
            # Collect SSE events via callback
            events = asyncio.Queue()

            def on_chunk(data):
                events.put_nowait(data)

            # Record queue entry time — queue wait = time until task_factory() is called
            t_queue_entry = time.perf_counter()

            async def run_agent_task():
                timing.record_queue_wait((time.perf_counter() - t_queue_entry) * 1000)

                # Resolve the provider function from the ContextVar set above — this
                # avoids a second DB read and eliminates the TOCTOU race where the
                # active provider could be switched between config resolution and dispatch.
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
                            timing_collector=timing,
                        )

                    if isinstance(result, dict):
                        result["provider"] = active_provider
                        result["model"] = resolved_model
                    return result

            # Callback for queue updates
            def on_queue_waiting(position):
                events.put_nowait({"type": "queue", "position": position})

            # EXECUTE THROUGH QUEUE
            # This will block until a slot is available
            agent_task = asyncio.create_task(
                request_queue.enqueue(run_agent_task, on_waiting=on_queue_waiting)
            )

            # Timeout warning task
            timeout_task = asyncio.create_task(asyncio.sleep(300))

            # Persistent get-task: awaited via asyncio.wait (which does NOT cancel
            # it on timeout), so an event delivered right as the 0.5s window
            # elapses is never lost — unlike wait_for(queue.get()), which cancels
            # the get() and can drop an already-dequeued item.
            get_task = asyncio.ensure_future(events.get())
            try:
                while not agent_task.done():
                    done, _ = await asyncio.wait({get_task}, timeout=0.5)
                    if get_task in done:
                        yield f"data: {json.dumps(get_task.result())}\n\n"
                        get_task = asyncio.ensure_future(events.get())
                    elif timeout_task.done() and not warning_sent:
                        warning_sent = True
                        yield f"data: {json.dumps({'type': 'warning', 'message': 'The request is taking longer than usual. Please be patient...'})}\n\n"

                # Drain remaining events — the pending get_task first (it may
                # already hold the next item), then anything still queued.
                if get_task.done():
                    yield f"data: {json.dumps(get_task.result())}\n\n"
                else:
                    get_task.cancel()
                while not events.empty():
                    yield f"data: {json.dumps(events.get_nowait())}\n\n"
            finally:
                if not get_task.done():
                    get_task.cancel()

            # Get final result
            result_message = agent_task.result()

            # Record total and emit timing summary before result
            timing.record_total((time.perf_counter() - t_request) * 1000)
            yield f"data: {json.dumps({'type': 'timing', **timing.to_dict()})}\n\n"

            if result_message:
                yield f"data: {json.dumps({'type': 'result', 'message': result_message})}\n\n"
            else:
                logger.error("[AI] Agent returned no result — sending error to client")
                yield f"data: {json.dumps({'type': 'error', 'error': 'The agent completed but returned no response. Please try again.'})}\n\n"

        except asyncio.CancelledError:
            logger.info("[AI] Client closed connection, aborted processing.")
        except ConnectionError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        except Exception as e:
            logger.error(f"[AI] Chat error: {e}", exc_info=True)
            error_msg = str(e)
            if "ECONNREFUSED" in error_msg or "ConnectError" in error_msg:
                error_msg = "Agent Service (Ollama) is not reachable. Please ensure it is running."
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
        finally:
            cancel_event.set()
            disconnect_task.cancel()

            # Ensure total_ms is recorded even if an exception cut us short
            if timing.total_ms == 0:
                timing.record_total((time.perf_counter() - t_request) * 1000)

            # Persist timing + efficiency metrics if we got at least as far as queue entry
            if timing.queue_wait_ms > 0 or timing.llm_calls > 0:
                metrics = timing.to_dict()
                # Effective per-request research mode (bot override wins, then the
                # frontend value). Persisted for future per-mode filtering; not
                # consumed by the efficiency queries (those key on the bot profile).
                metrics["research_mode"] = (
                    settings.research_mode or body.research_mode or "legislation_only"
                )
                # Segments Deep Research (N delegations by design) from standard
                # requests; evaluate_efficiency_breaches skips deep_research rows.
                metrics["chat_mode"] = body.chat_mode or "research"
                # Resolved active provider (D8) — replaces the cost>0 proxy for
                # "OpenRouter-eligible" in the Cache tab going forward.
                metrics["provider"] = active_provider
                # One-line efficiency summary for grep-ability in the agent log.
                logging.getLogger("agent").info(
                    "[Efficiency] req=%s delegations=%s worker_tools=%s phase1=%s phase2=%s "
                    "distinct_retrieved=%s redundant=%s summ=%s trunc=%s kept=%s/%s turns=%s cost=%.4f",
                    metrics["request_id"], metrics["manager_delegations"], metrics["worker_tool_calls"],
                    metrics["phase1_search_calls"], metrics["phase2_retrieval_calls"],
                    metrics["distinct_legislation_ids_retrieved"], metrics["redundant_tool_calls"],
                    metrics["summarisation_calls"], metrics["truncation_events"],
                    metrics["sources_kept"], metrics["sources_extracted"],
                    metrics["react_turns_max"], metrics["total_cost_usd"],
                )
                try:
                    async with async_session_maker() as db_save:
                        db_save.add(RequestTiming(**metrics))
                        # Automated alert: a per-request efficiency breach becomes an
                        # ActivityLog row so it surfaces in the admin activity feed.
                        breaches = evaluate_efficiency_breaches(metrics)
                        if breaches:
                            db_save.add(ActivityLog(
                                event_type="EFFICIENCY",
                                username=user.get("username", "system"),
                                description=f"req {metrics['request_id']}: " + "; ".join(breaches),
                            ))
                        await db_save.commit()
                except Exception as save_err:
                    logger.error(f"[AI] Failed to persist request timing: {save_err}", exc_info=True)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def _load_doc_context(chat_id: int) -> str:
    """Return a formatted document context block for the given chat, or empty string."""
    from sqlalchemy import select as sa_select
    try:
        async with async_session_maker() as db:
            rows = await db.execute(
                sa_select(Document)
                .where(Document.chat_id == chat_id)
                .order_by(Document.created_at)
            )
            docs = rows.scalars().all()
    except Exception as e:
        logger.error(f"[AI] Failed to load documents for chat {chat_id}: {e}", exc_info=True)
        return ""

    if not docs:
        return ""

    parts = []
    total = 0
    for doc in docs:
        remaining = MAX_TOTAL_DOC_CHARS - total
        if remaining <= 0:
            break
        text = doc.content_text[:remaining]
        parts.append(f"[{doc.filename}]\n{text}")
        total += len(text)

    header = (
        "UPLOADED DOCUMENTS FOR THIS SESSION\n"
        "The following documents were provided by the user. Reference them directly as "
        "primary source material. Extract any relevant statutory references, case names, "
        "dates, or facts and include them in `delegate_research` briefs.\n\n"
    )
    return header + "\n\n---\n\n".join(parts)


async def _load_matter_context(chat_id: int) -> str:
    """Return a formatted matter context block if this chat is assigned to a matter."""
    from sqlalchemy import select as sa_select
    try:
        async with async_session_maker() as db:
            row = await db.execute(sa_select(Chat).where(Chat.id == chat_id))
            chat = row.scalar_one_or_none()
            if chat is None or chat.matter_id is None:
                return ""
            mrow = await db.execute(sa_select(Matter).where(Matter.id == chat.matter_id))
            matter = mrow.scalar_one_or_none()
            if matter is None:
                return ""
    except Exception as e:
        logger.error(f"[AI] Failed to load matter context for chat {chat_id}: {e}", exc_info=True)
        return ""

    parts = [f"Title: {matter.title}"]
    if matter.description:
        parts.append(f"Description: {matter.description}")
    if matter.jurisdiction:
        parts.append(f"Jurisdiction: {matter.jurisdiction.replace('_', ' ').title()}")
    if matter.legislation_type:
        parts.append(f"Legislation type: {matter.legislation_type}")

    header = "MATTER CONTEXT\nThis conversation is part of the following legal matter:\n"
    return header + "\n".join(parts)


async def _watch_disconnect(request: Request, cancel_event: asyncio.Event):
    """Watch for client disconnection and signal cancellation."""
    try:
        while not cancel_event.is_set():
            if await request.is_disconnected():
                logger.info("[AI] Client disconnected, cancelling processing.")
                cancel_event.set()
                return
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


async def _error_stream(msg: str):
    yield f"data: {json.dumps({'type': 'error', 'error': msg})}\n\n"
