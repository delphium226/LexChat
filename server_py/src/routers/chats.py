from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Chat, Message

router = APIRouter(prefix="/api/chats", tags=["Chats"])


# --- Pydantic schemas ---

class ChatCreate(BaseModel):
    model: str
    title: Optional[str] = None


class ChatUpdate(BaseModel):
    title: str


class ChatOut(BaseModel):
    id: int
    user_id: int
    title: Optional[str]
    model: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    role: str
    content: str


class RatingUpdate(BaseModel):
    rating: int
    comment: Optional[str] = None


class MessageOut(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    rating: Optional[int] = None
    feedback_comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Helpers ---

async def _get_owned_chat(
    chat_id: int, user_id: int, db: AsyncSession
) -> Chat:
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    chat = result.scalar_one_or_none()
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


# --- Endpoints ---

@router.get("", response_model=List[ChatOut])
async def list_chats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == user["id"])
        .order_by(Chat.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ChatOut)
async def create_chat(
    body: ChatCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_chat = Chat(
        user_id=user["id"],
        title=body.title or "New Chat",
        model=body.model,
    )
    db.add(new_chat)
    await db.commit()
    await db.refresh(new_chat)
    return new_chat


@router.put("/{chat_id}", response_model=ChatOut)
async def update_chat(
    chat_id: int,
    body: ChatUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await _get_owned_chat(chat_id, user["id"], db)
    chat.title = body.title
    await db.commit()
    await db.refresh(chat)
    return chat


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await _get_owned_chat(chat_id, user["id"], db)
    await db.delete(chat)
    await db.commit()
    return {"message": "Chat deleted"}


@router.get("/{chat_id}/messages", response_model=List[MessageOut])
async def get_messages(
    chat_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_chat(chat_id, user["id"], db)
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{chat_id}/messages", response_model=MessageOut)
async def add_message(
    chat_id: int,
    body: MessageCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_chat(chat_id, user["id"], db)
    new_msg = Message(
        chat_id=chat_id,
        role=body.role,
        content=body.content,
    )
    db.add(new_msg)
    await db.commit()
    await db.refresh(new_msg)
    return new_msg


@router.put("/messages/{message_id}/rating", response_model=MessageOut)
async def rate_message(
    message_id: int,
    body: RatingUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    # Verify ownership via join with chats
    result = await db.execute(
        select(Message)
        .join(Chat, Message.chat_id == Chat.id)
        .where(Message.id == message_id, Chat.user_id == user["id"])
    )
    msg = result.scalar_one_or_none()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    msg.rating = body.rating
    msg.feedback_comment = body.comment
    await db.commit()
    await db.refresh(msg)
    return msg
