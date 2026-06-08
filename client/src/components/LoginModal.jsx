import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { LexMark } from './LexMark';

const LoginModal = ({ botName = 'AILA', botLogoEmoji = null }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [rememberMe, setRememberMe] = useState(false);
    const [error, setError] = useState('');
    const [showForgotDialog, setShowForgotDialog] = useState(false);
    const { login } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        const result = await login(username, password, rememberMe);
        if (!result.success) {
            setError(result.message);
        }
    };

    return (
        <div className="fixed inset-0 bg-ink-950/50 flex items-center justify-center z-50">
            <div className="bg-paper p-8 rounded-lg shadow-xl w-96">
                <div className="flex items-center justify-center gap-2 mb-6">
                    {botLogoEmoji
                        ? <span style={{ fontSize: 40, lineHeight: 1, userSelect: 'none' }} aria-hidden="true">{botLogoEmoji}</span>
                        : <LexMark size={40} color="var(--accent)" />
                    }
                    <h1 className="text-3xl font-bold tracking-tight text-accent">{botName}</h1>
                </div>
                <h2 className="text-2xl font-bold mb-6 text-ink-900 text-center">
                    Login
                </h2>

                {error && (
                    <div className="bg-danger-soft border border-danger text-danger px-4 py-3 rounded mb-4">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div className="mb-4">
                        <label className="block text-ink-700 text-sm font-bold mb-2">
                            Username
                        </label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full px-3 py-2 border border-ink-200 rounded-lg bg-paper text-ink-900 focus:outline-none focus:ring-2 focus:ring-accent"
                            required
                        />
                    </div>

                    <div className="mb-6">
                        <label className="block text-ink-700 text-sm font-bold mb-2">
                            Password
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full px-3 py-2 border border-ink-200 rounded-lg bg-paper text-ink-900 focus:outline-none focus:ring-2 focus:ring-accent"
                            required
                        />
                    </div>

                    <div className="flex items-center justify-between mb-6">
                        <label className="flex items-center">
                            <input
                                type="checkbox"
                                checked={rememberMe}
                                onChange={(e) => setRememberMe(e.target.checked)}
                                className="mr-2"
                            />
                            <span className="text-sm text-ink-600">Remember me</span>
                        </label>
                        <button
                            type="button"
                            onClick={() => setShowForgotDialog(true)}
                            className="text-sm text-accent-ink hover:text-accent rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                        >
                            Forgot Password?
                        </button>
                    </div>

                    <button
                        type="submit"
                        className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium py-2 px-4 rounded-md w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Sign In
                    </button>
                </form>
            </div>

            {showForgotDialog && (
                <div className="fixed inset-0 bg-ink-950/60 flex items-center justify-center z-60">
                    <div className="bg-paper p-6 rounded-lg shadow-xl w-80 text-center">
                        <p className="text-ink-900 mb-6">
                            Please contact the Administrators to get your password reset. Thank you.
                        </p>
                        <button
                            onClick={() => setShowForgotDialog(false)}
                            className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium py-2 px-6 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
                        >
                            OK
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default LoginModal;
