const { Pool } = require('pg');
const config = require('../src/config');

const pool = new Pool({
    connectionString: config.database.connectionString,
});

async function checkAdmin() {
    try {
        const res = await pool.query("SELECT * FROM users WHERE username = 'admin'");
        console.log(res.rows[0]);
    } catch (err) {
        console.error(err);
    } finally {
        pool.end();
    }
}

checkAdmin();
