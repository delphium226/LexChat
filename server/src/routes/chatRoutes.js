const express = require('express');
const router = express.Router();
const { query } = require('../db');
const { authenticateToken } = require('../middleware/auth');

router.use(authenticateToken);

// Get all chats for the user
router.get('/', async (req, res) => {
    try {
        const result = await query(
            'SELECT * FROM chats WHERE user_id = $1 ORDER BY created_at DESC',
            [req.user.id]
        );
        res.json(result.rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// Create a new chat
router.post('/', async (req, res) => {
    const { title, model } = req.body;
    try {
        const result = await query(
            'INSERT INTO chats (user_id, title, model) VALUES ($1, $2, $3) RETURNING *',
            [req.user.id, title || 'New Chat', model]
        );
        res.json(result.rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// Update chat (title)
router.put('/:id', async (req, res) => {
    const { title } = req.body;
    const { id } = req.params;
    try {
        // Verify ownership
        const check = await query('SELECT * FROM chats WHERE id = $1 AND user_id = $2', [id, req.user.id]);
        if (check.rows.length === 0) return res.status(404).json({ error: 'Chat not found' });

        const result = await query(
            'UPDATE chats SET title = $1 WHERE id = $2 RETURNING *',
            [title, id]
        );
        res.json(result.rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// Delete a chat
router.delete('/:id', async (req, res) => {
    const { id } = req.params;
    try {
        // Verify ownership
        const check = await query('SELECT * FROM chats WHERE id = $1 AND user_id = $2', [id, req.user.id]);
        if (check.rows.length === 0) return res.status(404).json({ error: 'Chat not found' });

        await query('DELETE FROM chats WHERE id = $1', [id]);
        res.json({ message: 'Chat deleted' });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// Get messages for a chat
router.get('/:id/messages', async (req, res) => {
    const { id } = req.params;
    try {
        // Verify ownership
        const check = await query('SELECT * FROM chats WHERE id = $1 AND user_id = $2', [id, req.user.id]);
        if (check.rows.length === 0) return res.status(404).json({ error: 'Chat not found' });

        const result = await query(
            'SELECT * FROM messages WHERE chat_id = $1 ORDER BY created_at ASC',
            [id]
        );
        res.json(result.rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// Add a message to a chat
router.post('/:id/messages', async (req, res) => {
    const { id } = req.params;
    const { role, content } = req.body;
    try {
        // Verify ownership
        const check = await query('SELECT * FROM chats WHERE id = $1 AND user_id = $2', [id, req.user.id]);
        if (check.rows.length === 0) return res.status(404).json({ error: 'Chat not found' });

        const result = await query(
            'INSERT INTO messages (chat_id, role, content) VALUES ($1, $2, $3) RETURNING *',
            [id, role, content]
        );
        res.json(result.rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// Rate a message
router.put('/messages/:id/rating', async (req, res) => {
    const { id } = req.params;
    const { rating, comment } = req.body;
    try {
        // Validation
        if (rating < 1 || rating > 5) return res.status(400).json({ error: 'Rating must be between 1 and 5' });

        // Verify ownership (join with chats)
        const check = await query(`
            SELECT m.* FROM messages m
            JOIN chats c ON m.chat_id = c.id
            WHERE m.id = $1 AND c.user_id = $2
        `, [id, req.user.id]);

        if (check.rows.length === 0) return res.status(404).json({ error: 'Message not found' });

        const result = await query(
            'UPDATE messages SET rating = $1, feedback_comment = $2 WHERE id = $3 RETURNING *',
            [rating, comment || null, id]
        );
        res.json(result.rows[0]);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

module.exports = router;
