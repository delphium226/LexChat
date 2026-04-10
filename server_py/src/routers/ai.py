import asyncio
import json
import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agent.deep_research import chat_with_deep_research
from ..agent.provider_factory import get_active_provider, get_list_models, get_process_user_request
from ..database import async_session_maker
from ..models import RequestTiming
from ..utils.queue import RequestQueue
from ..utils.stopwatch import TimingCollector

logger = logging.getLogger("app")

router = APIRouter(tags=["AI"])

from ..config import settings

# Global Request Queue
# This limits the number of simultaneous AI generations to prevent crashing the server/Ollama.
request_queue = RequestQueue(concurrency=settings.max_concurrent_requests)


@router.get("/api/models")
async def get_models():
    async with async_session_maker() as db:
        list_models = await get_list_models(db)
    return await list_models()


class ChatRequest(BaseModel):
    messages: List[dict]
    model: str
    num_ctx: Optional[int] = None
    deep_research: Optional[bool] = False


@router.post("/api/chat")
async def chat_endpoint(body: ChatRequest, request: Request):
    """Main chat endpoint with SSE streaming, agent system, and queue."""

    if not body.messages or not body.model:
        return StreamingResponse(
            _error_stream("Missing messages or model"),
            media_type="text/event-stream",
        )

    cancel_event = asyncio.Event()
    t_request = time.perf_counter()
    request_id = uuid.uuid4().hex[:8]
    timing = TimingCollector(request_id)

    async def event_stream():
        # Detect client disconnect
        disconnect_task = asyncio.create_task(_watch_disconnect(request, cancel_event))

        # 2-minute timeout warning
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

                # Get a DB session for provider resolution and learning injection
                async with async_session_maker() as db_session:
                    active_provider = await get_active_provider(db_session)
                    process_user_request = await get_process_user_request(db_session)

                    if body.deep_research:
                        result = await chat_with_deep_research(
                            list(body.messages),
                            body.model,
                            on_chunk,
                            cancel_event,
                            body.num_ctx or 0,
                        )
                    else:
                        result = await process_user_request(
                            list(body.messages),
                            body.model,
                            on_chunk,
                            cancel_event,
                            body.num_ctx or 0,
                            db_session=db_session,
                            timing_collector=timing,
                        )

                    if isinstance(result, dict):
                        result["provider"] = active_provider
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

            while not agent_task.done():
                # Drain event queue
                while not events.empty():
                    try:
                        event = events.get_nowait()
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.QueueEmpty:
                        break

                # Check timeout
                if timeout_task.done() and not warning_sent:
                    warning_sent = True
                    yield f"data: {json.dumps({'type': 'warning', 'message': 'The request is taking longer than usual. Please be patient...'})}\n\n"

                # Small sleep to avoid busy loop
                await asyncio.sleep(0.05)

            # Drain remaining events
            while not events.empty():
                try:
                    event = events.get_nowait()
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.QueueEmpty:
                    break

            # Get final result
            result_message = agent_task.result()

            # Record total and emit timing summary before result
            timing.record_total((time.perf_counter() - t_request) * 1000)
            yield f"data: {json.dumps({'type': 'timing', **timing.to_dict()})}\n\n"

            if result_message:
                yield f"data: {json.dumps({'type': 'result', 'message': result_message})}\n\n"

        except asyncio.CancelledError:
            logger.info("Client closed connection, aborted processing.")
        except ConnectionError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        except Exception as e:
            logger.error(f"Chat Error: {e}")
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

            # Persist timing to DB if we got at least as far as queue entry
            if timing.queue_wait_ms > 0 or timing.llm_calls > 0:
                try:
                    async with async_session_maker() as db_save:
                        row = RequestTiming(**timing.to_dict())
                        db_save.add(row)
                        await db_save.commit()
                except Exception as save_err:
                    logger.error(f"[Timing] Failed to persist request timing: {save_err}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def _watch_disconnect(request: Request, cancel_event: asyncio.Event):
    """Watch for client disconnection and signal cancellation."""
    try:
        while not cancel_event.is_set():
            if await request.is_disconnected():
                logger.info("Client disconnected, cancelling processing.")
                cancel_event.set()
                return
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


async def _error_stream(msg: str):
    yield f"data: {json.dumps({'type': 'error', 'error': msg})}\n\n"
