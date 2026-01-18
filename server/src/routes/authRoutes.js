const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { pool, query } = require('../db');
const { authenticateToken, JWT_SECRET } = require('../middleware/auth');

const router = express.Router();

router.post('/login', async (req, res) => {
    const { username, password, rememberMe } = req.body;

    try {
        const result = await query('SELECT * FROM users WHERE username = $1', [username]);
        if (result.rows.length === 0) {
            return res.status(401).json({ message: 'Invalid credentials' });
        }

        const user = result.rows[0];
        const validPassword = await bcrypt.compare(password, user.password_hash);

        if (!validPassword) {
            return res.status(401).json({ message: 'Invalid credentials' });
        }

        const expiresIn = rememberMe ? '30d' : '1d';
        const token = jwt.sign({ id: user.id, username: user.username, role: user.role }, JWT_SECRET, { expiresIn });

        res.cookie('token', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            maxAge: rememberMe ? 30 * 24 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000 // 30 days or 1 day
        });

        res.json({ token, user: { id: user.id, username: user.username, role: user.role, dark_mode: user.dark_mode } });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
});

router.post('/logout', (req, res) => {
    res.clearCookie('token');
    res.json({ message: 'Logged out successfully' });
});

router.post('/reset-password-request', async (req, res) => {
    const { username } = req.body;

    try {
        const result = await query('SELECT email FROM users WHERE username = $1', [username]);
        if (result.rows.length > 0 && result.rows[0].email) {
            const email = result.rows[0].email;
            // Send email
            const { sendPasswordResetEmail } = require('../services/emailService');
            sendPasswordResetEmail(email, username, 'mock-token');
            // Log for safe measure
            console.log(`[EMAIL SENT] Password reset email sent to ${email} for user ${username}`);
        } else {
            console.log(`[EMAIL SKIP] User ${username} not found or has no email.`);
        }
    } catch (err) {
        console.error('Error fetching user for reset:', err);
    }

    res.json({ message: 'If user exists, a password reset email has been sent.' });
});

router.post('/change-password', authenticateToken, async (req, res) => {
    const { currentPassword, newPassword } = req.body;
    const userId = req.user.id;

    try {
        const result = await query('SELECT * FROM users WHERE id = $1', [userId]);
        const user = result.rows[0];

        const validPassword = await bcrypt.compare(currentPassword, user.password_hash);
        if (!validPassword) {
            return res.status(400).json({ message: 'Incorrect current password' });
        }

        const hashedPassword = await bcrypt.hash(newPassword, 10);
        await query('UPDATE users SET password_hash = $1 WHERE id = $2', [hashedPassword, userId]);

        res.json({ message: 'Password updated successfully' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
});

// Endpoint to check current session
router.get('/me', authenticateToken, async (req, res) => {
    try {
        const result = await query('SELECT id, username, role, dark_mode FROM users WHERE id = $1', [req.user.id]);
        if (result.rows.length === 0) {
            return res.status(404).json({ message: 'User not found' });
        }
        res.json({ user: result.rows[0] });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
});

// Update user preferences
router.put('/preferences', authenticateToken, async (req, res) => {
    const { dark_mode } = req.body;
    try {
        await query('UPDATE users SET dark_mode = $1 WHERE id = $2', [dark_mode, req.user.id]);
        res.json({ message: 'Preferences updated' });
    } catch (error) {
        console.error(error);
        res.status(500).json({ message: 'Server error' });
    }
});

module.exports = router;
