const express = require('express');
const router = express.Router();
const { query } = require('../db');
const { authenticateToken, isAdmin } = require('../middleware/auth');
const { getRelevantExamples } = require('../agent/learning');

// Middleware: Admin only for these routes
router.use(authenticateToken);
router.use(isAdmin);

// GET /api/learning/feedback
// Retrieve all messages that have ratings/comments
router.get('/feedback', async (req, res) => {
    try {
        const result = await query(`
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
        `);
        res.json(result.rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error fetching feedback' });
    }
});

// GET /api/learning/stats
// Aggregate ratings by day for performance monitoring
router.get('/stats', async (req, res) => {
    try {
        const result = await query(`
            SELECT 
                DATE(created_at) as date, 
                AVG(rating) as avg_rating, 
                COUNT(*) as feedback_count 
            FROM messages 
            WHERE rating IS NOT NULL 
            GROUP BY DATE(created_at) 
            ORDER BY date ASC
            LIMIT 30
        `);
        // Note: Postgres DATE returns a Date object. Formatting might be needed on client or server.
        // We'll return it as is and handle in frontend.
        res.json(result.rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error fetching stats' });
    }
});

// POST /api/learning/test
// Test the retrieval logic with a hypothetical query
router.post('/test', async (req, res) => {
    const { query: userQuery } = req.body;
    if (!userQuery) return res.status(400).json({ error: 'Query required' });

    try {
        // We pass req.user.id but arguably the admin wants to see GLOBAL knowledge.
        // The current implementation of getRelevantExamples is global (doesn't filter by user, 
        // it filters by similarity). Wait, looking at learning.js...
        // ... it doesn't use userId in the query. It searches ALL chats. 
        // So passing userId is irrelevant but safe.

        const results = await getRelevantExamples(userQuery);
        res.json(results);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error during retrieval test' });
    }
});

module.exports = router;
