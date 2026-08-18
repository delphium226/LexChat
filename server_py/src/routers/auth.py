import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..dependencies import create_access_token, get_admin_user, get_current_db_user
from ..models import ActivityLog, User
from ..utils.redact import redact_email

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _request_is_https(request: Request) -> bool:
    """True when the *client* connection is HTTPS.

    Behind nginx uvicorn is spoken to over plain HTTP on 127.0.0.1, so the
    scheme on the ASGI request describes the proxy hop, not the browser's.
    X-Forwarded-Proto carries the real one (set in deployment/nginx/lexchat.conf).
    """
    forwarded = request.headers.get("X-Forwarded-Proto")
    if forwarded:
        return forwarded.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


# --- Pydantic schemas ---

class LoginRequest(BaseModel):
    username: str
    password: str
    rememberMe: Optional[bool] = False


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


class PreferencesRequest(BaseModel):
    dark_mode: Optional[bool] = None
    research_mode: Optional[str] = None
    chat_mode: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    username: str


# --- Response schemas ---

class AuthUser(BaseModel):
    id: int
    username: str
    role: str
    dark_mode: Optional[bool] = None
    research_mode: Optional[str] = None
    chat_mode: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: AuthUser


class UserWrapper(BaseModel):
    user: AuthUser


class MessageResponse(BaseModel):
    message: str


# --- Endpoints ---

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
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
    try:
        db.add(ActivityLog(event_type="LOGIN", username=user.username))
        await db.commit()
    except Exception:
        logger.warning("[Auth] Failed to write login activity log")

    token_data = {"sub": user.username, "id": user.id, "role": user.role}
    expires = timedelta(days=30) if creds.rememberMe else timedelta(days=7)
    access_token = create_access_token(data=token_data, expires_delta=expires)

    max_age = 30 * 24 * 60 * 60 if creds.rememberMe else 7 * 24 * 60 * 60
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,
        # Secure on HTTPS, not on plain HTTP. This MUST track the actual
        # scheme: the browser silently discards a Secure cookie served over
        # http://, and the frontend has no bearer-token fallback (it never
        # sends an Authorization header — get_current_user's header branch is
        # for machine callers only). A hardcoded secure=True therefore made
        # login a no-op on every plain-HTTP deployment: the POST returned 200,
        # no cookie was stored, and the next request 401'd into "your session
        # has expired". Only visible to a browser with an empty cookie jar,
        # so pre-existing sessions masked it.
        secure=_request_is_https(request),
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
            "research_mode": user.research_mode,
            "chat_mode": user.chat_mode,
        },
    }


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    response.delete_cookie("token")
    return {"message": "Logged out successfully"}


@router.post("/federation-token")
async def federation_token(admin: dict = Depends(get_admin_user)):
    """Mint a non-expiring admin token for use as a federation peer credential.

    Admin-only. The returned token has no ``exp`` claim, so it never needs
    re-issuing — peers registered with it stay wired up indefinitely.
    """
    token_data = {
        "sub": admin["username"],
        "id": admin["id"],
        "role": admin["role"],
        "scope": "federation",
    }
    token = create_access_token(data=token_data, no_expiry=True)
    logger.info(f"[Auth] Minted non-expiring federation token for {admin['username']!r}")
    return {"token": token}


@router.get("/me", response_model=UserWrapper)
async def get_me(
    db_user: User = Depends(get_current_db_user),
):
    return {
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "role": db_user.role,
            "dark_mode": db_user.dark_mode,
            "research_mode": db_user.research_mode,
            "chat_mode": db_user.chat_mode,
        }
    }


@router.post("/reset-password-request", response_model=MessageResponse)
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
        logger.info(
            f"[Auth] Password reset requested for user {user.username!r} "
            f"— email: {redact_email(user.email)}"
        )

    # Always return success to avoid user enumeration
    return {"message": "If user exists, a password reset email has been sent."}


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    db_user: User = Depends(get_current_db_user),
    db: AsyncSession = Depends(get_db),
):
    if not bcrypt.verify(body.currentPassword, db_user.password_hash):
        logger.warning(f"[Auth] Failed password change attempt for user id={db_user.id}")
        raise HTTPException(status_code=400, detail="Incorrect current password")

    db_user.password_hash = bcrypt.using(rounds=10).hash(body.newPassword)
    await db.commit()
    logger.info(f"[Auth] Password changed for user id={db_user.id}")

    return {"message": "Password updated successfully"}


@router.put("/preferences", response_model=MessageResponse)
async def update_preferences(
    body: PreferencesRequest,
    db_user: User = Depends(get_current_db_user),
    db: AsyncSession = Depends(get_db),
):
    if body.dark_mode is not None:
        db_user.dark_mode = body.dark_mode
    if body.research_mode is not None:
        db_user.research_mode = body.research_mode
    if body.chat_mode is not None:
        db_user.chat_mode = body.chat_mode
    await db.commit()

    return {"message": "Preferences updated"}
