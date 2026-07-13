from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    no_expiry: bool = False,
):
    """Mint a signed JWT.

    Set ``no_expiry=True`` to omit the ``exp`` claim entirely, producing a token
    that never expires. This is used for federation peer credentials so the bots
    don't need periodic re-wiring. python-jose only validates ``exp`` when the
    claim is present, so such tokens pass ``get_current_user`` indefinitely.
    """
    to_encode = data.copy()
    if not no_expiry:
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

async def get_current_user(request: Request):
    # Check cookie first, then header
    token = request.cookies.get("token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        role: str = payload.get("role")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
            
        return {"id": user_id, "username": username, "role": role}
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_admin_user(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user


async def get_current_db_user(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user's DB row (404 if the account no longer exists)."""
    result = await db.execute(select(User).where(User.id == user["id"]))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
