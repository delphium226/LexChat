import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Chat, Message

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/chats", tags=["Chats"])


# --- Pydantic schemas ---

class ChatCreate(BaseModel):
    model: str
    title: Optional[str] = None
    provider: Optional[str] = None


class ChatUpdate(BaseModel):
    title: str


class ChatOut(BaseModel):
    id: int
    user_id: int
    title: Optional[str]
    model: Optional[str]
    provider: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    role: str
    content: str
    model: Optional[str] = None
    provider: Optional[str] = None
    cost_usd: Optional[float] = None


class RatingUpdate(BaseModel):
    rating: int
    comment: Optional[str] = None


class MessageOut(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    model: Optional[str] = None
    provider: Optional[str] = None
    rating: Optional[int] = None
    feedback_comment: Optional[str] = None
    cost_usd: Optional[float] = None
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
@router.get("/", response_model=List[ChatOut], include_in_schema=False)
async def list_chats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == user["id"])
        .order_by(Chat.created_at.desc())
    )
    chats = result.scalars().all()
    return [
        ChatOut(
            id=c.id, user_id=c.user_id, title=c.title, model=c.model,
            provider=c.provider, created_at=c.created_at
        ) for c in chats
    ]


@router.post("", response_model=ChatOut)
@router.post("/", response_model=ChatOut, include_in_schema=False)
async def create_chat(
    body: ChatCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_chat = Chat(
        user_id=user["id"],
        title=body.title or "New Chat",
        model=body.model,
        provider=body.provider,
    )
    db.add(new_chat)
    await db.commit()
    await db.refresh(new_chat)
    logger.info(f"[Chats] Created chat id={new_chat.id} for user id={user['id']} model={new_chat.model!r}")
    return ChatOut(
        id=new_chat.id, user_id=new_chat.user_id, title=new_chat.title,
        model=new_chat.model, provider=new_chat.provider, created_at=new_chat.created_at
    )


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
    return ChatOut(
        id=chat.id, user_id=chat.user_id, title=chat.title, model=chat.model, created_at=chat.created_at
    )


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await _get_owned_chat(chat_id, user["id"], db)
    await db.delete(chat)
    await db.commit()
    logger.info(f"[Chats] Deleted chat id={chat_id} for user id={user['id']}")
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
    msgs = result.scalars().all()
    return [
        MessageOut(
            id=m.id, chat_id=m.chat_id, role=m.role, content=m.content,
            model=m.model, provider=m.provider,
            rating=m.rating, feedback_comment=m.feedback_comment,
            cost_usd=m.cost_usd, created_at=m.created_at
        ) for m in msgs
    ]


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
        model=body.model,
        provider=body.provider,
        cost_usd=body.cost_usd,
    )
    db.add(new_msg)
    await db.commit()
    await db.refresh(new_msg)
    return MessageOut(
        id=new_msg.id, chat_id=new_msg.chat_id, role=new_msg.role, content=new_msg.content,
        model=new_msg.model, provider=new_msg.provider,
        rating=new_msg.rating, feedback_comment=new_msg.feedback_comment,
        cost_usd=new_msg.cost_usd, created_at=new_msg.created_at
    )


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
    logger.info(f"[Chats] Message id={message_id} rated {body.rating}/5 by user id={user['id']}")
    return MessageOut(
        id=msg.id, chat_id=msg.chat_id, role=msg.role, content=msg.content,
        rating=msg.rating, feedback_comment=msg.feedback_comment, created_at=msg.created_at
    )
