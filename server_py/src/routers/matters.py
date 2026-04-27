import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import AppSetting, Matter, MatterNote

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/matters", tags=["Matters"])

_FEATURES_KEY = "features"


async def _assert_matters_enabled(db: AsyncSession) -> None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == _FEATURES_KEY))
    row = result.scalar_one_or_none()
    if row:
        try:
            features = json.loads(row.value)
            if not features.get("matters_enabled", True):
                raise HTTPException(status_code=403, detail="Matters feature is disabled.")
        except (json.JSONDecodeError, ValueError):
            pass


# --- Pydantic schemas ---

class MatterCreate(BaseModel):
    title: str
    description: Optional[str] = None


class MatterUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class MatterOut(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    status: str
    note_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MatterNoteCreate(BaseModel):
    content: str
    message_id: Optional[int] = None


class MatterNoteOut(BaseModel):
    id: int
    matter_id: int
    content: str
    message_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Helpers ---

async def _get_owned_matter(matter_id: int, user_id: int, db: AsyncSession) -> Matter:
    result = await db.execute(
        select(Matter).where(Matter.id == matter_id, Matter.user_id == user_id)
    )
    matter = result.scalar_one_or_none()
    if matter is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter


# --- Matter endpoints ---

@router.get("", response_model=List[MatterOut])
async def list_matters(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_matters_enabled(db)
    result = await db.execute(
        select(Matter, func.count(MatterNote.id).label("note_count"))
        .outerjoin(MatterNote, MatterNote.matter_id == Matter.id)
        .where(Matter.user_id == user["id"], Matter.status == "open")
        .group_by(Matter.id)
        .order_by(Matter.created_at.desc())
    )
    rows = result.all()
    return [
        MatterOut(
            id=row.Matter.id,
            user_id=row.Matter.user_id,
            title=row.Matter.title,
            description=row.Matter.description,
            status=row.Matter.status,
            note_count=row.note_count,
            created_at=row.Matter.created_at,
            updated_at=row.Matter.updated_at,
        )
        for row in rows
    ]


@router.post("", response_model=MatterOut)
async def create_matter(
    body: MatterCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_matters_enabled(db)
    matter = Matter(
        user_id=user["id"],
        title=body.title.strip(),
        description=body.description,
    )
    db.add(matter)
    await db.commit()
    await db.refresh(matter)
    logger.info(f"[Matters] Created matter id={matter.id} for user id={user['id']}")
    return MatterOut(
        id=matter.id, user_id=matter.user_id, title=matter.title,
        description=matter.description, status=matter.status, note_count=0,
        created_at=matter.created_at, updated_at=matter.updated_at,
    )


@router.put("/{matter_id}", response_model=MatterOut)
async def update_matter(
    matter_id: int,
    body: MatterUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_matters_enabled(db)
    matter = await _get_owned_matter(matter_id, user["id"], db)
    if body.title is not None:
        matter.title = body.title.strip()
    if body.description is not None:
        matter.description = body.description
    if body.status is not None:
        matter.status = body.status
    matter.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(matter)

    note_count_result = await db.execute(
        select(func.count(MatterNote.id)).where(MatterNote.matter_id == matter.id)
    )
    note_count = note_count_result.scalar() or 0

    return MatterOut(
        id=matter.id, user_id=matter.user_id, title=matter.title,
        description=matter.description, status=matter.status, note_count=note_count,
        created_at=matter.created_at, updated_at=matter.updated_at,
    )


@router.delete("/{matter_id}")
async def delete_matter(
    matter_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_matters_enabled(db)
    matter = await _get_owned_matter(matter_id, user["id"], db)
    await db.delete(matter)
    await db.commit()
    logger.info(f"[Matters] Deleted matter id={matter_id} for user id={user['id']}")
    return {"message": "Matter deleted"}


# --- Note endpoints ---

@router.get("/{matter_id}/notes", response_model=List[MatterNoteOut])
async def list_notes(
    matter_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_matters_enabled(db)
    await _get_owned_matter(matter_id, user["id"], db)
    result = await db.execute(
        select(MatterNote)
        .where(MatterNote.matter_id == matter_id)
        .order_by(MatterNote.created_at.asc())
    )
    notes = result.scalars().all()
    return [
        MatterNoteOut(
            id=n.id, matter_id=n.matter_id, content=n.content,
            message_id=n.message_id, created_at=n.created_at,
        )
        for n in notes
    ]


@router.post("/{matter_id}/notes", response_model=MatterNoteOut)
async def add_note(
    matter_id: int,
    body: MatterNoteCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_matters_enabled(db)
    await _get_owned_matter(matter_id, user["id"], db)
    note = MatterNote(
        matter_id=matter_id,
        content=body.content,
        message_id=body.message_id,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    logger.info(f"[Matters] Added note id={note.id} to matter id={matter_id}")
    return MatterNoteOut(
        id=note.id, matter_id=note.matter_id, content=note.content,
        message_id=note.message_id, created_at=note.created_at,
    )


@router.delete("/{matter_id}/notes/{note_id}")
async def delete_note(
    matter_id: int,
    note_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _assert_matters_enabled(db)
    await _get_owned_matter(matter_id, user["id"], db)
    result = await db.execute(
        select(MatterNote).where(MatterNote.id == note_id, MatterNote.matter_id == matter_id)
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await db.commit()
    return {"message": "Note deleted"}
