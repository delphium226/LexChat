const express = require('express');
const router = express.Router();
const { query } = require('../db');
const { faker } = require('@faker-js/faker');
const bcrypt = require('bcryptjs');

// Helper to hash password once
const getHashedPassword = async () => {
    return await bcrypt.hash('password123', 10);
};

// POST /api/developer/seed
router.post('/seed', async (req, res) => {
    try {
        console.log('Starting synthetic data generation...');
        const hashedPassword = await getHashedPassword();
        const usersToCreate = 100;
        const generatedUsers = [];

        // 1. Create Users
        for (let i = 0; i < usersToCreate; i++) {
            const firstName = faker.person.firstName();
            const lastName = faker.person.lastName();
            const username = faker.internet.userName({ firstName, lastName }).toLowerCase().replace(/[^a-z0-9]/g, '') + Math.floor(Math.random() * 1000);
            const email = faker.internet.email({ firstName, lastName });

            generatedUsers.push({ username, email, password: hashedPassword, role: 'user' });
        }

        // Insert Users
        const userIds = [];
        for (const user of generatedUsers) {
            // Check if exists
            const existing = await query('SELECT id FROM users WHERE username = $1', [user.username]);
            if (existing.rows.length === 0) {
                const res = await query(
                    'INSERT INTO users (username, password_hash, role, email) VALUES ($1, $2, $3, $4) RETURNING id',
                    [user.username, user.password, user.role, user.email]
                );
                userIds.push(res.rows[0].id);
            } else {
                userIds.push(existing.rows[0].id);
            }
        }
        console.log(`Created/Found ${userIds.length} users.`);

        // 2. Generate History (6 months)
        const endDate = new Date();
        const startDate = new Date();
        startDate.setMonth(startDate.getMonth() - 6);

        let totalChats = 0;
        let totalMessages = 0;

        // Iterate through each week
        const currentDate = new Date(startDate);
        while (currentDate <= endDate) {
            // For each user, simulate activity this week
            for (const userId of userIds) {
                // 30% chance of activity per user per week
                if (Math.random() < 0.3) {
                    const chatsThisWeek = Math.floor(Math.random() * 3) + 1; // 1-3 chats

                    for (let c = 0; c < chatsThisWeek; c++) {
                        // Random time within this week
                        const chatDate = new Date(currentDate);
                        chatDate.setDate(chatDate.getDate() + Math.floor(Math.random() * 7));
                        chatDate.setHours(Math.floor(Math.random() * 24), Math.floor(Math.random() * 60));

                        if (chatDate > endDate) continue;

                        const legalTopics = ['Contract Law', 'Tort Liability', 'GDPR Compliance', 'Employment Rights', 'Property Dispute', 'Intellectual Property'];
                        const topic = legalTopics[Math.floor(Math.random() * legalTopics.length)];
                        const title = `${topic} Inquiry`;

                        // Create Chat
                        const chatRes = await query(
                            'INSERT INTO chats (user_id, title, model, created_at) VALUES ($1, $2, $3, $4) RETURNING id',
                            [userId, title, 'llama3', chatDate]
                        );
                        const chatId = chatRes.rows[0].id;
                        totalChats++;

                        // Create Messages (User Query + Assistant Response)
                        // User
                        await query(
                            'INSERT INTO messages (chat_id, role, content, created_at) VALUES ($1, $2, $3, $4)',
                            [chatId, 'user', `I have a question about ${topic}.`, chatDate]
                        );

                        // Assistant (with simulated delay)
                        const responseDate = new Date(chatDate);
                        responseDate.setSeconds(responseDate.getSeconds() + 5);

                        // 50% chance of rating
                        let rating = null;
                        let comment = null;
                        if (Math.random() < 0.5) {
                            // Weighted rating: mostly 3-5, rare 1-2
                            const rand = Math.random();
                            if (rand < 0.1) rating = 1;
                            else if (rand < 0.2) rating = 2;
                            else if (rand < 0.4) rating = 3;
                            else if (rand < 0.7) rating = 4;
                            else rating = 5;

                            if (Math.random() < 0.4) {
                                comment = faker.lorem.sentence();
                            }
                        }

                        await query(
                            'INSERT INTO messages (chat_id, role, content, created_at, rating, feedback_comment) VALUES ($1, $2, $3, $4, $5, $6)',
                            [chatId, 'assistant', `Here is some information regarding ${topic}... [Synthetic Response]`, responseDate, rating, comment]
                        );
                        totalMessages += 2;
                    }
                }
            }
            // Advance one week
            currentDate.setDate(currentDate.getDate() + 7);
        }

        res.json({
            success: true,
            message: `Synthetic data generated successfully.`,
            stats: {
                users: userIds.length,
                chats: totalChats,
                messages: totalMessages
            }
        });

    } catch (err) {
        console.error('Seed error:', err);
        res.status(500).json({ error: 'Failed to generate synthetic data' });
    }
});

module.exports = router;
