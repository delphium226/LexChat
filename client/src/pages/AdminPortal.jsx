import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getFeedbackStats, testLearningRetrieval, getPerformanceStats, generateSyntheticData } from '../services/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const AdminPortal = () => {
    const [activeTab, setActiveTab] = useState('users');
    const [isLoading, setIsLoading] = useState(false);

    // --- USER MANAGEMENT STATE ---
    const [users, setUsers] = useState([]);
    const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user', email: '' });
    const [editingUser, setEditingUser] = useState(null);
    const [message, setMessage] = useState('');

    // --- LEARNING DASHBOARD STATE ---
    const [feedback, setFeedback] = useState([]);
    const [stats, setStats] = useState([]);
    const [testQuery, setTestQuery] = useState('');
    const [testResults, setTestResults] = useState(null);

    // --- INITIAL FETCH ---
    useEffect(() => {
        if (activeTab === 'users') {
            fetchUsers();
        } else if (activeTab === 'learning') {
            fetchFeedback();
            fetchStats();
        }
    }, [activeTab]);

    // ==========================================
    // USER MANAGEMENT LOGIC
    // ==========================================
    const fetchUsers = async () => {
        setIsLoading(true);
        try {
            const { data } = await axios.get('/api/users');
            setUsers(data);
        } catch (error) {
            console.error('Failed to fetch users', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCreateOrUpdateUser = async (e) => {
        e.preventDefault();
        try {
            if (editingUser) {
                await axios.put(`/api/users/${editingUser.id}`, newUser);
                setMessage('User updated successfully');
                setEditingUser(null);
            } else {
                await axios.post('/api/users', newUser);
                setMessage('User created successfully');
            }
            setNewUser({ username: '', password: '', role: 'user', email: '' });
            fetchUsers();
        } catch (error) {
            setMessage(error.response?.data?.message || (editingUser ? 'Error updating user' : 'Error creating user'));
        }
    };

    const startEditing = (user) => {
        setEditingUser(user);
        setNewUser({ username: user.username, password: '', role: user.role, email: user.email || '' });
        setMessage('');
    };

    const cancelEditing = () => {
        setEditingUser(null);
        setNewUser({ username: '', password: '', role: 'user', email: '' });
        setMessage('');
    };

    const handleDeleteUser = async (id) => {
        if (!window.confirm('Are you sure you want to delete this user?')) return;
        try {
            await axios.delete(`/api/users/${id}`);
            fetchUsers();
        } catch (error) {
            alert(error.response?.data?.message || 'Error deleting user');
        }
    };

    // ==========================================
    // LEARNING DASHBOARD LOGIC
    // ==========================================
    const fetchFeedback = async () => {
        setIsLoading(true);
        try {
            const data = await getFeedbackStats();
            setFeedback(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchStats = async () => {
        try {
            const data = await getPerformanceStats();
            // Format dates for display
            const formattedData = data.map(item => ({
                ...item,
                avg_rating: parseFloat(item.avg_rating).toFixed(1), // Ensure float
                date: new Date(item.date).toLocaleDateString()
            }));
            setStats(formattedData);
        } catch (err) {
            console.error(err);
        }
    };

    const handleTestRetrieval = async (e) => {
        e.preventDefault();
        if (!testQuery.trim()) return;
        try {
            const results = await testLearningRetrieval(testQuery);
            setTestResults(results);
        } catch (err) {
            console.error(err);
            alert('Failed to test retrieval');
        }
    };


    return (
        <div className="p-6 h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold dark:text-white">Admin Portal</h1>

                {/* TABS */}
                <div className="flex space-x-1 bg-gray-200 dark:bg-gray-700 p-1 rounded-lg">
                    <button
                        onClick={() => setActiveTab('users')}
                        className={`px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'users'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        User Management
                    </button>
                    <button
                        onClick={() => setActiveTab('learning')}
                        className={`px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'learning'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Learning Monitor
                    </button>
                    <button
                        onClick={() => setActiveTab('developer')}
                        className={`px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'developer'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Developer
                    </button>
                </div>
            </div>

            {message && (
                <div className="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded mb-4">
                    {message}
                </div>
            )}

            {/* CONTENT AREA */}
            <div className="flex-1 overflow-y-auto">

                {/* USER MANAGEMENT TAB */}
                {activeTab === 'users' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* LEFT COLUMN: FORM */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow h-fit">
                            <h2 className="text-lg font-bold mb-4 dark:text-white">{editingUser ? 'Edit User' : 'Add New User'}</h2>
                            <form onSubmit={handleCreateOrUpdateUser} className="grid grid-cols-1 gap-4">
                                <input
                                    type="text"
                                    placeholder="Username"
                                    value={newUser.username}
                                    onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                                    className="p-2 border rounded dark:bg-zinc-700 dark:text-white text-sm"
                                    required
                                />
                                <input
                                    type="password"
                                    placeholder={editingUser ? "Leave blank to keep current password" : "Password"}
                                    value={newUser.password}
                                    onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                                    className="p-2 border rounded dark:bg-zinc-700 dark:text-white text-sm"
                                    required={!editingUser}
                                />
                                <input
                                    type="email"
                                    placeholder="Email"
                                    value={newUser.email}
                                    onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                                    className="p-2 border rounded dark:bg-zinc-700 dark:text-white text-sm"
                                />
                                <select
                                    value={newUser.role}
                                    onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                                    className="p-2 border rounded dark:bg-zinc-700 dark:text-white text-sm"
                                >
                                    <option value="user">User</option>
                                    <option value="admin">Admin</option>
                                </select>
                                <button
                                    type="submit"
                                    className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded text-sm w-full"
                                >
                                    {editingUser ? 'Update User' : 'Create User'}
                                </button>
                                {editingUser && (
                                    <button
                                        type="button"
                                        onClick={cancelEditing}
                                        className="bg-gray-500 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded text-sm w-full"
                                    >
                                        Cancel
                                    </button>
                                )}
                            </form>
                        </div>

                        {/* RIGHT COLUMN: LIST */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow lg:col-span-2">
                            <h2 className="text-lg font-bold mb-4 dark:text-white">Existing Users</h2>
                            <div className="overflow-x-auto">
                                <table className="min-w-full leading-normal">
                                    <thead>
                                        <tr>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Username</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Role</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Email</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {users.map((user) => (
                                            <tr key={user.id}>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs dark:text-gray-200">{user.username}</td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs dark:text-gray-200">{user.role}</td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs dark:text-gray-200">{user.email}</td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-gray-200">
                                                    <button onClick={() => startEditing(user)} className="text-blue-500 hover:text-blue-700 mr-3 text-xs">Edit</button>
                                                    {user.username !== 'admin' && (
                                                        <button onClick={() => handleDeleteUser(user.id)} className="text-red-500 hover:text-red-700 text-xs">Delete</button>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}

                {/* LEARNING DASHBOARD TAB */}
                {activeTab === 'learning' && (
                    <div className="space-y-6">
                        {/* 0. PERFORMANCE TRENDS CHART */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-lg font-bold mb-4 dark:text-white">Performance Trends (Avg Rating over Time)</h2>
                            <div className="h-64 w-full">
                                {stats.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart
                                            data={stats}
                                            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                                        >
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                            <XAxis
                                                dataKey="date"
                                                stroke="#9ca3af"
                                                tick={{ fontSize: 12 }}
                                            />
                                            <YAxis
                                                domain={[0, 5]}
                                                stroke="#9ca3af"
                                                tick={{ fontSize: 12 }}
                                            />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb' }}
                                                itemStyle={{ color: '#374151' }}
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="avg_rating"
                                                stroke="#2563eb"
                                                strokeWidth={2}
                                                activeDot={{ r: 8 }}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="h-full flex items-center justify-center text-gray-500 text-sm">
                                        Not enough data to display trends yet.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* 1. RECENT FEEDBACK */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-lg font-bold mb-4 dark:text-white flex justify-between items-center">
                                <span>Recent User Feedback</span>
                                <button onClick={fetchFeedback} className="text-xs text-blue-500 hover:underline">Refresh</button>
                            </h2>
                            <div className="overflow-x-auto max-h-96">
                                <table className="min-w-full leading-normal">
                                    <thead>
                                        <tr>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Date</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">User</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Rating</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Comment</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {feedback.map((item) => (
                                            <tr key={item.id} className={item.rating >= 4 ? 'bg-green-50 dark:bg-green-900/10' : (item.rating <= 2 ? 'bg-red-50 dark:bg-red-900/10' : '')}>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 text-xs dark:text-gray-200">
                                                    {new Date(item.created_at).toLocaleDateString()}
                                                </td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 text-xs dark:text-gray-200 font-medium">
                                                    {item.username}
                                                </td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 text-xs dark:text-gray-200">
                                                    <div className="flex text-yellow-500">
                                                        {[...Array(5)].map((_, i) => (
                                                            <svg key={i} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-4 h-4 ${i < item.rating ? '' : 'text-gray-300 dark:text-gray-600'}`}>
                                                                <path fillRule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clipRule="evenodd" />
                                                            </svg>
                                                        ))}
                                                    </div>
                                                </td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 text-xs dark:text-gray-200 italic">
                                                    "{item.feedback_comment || 'No comment'}"
                                                </td>
                                            </tr>
                                        ))}
                                        {feedback.length === 0 && (
                                            <tr>
                                                <td colSpan="4" className="px-5 py-5 text-center text-gray-500 text-xs">No feedback data recorded yet.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* 2. KNOWLEDGE BASE PLAYGROUND */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-lg font-bold mb-4 dark:text-white">Knowledge Retrieval Playground</h2>
                            <p className="mb-4 text-xs text-gray-600 dark:text-gray-400">
                                Test what "memories" the agent retrieves for a given user query.
                            </p>
                            <form onSubmit={handleTestRetrieval} className="flex gap-2 mb-6">
                                <input
                                    type="text"
                                    placeholder="Enter a test query (e.g. 'Duty of Care')..."
                                    value={testQuery}
                                    onChange={(e) => setTestQuery(e.target.value)}
                                    className="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-700 dark:border-zinc-600 dark:text-white text-sm"
                                />
                                <button
                                    type="submit"
                                    className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors text-sm"
                                >
                                    Test
                                </button>
                            </form>

                            {/* RESULTS */}
                            {testResults && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* POSITIVE EXAMPLES */}
                                    <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg border border-green-200 dark:border-green-900">
                                        <h3 className="font-bold text-green-800 dark:text-green-200 mb-3 flex items-center text-sm">
                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 mr-2">
                                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                            </svg>
                                            Positive Examples ({testResults.examples.length})
                                        </h3>
                                        <div className="space-y-4">
                                            {testResults.examples.map((ex, i) => (
                                                <div key={i} className="bg-white dark:bg-zinc-900 p-3 rounded shadow-sm text-xs">
                                                    <div className="font-semibold text-gray-700 dark:text-gray-300 mb-1">Q: {ex.question}</div>
                                                    <div className="text-gray-600 dark:text-gray-400 line-clamp-3 mb-2">A: {ex.answer}</div>
                                                    {ex.feedback_comment && (
                                                        <div className="text-xs text-green-600 dark:text-green-400 italic border-l-2 border-green-400 pl-2">
                                                            User Note: "{ex.feedback_comment}"
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                            {testResults.examples.length === 0 && <p className="text-xs text-gray-500 italic">No positive examples found.</p>}
                                        </div>
                                    </div>

                                    {/* CRITIQUES */}
                                    <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg border border-red-200 dark:border-red-900">
                                        <h3 className="font-bold text-red-800 dark:text-red-200 mb-3 flex items-center text-sm">
                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 mr-2">
                                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                                            </svg>
                                            Past Critiques ({testResults.critiques.length})
                                        </h3>
                                        <div className="space-y-4">
                                            {testResults.critiques.map((c, i) => (
                                                <div key={i} className="bg-white dark:bg-zinc-900 p-3 rounded shadow-sm text-xs">
                                                    <div className="text-red-600 dark:text-red-400 font-medium mb-1">"{c.feedback_comment}"</div>
                                                    <div className="text-xs text-gray-500">Context: "{c.question}"</div>
                                                </div>
                                            ))}
                                            {testResults.critiques.length === 0 && <p className="text-xs text-gray-500 italic">No critiques found.</p>}
                                        </div>
                                    </div>
                                </div>
                            )}

                        </div>
                    </div>
                )}

                {/* DEVELOPER TAB */}
                {activeTab === 'developer' && (
                    <div className="space-y-6">
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-lg font-bold mb-4 dark:text-white">Synthetic Data Generation</h2>
                            <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
                                Generate synthetic users, chat history, and ratings to test system performance and visualization.
                                <strong> Warning: This adds significant data to the database.</strong>
                            </p>
                            <button
                                onClick={async () => {
                                    if (!window.confirm('This will generate 100 users and ~6 months of data. Continue?')) return;
                                    setIsLoading(true);
                                    try {
                                        const res = await generateSyntheticData();
                                        setMessage(res.message);
                                        // Refresh other tabs if needed
                                        fetchStats();
                                    } catch (err) {
                                        setMessage('Error generating data: ' + err.message);
                                    } finally {
                                        setIsLoading(false);
                                    }
                                }}
                                disabled={isLoading}
                                className={`bg-purple-600 text-white px-6 py-3 rounded-lg hover:bg-purple-700 transition-colors text-sm ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                {isLoading ? 'Generating Data...' : 'Generate 100 Synthetic Users (6 Months History)'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AdminPortal;
