const { query } = require('../db');
const { agentLogger } = require('../utils/logger');

/**
 * Basic keyword extraction for similarity search.
 * In a real production system, this should use vector embeddings (pgvector).
 * For now, we'll use Postgres text search (tsquery).
 */
const extractKeywords = (text) => {
    // Remove common stop words (very basic list)
    const stopWords = new Set(['the', 'is', 'at', 'which', 'on', 'in', 'a', 'an', 'and', 'or', 'to', 'of', 'for', 'with']);
    return text.toLowerCase()
        .replace(/[^\w\s]/g, '') // Remove punctuation
        .split(/\s+/)
        .filter(w => w.length > 3 && !stopWords.has(w))
        .join(' | '); // 'OR' combined for broader matching
};

/**
 * Retrieval Augmented Generation (RAG) for Learning
 * Fetches "Good Examples" (Rating >= 4) and "Past Critiques" (Rating <= 3 with comments).
 */
const getRelevantExamples = async (userQuery, currentUserId) => {
    try {
        const keywords = extractKeywords(userQuery);
        if (!keywords) return { examples: [], critiques: [] };

        agentLogger.info(`[Learning] Searching for examples with keywords: ${keywords}`);

        // 1. Get Positive Examples (Rating >= 4)
        // matches user messages with keywords, then joins with the NEXT message (assistant)
        const positiveQuery = `
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
        `;

        const positiveResult = await query(positiveQuery, [keywords]);

        // 2. Get Critiques (Rating <= 3 AND has comment)
        // We warn the model about what NOT to do based on user feedback
        const negativeQuery = `
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
        `;

        const negativeResult = await query(negativeQuery, [keywords]);

        return {
            examples: positiveResult.rows,
            critiques: negativeResult.rows
        };

    } catch (err) {
        agentLogger.error(`[Learning] Error fetching examples: ${err.message}`);
        return { examples: [], critiques: [] };
    }
};

/**
 * Format retrieved data into a System Prompt injection string
 */
const formatLearningContext = (learningData) => {
    let contextString = '';

    // Add Critiques (Warnings)
    if (learningData.critiques && learningData.critiques.length > 0) {
        contextString += `\n### CRITICAL FEEDBACK FROM PAST INTERACTIONS\n`;
        contextString += `Users have previously critiqued responses on this topic. AVOID these mistakes:\n`;
        learningData.critiques.forEach(c => {
            contextString += `- User Critique: "${c.feedback_comment}" (for query: "${c.question.substring(0, 50)}...")\n`;
        });
        contextString += `\n`;
    }

    // Add Positive Examples (Few-Shot)
    if (learningData.examples && learningData.examples.length > 0) {
        contextString += `\n### SUCCESSFUL EXAMPLES (Few-Shot Learning)\n`;
        contextString += `Here are examples of responses that users rated highly for similar queries. Emulate their style and depth:\n\n`;
        learningData.examples.forEach((ex, i) => {
            contextString += `Example ${i + 1}:\n`;
            contextString += `User: ${ex.question}\n`;
            contextString += `Assistant: ${ex.answer}\n`;
            if (ex.feedback_comment) {
                contextString += `(User Note: "${ex.feedback_comment}")\n`;
            }
            contextString += `\n---\n`;
        });
    }

    return contextString;
};

module.exports = {
    getRelevantExamples,
    formatLearningContext
};
