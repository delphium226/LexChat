from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json
from services.ollama import chat_with_ollama, chat_with_deep_research
import asyncio
import logging

logger = logging.getLogger("lexchat.agent")

router = APIRouter()

@router.post("/api/chat") # Root level as per spec
async def chat_stream(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    model = data.get("model")
    num_ctx = data.get("num_ctx", 4096)
    deep_research = data.get("deep_research", False)
    
    if not messages or not model:
        return {"error": "Missing messages or model"}
    
    async def event_generator():
        async def signal_check():
            return await request.is_disconnected()

        if deep_research:
            # We iterate over the generator created by chat_with_deep_research if it yielded messages, 
            # BUT chat_with_deep_research in my implementation does NOT yield directly, it uses on_chunk callback?
            # Wait, the node.js implementation passes a callback `onChunk` and executes. 
            # My python implementation `chat_with_deep_research` effectively mimics `chat_with_ollama` which returns a string result,
            # but we need it to be a generator for StreamingResponse?
            # NO. The Node.js implementation:
            # Writes to `res` in the callback, then sends final result.
            # Here in FastAPI StreamingResponse expects an async generator yielding strings (SSE format).
            
            # So we must create a queue to bridge the callback-based logic to the generator.
            queue = asyncio.Queue()
            
            async def on_chunk(data):
                await queue.put(f"data: {json.dumps(data)}\\n\\n")
            
            # Run the chat task in background
            task = asyncio.create_task(
                chat_with_deep_research(messages, model, on_chunk, signal_check, num_ctx)
            )
            
            try:
                while not task.done():
                    # Wait for items in queue or task completion
                    # We use a timeout to check task status periodically or wait for item
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=0.1)
                        yield item
                        queue.task_done()
                    except asyncio.TimeoutError:
                        continue
                
                # If task finished successfully, get return value (final message)
                if task.exception():
                    raise task.exception()
                    
                final_msg = task.result()
                yield f"data: {json.dumps({'type': 'result', 'message': final_msg})}\\n\\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\\n\\n"

        else:
             # Logic for Normal Chat (Manager)
            queue = asyncio.Queue()
            async def on_chunk(data):
                await queue.put(f"data: {json.dumps(data)}\\n\\n")

            task = asyncio.create_task(
                chat_with_ollama(messages, model, on_chunk, signal_check, num_ctx)
            )

            try:
                while not task.done():
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=0.1)
                        yield item
                        queue.task_done()
                    except asyncio.TimeoutError:
                        continue
                
                if task.exception():
                    raise task.exception()
                    
                final_msg = task.result()
                yield f"data: {json.dumps({'type': 'result', 'message': final_msg})}\\n\\n"

            except Exception as e:
                logger.error(f"Chat Error: {e}")
                # Check for friendly error
                msg = str(e)
                if "Ollama" in msg or "Connect" in msg:
                     msg = "Agent Service (Ollama) is not reachable."
                yield f"data: {json.dumps({'type': 'error', 'error': msg})}\\n\\n"

    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
