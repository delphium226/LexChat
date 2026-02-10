import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("agent")

# Basic stop words for keyword extraction
_STOP_WORDS = frozenset({
    "the", "is", "at", "which", "on", "in", "a", "an", "and", "or",
    "to", "of", "for", "with", "what", "how", "does", "can", "about",
})


def extract_keywords(user_text: str) -> str:
    """Extract keywords from text for PostgreSQL tsquery.

    Removes punctuation, filters stop words and short words,
    joins with ' | ' for OR-combined full-text search.
    """
    import re

    cleaned = re.sub(r"[^\w\s]", "", user_text.lower())
    words = [
        w for w in cleaned.split()
        if len(w) > 3 and w not in _STOP_WORDS
    ]
    return " | ".join(words)


async def get_relevant_examples(
    user_query: str, db: AsyncSession
) -> dict:
    """Retrieve positive examples and critiques via PostgreSQL full-text search.

    Returns:
        {"examples": [...], "critiques": [...]}
    """
    try:
        keywords = extract_keywords(user_query)
        if not keywords:
            return {"examples": [], "critiques": []}

        logger.info(f"[Learning] Searching with keywords: {keywords}")

        # Positive examples (rating >= 4)
        positive_sql = text("""
            WITH relevant_chats AS (
                SELECT
                    m1.chat_id,
                    m1.created_at AS question_time,
                    m1.content AS question,
                    m2.content AS answer,
                    m2.rating,
                    m2.feedback_comment
                FROM messages m1
                JOIN messages m2 ON m1.chat_id = m2.chat_id
                    AND m2.id > m1.id
                    AND m2.role = 'assistant'
                WHERE m1.role = 'user'
                  AND to_tsvector('english', m1.content) @@ to_tsquery('english', :keywords)
                  AND m2.rating >= 4
                ORDER BY m2.rating DESC, m2.created_at DESC
                LIMIT 3
            )
            SELECT * FROM relevant_chats;
        """)
        pos_result = await db.execute(positive_sql, {"keywords": keywords})
        examples = [dict(row._mapping) for row in pos_result]

        # Critiques (rating <= 3 with comment)
        negative_sql = text("""
            WITH relevant_critiques AS (
                SELECT
                    m1.content AS question,
                    m2.rating,
                    m2.feedback_comment
                FROM messages m1
                JOIN messages m2 ON m1.chat_id = m2.chat_id
                    AND m2.id > m1.id
                    AND m2.role = 'assistant'
                WHERE m1.role = 'user'
                  AND to_tsvector('english', m1.content) @@ to_tsquery('english', :keywords)
                  AND m2.rating <= 3
                  AND m2.feedback_comment IS NOT NULL
                  AND LENGTH(m2.feedback_comment) > 0
                ORDER BY m2.created_at DESC
                LIMIT 3
            )
            SELECT * FROM relevant_critiques;
        """)
        neg_result = await db.execute(negative_sql, {"keywords": keywords})
        critiques = [dict(row._mapping) for row in neg_result]

        return {"examples": examples, "critiques": critiques}

    except Exception as e:
        logger.error(f"[Learning] Error fetching examples: {e}")
        return {"examples": [], "critiques": []}


def format_learning_context(learning_data: dict) -> str:
    """Format retrieved examples/critiques into a system prompt injection string."""
    context = ""

    critiques = learning_data.get("critiques", [])
    if critiques:
        context += "\n### CRITICAL FEEDBACK FROM PAST INTERACTIONS\n"
        context += "Users have previously critiqued responses on this topic. AVOID these mistakes:\n"
        for c in critiques:
            question_preview = str(c.get("question", ""))[:50]
            comment = c.get("feedback_comment", "")
            context += f'- User Critique: "{comment}" (for query: "{question_preview}...")\n'
        context += "\n"

    examples = learning_data.get("examples", [])
    if examples:
        context += "\n### SUCCESSFUL EXAMPLES (Few-Shot Learning)\n"
        context += "Here are examples of responses that users rated highly for similar queries. Emulate their style and depth:\n\n"
        for i, ex in enumerate(examples):
            context += f"Example {i + 1}:\n"
            context += f"User: {ex.get('question', '')}\n"
            context += f"Assistant: {ex.get('answer', '')}\n"
            if ex.get("feedback_comment"):
                context += f'(User Note: "{ex["feedback_comment"]}")\n'
            context += "\n---\n"

    return context
