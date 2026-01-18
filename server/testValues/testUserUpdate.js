const axios = require('axios');

async function testUserUpdate() {
    const baseUrl = 'http://localhost:3000/api';
    let token;
    let userId;

    try {
        // 1. Login as Admin (assuming 'admin' exists with password 'admin123' or similar from seed)
        // Adjust these credentials to match a known admin in your DB
        const loginRes = await axios.post(`${baseUrl}/auth/login`, {
            username: 'admin',
            password: 'admin'
        });
        token = loginRes.data.token;
        console.log('Login successful');

        // 2. Create a temporary user to update
        const createRes = await axios.post(`${baseUrl}/users`, {
            username: 'testupdateuser',
            password: 'password123',
            role: 'user',
            email: 'test@example.com'
        }, {
            headers: { Authorization: `Bearer ${token}` }
        });
        userId = createRes.data.id;
        console.log('Created temporary user:', createRes.data);

        // 3. Update the user
        const updateRes = await axios.put(`${baseUrl}/users/${userId}`, {
            username: 'updatedUser',
            role: 'admin',
            email: 'updated@example.com'
        }, {
            headers: { Authorization: `Bearer ${token}` }
        });
        console.log('Updated user:', updateRes.data);

        if (updateRes.data.username === 'updatedUser' && updateRes.data.role === 'admin') {
            console.log('✅ Update valid!');
        } else {
            console.error('❌ Update failed validation');
        }

        // 4. Cleanup
        await axios.delete(`${baseUrl}/users/${userId}`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        console.log('Cleanup successful');

    } catch (error) {
        if (error.response) {
            console.error('Test failed with response:', error.response.status, error.response.data);
        } else {
            console.error('Test failed with error:', error.message);
        }
    }
}

testUserUpdate();
