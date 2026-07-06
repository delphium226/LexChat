import asyncio
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agent.provider_factory import (
    get_active_provider,
    get_provider_config,
    get_process_user_request_from_context,
    get_request_queue,
    set_request_provider_config,
)
from ..database import async_session_maker
from ..dependencies import get_current_user

logger = logging.getLogger("app")

router = APIRouter(tags=["System"])

class SystemChatRequest(BaseModel):
    messages: List[dict]
    model: str
    num_ctx: Optional[int] = None
    # We could add more options here if needed for system systems

@router.post("/api/system/chat")
async def system_chat_endpoint(body: SystemChatRequest, request: Request, user: dict = Depends(get_current_user)):
    """
    System-to-system chat endpoint.
    Relays all detailed events (thinking, tool calls, results) to the caller.
    """

    if not body.messages or not body.model:
        raise HTTPException(status_code=400, detail="Missing messages or model")

    cancel_event = asyncio.Event()

    async def event_stream():
        # get_active_provider re-raises on DB error; emit a clean SSE error event
        # rather than letting the exception break the stream before the try block.
        try:
            async with async_session_maker() as _cfg_db:
                active_provider = await get_active_provider(_cfg_db)
                provider_config = await get_provider_config(_cfg_db, active_provider)
        except Exception as e:
            logger.error(f"[System] Provider resolution failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': 'Service temporarily unavailable. Please try again.'})}\n\n"
            return

        set_request_provider_config({
            **provider_config,
            "_provider": active_provider,
        })
        resolved_model = provider_config.get("model") or body.model
        request_queue = get_request_queue(
            active_provider, provider_config["max_concurrent_requests"]
        )

        # Detect client disconnect
        disconnect_task = asyncio.create_task(_watch_disconnect(request, cancel_event))

        try:
            # Collect SSE events via callback
            events = asyncio.Queue()

            def on_chunk(data):
                events.put_nowait(data)

            async def run_agent_task():
                process_user_request = get_process_user_request_from_context()
                async with async_session_maker() as db_session:
                    return await process_user_request(
                        list(body.messages),
                        resolved_model,
                        on_chunk,
                        cancel_event,
                        body.num_ctx or 0,
                        db_session=db_session,
                        emit_tool_details=True,
                    )

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
            logger.info("[System] Client disconnected.")
        except Exception as e:
            logger.error(f"[System] Chat error: {e}")
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
