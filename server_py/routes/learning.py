from fastapi import APIRouter, HTTPException, Request, Depends
from services.auth import get_current_user
from services.learning import get_relevant_examples
from database import db
from models.auth import UserResponse
import logging

logger = logging.getLogger("lexchat.learning_routes")
router = APIRouter(prefix="/api/learning", tags=["Learning"])

@router.get("/feedback")
async def get_feedback(user: UserResponse = Depends(get_current_user)):
    # Admin check? Node.js had isAdmin middleware. 
    # For now we allow any authenticated user or check role.
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
        
    try:
        query = """
            SELECT 
                m.id, 
                m.content as assistant_response, 
                m.rating, 
                m.feedback_comment, 
                m.created_at, 
                c.title as chat_title, 
                u.username
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            JOIN users u ON c.user_id = u.id
            WHERE m.rating IS NOT NULL
            ORDER BY m.created_at DESC
            LIMIT 100
        """
        rows = await db.fetch_all(query)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching feedback: {e}")
        raise HTTPException(status_code=500, detail="Server error fetching feedback")

@router.get("/stats")
async def get_stats(days: str = '30', user: UserResponse = Depends(get_current_user)):
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        date_filter = ""
        if days != 'all':
            days_num = int(days)
            date_filter = f"AND m.created_at > NOW() - INTERVAL '{days_num} days'"
            
        query = f"""
            SELECT 
                DATE(m.created_at) as date, 
                c.model,
                AVG(m.rating) as avg_rating, 
                COUNT(*) as feedback_count 
            FROM messages m
            JOIN chats c ON m.chat_id = c.id
            WHERE m.rating IS NOT NULL 
            {date_filter}
            GROUP BY DATE(m.created_at), c.model
            ORDER BY date ASC
        """
        rows = await db.fetch_all(query)
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Server error fetching stats")

@router.post("/test")
async def test_retrieval(request: Request, user: UserResponse = Depends(get_current_user)):
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
        
    data = await request.json()
    query = data.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Query required")
        
    try:
        results = await get_relevant_examples(query)
        return results
    except Exception as e:
        logger.error(f"Error testing retrieval: {e}")
        raise HTTPException(status_code=500, detail=str(e))
