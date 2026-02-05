from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from models.auth import UserResponse
from services.auth import get_current_user, get_password_hash
from database import db

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("", response_model=List[UserResponse])
async def list_users(current_user: UserResponse = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    users = await db.fetch_all("SELECT * FROM users")
    # Convert records to dicts for Pydantic safe parsing if needed, but simple fields might work
    return [dict(u) for u in users]

@router.post("", response_model=UserResponse)
async def create_user(user_data: dict, current_user: UserResponse = Depends(get_current_user)):
    # Simple creation for admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    existing = await db.fetch_one("SELECT * FROM users WHERE username = $1", user_data['username'])
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
        
    hashed_pw = get_password_hash(user_data['password'])
    row = await db.fetch_one(
        "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, $3) RETURNING *",
        user_data['username'], hashed_pw, user_data.get('role', 'user')
    )
    return dict(row)

@router.delete("/{user_id}")
async def delete_user(user_id: int, current_user: UserResponse = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    await db.execute("DELETE FROM users WHERE id = $1", user_id)
    return {"message": "User deleted"}
