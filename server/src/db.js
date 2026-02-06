const { Pool } = require('pg');
const bcrypt = require('bcryptjs');
const config = require('./config');

const pool = new Pool({
    connectionString: config.database.connectionString,
    max: config.database.maxConnections
});

const query = (text, params) => pool.query(text, params);

const initializeDB = async () => {
    try {
        console.log('Initializing database...');

        // Create users table
        await query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE,
        role VARCHAR(50) DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS chats (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );

      CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        chat_id INTEGER REFERENCES chats(id) ON DELETE CASCADE,
        role VARCHAR(50) NOT NULL, -- 'user' or 'assistant'
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

        // Add new columns if they don't exist (Migration)
        await query(`
            ALTER TABLE messages ADD COLUMN IF NOT EXISTS rating INTEGER CHECK (rating >= 1 AND rating <= 5);
            ALTER TABLE chats ADD COLUMN IF NOT EXISTS model VARCHAR(255);
            ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback_comment TEXT;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS dark_mode BOOLEAN DEFAULT FALSE;
        `);

        // Check if admin exists
        const adminCheck = await query("SELECT * FROM users WHERE username = 'admin'");
        if (adminCheck.rows.length === 0) {
            const hashedPassword = await bcrypt.hash('admin', 10);
            await query(
                "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, $3)",
                ['admin', hashedPassword, 'admin']
            );
            console.log('Default admin user created.');
        } else {
            console.log('Admin user already exists.');
        }

        console.log('Database initialized successfully.');
    } catch (err) {
        console.error('Error initializing database:', err);
        // Don't exit process, just log error, maybe DB isn't ready yet
    }
};

module.exports = {
    query,
    initializeDB,
    pool,
};
