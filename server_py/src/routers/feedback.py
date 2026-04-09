from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import ProductFeedback, User

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])


class FeedbackCreate(BaseModel):
    message: str


class FeedbackOut(BaseModel):
    id: int
    username: str
    message: str
    created_at: str


@router.post("", status_code=201)
async def submit_feedback(
    body: FeedbackCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Feedback message cannot be empty.")
    entry = ProductFeedback(user_id=user["id"], message=body.message.strip())
    db.add(entry)
    await db.commit()
    return {"status": "ok"}


@router.get("", response_model=list[FeedbackOut])
async def get_all_feedback(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    result = await db.execute(
        select(ProductFeedback, User.username)
        .join(User, ProductFeedback.user_id == User.id)
        .order_by(desc(ProductFeedback.created_at))
    )
    rows = result.all()
    return [
        FeedbackOut(
            id=fb.id,
            username=username,
            message=fb.message,
            created_at=fb.created_at.isoformat(),
        )
        for fb, username in rows
    ]
