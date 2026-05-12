import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { LexMark } from './LexMark';

const LoginModal = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [rememberMe, setRememberMe] = useState(false);
    const [error, setError] = useState('');
    const [isForgotPassword, setIsForgotPassword] = useState(false);
    const { login } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (isForgotPassword) {
            try {
                await axios.post('/api/auth/reset-password-request', { username });
                alert('If the user exists, a password reset email has been sent.');
                setIsForgotPassword(false);
            } catch (err) {
                alert('Error requesting password reset.');
            }
            return;
        }

        const result = await login(username, password, rememberMe);
        if (!result.success) {
            setError(result.message);
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white dark:bg-zinc-800 p-8 rounded-lg shadow-xl w-96">
                <div className="flex items-center justify-center gap-0 mb-6">
                    <LexMark size={40} color="#2563eb" />
                    <h1 className="text-3xl font-bold tracking-tight" style={{ color: 'var(--accent)' }}>AILA</h1>
                </div>
                <h2 className="text-2xl font-bold mb-6 text-zinc-900 dark:text-white text-center">
                    {isForgotPassword ? 'Reset Password' : 'Login'}
                </h2>

                {error && (
                    <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div className="mb-4">
                        <label className="block text-zinc-700 dark:text-zinc-300 text-sm font-bold mb-2">
                            Username
                        </label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-700 dark:border-zinc-600 dark:text-white"
                            required
                        />
                    </div>

                    {!isForgotPassword && (
                        <div className="mb-6">
                            <label className="block text-zinc-700 dark:text-zinc-300 text-sm font-bold mb-2">
                                Password
                            </label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-700 dark:border-zinc-600 dark:text-white"
                                required
                            />
                        </div>
                    )}

                    {!isForgotPassword && (
                        <div className="flex items-center justify-between mb-6">
                            <label className="flex items-center">
                                <input
                                    type="checkbox"
                                    checked={rememberMe}
                                    onChange={(e) => setRememberMe(e.target.checked)}
                                    className="mr-2"
                                />
                                <span className="text-sm text-zinc-600 dark:text-zinc-400">Remember me</span>
                            </label>
                            <button
                                type="button"
                                onClick={() => setIsForgotPassword(true)}
                                className="text-sm text-blue-500 hover:text-blue-700"
                            >
                                Forgot Password?
                            </button>
                        </div>
                    )}

                    <div className="flex items-center justify-between">
                        {isForgotPassword && (
                            <button
                                type="button"
                                onClick={() => setIsForgotPassword(false)}
                                className="text-gray-500 hover:text-gray-700 font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                            >
                                Cancel
                            </button>
                        )}
                        <button
                            type="submit"
                            className="bg-brand-navy hover:bg-brand-navy-dark text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline w-full ml-2"
                        >
                            {isForgotPassword ? 'Send Reset email' : 'Sign In'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default LoginModal;
