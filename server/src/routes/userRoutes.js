const express = require('express');
const bcrypt = require('bcryptjs');
const { query } = require('../db');
const { authenticateToken, isAdmin } = require('../middleware/auth');

const router = express.Router();

router.use(authenticateToken);
router.use(isAdmin);

router.get('/', async (req, res) => {
    try {
        const result = await query('SELECT id, username, email, role, created_at FROM users ORDER BY id');
        res.json(result.rows);
    } catch (error) {
        res.status(500).json({ message: 'Server error' });
    }
});

const { sendWelcomeEmail } = require('../services/emailService');

router.post('/', async (req, res) => {
    const { username, password, role, email } = req.body;

    // Basic validation
    if (!username || !password) {
        return res.status(400).json({ message: 'Username and password are required' });
    }

    try {
        const hashedPassword = await bcrypt.hash(password, 10);
        const result = await query(
            'INSERT INTO users (username, password_hash, role, email) VALUES ($1, $2, $3, $4) RETURNING id, username, role, email',
            [username, hashedPassword, role || 'user', email]
        );

        const newUser = result.rows[0];

        // Send welcome email if email is present
        if (email) {
            sendWelcomeEmail(email, username, password);
        }

        res.status(201).json(newUser);
    } catch (error) {
        if (error.code === '23505') { // Unique constraint violation
            return res.status(400).json({ message: 'Username or email already exists' });
        }
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
});

router.delete('/:id', async (req, res) => {
    const { id } = req.params;
    try {
        // Prevent deleting self?
        if (parseInt(id) === req.user.id) {
            return res.status(400).json({ message: 'Cannot delete your own account' });
        }

        // Check if target is admin
        const targetUser = await query('SELECT username FROM users WHERE id = $1', [id]);
        if (targetUser.rows.length > 0 && targetUser.rows[0].username === 'admin') {
            return res.status(403).json({ message: 'Cannot delete the main admin account' });
        }

        await query('DELETE FROM users WHERE id = $1', [id]);
        res.json({ message: 'User deleted' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
});

router.put('/:id', async (req, res) => {
    const { id } = req.params;
    const { username, password, role, email } = req.body;

    try {
        let queryText = 'UPDATE users SET username = $1, role = $2, email = $3';
        let queryParams = [username, role, email];
        let paramIndex = 4;

        if (password && password.trim() !== '') {
            const hashedPassword = await bcrypt.hash(password, 10);
            queryText += `, password_hash = $${paramIndex}`;
            queryParams.push(hashedPassword);
            paramIndex++;
        }

        queryText += ` WHERE id = $${paramIndex} RETURNING id, username, role, email`;
        queryParams.push(id);

        const result = await query(queryText, queryParams);

        if (result.rows.length === 0) {
            return res.status(404).json({ message: 'User not found' });
        }

        res.json(result.rows[0]);
    } catch (error) {
        if (error.code === '23505') {
            return res.status(400).json({ message: 'Username or email already exists' });
        }
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
});

module.exports = router;
