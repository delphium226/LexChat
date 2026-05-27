import React, { useState } from 'react';
import axios from 'axios';

const Settings = () => {
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    const handlePasswordChange = async (e) => {
        e.preventDefault();
        setMessage('');
        setError('');

        if (newPassword !== confirmPassword) {
            setError("New passwords don't match");
            return;
        }

        try {
            await axios.post('/api/auth/change-password', {
                currentPassword,
                newPassword
            });
            setMessage('Password updated successfully');
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch (err) {
            setError(err.response?.data?.message || 'Failed to update password');
        }
    };

    return (
        <div>
            <h1 className="text-xl font-bold mb-5 text-ink-900 font-ui">Account Settings</h1>

            <div className="max-w-md">
                <h2 className="text-sm font-semibold text-ink-700 font-ui uppercase tracking-wide mb-4">Change Password</h2>

                {message && (
                    <div className="border border-success/40 bg-success/10 text-success px-4 py-3 rounded-md mb-4 text-sm font-ui">
                        {message}
                    </div>
                )}
                {error && (
                    <div className="border border-danger/40 bg-danger/10 text-danger px-4 py-3 rounded-md mb-4 text-sm font-ui">
                        {error}
                    </div>
                )}

                <form onSubmit={handlePasswordChange}>
                    <div className="mb-4">
                        <label className="block text-ink-700 font-ui text-xs font-semibold uppercase tracking-wide mb-2">
                            Current Password
                        </label>
                        <input
                            type="password"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            className="w-full px-3 py-2 border border-ink-300 rounded-md text-sm text-ink-900 bg-paper focus:outline-none focus:ring-2 focus:ring-accent font-ui"
                            required
                        />
                    </div>
                    <div className="mb-4">
                        <label className="block text-ink-700 font-ui text-xs font-semibold uppercase tracking-wide mb-2">
                            New Password
                        </label>
                        <input
                            type="password"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            className="w-full px-3 py-2 border border-ink-300 rounded-md text-sm text-ink-900 bg-paper focus:outline-none focus:ring-2 focus:ring-accent font-ui"
                            required
                        />
                    </div>
                    <div className="mb-6">
                        <label className="block text-ink-700 font-ui text-xs font-semibold uppercase tracking-wide mb-2">
                            Confirm New Password
                        </label>
                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            className="w-full px-3 py-2 border border-ink-300 rounded-md text-sm text-ink-900 bg-paper focus:outline-none focus:ring-2 focus:ring-accent font-ui"
                            required
                        />
                    </div>
                    <button
                        type="submit"
                        className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium py-2 px-4 rounded-md w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
                    >
                        Update Password
                    </button>
                </form>
            </div>
        </div>
    );
};

export default Settings;
