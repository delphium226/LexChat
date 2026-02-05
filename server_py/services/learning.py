import re
from database import db
import logging

logger = logging.getLogger("lexchat.learning")

def extract_keywords(text: str) -> str:
    stop_words = {'the', 'is', 'at', 'which', 'on', 'in', 'a', 'an', 'and', 'or', 'to', 'of', 'for', 'with'}
    # Remove punctuation and split
    words = re.sub(r'[^\w\s]', '', text.lower()).split()
    # Filter
    filtered = [w for w in words if len(w) > 3 and w not in stop_words]
    return ' | '.join(filtered)

async def get_relevant_examples(user_query: str):
    try:
        keywords = extract_keywords(user_query)
        if not keywords:
            return {"examples": [], "critiques": []}
            
        logger.info(f"Searching for examples with keywords: {keywords}")
        
        # 1. Positive Examples (Rating >= 4)
        positive_query = """
            WITH relevant_chats AS (
                SELECT 
                    m1.chat_id, 
                    m1.created_at as question_time,
                    m1.content as question,
                    m2.content as answer,
                    m2.rating,
                    m2.feedback_comment
                FROM messages m1
                JOIN messages m2 ON m1.chat_id = m2.chat_id 
                    AND m2.id > m1.id 
                    AND m2.role = 'assistant'
                WHERE m1.role = 'user'
                  AND to_tsvector('english', m1.content) @@ to_tsquery('english', $1)
                  AND m2.rating >= 4
                ORDER BY m2.rating DESC, m2.created_at DESC
                LIMIT 3
            )
            SELECT * FROM relevant_chats;
        """
        
        positive_rows = await db.fetch_all(positive_query, keywords)
        
        # 2. Critiques (Rating <= 3)
        negative_query = """
            WITH relevant_critiques AS (
                SELECT 
                    m1.content as question,
                    m2.rating,
                    m2.feedback_comment
                FROM messages m1
                JOIN messages m2 ON m1.chat_id = m2.chat_id 
                    AND m2.id > m1.id 
                    AND m2.role = 'assistant'
                WHERE m1.role = 'user'
                  AND to_tsvector('english', m1.content) @@ to_tsquery('english', $1)
                  AND m2.rating <= 3
                  AND m2.feedback_comment IS NOT NULL
                  AND LENGTH(m2.feedback_comment) > 0
                ORDER BY m2.created_at DESC
                LIMIT 3
            )
            SELECT * FROM relevant_critiques;
        """
        
        negative_rows = await db.fetch_all(negative_query, keywords)
        
        return {
            "examples": [dict(row) for row in positive_rows],
            "critiques": [dict(row) for row in negative_rows]
        }
        
    except Exception as e:
        logger.error(f"Error fetching examples: {e}")
        return {"examples": [], "critiques": []}
