import asyncio
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agent.deep_research import chat_with_deep_research
from ..agent.ollama_client import list_models, process_user_request
from ..database import async_session_maker
from ..utils.queue import RequestQueue

logger = logging.getLogger("app")

router = APIRouter(tags=["AI"])

from ..config import settings

# Global Request Queue
# This limits the number of simultaneous AI generations to prevent crashing the server/Ollama.
request_queue = RequestQueue(concurrency=settings.max_concurrent_requests)


@router.get("/api/models")
async def get_models():
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

            async def run_agent_task():
                # Get a DB session for learning injection
                async with async_session_maker() as db_session:
                    if body.deep_research:
                        return await chat_with_deep_research(
                            list(body.messages),
                            body.model,
                            on_chunk,
                            cancel_event,
                            body.num_ctx or 0,
                        )
                    else:
                        return await process_user_request(
                            list(body.messages),
                            body.model,
                            on_chunk,
                            cancel_event,
                            body.num_ctx or 0,
                            db_session=db_session,
                        )

            # Callback for queue updates
            def on_queue_waiting(position):
                events.put_nowait({"type": "queue", "position": position})

            # EXECUTE THROUGH QUEUE
            # This will block until a slot is available
            agent_task = asyncio.create_task(
                request_queue.enqueue(run_agent_task, on_waiting=on_queue_waiting)
            )

            # Timeout warning task
            timeout_task = asyncio.create_task(asyncio.sleep(120))

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
