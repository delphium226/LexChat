import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_admin_user
from ..models import User

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/users", tags=["Users"])


# --- Pydantic schemas ---

class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"
    email: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    email: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.get("", response_model=List[UserOut])
async def list_users(
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(User.id)
    )
    users = result.scalars().all()
    return [
        UserOut(
            id=u.id,
            username=u.username,
            role=u.role,
            email=u.email,
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    # Check for duplicates
    existing = await db.execute(
        select(User).where(
            (User.username == body.username)
            | ((User.email == body.email) & (body.email != None))  # noqa: E711
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already exists")

    hashed = bcrypt.using(rounds=10).hash(body.password)
    new_user = User(
        username=body.username,
        password_hash=hashed,
        role=body.role or "user",
        email=body.email,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Email service will be wired in Phase 7
    if body.email:
        logger.info(f"[EMAIL] Welcome email would be sent to {body.email}")

    return UserOut(
        id=new_user.id,
        username=new_user.username,
        role=new_user.role,
        email=new_user.email,
    )


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.username is not None:
        db_user.username = body.username
    if body.role is not None:
        db_user.role = body.role
    if body.email is not None:
        db_user.email = body.email
    if body.password and body.password.strip():
        db_user.password_hash = bcrypt.using(rounds=10).hash(body.password)

    try:
        await db.commit()
        await db.refresh(db_user)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Username or email already exists")

    return UserOut(
        id=db_user.id,
        username=db_user.username,
        role=db_user.role,
        email=db_user.email,
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    admin: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    # Prevent deleting self
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()

    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deleting main admin
    if db_user.username == "admin":
        raise HTTPException(status_code=403, detail="Cannot delete the main admin account")

    await db.delete(db_user)
    await db.commit()

    return {"message": "User deleted"}
