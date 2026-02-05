from fastapi import APIRouter, Depends, HTTPException, status, Response
from services.auth import verify_password, create_access_token, get_current_user
from models.auth import UserResponse, LoginRequest, LoginResponse
from database import db
from datetime import timedelta
import logging

logger = logging.getLogger("lexchat.auth")

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, response: Response):
    try:
        user = await db.fetch_one("SELECT * FROM users WHERE username = $1", login_data.username)
        if not user or not verify_password(login_data.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        expires_in = timedelta(days=30) if login_data.remember_me else timedelta(days=1)
        token = create_access_token(
            data={"id": user['id'], "username": user['username'], "role": user['role']},
            expires_delta=expires_in
        )
        
        # Set Cookie
        response.set_cookie(
            key="token",
            value=token,
            httponly=True,
            max_age=int(expires_in.total_seconds()),
            path="/",
            secure=False, # Set True in prod
            samesite="lax"
        )
        
        # Convert to dict for safe get
        user_dict = dict(user)
        
        return LoginResponse(
            token=token,
            user=UserResponse(
                id=user['id'],
                username=user['username'],
                role=user['role'],
                dark_mode=user_dict.get('dark_mode', False)
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("token")
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=dict)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    return {"user": current_user}

# Added Routes for parity with Node.js
from pydantic import BaseModel

class ResetPasswordRequest(BaseModel):
    username: str

@router.post("/reset-password-request")
async def request_password_reset(request: ResetPasswordRequest):
    try:
        user = await db.fetch_one("SELECT email FROM users WHERE username = $1", request.username)
        if user and user['email']:
            from services.email import send_password_reset_email
            # send_password_reset_email(user['email'], request.username, 'mock-token')
            # Warning: Blocking call in async? smtplib is blocking. Should run in threadpool?
            # For low volume, maybe ok. Or best practice:
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, send_password_reset_email, user['email'], request.username, 'mock-token')
            
            logger.info(f"[EMAIL SENT] Password reset email sent to {user['email']} for {request.username}")
        else:
            logger.info(f"[EMAIL SKIP] User {request.username} not found or no email")
            
        return {"message": "If user exists, a password reset email has been sent."}
    except Exception as e:
        logger.error(f"Reset request error: {e}")
        return {"message": "If user exists, a password reset email has been sent."}

class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

@router.post("/change-password")
async def change_password(request: ChangePasswordRequest, user: UserResponse = Depends(get_current_user)):
    try:
        # Verify current - Need to fetch hash mostly, although user object might already have it if we fetched everything in get_current_user?
        # get_current_user implementation fetches everything but returns UserResponse model which might exclude hash.
        # Let's fetch hash again.
        db_user = await db.fetch_one("SELECT password_hash FROM users WHERE id = $1", user.id)
        if not db_user or not verify_password(request.currentPassword, db_user['password_hash']):
            raise HTTPException(status_code=400, detail="Incorrect current password")
            
        from services.auth import get_password_hash
        new_hash = get_password_hash(request.newPassword)
        
        await db.execute("UPDATE users SET password_hash = $1 WHERE id = $2", new_hash, user.id)
        return {"message": "Password updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {e}")
        raise HTTPException(status_code=500, detail="Server error")

class PreferencesRequest(BaseModel):
    dark_mode: bool

@router.put("/preferences")
async def update_preferences(request: PreferencesRequest, user: UserResponse = Depends(get_current_user)):
    try:
        await db.execute("UPDATE users SET dark_mode = $1 WHERE id = $2", request.dark_mode, user.id)
        return {"message": "Preferences updated"}
    except Exception as e:
        logger.error(f"Preferences update error: {e}")
        raise HTTPException(status_code=500, detail="Server error")

