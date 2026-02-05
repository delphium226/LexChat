from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from typing import List
from models.auth import UserResponse
from models.chat import Chat, CreateChatRequest, UpdateChatRequest, Message, CreateMessageRequest
from services.auth import get_current_user
from database import db
import json
import logging

logger = logging.getLogger("lexchat.chats")
router = APIRouter(prefix="/api/chats", tags=["Chats"])

@router.get("", response_model=List[Chat])
async def list_chats(user: UserResponse = Depends(get_current_user)):
    try:
        rows = await db.fetch_all("SELECT * FROM chats WHERE user_id = $1 ORDER BY created_at DESC", user.id)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"List Chats Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=Chat)
async def create_chat(request: CreateChatRequest, user: UserResponse = Depends(get_current_user)):
    try:
        row = await db.fetch_one(
            "INSERT INTO chats (user_id, title, model) VALUES ($1, $2, $3) RETURNING *",
            user.id, request.title or "New Chat", request.model
        )
        return dict(row)
    except Exception as e:
        logger.error(f"Create Chat Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{chat_id}", response_model=Chat)
async def update_chat(chat_id: int, request: UpdateChatRequest, user: UserResponse = Depends(get_current_user)):
    try:
        existing = await db.fetch_one("SELECT * FROM chats WHERE id = $1 AND user_id = $2", chat_id, user.id)
        if not existing:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        row = await db.fetch_one(
            "UPDATE chats SET title = $1 WHERE id = $2 RETURNING *",
            request.title, chat_id
        )
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update Chat Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{chat_id}")
async def delete_chat(chat_id: int, user: UserResponse = Depends(get_current_user)):
    try:
        result = await db.execute("DELETE FROM chats WHERE id = $1 AND user_id = $2", chat_id, user.id)
        return {"message": "Chat deleted"}
    except Exception as e:
        logger.error(f"Delete Chat Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{chat_id}/messages", response_model=List[Message])
async def get_messages(chat_id: int, user: UserResponse = Depends(get_current_user)):
    try:
        existing = await db.fetch_one("SELECT * FROM chats WHERE id = $1 AND user_id = $2", chat_id, user.id)
        if not existing:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        rows = await db.fetch_all("SELECT * FROM messages WHERE chat_id = $1 ORDER BY created_at ASC", chat_id)
        return [dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get Messages Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{chat_id}/messages", response_model=Message)
async def add_message_to_history(chat_id: int, request: CreateMessageRequest, user: UserResponse = Depends(get_current_user)):
    try:
        # Check chat ownership
        existing = await db.fetch_one("SELECT * FROM chats WHERE id = $1 AND user_id = $2", chat_id, user.id)
        if not existing:
             raise HTTPException(status_code=404, detail="Chat not found")

        row = await db.fetch_one(
            "INSERT INTO messages (chat_id, role, content) VALUES ($1, $2, $3) RETURNING *",
            chat_id, request.role, request.content
        )
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add Message Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Root level /api/chat endpoint from logic
# It needs to handle streaming and "Deep Research"
# We'll put it here or in a separate agent route
