const express = require('express');
const router = express.Router();
const { query } = require('../db');
const { authenticateToken, isAdmin } = require('../middleware/auth');

router.use(authenticateToken);
router.use(isAdmin);

// GET /api/stats/usage
router.get('/usage', async (req, res) => {
    try {
        const { days = '30' } = req.query;

        // Build Date Filter Clause
        // If days === 'all', we don't filter by date (except maybe for daily activity to limit points? No, user asked for all).
        // If days is number, we use interval.
        let dateFilterChats = '';
        let dateFilterMessages = '';

        if (days !== 'all') {
            const daysNum = parseInt(days) || 30; // Safety fallback
            dateFilterChats = `WHERE created_at > NOW() - INTERVAL '${daysNum} days'`;
            dateFilterMessages = `WHERE created_at > NOW() - INTERVAL '${daysNum} days'`;
        }

        // 1. KPI Counts
        // Total Users: Usually global, but let's keep it global as registry size.
        const totalUsers = await query('SELECT COUNT(*) FROM users');

        // Total Chats (Filtered)
        const totalChats = await query(`SELECT COUNT(*) FROM chats ${dateFilterChats}`);

        // Total Messages (Filtered)
        const totalMessages = await query(`SELECT COUNT(*) FROM messages ${dateFilterMessages}`);

        // Active Users (Filtered)
        const activeUsers = await query(`
            SELECT COUNT(DISTINCT user_id) 
            FROM chats 
            ${dateFilterChats}
        `);

        // 2. Daily Activity
        // Note: For 'all', this might return a lot of rows, but for 6 months history it's ~180 rows, which is fine.
        const dailyActivity = await query(`
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM chats
            ${dateFilterChats}
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) ASC
        `);

        // 3. Model Distribution
        const modelDist = await query(`
            SELECT model, COUNT(*) as count
            FROM chats
            ${dateFilterChats}
            GROUP BY model
        `);

        // 4. Power Users
        // Need to filter messages by date, which means we strictly need to join on chats if filtering by chat date, 
        // or filter messages directly if they have created_at. Messages DO have created_at.
        // However, existing query joins chats. Let's filter on messages.created_at for consistency.
        let powerUserMsgFilter = '';
        if (days !== 'all') {
            const daysNum = parseInt(days) || 30;
            // ambiguous column 'created_at' in join? messages.created_at
            powerUserMsgFilter = `WHERE m.created_at > NOW() - INTERVAL '${daysNum} days'`;
        }

        const powerUsers = await query(`
            SELECT u.username, COUNT(m.id) as msg_count
            FROM users u
            JOIN chats c ON u.id = c.user_id
            JOIN messages m ON c.id = m.chat_id
            ${powerUserMsgFilter}
            GROUP BY u.username
            ORDER BY msg_count DESC
            LIMIT 5
        `);

        res.json({
            kpi: {
                users: parseInt(totalUsers.rows[0].count),
                chats: parseInt(totalChats.rows[0].count),
                messages: parseInt(totalMessages.rows[0].count),
                activeUsers: parseInt(activeUsers.rows[0].count)
            },
            // Parse counts to integers for Recharts
            activity: dailyActivity.rows.map(row => ({ ...row, count: parseInt(row.count) })),
            models: modelDist.rows.map(row => ({ ...row, count: parseInt(row.count) })),
            topUsers: powerUsers.rows.map(row => ({ ...row, msg_count: parseInt(row.msg_count) }))
        });

    } catch (err) {
        console.error('Error fetching usage stats:', err);
        res.status(500).json({ error: 'Failed to fetch usage statistics' });
    }
});

module.exports = router;
