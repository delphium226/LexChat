const axios = require('axios');
const assert = require('assert');

const BASE_URL = 'http://localhost:3000/api';
let adminCookie = '';
let userCookie = '';
let userId = '';

async function runTests() {
    console.log('Starting Auth Verification Tests...');

    try {
        // 1. Test Admin Login
        console.log('1. Testing Admin Login...');
        const loginRes = await axios.post(`${BASE_URL}/auth/login`, {
            username: 'admin',
            password: 'admin',
            rememberMe: true
        });
        assert.strictEqual(loginRes.status, 200);
        assert.strictEqual(loginRes.data.user.username, 'admin');
        assert.strictEqual(loginRes.data.user.role, 'admin');

        // Extract cookie
        const cookies = loginRes.headers['set-cookie'];
        assert.ok(cookies, 'Cookies should be set');
        adminCookie = cookies.find(c => c.startsWith('token='));
        assert.ok(adminCookie, 'Token cookie should be present');
        console.log('   Admin Login Passed ✅');

        // 2. Test Create New User (as Admin)
        console.log('2. Testing Create New User...');
        const createRes = await axios.post(`${BASE_URL}/users`, {
            username: 'test_user_' + Date.now(),
            password: 'password123',
            role: 'user',
            email: `test${Date.now()}@example.com`
        }, {
            headers: { Cookie: adminCookie }
        });
        assert.strictEqual(createRes.status, 201);
        userId = createRes.data.id;
        const testUsername = createRes.data.username;
        console.log('   Create User Passed ✅');

        // 3. Test New User Login
        console.log('3. Testing New User Login...');
        const userLoginRes = await axios.post(`${BASE_URL}/auth/login`, {
            username: testUsername,
            password: 'password123'
        });
        assert.strictEqual(userLoginRes.status, 200);
        assert.strictEqual(userLoginRes.data.user.username, testUsername);
        userCookie = userLoginRes.headers['set-cookie'].find(c => c.startsWith('token='));
        console.log('   New User Login Passed ✅');

        // 4. Test Access Control (User accessing Admin route)
        console.log('4. Testing Access Control (User accessing Admin route)...');
        try {
            await axios.get(`${BASE_URL}/users`, {
                headers: { Cookie: userCookie }
            });
            assert.fail('User should not be able to access admin route');
        } catch (err) {
            assert.strictEqual(err.response.status, 403, 'Should return 403 Forbidden');
            console.log('   Access Control Passed ✅');
        }

        // 4.5. Test Edit User (as Admin)
        console.log('4.5. Testing Edit User (Admin)...');
        const updatedUsername = testUsername + '_updated';
        const editRes = await axios.put(`${BASE_URL}/users/${userId}`, {
            username: updatedUsername,
            role: 'user', // keep as user
            email: `updated_${Date.now()}@example.com`
        }, {
            headers: { Cookie: adminCookie }
        });
        assert.strictEqual(editRes.status, 200);
        assert.strictEqual(editRes.data.username, updatedUsername);
        console.log('   Edit User Passed ✅');

        // Update testUsername for subsequent login tests
        // Note: The variable testUsername is const in the scope above, but we need it for login. 
        // We generally can't reassign const. Let's rely on the new username string for step 6.
        const currentUsername = updatedUsername;

        // 5. Test Change Password
        console.log('5. Testing Change Password...');
        const changePassRes = await axios.post(`${BASE_URL}/auth/change-password`, {
            currentPassword: 'password123',
            newPassword: 'newpassword456'
        }, {
            // We need to re-login as the user because the username changed? 
            // The token contains the username. If we changed the username in DB, the old token might still be valid for ID but have old username claim.
            // However, usually ID is the subject. 
            // BUT, if we want to be safe, let's re-login the user to get a fresh token, 
            // OR just use the existing cookie if the backend relies on ID.
            // Let's TRY with existing cookie.
            headers: { Cookie: userCookie }
        });
        // Wait, if we changed the username, the old token (if it has username payload) might be mismatch? 
        // The auth middleware verifies signature. req.user comes from token.
        // If the backend uses req.user.id to find user for password change, it should work.
        // Let's see authRoutes.js... it uses req.user.id. So it should work.
        assert.strictEqual(changePassRes.status, 200);
        console.log('   Change Password Passed ✅');

        // 6. Test Login with New Password logic adjustment below...

        // 6. Test Login with New Password
        console.log('6. Testing Login with New Password...');
        const newPassLoginRes = await axios.post(`${BASE_URL}/auth/login`, {
            username: currentUsername, // Use the updated username
            password: 'newpassword456'
        });
        assert.strictEqual(newPassLoginRes.status, 200);
        console.log('   Login with New Password Passed ✅');

        // 7. Test Logout
        console.log('7. Testing Logout...');
        const logoutRes = await axios.post(`${BASE_URL}/auth/logout`);
        assert.strictEqual(logoutRes.status, 200);
        // Note: Checking cookie clearing is tricky without browser, but we check response
        const clearCookie = logoutRes.headers['set-cookie'].find(c => c.startsWith('token=;'));
        assert.ok(clearCookie, 'Token cookie should be cleared (empty value or expired)');
        console.log('   Logout Passed ✅');

        console.log('\nAll Backend Verification Tests Passed! 🎉');

    } catch (error) {
        console.error('\n❌ Test Failed:', error.message);
        if (error.response) {
            console.error('Response Status:', error.response.status);
            console.error('Response Data:', error.response.data);
        }
        process.exit(1);
    }
}

// Wait a bit for server to be ready if we were running it, assuming it's running
runTests();
