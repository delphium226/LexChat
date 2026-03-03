import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getFeedbackStats, testLearningRetrieval, getPerformanceStats, generateSyntheticData, getUsageStats, resetDatabase, getLatestHealthStatus, getHealthHistory, triggerHealthCheck } from '../services/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend } from 'recharts';

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
    const [learningTimeframe, setLearningTimeframe] = useState('30');
    const [testQuery, setTestQuery] = useState('');
    const [testResults, setTestResults] = useState(null);

    // --- USAGE STATS STATE ---
    const [usageStats, setUsageStats] = useState(null);
    const [timeframe, setTimeframe] = useState('30');

    // --- SERVICE HEALTH STATE ---
    const [healthStatus, setHealthStatus] = useState(null);
    const [isTriggeringHealth, setIsTriggeringHealth] = useState(false);

    // --- INITIAL FETCH ---
    useEffect(() => {
        if (activeTab === 'users') {
            fetchUsers();
        } else if (activeTab === 'learning') {
            fetchFeedback();
            fetchStats(learningTimeframe);
        } else if (activeTab === 'usage') {
            fetchUsageStats(timeframe);
        } else if (activeTab === 'health') {
            fetchHealthStatus();
        }
    }, [activeTab, timeframe, learningTimeframe]);

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

    const fetchStats = async (days) => {
        try {
            const rawData = await getPerformanceStats(days);

            // Transform Data for Recharts: Group by Date
            // Expected: [{ date: '...', 'llama3': 4.5, 'gpt4': 4.8 }, ...]
            const processedMap = {};
            const modelSet = new Set();

            rawData.forEach(item => {
                const dateStr = new Date(item.date).toLocaleDateString();
                if (!processedMap[dateStr]) {
                    processedMap[dateStr] = { date: dateStr, rawDate: item.date }; // Keep rawDate for sorting if needed
                }
                const rating = parseFloat(item.avg_rating).toFixed(1);
                const modelName = item.model || 'Unknown';
                processedMap[dateStr][modelName] = rating;
                modelSet.add(modelName);
            });

            // Convert to array
            const chartData = Object.values(processedMap);
            // Sort by date just in case
            chartData.sort((a, b) => new Date(a.rawDate) - new Date(b.rawDate));

            setStats({ data: chartData, models: Array.from(modelSet) });
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

    const fetchUsageStats = async (days) => {
        try {
            const data = await getUsageStats(days);
            setUsageStats(data);
        } catch (err) {
            console.error(err);
        }
    };

    // ==========================================
    // SERVICE HEALTH LOGIC
    // ==========================================
    const fetchHealthStatus = async () => {
        // Only set loading on initial fetch so background polling is seamless
        if (!healthStatus) setIsLoading(true);
        try {
            const data = await getLatestHealthStatus();
            setHealthStatus(data);
        } catch (err) {
            console.error('Failed to fetch health status', err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleTriggerHealthCheck = async () => {
        setIsTriggeringHealth(true);
        try {
            const data = await triggerHealthCheck();
            setHealthStatus(data);
            setMessage('Health check triggered and updated successfully');
            setTimeout(() => setMessage(''), 3000);
        } catch (err) {
            console.error('Failed to trigger health check', err);
            setMessage(err.message || 'Error triggering health check');
        } finally {
            setIsTriggeringHealth(false);
        }
    };

    // Poll health status
    useEffect(() => {
        let intervalId;
        if (activeTab === 'health') {
            intervalId = setInterval(() => {
                fetchHealthStatus();
            }, 60000); // 60s
        }
        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [activeTab]);


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
                        onClick={() => setActiveTab('usage')}
                        className={`px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'usage'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Usage Stats
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
                    <button
                        onClick={() => setActiveTab('health')}
                        className={`px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'health'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Service Health
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

                {/* SERVICE HEALTH TAB */}
                {activeTab === 'health' && (
                    <div className="space-y-6">
                        <div className="flex justify-between items-center bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                            <h2 className="text-lg font-bold dark:text-white">System Service Health</h2>
                            <button
                                onClick={handleTriggerHealthCheck}
                                disabled={isTriggeringHealth}
                                className={`bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 transition-colors ${isTriggeringHealth ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                {isTriggeringHealth ? 'Checking...' : 'Run Health Check Now'}
                            </button>
                        </div>

                        {healthStatus ? (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                {/* Database Card */}
                                <div className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.database?.is_healthy ? 'border-green-500 bg-white dark:bg-zinc-800' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}>
                                    <h3 className="text-lg font-bold mb-2 dark:text-white flex items-center justify-between">
                                        PostgreSQL Database
                                        <span className={`inline-block w-3 h-3 rounded-full ${healthStatus?.database?.is_healthy ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                    </h3>
                                    <div className="text-sm space-y-2 dark:text-gray-300">
                                        <p><strong>Status:</strong> {healthStatus?.database?.is_healthy ? 'Healthy' : 'Degraded'}</p>
                                        <p><strong>Latency:</strong> {healthStatus?.database?.latency_ms !== null ? `${healthStatus.database.latency_ms}ms` : 'N/A'}</p>
                                        {!healthStatus?.database?.is_healthy && healthStatus?.database?.error_message && (
                                            <p className="text-red-600 dark:text-red-400 text-xs mt-2 mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                                                <strong>Error:</strong> {healthStatus.database.error_message}
                                            </p>
                                        )}
                                        <p className="text-xs text-gray-500 mt-4">Last checked: {healthStatus?.database?.checked_at ? new Date(healthStatus.database.checked_at).toLocaleString() : 'Never'}</p>
                                    </div>
                                </div>
                                {/* Ollama Card */}
                                <div className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.ollama?.is_healthy ? 'border-green-500 bg-white dark:bg-zinc-800' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}>
                                    <h3 className="text-lg font-bold mb-2 dark:text-white flex items-center justify-between">
                                        Ollama Reasoning Engine
                                        <span className={`inline-block w-3 h-3 rounded-full ${healthStatus?.ollama?.is_healthy ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`}></span>
                                    </h3>
                                    <div className="text-sm space-y-2 dark:text-gray-300">
                                        <p><strong>Status:</strong> {healthStatus?.ollama?.is_healthy ? 'Healthy' : 'Disconnected / Refused'}</p>
                                        <p><strong>Latency:</strong> {healthStatus?.ollama?.latency_ms !== null ? `${healthStatus.ollama.latency_ms}ms` : 'N/A'}</p>
                                        {!healthStatus?.ollama?.is_healthy && healthStatus?.ollama?.error_message && (
                                            <p className="text-red-600 dark:text-red-400 text-xs mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                                                <strong>Error:</strong> {healthStatus.ollama.error_message}
                                            </p>
                                        )}
                                        <p className="text-xs text-gray-500 mt-4">Last checked: {healthStatus?.ollama?.checked_at ? new Date(healthStatus.ollama.checked_at).toLocaleString() : 'Never'}</p>
                                    </div>
                                </div>
                                {/* LEX API Card */}
                                <div className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.lex_api?.is_healthy ? 'border-green-500 bg-white dark:bg-zinc-800' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}>
                                    <h3 className="text-lg font-bold mb-2 dark:text-white flex items-center justify-between">
                                        External LEX Data API
                                        <span className={`inline-block w-3 h-3 rounded-full ${healthStatus?.lex_api?.is_healthy ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                    </h3>
                                    <div className="text-sm space-y-2 dark:text-gray-300">
                                        <p><strong>Status:</strong> {healthStatus?.lex_api?.is_healthy ? 'Reachable' : 'Unreachable'}</p>
                                        <p><strong>Latency:</strong> {healthStatus?.lex_api?.latency_ms !== null ? `${healthStatus.lex_api.latency_ms}ms` : 'N/A'}</p>
                                        {!healthStatus?.lex_api?.is_healthy && healthStatus?.lex_api?.error_message && (
                                            <p className="text-red-600 dark:text-red-400 text-xs mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                                                <strong>Error:</strong> {healthStatus.lex_api.error_message}
                                            </p>
                                        )}
                                        <p className="text-xs text-gray-500 mt-4">Last checked: {healthStatus?.lex_api?.checked_at ? new Date(healthStatus.lex_api.checked_at).toLocaleString() : 'Never'}</p>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex justify-center items-center h-40">
                                <span className="text-gray-500 dark:text-gray-400">Loading health data...</span>
                            </div>
                        )}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow mt-6">
                            <h3 className="text-md font-bold mb-2 dark:text-white">Note regarding Service Health</h3>
                            <p className="text-sm text-gray-600 dark:text-gray-400">Health checks execute automatically in the background every 60 seconds starting from server boot. If a component goes down, LexChat will isolate the fault to its container to make proxy or downtime troubleshooting instantaneous.</p>
                        </div>
                    </div>
                )}

                {/* USAGE STATS TAB */}
                {activeTab === 'usage' && usageStats && (
                    <div className="space-y-6">
                        {/* HEADER WITH FILTER */}
                        <div className="flex justify-between items-center bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                            <h2 className="text-lg font-bold dark:text-white">Usage Overview</h2>
                            <div className="flex items-center space-x-2">
                                <label className="text-sm text-gray-500 dark:text-gray-400 font-medium">Timeframe:</label>
                                <select
                                    value={timeframe}
                                    onChange={(e) => setTimeframe(e.target.value)}
                                    className="p-2 border rounded-md text-sm dark:bg-zinc-700 dark:border-zinc-600 dark:text-white focus:ring-2 focus:ring-blue-500"
                                >
                                    <option value="7">Last 7 Days</option>
                                    <option value="30">Last 30 Days</option>
                                    <option value="90">Last 90 Days</option>
                                    <option value="all">All Time</option>
                                </select>
                            </div>
                        </div>

                        {/* KPI CARDS */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Total Users (Global)</h3>
                                <p className="text-2xl font-bold dark:text-white">{usageStats.kpi.users}</p>
                            </div>
                            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Active Users {timeframe === 'all' ? '(All Time)' : `(${timeframe}d)`}</h3>
                                <p className="text-2xl font-bold text-green-600">{usageStats.kpi.activeUsers}</p>
                            </div>
                            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Total Chats</h3>
                                <p className="text-2xl font-bold dark:text-white">{usageStats.kpi.chats}</p>
                            </div>
                            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Total Messages</h3>
                                <p className="text-2xl font-bold dark:text-white">{usageStats.kpi.messages}</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {/* ACTIVITY CHART */}
                            <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                                <h2 className="text-lg font-bold mb-4 dark:text-white">Daily Chats {timeframe === 'all' ? '(All Time)' : `(Last ${timeframe} Days)`}</h2>
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={usageStats.activity}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                            <XAxis
                                                dataKey="date"
                                                stroke="#9ca3af"
                                                tick={{ fontSize: 10 }}
                                                tickFormatter={(str) => new Date(str).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' })}
                                            />
                                            <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
                                                itemStyle={{ color: '#374151' }}
                                            />
                                            <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* POWER USERS & MODELS */}
                            <div className="space-y-6">
                                {/* MODELS */}
                                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow h-fit">
                                    <h2 className="text-lg font-bold mb-4 dark:text-white">Model Distribution</h2>
                                    <div className="h-40 flex items-center justify-center">
                                        {/* Simple Pie Chart Placeholder or Real Implementation if easy */}
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={usageStats.models}
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={40}
                                                    outerRadius={70}
                                                    fill="#8884d8"
                                                    paddingAngle={5}
                                                    dataKey="count"
                                                    nameKey="model"
                                                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                                    labelLine={false}
                                                >
                                                    {usageStats.models.map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={['#0088FE', '#00C49F', '#FFBB28', '#FF8042'][index % 4]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                {/* TOP USERS */}
                                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                                    <h2 className="text-lg font-bold mb-4 dark:text-white">Top 5 Power Users</h2>
                                    <ul className="space-y-3">
                                        {usageStats.topUsers.map((u, i) => (
                                            <li key={i} className="flex justify-between items-center text-sm border-b dark:border-zinc-700 pb-2 last:border-0 last:pb-0">
                                                <span className="font-medium dark:text-gray-200">
                                                    {i + 1}. {u.username}
                                                </span>
                                                <span className="bg-gray-100 dark:bg-zinc-700 text-gray-800 dark:text-gray-300 px-2 py-1 rounded text-xs font-bold">
                                                    {u.msg_count} msgs
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* LEARNING DASHBOARD TAB */}
                {activeTab === 'learning' && (
                    <div className="space-y-6">
                        {/* 0. PERFORMANCE TRENDS CHART */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-lg font-bold dark:text-white">Performance Trends (Avg Rating)</h2>
                                <div className="flex items-center space-x-2">
                                    <label className="text-sm text-gray-500 dark:text-gray-400 font-medium">Timeframe:</label>
                                    <select
                                        value={learningTimeframe}
                                        onChange={(e) => setLearningTimeframe(e.target.value)}
                                        className="p-2 border rounded-md text-sm dark:bg-zinc-700 dark:border-zinc-600 dark:text-white focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="7">Last 7 Days</option>
                                        <option value="30">Last 30 Days</option>
                                        <option value="90">Last 90 Days</option>
                                        <option value="all">All Time</option>
                                    </select>
                                </div>
                            </div>

                            <div className="h-64 w-full">
                                {stats?.data && stats.data.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart
                                            data={stats.data}
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
                                            <Legend wrapperStyle={{ paddingTop: '10px' }} />
                                            {stats.models.map((model, index) => (
                                                <Line
                                                    key={model}
                                                    type="monotone"
                                                    dataKey={model}
                                                    name={model}
                                                    stroke={['#2563eb', '#db2777', '#ca8a04', '#16a34a', '#9333ea'][index % 5]}
                                                    strokeWidth={2}
                                                    activeDot={{ r: 8 }}
                                                    connectNulls
                                                />
                                            ))}
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

                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow border border-red-200 dark:border-red-900">
                            <h2 className="text-lg font-bold mb-4 text-red-600 dark:text-red-400">Danger Zone</h2>
                            <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
                                This action will delete all users (except 'admin'), all chats, and all messages.
                                <strong> This action is irreversible.</strong>
                            </p>
                            <button
                                onClick={async () => {
                                    if (!window.confirm('WARNING: This will delete ALL data (users, chats, messages). Only the admin account will be preserved.\n\nAre you sure you want to proceed?')) return;
                                    setIsLoading(true);
                                    try {
                                        const res = await resetDatabase();
                                        setMessage(res.message);
                                        // Refresh other tabs if needed
                                        fetchStats();
                                        fetchUsers();
                                    } catch (err) {
                                        setMessage('Error resetting database: ' + err.message);
                                    } finally {
                                        setIsLoading(false);
                                    }
                                }}
                                disabled={isLoading}
                                className={`bg-red-600 text-white px-6 py-3 rounded-lg hover:bg-red-700 transition-colors text-sm ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                {isLoading ? 'Processing...' : 'Reset Database'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AdminPortal;
