import asyncio
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agent.ollama_client import process_user_request
from ..database import async_session_maker
from ..utils.queue import RequestQueue
from ..config import settings

logger = logging.getLogger("app")

router = APIRouter(tags=["System"])

# We can reuse the same queue or a separate one. For now, sharing the global queue seems safe to prevent overload.
request_queue = RequestQueue(concurrency=settings.max_concurrent_requests)

class SystemChatRequest(BaseModel):
    messages: List[dict]
    model: str
    num_ctx: Optional[int] = None
    # We could add more options here if needed for system systems

@router.post("/api/system/chat")
async def system_chat_endpoint(body: SystemChatRequest, request: Request):
    """
    System-to-system chat endpoint.
    Relays all detailed events (thinking, tool calls, results) to the caller.
    """

    if not body.messages or not body.model:
        raise HTTPException(status_code=400, detail="Missing messages or model")

    cancel_event = asyncio.Event()

    async def event_stream():
        # Detect client disconnect
        disconnect_task = asyncio.create_task(_watch_disconnect(request, cancel_event))
        
        try:
            # Collect SSE events via callback
            events = asyncio.Queue()

            def on_chunk(data):
                events.put_nowait(data)

            async def run_agent_task():
                # Get a DB session for learning injection
                async with async_session_maker() as db_session:
                    return await process_user_request(
                        list(body.messages),
                        body.model,
                        on_chunk,
                        cancel_event,
                        body.num_ctx or 0,
                        db_session=db_session,
                        emit_tool_details=True  # ENABLE DETAILED EVENTS
                    )

            # Execution logic similar to ai.py but simplified (no queue waiting events needed for system? 
            # Actually, system might want to know it's queued. Let's keep it.)
            
            def on_queue_waiting(position):
                events.put_nowait({"type": "queue", "position": position})

            task = asyncio.create_task(
                request_queue.enqueue(run_agent_task, on_waiting=on_queue_waiting)
            )

            while not task.done():
                while not events.empty():
                    try:
                        event = events.get_nowait()
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.QueueEmpty:
                        break
                
                await asyncio.sleep(0.05)

            # Drain
            while not events.empty():
                 try:
                    event = events.get_nowait()
                    yield f"data: {json.dumps(event)}\n\n"
                 except asyncio.QueueEmpty:
                    break
            
            # Result
            result_message = task.result()
            if result_message:
                yield f"data: {json.dumps({'type': 'result', 'message': result_message})}\n\n"

        except asyncio.CancelledError:
            logger.info("System client disconnected.")
        except Exception as e:
            logger.error(f"System Chat Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
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
    try:
        while not cancel_event.is_set():
            if await request.is_disconnected():
                cancel_event.set()
                return
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
