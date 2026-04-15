import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..dependencies import create_access_token, get_current_user
from ..models import User

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# --- Pydantic schemas ---

class LoginRequest(BaseModel):
    username: str
    password: str
    rememberMe: Optional[bool] = False


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


class PreferencesRequest(BaseModel):
    dark_mode: bool


class ResetPasswordRequest(BaseModel):
    username: str


# --- Endpoints ---

@router.post("/login")
async def login(
    response: Response,
    creds: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.username == creds.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not bcrypt.verify(creds.password, user.password_hash):
        logger.warning(f"[Auth] Failed login attempt for username: {creds.username!r}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    logger.info(f"[Auth] Successful login: {user.username!r} (role={user.role})")
    token_data = {"sub": user.username, "id": user.id, "role": user.role}
    expires = timedelta(days=30) if creds.rememberMe else timedelta(days=1)
    access_token = create_access_token(data=token_data, expires_delta=expires)

    max_age = 30 * 24 * 60 * 60 if creds.rememberMe else 24 * 60 * 60
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production
        max_age=max_age,
        samesite="lax",
    )

    return {
        "token": access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "dark_mode": user.dark_mode,
        },
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("token")
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_me(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user["id"]))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "role": db_user.role,
            "dark_mode": db_user.dark_mode,
        }
    }


@router.post("/reset-password-request")
async def reset_password_request(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    if user and user.email:
        # Email service will be wired in Phase 7
        logger.info(f"[Auth] Password reset requested for user {user.username!r} — email: {user.email}")

    # Always return success to avoid user enumeration
    return {"message": "If user exists, a password reset email has been sent."}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user["id"]))
    db_user = result.scalar_one_or_none()

    if not bcrypt.verify(body.currentPassword, db_user.password_hash):
        logger.warning(f"[Auth] Failed password change attempt for user id={user['id']}")
        raise HTTPException(status_code=400, detail="Incorrect current password")

    db_user.password_hash = bcrypt.using(rounds=10).hash(body.newPassword)
    await db.commit()
    logger.info(f"[Auth] Password changed for user id={user['id']}")

    return {"message": "Password updated successfully"}


@router.put("/preferences")
async def update_preferences(
    body: PreferencesRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user["id"]))
    db_user = result.scalar_one_or_none()

    db_user.dark_mode = body.dark_mode
    await db.commit()

    return {"message": "Preferences updated"}
