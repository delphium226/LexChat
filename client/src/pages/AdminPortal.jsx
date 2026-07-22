import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import axios from 'axios';
import {
  getFeedbackStats,
  testLearningRetrieval,
  getPerformanceStats,
  getEfficiencyStats,
  getUsageStats,
  clearUsageData,
  exportUsers,
  clearPerformanceData,
  clearFeedbackData,
  getLatestHealthStatus,
  getHealthHistory,
  triggerHealthCheck,
  getQueryPerformanceStats,
  getProductFeedback,
  getSurveyCompliance,
  getMessageRatings,
  getProviderConfig,
  saveProviderConfig,
  setActiveProvider,
  getOpenRouterModels,
  getCostStats,
  getCacheStats,
  getFeatures,
  saveFeatures,
  getPeers,
  createPeer,
  updatePeer,
  deletePeer,
} from '../services/api';
import ActivityLogModal from '../components/ActivityLogModal';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import Spinner from '../components/ui/Spinner';
import InfoTip from '../components/ui/InfoTip';

import { PerformanceTab } from './admin/PerformanceTab';
import { EfficiencyTab } from './admin/EfficiencyTab';
import { CostTab } from './admin/CostTab';
import { CacheTab } from './admin/CacheTab';
import { ProviderConfigPanel } from './admin/ProviderConfigPanel';
import { PERF_COLORS, COST_COLORS } from './admin/chartConfig';
import { WeeklySurveyComplianceChart } from './admin/surveyCharts';
import { buildDailyRatingsData } from './admin/surveyData';

const AdminPortal = ({ currentUser }) => {
  const [activeTab, setActiveTab] = useState('users');
  const [isLoading, setIsLoading] = useState(false);
  const [isStatsLoading, setIsStatsLoading] = useState(false);
  const [isTestLoading, setIsTestLoading] = useState(false);

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

  // --- PERFORMANCE STATS STATE ---
  const [perfStats, setPerfStats] = useState(null);
  const [perfTimeframe, setPerfTimeframe] = useState('30');
  const [isPerfLoading, setIsPerfLoading] = useState(false);

  // --- EFFICIENCY STATS STATE ---
  const [effStats, setEffStats] = useState(null);
  const [effTimeframe, setEffTimeframe] = useState('30');
  const [isEffLoading, setIsEffLoading] = useState(false);

  // --- COST STATS STATE ---
  const [costStats, setCostStats] = useState(null);
  const [costTimeframe, setCostTimeframe] = useState('30');
  const [isCostLoading, setIsCostLoading] = useState(false);

  // --- CACHE STATS STATE ---
  const [cacheStats, setCacheStats] = useState(null);
  const [cacheTimeframe, setCacheTimeframe] = useState('30');
  const [isCacheLoading, setIsCacheLoading] = useState(false);

  // --- SERVICE HEALTH STATE ---
  const [healthStatus, setHealthStatus] = useState(null);
  const [isTriggeringHealth, setIsTriggeringHealth] = useState(false);

  // --- PRODUCT FEEDBACK STATE ---
  const [productFeedback, setProductFeedback] = useState([]);
  const [isProductFeedbackLoading, setIsProductFeedbackLoading] = useState(false);
  const [surveyCompliance, setSurveyCompliance] = useState(null);
  const [messageRatings, setMessageRatings] = useState([]);
  const [isMessageRatingsLoading, setIsMessageRatingsLoading] = useState(false);
  const [ratingsFilter, setRatingsFilter] = useState('all');
  const [expandedRatingRow, setExpandedRatingRow] = useState(null);
  const [ratingViewItem, setRatingViewItem] = useState(null);
  const [productFeedbackTimeframe, setProductFeedbackTimeframe] = useState('30');

  // --- FEATURE FLAGS STATE ---
  const [features, setFeatures] = useState({
    matters_enabled: true,
    prompt_caching_enabled: true,
    tool_memo_enabled: true,
    local_prompt_cache_enabled: true,
  });
  const [isSavingFeatures, setIsSavingFeatures] = useState(false);
  const [showActivityLog, setShowActivityLog] = useState(false);
  const [showUserExport, setShowUserExport] = useState(false);
  const [userExportCsv, setUserExportCsv] = useState('');
  const [userExportCount, setUserExportCount] = useState(0);
  const [userExportLoading, setUserExportLoading] = useState(false);
  const [userExportError, setUserExportError] = useState('');
  const [userExportCopied, setUserExportCopied] = useState(false);

  // --- FEDERATION STATE ---
  const [peers, setPeers] = useState([]);
  const [isPeersLoading, setIsPeersLoading] = useState(false);
  const [peerForm, setPeerForm] = useState({
    peer_id: '',
    name: '',
    base_url: '',
    api_key: '',
    description: '',
    enabled: true,
  });
  const [peerFormError, setPeerFormError] = useState('');
  const [isSavingPeer, setIsSavingPeer] = useState(false);

  // --- INITIAL FETCH ---
  useEffect(() => {
    if (activeTab === 'users') {
      fetchUsers();
    } else if (activeTab === 'learning') {
      fetchFeedback();
      fetchStats(learningTimeframe);
    } else if (activeTab === 'usage') {
      fetchUsageStats(timeframe);
    } else if (activeTab === 'performance') {
      fetchPerfStats(perfTimeframe);
    } else if (activeTab === 'efficiency') {
      fetchEffStats(effTimeframe);
    } else if (activeTab === 'cost') {
      fetchCostStats(costTimeframe);
    } else if (activeTab === 'cache') {
      fetchCacheStats(cacheTimeframe);
    } else if (activeTab === 'health') {
      fetchHealthStatus();
    } else if (activeTab === 'product-feedback') {
      fetchProductFeedback(productFeedbackTimeframe);
    } else if (activeTab === 'developer') {
      getFeatures()
        .then(setFeatures)
        .catch(() => {});
    } else if (activeTab === 'federation') {
      setIsPeersLoading(true);
      getPeers()
        .then(setPeers)
        .catch(() => {})
        .finally(() => setIsPeersLoading(false));
    }
  }, [activeTab, timeframe, learningTimeframe, perfTimeframe, effTimeframe, costTimeframe, cacheTimeframe, productFeedbackTimeframe]);

  const fetchProductFeedback = async (days = '30') => {
    setIsProductFeedbackLoading(true);
    setIsMessageRatingsLoading(true);
    const [surveyResult, complianceResult, ratingsResult] = await Promise.allSettled([
      getProductFeedback(days),
      getSurveyCompliance(),
      getMessageRatings(days),
    ]);
    if (surveyResult.status === 'fulfilled') setProductFeedback(surveyResult.value);
    else console.error('Failed to fetch product feedback:', surveyResult.reason);
    if (complianceResult.status === 'fulfilled') setSurveyCompliance(complianceResult.value);
    else console.error('Failed to fetch survey compliance:', complianceResult.reason);
    if (ratingsResult.status === 'fulfilled') setMessageRatings(ratingsResult.value);
    else console.error('Failed to fetch message ratings:', ratingsResult.reason);
    setIsProductFeedbackLoading(false);
    setIsMessageRatingsLoading(false);
  };

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

  const handleCreateOrUpdateUser = async e => {
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

  const startEditing = user => {
    setEditingUser(user);
    setNewUser({ username: user.username, password: '', role: user.role, email: user.email || '' });
    setMessage('');
  };

  const cancelEditing = () => {
    setEditingUser(null);
    setNewUser({ username: '', password: '', role: 'user', email: '' });
    setMessage('');
  };

  const handleDeleteUser = async id => {
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

  const fetchStats = async days => {
    setIsStatsLoading(true);
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
    } finally {
      setIsStatsLoading(false);
    }
  };

  const handleTestRetrieval = async e => {
    e.preventDefault();
    if (!testQuery.trim()) return;
    setIsTestLoading(true);
    try {
      const results = await testLearningRetrieval(testQuery);
      setTestResults(results);
    } catch (err) {
      console.error(err);
      alert('Failed to test retrieval');
    } finally {
      setIsTestLoading(false);
    }
  };

  const fetchUsageStats = async days => {
    setIsLoading(true);
    try {
      const data = await getUsageStats(days);
      setUsageStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchPerfStats = async days => {
    setIsPerfLoading(true);
    try {
      const data = await getQueryPerformanceStats(days);
      setPerfStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsPerfLoading(false);
    }
  };

  const fetchCostStats = async days => {
    setIsCostLoading(true);
    try {
      const data = await getCostStats(days);
      setCostStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsCostLoading(false);
    }
  };

  const fetchCacheStats = async days => {
    setIsCacheLoading(true);
    try {
      const data = await getCacheStats(days);
      setCacheStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsCacheLoading(false);
    }
  };

  const fetchEffStats = async days => {
    setIsEffLoading(true);
    try {
      const data = await getEfficiencyStats(days);
      setEffStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsEffLoading(false);
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
      <div className="mb-6">
        <h1 className="text-lg font-bold mb-3">Admin Portal</h1>

        {/* TABS */}
        <div className="flex space-x-1 bg-ink-100 p-1 rounded-lg w-full">
          {[
            { id: 'users', label: 'User Management' },
            { id: 'usage', label: 'Usage Stats' },
            { id: 'performance', label: 'Performance' },
            ...(currentUser?.username === 'admin' ? [{ id: 'efficiency', label: 'Efficiency' }] : []),
            { id: 'cost', label: 'Cost' },
            ...(currentUser?.username === 'admin' ? [{ id: 'cache', label: 'Cache' }] : []),
            { id: 'learning', label: 'Learning Monitor' },
            ...(currentUser?.username === 'admin' ? [{ id: 'developer', label: 'Developer' }] : []),
            ...(currentUser?.username === 'admin' ? [{ id: 'federation', label: 'Federation' }] : []),
            { id: 'health', label: 'Service Health' },
            { id: 'product-feedback', label: 'User Feedback' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                activeTab === tab.id ? 'bg-paper shadow text-ink-900' : 'text-ink-500 hover:text-ink-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {message && (
        <div className="bg-accent-soft border border-blue-400 text-accent-ink px-4 py-3 rounded mb-4">{message}</div>
      )}

      {/* CONTENT AREA */}
      <div className="flex-1 overflow-y-auto">
        {/* USER MANAGEMENT TAB */}
        {activeTab === 'users' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* LEFT COLUMN: FORM */}
            <div className="bg-paper p-6 rounded-lg shadow h-fit">
              <h2 className="text-lg font-bold mb-4">{editingUser ? 'Edit User' : 'Add New User'}</h2>
              <form onSubmit={handleCreateOrUpdateUser} className="grid grid-cols-1 gap-4">
                <input
                  type="text"
                  placeholder="Username"
                  value={newUser.username}
                  onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                  className="p-2 border rounded text-sm"
                  required
                />
                <input
                  type="password"
                  placeholder={editingUser ? 'Leave blank to keep current password' : 'Password'}
                  value={newUser.password}
                  onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                  className="p-2 border rounded text-sm"
                  required={!editingUser}
                />
                <input
                  type="email"
                  placeholder="Email"
                  value={newUser.email}
                  onChange={e => setNewUser({ ...newUser, email: e.target.value })}
                  className="p-2 border rounded text-sm"
                />
                <select
                  value={newUser.role}
                  onChange={e => setNewUser({ ...newUser, role: e.target.value })}
                  className="p-2 border rounded text-sm"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  type="submit"
                  className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium py-2 px-4 rounded-md w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
                >
                  {editingUser ? 'Update User' : 'Create User'}
                </button>
                {editingUser && (
                  <button
                    type="button"
                    onClick={cancelEditing}
                    className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium py-2 px-4 rounded-md w-full hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  >
                    Cancel
                  </button>
                )}
              </form>
            </div>

            {/* RIGHT COLUMN: LIST */}
            <div className="bg-paper p-6 rounded-lg shadow lg:col-span-2">
              <h2 className="text-lg font-bold mb-4">Existing Users</h2>
              {isLoading ? (
                <div className="flex justify-center items-center h-40">
                  <Spinner />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full leading-normal">
                    <thead>
                      <tr>
                        <th className="px-5 py-3 border-b-2 border-ink-200 text-left text-xs font-semibold text-ink-600 uppercase tracking-wider">
                          Username
                        </th>
                        <th className="px-5 py-3 border-b-2 border-ink-200 text-left text-xs font-semibold text-ink-600 uppercase tracking-wider">
                          Role
                        </th>
                        <th className="px-5 py-3 border-b-2 border-ink-200 text-left text-xs font-semibold text-ink-600 uppercase tracking-wider">
                          Email
                        </th>
                        <th className="px-5 py-3 border-b-2 border-ink-200 text-left text-xs font-semibold text-ink-600 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map(user => (
                        <tr key={user.id}>
                          <td className="px-5 py-5 border-b border-ink-200 bg-paper text-xs">{user.username}</td>
                          <td className="px-5 py-5 border-b border-ink-200 bg-paper text-xs">{user.role}</td>
                          <td className="px-5 py-5 border-b border-ink-200 bg-paper text-xs">{user.email}</td>
                          <td className="px-5 py-5 border-b border-ink-200 bg-paper text-sm">
                            <button
                              onClick={() => startEditing(user)}
                              className="text-accent hover:underline mr-3 text-xs font-ui"
                            >
                              Edit
                            </button>
                            {user.username !== 'admin' && (
                              <button
                                onClick={() => handleDeleteUser(user.id)}
                                className="text-danger hover:underline text-xs font-ui"
                              >
                                Delete
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SERVICE HEALTH TAB */}
        {activeTab === 'health' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center bg-paper p-4 rounded-lg shadow">
              <h2 className="text-lg font-bold">System Service Health</h2>
              <button
                onClick={handleTriggerHealthCheck}
                disabled={isTriggeringHealth}
                className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium px-4 py-2 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isTriggeringHealth ? 'Checking...' : 'Run Health Check Now'}
              </button>
            </div>

            {healthStatus ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Database Card */}
                <div
                  className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.database?.is_healthy ? 'border-green-500 bg-paper ' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}
                >
                  <h3 className="text-lg font-bold mb-2 flex items-center justify-between">
                    PostgreSQL Database
                    <span
                      className={`inline-block w-3 h-3 rounded-full ${healthStatus?.database?.is_healthy ? 'bg-green-500' : 'bg-red-500'}`}
                    ></span>
                  </h3>
                  <div className="text-sm space-y-2">
                    <p>
                      <strong>Status:</strong> {healthStatus?.database?.is_healthy ? 'Healthy' : 'Degraded'}
                    </p>
                    <p>
                      <strong>Latency:</strong>{' '}
                      {healthStatus?.database?.latency_ms !== null ? `${healthStatus.database.latency_ms}ms` : 'N/A'}
                    </p>
                    {!healthStatus?.database?.is_healthy && healthStatus?.database?.error_message && (
                      <p className="text-red-600 dark:text-red-400 text-xs mt-2 mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                        <strong>Error:</strong> {healthStatus.database.error_message}
                      </p>
                    )}
                    <p className="text-xs text-ink-500 mt-4">
                      Last checked:{' '}
                      {healthStatus?.database?.checked_at
                        ? new Date(healthStatus.database.checked_at).toLocaleString()
                        : 'Never'}
                    </p>
                  </div>
                </div>
                {/* LLM Provider Card */}
                <div
                  className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.llm?.is_healthy ? 'border-green-500 bg-paper ' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}
                >
                  <h3 className="text-lg font-bold mb-2 flex items-center justify-between">
                    {healthStatus?.active_llm_provider === 'openrouter' ? 'OpenRouter API' : 'Ollama Reasoning Engine'}
                    <span
                      className={`inline-block w-3 h-3 rounded-full ${healthStatus?.llm?.is_healthy ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`}
                    ></span>
                  </h3>
                  <div className="text-sm space-y-2">
                    <p>
                      <strong>Status:</strong> {healthStatus?.llm?.is_healthy ? 'Healthy' : 'Disconnected / Refused'}
                    </p>
                    <p>
                      <strong>Latency:</strong>{' '}
                      {healthStatus?.llm?.latency_ms !== null ? `${healthStatus.llm.latency_ms}ms` : 'N/A'}
                    </p>
                    {!healthStatus?.llm?.is_healthy && healthStatus?.llm?.error_message && (
                      <p className="text-red-600 dark:text-red-400 text-xs mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                        <strong>Error:</strong> {healthStatus.llm.error_message}
                      </p>
                    )}
                    <p className="text-xs text-ink-500 mt-4">
                      Last checked:{' '}
                      {healthStatus?.llm?.checked_at ? new Date(healthStatus.llm.checked_at).toLocaleString() : 'Never'}
                    </p>
                  </div>
                </div>
                {/* LEX API Card */}
                <div
                  className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.lex_api?.is_healthy ? 'border-green-500 bg-paper ' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}
                >
                  <h3 className="text-lg font-bold mb-2 flex items-center justify-between">
                    External LEX Data API
                    <span
                      className={`inline-block w-3 h-3 rounded-full ${healthStatus?.lex_api?.is_healthy ? 'bg-green-500' : 'bg-red-500'}`}
                    ></span>
                  </h3>
                  <div className="text-sm space-y-2">
                    <p>
                      <strong>Status:</strong> {healthStatus?.lex_api?.is_healthy ? 'Reachable' : 'Unreachable'}
                    </p>
                    <p>
                      <strong>Latency:</strong>{' '}
                      {healthStatus?.lex_api?.latency_ms !== null ? `${healthStatus.lex_api.latency_ms}ms` : 'N/A'}
                    </p>
                    {!healthStatus?.lex_api?.is_healthy && healthStatus?.lex_api?.error_message && (
                      <p className="text-red-600 dark:text-red-400 text-xs mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                        <strong>Error:</strong> {healthStatus.lex_api.error_message}
                      </p>
                    )}
                    <p className="text-xs text-ink-500 mt-4">
                      Last checked:{' '}
                      {healthStatus?.lex_api?.checked_at
                        ? new Date(healthStatus.lex_api.checked_at).toLocaleString()
                        : 'Never'}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex justify-center items-center h-40">
                <Spinner />
              </div>
            )}
            <div className="bg-paper p-6 rounded-lg shadow mt-6">
              <h3 className="text-md font-bold mb-2">Note regarding Service Health</h3>
              <p className="text-sm text-ink-600">
                Health checks execute automatically in the background every 60 seconds starting from server boot. If a
                component goes down, AILA will isolate the fault to its container to make proxy or downtime
                troubleshooting instantaneous.
              </p>
            </div>
          </div>
        )}

        {/* USAGE STATS TAB */}
        {activeTab === 'usage' && isLoading && (
          <div className="flex justify-center items-center h-64">
            <Spinner />
          </div>
        )}
        {activeTab === 'usage' && !isLoading && usageStats && (
          <div className="space-y-6">
            {/* HEADER WITH FILTER */}
            <div className="flex justify-between items-center bg-paper p-4 rounded-lg shadow">
              <h2 className="text-lg font-bold">Usage Overview</h2>
              <div className="flex items-center space-x-2">
                <label className="text-sm text-ink-500 font-medium">Timeframe:</label>
                <select
                  value={timeframe}
                  onChange={e => setTimeframe(e.target.value)}
                  className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                >
                  <option value="1">Last 1 Day</option>
                  <option value="3">Last 3 Days</option>
                  <option value="7">Last 7 Days</option>
                  <option value="30">Last 30 Days</option>
                  <option value="90">Last 90 Days</option>
                  <option value="all">All Time</option>
                </select>
              </div>
            </div>

            {/* KPI CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-paper p-4 rounded-lg shadow">
                <h3 className="text-ink-500 text-xs font-bold uppercase">Total Users (Global)</h3>
                <p className="text-2xl font-bold">{usageStats.kpi.users}</p>
              </div>
              <div className="bg-paper p-4 rounded-lg shadow">
                <h3 className="text-ink-500 text-xs font-bold uppercase">
                  Active Users {timeframe === 'all' ? '(All Time)' : `(${timeframe}d)`}
                </h3>
                <p className="text-2xl font-bold text-green-600">{usageStats.kpi.activeUsers}</p>
              </div>
              <div className="bg-paper p-4 rounded-lg shadow">
                <h3 className="text-ink-500 text-xs font-bold uppercase">Total Chats</h3>
                <p className="text-2xl font-bold">{usageStats.kpi.chats}</p>
              </div>
              <div className="bg-paper p-4 rounded-lg shadow">
                <h3 className="text-ink-500 text-xs font-bold uppercase">Total Messages</h3>
                <p className="text-2xl font-bold">{usageStats.kpi.messages}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* ACTIVITY CHART */}
              <div className="bg-paper p-6 rounded-lg shadow">
                <h2 className="text-lg font-bold mb-4">
                  Daily Chats {timeframe === 'all' ? '(All Time)' : `(Last ${timeframe} Days)`}
                </h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={usageStats.activity}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis
                        dataKey="date"
                        stroke="#9ca3af"
                        tick={{ fontSize: 10 }}
                        tickFormatter={str =>
                          new Date(str).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' })
                        }
                      />
                      <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#fff',
                          borderRadius: '8px',
                          border: '1px solid #e5e7eb',
                          fontSize: '12px',
                        }}
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
                <div className="bg-paper p-6 rounded-lg shadow h-fit">
                  <h2 className="text-lg font-bold mb-4">Model Distribution</h2>
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
                            <Cell
                              key={`cell-${index}`}
                              fill={['#0088FE', '#00C49F', '#FFBB28', '#FF8042'][index % 4]}
                            />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* TOP USERS */}
                <div className="bg-paper p-6 rounded-lg shadow">
                  <h2 className="text-lg font-bold mb-4">Top 5 Power Users</h2>
                  <ul className="space-y-3">
                    {usageStats.topUsers.map((u, i) => (
                      <li
                        key={i}
                        className="flex justify-between items-center text-sm border-b pb-2 last:border-0 last:pb-0"
                      >
                        <span className="font-medium">
                          {i + 1}. {u.username}
                        </span>
                        <span className="bg-ink-100 text-ink-800 px-2 py-1 rounded text-xs font-bold">
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

        {/* PERFORMANCE TAB */}
        {activeTab === 'performance' && isPerfLoading && (
          <div className="flex justify-center items-center h-64">
            <Spinner />
          </div>
        )}
        {activeTab === 'performance' && !isPerfLoading && perfStats && (
          <PerformanceTab perfStats={perfStats} perfTimeframe={perfTimeframe} setPerfTimeframe={setPerfTimeframe} />
        )}
        {activeTab === 'performance' && !isPerfLoading && !perfStats && (
          <div className="flex justify-center items-center h-64 text-ink-500 text-sm">
            No performance data recorded yet. Run some queries to start collecting timings.
          </div>
        )}

        {/* EFFICIENCY TAB */}
        {activeTab === 'efficiency' && isEffLoading && (
          <div className="flex justify-center items-center h-64">
            <Spinner />
          </div>
        )}
        {activeTab === 'efficiency' && !isEffLoading && effStats && (
          <EfficiencyTab effStats={effStats} effTimeframe={effTimeframe} setEffTimeframe={setEffTimeframe} />
        )}
        {activeTab === 'efficiency' && !isEffLoading && !effStats && (
          <div className="flex justify-center items-center h-64 text-ink-500 text-sm">
            No efficiency data recorded yet. Run some research queries to start collecting metrics.
          </div>
        )}

        {/* COST TAB */}
        {activeTab === 'cost' && isCostLoading && (
          <div className="flex justify-center items-center h-64">
            <Spinner />
          </div>
        )}
        {activeTab === 'cost' && !isCostLoading && costStats && (
          <CostTab costStats={costStats} costTimeframe={costTimeframe} setCostTimeframe={setCostTimeframe} />
        )}
        {activeTab === 'cost' && !isCostLoading && !costStats && (
          <div className="flex justify-center items-center h-64 text-ink-500 text-sm">No cost data available yet.</div>
        )}

        {/* CACHE TAB */}
        {activeTab === 'cache' && isCacheLoading && (
          <div className="flex justify-center items-center h-64">
            <Spinner />
          </div>
        )}
        {activeTab === 'cache' && !isCacheLoading && cacheStats && (
          <CacheTab
            cacheStats={cacheStats}
            cacheTimeframe={cacheTimeframe}
            setCacheTimeframe={setCacheTimeframe}
            refetchCacheStats={() => fetchCacheStats(cacheTimeframe)}
          />
        )}
        {activeTab === 'cache' && !isCacheLoading && !cacheStats && (
          <div className="flex justify-center items-center h-64 text-ink-500 text-sm">No cache data available yet.</div>
        )}

        {/* LEARNING DASHBOARD TAB */}
        {activeTab === 'learning' && (
          <div className="space-y-6">
            {/* 0. PERFORMANCE TRENDS CHART */}
            <div className="bg-paper p-6 rounded-lg shadow">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold">Performance Trends (Avg Rating)</h2>
                <div className="flex items-center space-x-2">
                  <label className="text-sm text-ink-500 font-medium">Timeframe:</label>
                  <select
                    value={learningTimeframe}
                    onChange={e => setLearningTimeframe(e.target.value)}
                    className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="1">Last 1 Day</option>
                    <option value="3">Last 3 Days</option>
                    <option value="7">Last 7 Days</option>
                    <option value="30">Last 30 Days</option>
                    <option value="90">Last 90 Days</option>
                    <option value="all">All Time</option>
                  </select>
                </div>
              </div>

              <div className="h-64 w-full">
                {isStatsLoading ? (
                  <div className="h-full flex items-center justify-center">
                    <Spinner />
                  </div>
                ) : stats?.data && stats.data.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={stats.data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="date" stroke="#9ca3af" tick={{ fontSize: 12 }} />
                      <YAxis domain={[0, 5]} stroke="#9ca3af" tick={{ fontSize: 12 }} />
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
                  <div className="h-full flex items-center justify-center text-ink-500 text-sm">
                    Not enough data to display trends yet.
                  </div>
                )}
              </div>
            </div>

            {/* 1. RECENT FEEDBACK */}
            <div className="bg-paper p-6 rounded-lg shadow">
              <h2 className="text-lg font-bold mb-4 flex justify-between items-center">
                <span>Recent User Feedback</span>
                <button onClick={fetchFeedback} className="text-xs text-accent hover:underline font-ui">
                  Refresh
                </button>
              </h2>
              {isLoading ? (
                <div className="flex justify-center items-center h-40">
                  <Spinner />
                </div>
              ) : (
                <div className="overflow-x-auto max-h-96">
                  <table className="min-w-full leading-normal">
                    <thead>
                      <tr>
                        <th className="px-5 py-3 border-b-2 border-ink-200 text-left text-xs font-semibold text-ink-600 uppercase tracking-wider">
                          Date
                        </th>
                        <th className="px-5 py-3 border-b-2 border-ink-200 text-left text-xs font-semibold text-ink-600 uppercase tracking-wider">
                          User
                        </th>
                        <th className="px-5 py-3 border-b-2 border-ink-200 text-left text-xs font-semibold text-ink-600 uppercase tracking-wider">
                          Rating
                        </th>
                        <th className="px-5 py-3 border-b-2 border-ink-200 text-left text-xs font-semibold text-ink-600 uppercase tracking-wider">
                          Comment
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {feedback.map(item => (
                        <tr
                          key={item.id}
                          className={
                            item.rating >= 4
                              ? 'bg-green-50 dark:bg-green-900/10'
                              : item.rating <= 2
                                ? 'bg-red-50 dark:bg-red-900/10'
                                : ''
                          }
                        >
                          <td className="px-5 py-5 border-b border-ink-200 text-xs">
                            {new Date(item.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-5 py-5 border-b border-ink-200 text-xs font-medium">{item.username}</td>
                          <td className="px-5 py-5 border-b border-ink-200 text-xs">
                            <div className="flex text-yellow-500">
                              {[...Array(5)].map((_, i) => (
                                <svg
                                  key={i}
                                  xmlns="http://www.w3.org/2000/svg"
                                  viewBox="0 0 20 20"
                                  fill="currentColor"
                                  className={`w-4 h-4 ${i < item.rating ? '' : 'text-ink-300 '}`}
                                >
                                  <path
                                    fillRule="evenodd"
                                    d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z"
                                    clipRule="evenodd"
                                  />
                                </svg>
                              ))}
                            </div>
                          </td>
                          <td className="px-5 py-5 border-b border-ink-200 text-xs italic">
                            "{item.feedback_comment || 'No comment'}"
                          </td>
                        </tr>
                      ))}
                      {feedback.length === 0 && (
                        <tr>
                          <td colSpan="4" className="px-5 py-5 text-center text-ink-500 text-xs">
                            No feedback data recorded yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 2. KNOWLEDGE BASE PLAYGROUND */}
            <div className="bg-paper p-6 rounded-lg shadow">
              <h2 className="text-lg font-bold mb-4">Knowledge Retrieval Playground</h2>
              <p className="mb-4 text-xs text-ink-600">
                Test what "memories" the agent retrieves for a given user query.
              </p>
              <form onSubmit={handleTestRetrieval} className="flex gap-2 mb-6">
                <input
                  type="text"
                  placeholder="Enter a test query (e.g. 'Duty of Care')..."
                  value={testQuery}
                  onChange={e => setTestQuery(e.target.value)}
                  className="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
                <button
                  type="submit"
                  disabled={isTestLoading}
                  className="bg-brand hover:bg-brand-hover text-white px-6 py-3 rounded-md font-ui text-sm font-medium flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isTestLoading && <Spinner size="sm" />}
                  {isTestLoading ? 'Testing...' : 'Test'}
                </button>
              </form>

              {/* RESULTS */}
              {testResults && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* POSITIVE EXAMPLES */}
                  <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg border border-green-200 dark:border-green-900">
                    <h3 className="font-bold text-green-800 dark:text-green-200 mb-3 flex items-center text-sm">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="w-5 h-5 mr-2"
                      >
                        <path
                          fillRule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                          clipRule="evenodd"
                        />
                      </svg>
                      Positive Examples ({testResults.examples.length})
                    </h3>
                    <div className="space-y-4">
                      {testResults.examples.map((ex, i) => (
                        <div key={i} className="bg-paper p-3 rounded shadow-sm text-xs">
                          <div className="font-semibold text-ink-700 mb-1">Q: {ex.question}</div>
                          <div className="text-ink-600 line-clamp-3 mb-2">A: {ex.answer}</div>
                          {ex.feedback_comment && (
                            <div className="text-xs text-green-600 dark:text-green-400 italic border-l-2 border-green-400 pl-2">
                              User Note: "{ex.feedback_comment}"
                            </div>
                          )}
                        </div>
                      ))}
                      {testResults.examples.length === 0 && (
                        <p className="text-xs text-ink-500 italic">No positive examples found.</p>
                      )}
                    </div>
                  </div>

                  {/* CRITIQUES */}
                  <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg border border-red-200 dark:border-red-900">
                    <h3 className="font-bold text-red-800 dark:text-red-200 mb-3 flex items-center text-sm">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="w-5 h-5 mr-2"
                      >
                        <path
                          fillRule="evenodd"
                          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
                          clipRule="evenodd"
                        />
                      </svg>
                      Past Critiques ({testResults.critiques.length})
                    </h3>
                    <div className="space-y-4">
                      {testResults.critiques.map((c, i) => (
                        <div key={i} className="bg-paper p-3 rounded shadow-sm text-xs">
                          <div className="text-red-600 dark:text-red-400 font-medium mb-1">"{c.feedback_comment}"</div>
                          <div className="text-xs text-ink-500">Context: "{c.question}"</div>
                        </div>
                      ))}
                      {testResults.critiques.length === 0 && (
                        <p className="text-xs text-ink-500 italic">No critiques found.</p>
                      )}
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
            {/* LLM Provider Configuration */}
            <ProviderConfigPanel />

            {/* Feature Flags */}
            <div className="bg-paper p-6 rounded-lg shadow">
              <h2 className="text-lg font-bold mb-1">Feature Flags</h2>
              <p className="text-sm text-ink-500 mb-5">
                Toggle features on or off for all users. Changes take effect immediately.
              </p>
              {[
                {
                  flag: 'matters_enabled',
                  label: 'Matters',
                  desc: 'Lets users organise threads into named matters with notes.',
                },
                {
                  flag: 'prompt_caching_enabled',
                  label: 'Prompt caching (Anthropic via OpenRouter)',
                  desc: 'Marks cache breakpoints on Anthropic models so repeated agent-loop context is billed at the cached rate.',
                },
                {
                  flag: 'tool_memo_enabled',
                  label: 'Tool-call caching (Deep Research)',
                  desc: 'Serves exact repeat tool calls across Deep Research steps from memory instead of re-fetching and re-summarising.',
                },
                {
                  flag: 'local_prompt_cache_enabled',
                  label: 'Local prompt caching',
                  desc: 'Reuses document summaries across users and providers when the same text is researched with the same question — exact match only.',
                },
              ].map(({ flag, label, desc }) => (
                <div key={flag} className="flex items-center justify-between py-3 border-b border-ink-100">
                  <div>
                    <p className="text-sm font-medium">{label}</p>
                    <p className="text-xs text-ink-500">{desc}</p>
                  </div>
                  <button
                    role="switch"
                    aria-checked={features[flag]}
                    disabled={isSavingFeatures}
                    onClick={async () => {
                      const next = { ...features, [flag]: !features[flag] };
                      setIsSavingFeatures(true);
                      try {
                        const saved = await saveFeatures(next);
                        setFeatures(saved.features);
                      } catch {
                        setMessage('Failed to save feature flags.');
                      } finally {
                        setIsSavingFeatures(false);
                      }
                    }}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${features[flag] ? 'bg-accent' : 'bg-ink-300'} ${isSavingFeatures ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-paper shadow transition-transform ${features[flag] ? 'translate-x-6' : 'translate-x-1'}`}
                    />
                  </button>
                </div>
              ))}
            </div>

            {/* Activity Log */}
            <div className="bg-paper p-6 rounded-lg shadow">
              <h2 className="font-ui text-base font-semibold text-ink-900 mb-1">Activity Log</h2>
              <p className="font-ui text-sm text-ink-500 mb-4">
                Live feed of user logins, queries submitted, feedback, surveys, and service errors. Auto-refreshes every
                10 minutes while open.
              </p>
              <button
                onClick={() => setShowActivityLog(true)}
                className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
              >
                View Activity Log
              </button>
            </div>

            {/* User Export */}
            <div className="bg-paper p-6 rounded-lg shadow">
              <h2 className="font-ui text-base font-semibold text-ink-900 mb-1">Export Users</h2>
              <p className="font-ui text-sm text-ink-500 mb-4">
                Generate a CSV list of all user accounts (name, email, role) to copy and paste.
              </p>
              <button
                onClick={async () => {
                  setShowUserExport(true);
                  setUserExportLoading(true);
                  setUserExportError('');
                  setUserExportCopied(false);
                  try {
                    const res = await exportUsers();
                    setUserExportCsv(res.csv || '');
                    setUserExportCount(res.count || 0);
                  } catch (err) {
                    setUserExportError('Error exporting users: ' + err.message);
                  } finally {
                    setUserExportLoading(false);
                  }
                }}
                className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
              >
                Export Users (CSV)
              </button>
            </div>

            <div className="bg-paper p-6 rounded-lg shadow border border-red-200 dark:border-red-900">
              <h2 className="text-lg font-bold mb-4 text-red-600 dark:text-red-400">Danger Zone</h2>
              <p className="mb-2 text-sm text-ink-600">
                These actions permanently delete data and <strong>cannot be undone.</strong>
              </p>
              <div className="flex flex-wrap gap-3 mb-6">
                <button
                  onClick={async () => {
                    if (
                      !window.confirm(
                        'This will delete all chats and messages. User accounts will be kept.\n\nAre you sure?'
                      )
                    )
                      return;
                    setIsLoading(true);
                    try {
                      const res = await clearUsageData();
                      setMessage(res.message);
                      fetchStats();
                    } catch (err) {
                      setMessage('Error clearing usage data: ' + err.message);
                    } finally {
                      setIsLoading(false);
                    }
                  }}
                  disabled={isLoading}
                  className="bg-danger text-white px-5 py-2.5 rounded-md font-ui text-sm font-medium flex items-center gap-2 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading && <Spinner size="sm" />}
                  Clear All Usage Data
                </button>
                <button
                  onClick={async () => {
                    if (!window.confirm('This will delete all performance timing records.\n\nAre you sure?')) return;
                    setIsLoading(true);
                    try {
                      const res = await clearPerformanceData();
                      setMessage(res.message);
                    } catch (err) {
                      setMessage('Error clearing performance data: ' + err.message);
                    } finally {
                      setIsLoading(false);
                    }
                  }}
                  disabled={isLoading}
                  className="bg-danger text-white px-5 py-2.5 rounded-md font-ui text-sm font-medium flex items-center gap-2 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading && <Spinner size="sm" />}
                  Clear All Performance Data
                </button>
                <button
                  onClick={async () => {
                    if (
                      !window.confirm(
                        'This will delete all product feedback surveys and clear all message ratings and comments.\n\nAre you sure?'
                      )
                    )
                      return;
                    setIsLoading(true);
                    try {
                      const res = await clearFeedbackData();
                      setMessage(res.message);
                    } catch (err) {
                      setMessage('Error clearing feedback data: ' + err.message);
                    } finally {
                      setIsLoading(false);
                    }
                  }}
                  disabled={isLoading}
                  className="bg-danger text-white px-5 py-2.5 rounded-md font-ui text-sm font-medium flex items-center gap-2 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading && <Spinner size="sm" />}
                  Clear User Feedback
                </button>
              </div>
            </div>
          </div>
        )}
        {/* USER FEEDBACK TAB */}
        {activeTab === 'product-feedback' &&
          (() => {
            const timeframeLabel =
              productFeedbackTimeframe === 'all' ? 'All Time' : `Last ${productFeedbackTimeframe} Days`;
            const withTime = productFeedback.filter(
              f => f.time_saved_hours != null && f.time_without_aila_hours != null
            );
            const avgSaved =
              withTime.length > 0 ? withTime.reduce((s, f) => s + f.time_saved_hours, 0) / withTime.length : null;
            const avgWithout =
              withTime.length > 0
                ? withTime.reduce((s, f) => s + f.time_without_aila_hours, 0) / withTime.length
                : null;
            const withConf = productFeedback.filter(f => f.confidence != null);
            const avgConf =
              withConf.length > 0 ? withConf.reduce((s, f) => s + f.confidence, 0) / withConf.length : null;
            const withVerif = productFeedback.filter(f => f.verification_hours != null);
            const avgVerif =
              withVerif.length > 0 ? withVerif.reduce((s, f) => s + f.verification_hours, 0) / withVerif.length : null;
            const withUsab = productFeedback.filter(f => f.usability != null);
            const avgUsab =
              withUsab.length > 0 ? withUsab.reduce((s, f) => s + f.usability, 0) / withUsab.length : null;
            const thCls =
              'px-4 py-2 border-b-2 border-ink-200  text-left font-semibold text-ink-500  uppercase tracking-wider whitespace-nowrap';
            return (
              <div className="space-y-4">
                {/* TIMEFRAME FILTER HEADER */}
                <div className="flex justify-between items-center bg-paper p-4 rounded-lg shadow">
                  <h2 className="text-lg font-bold">User Feedback</h2>
                  <div className="flex items-center space-x-2">
                    <label className="text-sm text-ink-500 font-medium">Timeframe:</label>
                    <select
                      value={productFeedbackTimeframe}
                      onChange={e => setProductFeedbackTimeframe(e.target.value)}
                      className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="1">Last 1 Day</option>
                      <option value="3">Last 3 Days</option>
                      <option value="7">Last 7 Days</option>
                      <option value="30">Last 30 Days</option>
                      <option value="90">Last 90 Days</option>
                      <option value="all">All Time</option>
                    </select>
                  </div>
                </div>

                {/* RESPONSE RATINGS CARD */}
                {(() => {
                  const total = messageRatings.length;
                  const upCount = messageRatings.filter(r => r.rating === 5).length;
                  const downCount = messageRatings.filter(r => r.rating === 1).length;
                  const commentedCount = messageRatings.filter(r => r.feedback_comment).length;
                  const upPct = total > 0 ? Math.round((upCount / total) * 100) : null;
                  const downPct = total > 0 ? Math.round((downCount / total) * 100) : null;
                  const filtered = messageRatings.filter(r => {
                    if (ratingsFilter === 'up') return r.rating === 5;
                    if (ratingsFilter === 'down') return r.rating === 1;
                    if (ratingsFilter === 'commented') return !!r.feedback_comment;
                    return true;
                  });
                  const thR =
                    'px-4 py-2 border-b-2 border-ink-200  text-left font-semibold text-ink-500  uppercase tracking-wider whitespace-nowrap text-xs';
                  return (
                    <div className="bg-paper p-6 rounded-lg shadow">
                      <div className="flex justify-between items-center mb-5">
                        <h2 className="text-lg font-bold">LLM Response Ratings</h2>
                        <button
                          onClick={() => fetchProductFeedback(productFeedbackTimeframe)}
                          className="text-xs text-accent hover:underline font-ui"
                        >
                          Refresh
                        </button>
                      </div>

                      {/* KPIs */}
                      {!isMessageRatingsLoading && total > 0 && (
                        <>
                          <h3 className="text-sm font-bold mb-3">Rating Summary</h3>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                            <div className="bg-ink-50 rounded-lg p-4 text-center">
                              <div className="text-2xl font-bold text-ink-800">{total}</div>
                              <div className="text-xs text-ink-500 mt-1">Total rated</div>
                            </div>
                            <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-4 text-center">
                              <div className="text-2xl font-bold text-green-700 dark:text-green-300">{upCount}</div>
                              <div className="text-xs text-green-600 dark:text-green-400 mt-1">
                                👍 Helpful{upPct != null ? ` (${upPct}%)` : ''}
                              </div>
                            </div>
                            <div className="bg-red-50 dark:bg-red-900/30 rounded-lg p-4 text-center">
                              <div className="text-2xl font-bold text-red-700 dark:text-red-300">{downCount}</div>
                              <div className="text-xs text-red-600 dark:text-red-400 mt-1">
                                👎 Unhelpful{downPct != null ? ` (${downPct}%)` : ''}
                              </div>
                            </div>
                            <div className="bg-ink-50 rounded-lg p-4 text-center">
                              <div className="text-2xl font-bold text-ink-800">{commentedCount}</div>
                              <div className="text-xs text-ink-500 mt-1">With comments</div>
                            </div>
                          </div>
                        </>
                      )}

                      {/* Daily ratings chart */}
                      {!isMessageRatingsLoading && total > 0 && (
                        <div className="mb-6">
                          <h3 className="text-sm font-bold mb-3">Daily Ratings</h3>
                          <ResponsiveContainer width="100%" height={160}>
                            <BarChart
                              data={buildDailyRatingsData(messageRatings, productFeedbackTimeframe)}
                              barCategoryGap="35%"
                            >
                              <CartesianGrid strokeDasharray="3 3" vertical={false} />
                              <XAxis
                                dataKey="day"
                                tick={{ fontSize: 11 }}
                                interval={
                                  Math.max(0, Math.floor(parseInt(productFeedbackTimeframe) / 7) - 1) ||
                                  'preserveStartEnd'
                                }
                              />
                              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={24} />
                              <Tooltip />
                              <Legend wrapperStyle={{ fontSize: 12 }} />
                              <Bar dataKey="up" name="Helpful" fill="#22c55e" radius={[3, 3, 0, 0]} />
                              <Bar dataKey="down" name="Unhelpful" fill="#ef4444" radius={[3, 3, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      )}

                      {/* Filter tabs */}
                      {!isMessageRatingsLoading && total > 0 && (
                        <div className="flex flex-wrap gap-2 mb-4">
                          {[
                            { key: 'all', label: `All (${total})` },
                            { key: 'down', label: `👎 Unhelpful (${downCount})` },
                            { key: 'up', label: `👍 Helpful (${upCount})` },
                            { key: 'commented', label: `💬 With comments (${commentedCount})` },
                          ].map(f => (
                            <button
                              key={f.key}
                              onClick={() => setRatingsFilter(f.key)}
                              className={`px-3 py-1 rounded-full text-xs font-medium border font-ui focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                                ratingsFilter === f.key
                                  ? 'bg-accent text-white border-transparent'
                                  : 'bg-paper text-ink-600 border-ink-200 hover:bg-ink-50'
                              }`}
                            >
                              {f.label}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Table */}
                      <h3 className="text-sm font-bold mb-3 mt-2">Individual LLM Response Ratings</h3>
                      {isMessageRatingsLoading ? (
                        <div className="flex justify-center items-center h-32">
                          <Spinner />
                        </div>
                      ) : total === 0 ? (
                        <p className="text-ink-400 text-sm">No responses have been rated yet.</p>
                      ) : filtered.length === 0 ? (
                        <p className="text-ink-400 text-sm">No ratings match this filter.</p>
                      ) : (
                        <>
                          <div className="overflow-x-auto">
                            <table className="min-w-full text-sm">
                              <thead>
                                <tr>
                                  <th className={`${thR} w-24`}>User</th>
                                  <th className={`${thR} w-32`}>Date</th>
                                  <th className={`${thR} w-24`}>Rating</th>
                                  <th className={`${thR} w-48`}>Comment</th>
                                  <th className={`${thR} w-40`}>Query / Response</th>
                                </tr>
                              </thead>
                              <tbody>
                                {filtered.map(item => (
                                  <tr key={item.id} className="border-b border-ink-100 align-top">
                                    <td className="px-4 py-3 font-medium text-ink-800 whitespace-nowrap">
                                      {item.username}
                                    </td>
                                    <td className="px-4 py-3 text-ink-500 whitespace-nowrap text-xs">
                                      {new Date(item.created_at).toLocaleString('en-GB', {
                                        day: '2-digit',
                                        month: 'short',
                                        year: 'numeric',
                                        hour: '2-digit',
                                        minute: '2-digit',
                                      })}
                                    </td>
                                    <td className="px-4 py-3">
                                      {item.rating === 5 ? (
                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 text-xs font-semibold whitespace-nowrap">
                                          👍 Helpful
                                        </span>
                                      ) : (
                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 text-xs font-semibold whitespace-nowrap">
                                          👎 Unhelpful
                                        </span>
                                      )}
                                    </td>
                                    <td className="px-4 py-3 text-ink-600">
                                      {item.feedback_comment ? (
                                        <span className="italic text-xs">{item.feedback_comment}</span>
                                      ) : (
                                        <span className="text-ink-400 text-xs">—</span>
                                      )}
                                    </td>
                                    <td className="px-4 py-3">
                                      <button
                                        onClick={() => setRatingViewItem(item)}
                                        className="px-3 py-1 text-xs rounded-md border border-ink-200 bg-paper text-ink-700 hover:bg-ink-50 font-ui font-medium whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                                      >
                                        View query/response
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>

                          {/* Query/Response modal */}
                          {ratingViewItem && (
                            <div
                              className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
                              onClick={() => setRatingViewItem(null)}
                            >
                              <div
                                className="bg-paper rounded-xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col max-h-[80vh]"
                                onClick={e => e.stopPropagation()}
                              >
                                <div className="flex items-center justify-between px-6 py-4 border-b border-ink-200">
                                  <h3 className="font-semibold text-ink-800 text-sm">Query &amp; Response</h3>
                                  <span className="text-xs text-ink-500">
                                    {ratingViewItem.username} ·{' '}
                                    {new Date(ratingViewItem.created_at).toLocaleString('en-GB', {
                                      day: '2-digit',
                                      month: 'short',
                                      year: 'numeric',
                                      hour: '2-digit',
                                      minute: '2-digit',
                                    })}
                                  </span>
                                </div>
                                <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
                                  {(() => {
                                    const mdComponents = {
                                      p: ({ node, ...p }) => <p {...p} className="mb-3 last:mb-0" />,
                                      ul: ({ node, ...p }) => <ul {...p} className="list-disc pl-5 mb-3" />,
                                      ol: ({ node, ...p }) => <ol {...p} className="list-decimal pl-5 mb-3" />,
                                      li: ({ node, ...p }) => <li {...p} className="mb-1" />,
                                      h1: ({ node, ...p }) => <h1 {...p} className="text-base font-bold mt-3 mb-2" />,
                                      h2: ({ node, ...p }) => <h2 {...p} className="text-sm font-bold mt-3 mb-1" />,
                                      h3: ({ node, ...p }) => <h3 {...p} className="text-sm font-semibold mt-2 mb-1" />,
                                      strong: ({ node, ...p }) => <strong {...p} className="font-semibold" />,
                                      blockquote: ({ node, ...p }) => (
                                        <blockquote
                                          {...p}
                                          className="border-l-2 border-ink-300 pl-3 italic text-ink-600 my-2"
                                        />
                                      ),
                                      code: ({ node, inline, ...p }) =>
                                        inline ? (
                                          <code {...p} className="bg-ink-100 px-1 py-0.5 rounded text-xs font-mono" />
                                        ) : (
                                          <code {...p} className="text-xs font-mono" />
                                        ),
                                      pre: ({ node, ...p }) => (
                                        <pre
                                          {...p}
                                          className="bg-ink-100 rounded p-3 overflow-x-auto text-xs font-mono mb-3"
                                        />
                                      ),
                                      a: ({ node, ...p }) => (
                                        <a
                                          {...p}
                                          className="text-accent underline"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                        />
                                      ),
                                    };
                                    return (
                                      <>
                                        <div>
                                          <p className="text-xs font-semibold text-ink-500 uppercase tracking-wide mb-2">
                                            Query
                                          </p>
                                          <div className="text-sm text-ink-800">
                                            {ratingViewItem.query ? (
                                              <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                                                {ratingViewItem.query}
                                              </ReactMarkdown>
                                            ) : (
                                              <span className="italic text-ink-400">—</span>
                                            )}
                                          </div>
                                        </div>
                                        <div className="border-t border-ink-100 pt-4">
                                          <p className="text-xs font-semibold text-ink-500 uppercase tracking-wide mb-2">
                                            Response
                                          </p>
                                          <div className="text-sm text-ink-800">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                                              {ratingViewItem.response || '—'}
                                            </ReactMarkdown>
                                          </div>
                                        </div>
                                      </>
                                    );
                                  })()}
                                </div>
                                <div className="flex justify-end gap-3 px-6 py-4 border-t border-ink-200">
                                  <button
                                    onClick={() => {
                                      const text = `Query:\n${ratingViewItem.query || ''}\n\nResponse:\n${ratingViewItem.response || ''}`;
                                      navigator.clipboard.writeText(text);
                                    }}
                                    className="px-4 py-2 text-xs rounded-md border border-ink-200 bg-paper text-ink-700 hover:bg-ink-50 font-ui font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                                  >
                                    Copy to clipboard
                                  </button>
                                  <button
                                    onClick={() => setRatingViewItem(null)}
                                    className="px-4 py-2 text-xs rounded-md bg-brand hover:bg-brand-hover text-white font-ui font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
                                  >
                                    Close
                                  </button>
                                </div>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  );
                })()}

                <div className="bg-paper p-6 rounded-lg shadow">
                  <div className="flex justify-between items-center mb-4">
                    <h2 className="text-lg font-bold">Weekly User Surveys</h2>
                    <button
                      onClick={() => fetchProductFeedback(productFeedbackTimeframe)}
                      className="text-xs text-accent hover:underline font-ui"
                    >
                      Refresh
                    </button>
                  </div>

                  {!isProductFeedbackLoading && surveyCompliance && (
                    <WeeklySurveyComplianceChart surveyCompliance={surveyCompliance} />
                  )}

                  {/* Aggregate summary */}
                  {!isProductFeedbackLoading && productFeedback.length > 0 && (
                    <>
                      <h3 className="text-sm font-bold mb-3">Productivity Summary</h3>
                      <div className="grid grid-cols-2 sm:grid-cols-6 gap-4 mb-6">
                        <div className="bg-ink-50 rounded-lg p-4 text-center">
                          <div className="text-2xl font-bold text-ink-800">
                            {avgWithout != null ? avgWithout.toFixed(1) : '—'}
                          </div>
                          <div className="text-xs text-ink-500 mt-1">Avg manual hrs</div>
                        </div>
                        <div className="bg-ink-50 rounded-lg p-4 text-center">
                          <div className="text-2xl font-bold text-ink-800">
                            {avgSaved != null ? avgSaved.toFixed(1) : '—'}
                          </div>
                          <div className="text-xs text-ink-500 mt-1">Avg hrs saved</div>
                        </div>
                        <div className="bg-ink-50 rounded-lg p-4 text-center">
                          <div className="text-2xl font-bold text-ink-800">
                            {avgSaved != null && avgWithout != null && avgWithout - avgSaved > 0
                              ? `${(avgWithout / (avgWithout - avgSaved)).toFixed(1)}×`
                              : '—'}
                          </div>
                          <div className="text-xs text-ink-500 mt-1">Efficiency ratio</div>
                        </div>
                        <div className="bg-ink-50 rounded-lg p-4 text-center">
                          <div className="text-2xl font-bold text-ink-800">
                            {avgVerif != null ? avgVerif.toFixed(1) : '—'}
                          </div>
                          <div className="text-xs text-ink-500 mt-1">Avg verification hrs</div>
                        </div>
                        <div className="bg-ink-50 rounded-lg p-4 text-center">
                          <div className="text-2xl font-bold text-ink-800">
                            {avgConf != null ? `${avgConf.toFixed(1)}/5` : '—'}
                          </div>
                          <div className="text-xs text-ink-500 mt-1">Avg confidence</div>
                        </div>
                        <div className="bg-ink-50 rounded-lg p-4 text-center">
                          <div className="text-2xl font-bold text-ink-800">
                            {avgUsab != null ? `${avgUsab.toFixed(1)}/5` : '—'}
                          </div>
                          <div className="text-xs text-ink-500 mt-1">Avg usability</div>
                        </div>
                      </div>
                    </>
                  )}

                  <h3 className="text-sm font-bold mb-3 mt-2">Individual Survey Responses</h3>
                  {isProductFeedbackLoading ? (
                    <div className="flex justify-center items-center h-32">
                      <Spinner />
                    </div>
                  ) : productFeedback.length === 0 ? (
                    <p className="text-ink-400 text-sm">No feedback has been submitted yet.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr>
                            <th className={`${thCls} w-32`}>User</th>
                            <th className={`${thCls} w-44`}>Date &amp; Time</th>
                            <th className={`${thCls} w-32`}>Manual (hrs)</th>
                            <th className={`${thCls} w-28`}>Saved (hrs)</th>
                            <th className={`${thCls} w-24`}>Confidence</th>
                            <th className={`${thCls} w-24`}>Usability</th>
                            <th className={`${thCls} w-32`}>Verification (hrs)</th>
                            <th className={thCls}>Comments</th>
                          </tr>
                        </thead>
                        <tbody>
                          {productFeedback.map(item => (
                            <tr key={item.id} className="border-b border-ink-100 align-top">
                              <td className="px-4 py-3 font-medium text-ink-800 whitespace-nowrap">{item.username}</td>
                              <td className="px-4 py-3 text-ink-500 whitespace-nowrap">
                                {new Date(item.created_at).toLocaleString()}
                              </td>
                              <td className="px-4 py-3 text-ink-700 text-center">
                                {item.time_without_aila_hours != null ? item.time_without_aila_hours : '—'}
                              </td>
                              <td className="px-4 py-3 text-ink-700 text-center">
                                {item.time_saved_hours != null ? item.time_saved_hours : '—'}
                              </td>
                              <td className="px-4 py-3 text-ink-700 text-center">
                                {item.confidence != null ? `${item.confidence}/5` : '—'}
                              </td>
                              <td className="px-4 py-3 text-ink-700 text-center">
                                {item.usability != null ? `${item.usability}/5` : '—'}
                              </td>
                              <td className="px-4 py-3 text-ink-700 text-center">
                                {item.verification_hours != null ? item.verification_hours : '—'}
                              </td>
                              <td className="px-4 py-3 text-ink-700 whitespace-pre-wrap">{item.message || ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Survey compliance grid */}
                {surveyCompliance &&
                  (() => {
                    const cellColor = (weekData, isCurrent) => {
                      if (weekData.survey_submitted)
                        return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200';
                      if (weekData.query_count === 0) return 'bg-ink-100  text-ink-400 ';
                      if (isCurrent) return 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200';
                      return 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200';
                    };
                    return (
                      <>
                        <div className="bg-paper p-6 rounded-lg shadow">
                          <h2 className="text-lg font-bold mb-4">Survey Completion — Last 4 Weeks</h2>
                          <div className="overflow-x-auto">
                            <table className="min-w-full text-sm">
                              <thead>
                                <tr>
                                  <th className="px-4 py-2 border-b-2 border-ink-200 text-left font-semibold text-ink-500 uppercase tracking-wider whitespace-nowrap w-32">
                                    User
                                  </th>
                                  {surveyCompliance.weeks.map((w, i) => (
                                    <th
                                      key={i}
                                      className="px-4 py-2 border-b-2 border-ink-200 text-center font-semibold text-ink-500 uppercase tracking-wider whitespace-nowrap"
                                    >
                                      {w.label}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {surveyCompliance.users.map(u => (
                                  <tr key={u.user_id} className="border-b border-ink-100">
                                    <td className="px-4 py-2 font-medium text-ink-800 whitespace-nowrap">
                                      {u.username}
                                    </td>
                                    {u.weeks.map((w, i) => (
                                      <td key={i} className="px-2 py-2 text-center">
                                        <span
                                          className={`inline-block rounded px-2 py-1 text-xs font-semibold ${cellColor(w, surveyCompliance.weeks[i].is_current)}`}
                                        >
                                          {w.query_count} {w.query_count === 1 ? 'query' : 'queries'}
                                        </span>
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <div className="flex gap-4 mt-4 text-xs text-ink-500">
                            <span className="flex items-center gap-1">
                              <span className="inline-block w-3 h-3 rounded bg-green-200"></span> Survey submitted
                            </span>
                            <span className="flex items-center gap-1">
                              <span className="inline-block w-3 h-3 rounded bg-yellow-200"></span> Active, survey
                              pending
                            </span>
                            <span className="flex items-center gap-1">
                              <span className="inline-block w-3 h-3 rounded bg-red-200"></span> Active, survey missed
                            </span>
                            <span className="flex items-center gap-1">
                              <span className="inline-block w-3 h-3 rounded bg-ink-200"></span> No activity
                            </span>
                          </div>
                        </div>

                        {/* Survey Non-completion table */}
                        {(() => {
                          const nonCompleters = surveyCompliance.users.filter(u =>
                            u.weeks.some(
                              (w, i) =>
                                !surveyCompliance.weeks[i].is_current && w.query_count > 0 && !w.survey_submitted
                            )
                          );
                          const thNC =
                            'px-4 py-2 border-b-2 border-ink-200  text-center font-semibold text-ink-500  uppercase tracking-wider whitespace-nowrap text-xs';
                          return (
                            <div className="bg-paper p-6 rounded-lg shadow mt-4">
                              <h2 className="text-lg font-bold mb-4">Survey Non-completion — Last 4 Weeks</h2>
                              {nonCompleters.length === 0 ? (
                                <p className="text-sm text-green-600 dark:text-green-400">
                                  All active users have completed their weekly surveys.
                                </p>
                              ) : (
                                <>
                                  <div className="overflow-x-auto">
                                    <table className="min-w-full text-sm">
                                      <thead>
                                        <tr>
                                          <th className="px-4 py-2 border-b-2 border-ink-200 text-left font-semibold text-ink-500 uppercase tracking-wider whitespace-nowrap w-32 text-xs">
                                            User
                                          </th>
                                          {surveyCompliance.weeks.map((w, i) => (
                                            <th key={i} className={thNC}>
                                              {w.label}
                                            </th>
                                          ))}
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {nonCompleters.map(u => (
                                          <tr key={u.user_id} className="border-b border-ink-100">
                                            <td className="px-4 py-2 font-medium text-ink-800 whitespace-nowrap text-xs">
                                              {u.username}
                                            </td>
                                            {u.weeks.map((w, i) => {
                                              const isMissed =
                                                !surveyCompliance.weeks[i].is_current &&
                                                w.query_count > 0 &&
                                                !w.survey_submitted;
                                              return (
                                                <td key={i} className="px-2 py-2 text-center">
                                                  {isMissed ? (
                                                    <span className="inline-block rounded px-2 py-1 text-xs font-semibold bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200">
                                                      {w.query_count} {w.query_count === 1 ? 'query' : 'queries'}
                                                    </span>
                                                  ) : w.survey_submitted ? (
                                                    <span className="inline-block rounded px-2 py-1 text-xs font-semibold bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">
                                                      ✓
                                                    </span>
                                                  ) : (
                                                    <span className="text-ink-400 text-xs">—</span>
                                                  )}
                                                </td>
                                              );
                                            })}
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                  <div className="flex gap-4 mt-4 text-xs text-ink-500">
                                    <span className="flex items-center gap-1">
                                      <span className="inline-block w-3 h-3 rounded bg-red-200"></span> Active, survey
                                      missed
                                    </span>
                                    <span className="flex items-center gap-1">
                                      <span className="inline-block w-3 h-3 rounded bg-green-200"></span> Survey
                                      submitted
                                    </span>
                                    <span className="flex items-center gap-1">
                                      <span className="text-ink-400 mr-1">—</span> No activity
                                    </span>
                                  </div>
                                </>
                              )}
                            </div>
                          );
                        })()}
                      </>
                    );
                  })()}
              </div>
            );
          })()}

        {/* FEDERATION TAB */}
        {activeTab === 'federation' && (
          <div className="space-y-6 p-1">
            <div className="bg-paper rounded-lg shadow p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold text-ink-900">Registered Peers</h2>
                <button
                  onClick={() => {
                    setIsPeersLoading(true);
                    getPeers()
                      .then(setPeers)
                      .catch(() => {})
                      .finally(() => setIsPeersLoading(false));
                  }}
                  className="border border-ink-200 text-ink-600 bg-paper font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:ring-2 focus-visible:ring-accent"
                >
                  Refresh
                </button>
              </div>

              {isPeersLoading ? (
                <div className="flex justify-center py-8">
                  <Spinner />
                </div>
              ) : peers.length === 0 ? (
                <p className="text-ink-500 text-sm italic">No peers registered yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-ink-200">
                        {['Name', 'Peer ID', 'Base URL', 'Description', 'API Key', 'Enabled', ''].map(h => (
                          <th
                            key={h}
                            className="px-3 py-2 text-left font-semibold text-ink-500 text-xs uppercase tracking-wider whitespace-nowrap"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {peers.map(p => (
                        <tr key={p.peer_id} className="border-b border-ink-100 hover:bg-ink-50">
                          <td className="px-3 py-2 font-medium text-ink-900 whitespace-nowrap">{p.name}</td>
                          <td className="px-3 py-2 font-mono text-ink-600 text-xs whitespace-nowrap">{p.peer_id}</td>
                          <td className="px-3 py-2 text-ink-600 text-xs max-w-[180px] truncate" title={p.base_url}>
                            {p.base_url}
                          </td>
                          <td className="px-3 py-2 text-ink-600 max-w-[200px] truncate" title={p.description}>
                            {p.description}
                          </td>
                          <td className="px-3 py-2 text-ink-500 text-xs">{p.has_api_key ? '••••••••' : '—'}</td>
                          <td className="px-3 py-2">
                            <button
                              onClick={async () => {
                                await updatePeer(p.peer_id, { enabled: !p.enabled });
                                setPeers(prev =>
                                  prev.map(x => (x.peer_id === p.peer_id ? { ...x, enabled: !x.enabled } : x))
                                );
                              }}
                              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-accent ${p.enabled ? 'bg-brand' : 'bg-ink-300'}`}
                              aria-label={p.enabled ? 'Disable peer' : 'Enable peer'}
                            >
                              <span
                                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-paper transition-transform ${p.enabled ? 'translate-x-4' : 'translate-x-1'}`}
                              />
                            </button>
                          </td>
                          <td className="px-3 py-2">
                            <button
                              onClick={async () => {
                                if (!window.confirm(`Delete peer "${p.peer_id}"?`)) return;
                                await deletePeer(p.peer_id);
                                setPeers(prev => prev.filter(x => x.peer_id !== p.peer_id));
                              }}
                              className="bg-danger text-white font-ui text-xs font-medium rounded px-2 py-1 hover:opacity-90 focus-visible:ring-2 focus-visible:ring-danger"
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* ADD PEER FORM */}
            <div className="bg-paper rounded-lg shadow p-6">
              <h2 className="text-base font-bold text-ink-900 mb-4">Add Peer</h2>
              {peerFormError && (
                <div className="mb-3 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">
                  {peerFormError}
                </div>
              )}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {[
                  { key: 'peer_id', label: 'Peer ID', placeholder: 'legislation_bot', mono: true },
                  { key: 'name', label: 'Name', placeholder: 'Legislation Bot' },
                  { key: 'base_url', label: 'Base URL', placeholder: 'http://localhost:8001' },
                  { key: 'api_key', label: 'API Key', placeholder: '(optional)', type: 'password' },
                ].map(({ key, label, placeholder, mono, type }) => (
                  <div key={key}>
                    <label className="block text-xs font-semibold text-ink-600 mb-1 font-ui">{label}</label>
                    <input
                      type={type || 'text'}
                      value={peerForm[key]}
                      onChange={e => setPeerForm(f => ({ ...f, [key]: e.target.value }))}
                      placeholder={placeholder}
                      className={`w-full rounded-md border border-ink-200 bg-paper px-3 py-2 text-sm text-ink-900 placeholder-ink-400 focus:outline-none focus:ring-2 focus:ring-accent ${mono ? 'font-mono' : 'font-ui'}`}
                    />
                  </div>
                ))}
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-ink-600 mb-1 font-ui">
                    Description (shown to the Manager LLM as tool description)
                  </label>
                  <textarea
                    value={peerForm.description}
                    onChange={e => setPeerForm(f => ({ ...f, description: e.target.value }))}
                    placeholder="Searches Scottish Parliamentary records and debates"
                    rows={2}
                    className="w-full rounded-md border border-ink-200 bg-paper px-3 py-2 text-sm text-ink-900 placeholder-ink-400 font-ui focus:outline-none focus:ring-2 focus:ring-accent resize-none"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="peer-enabled"
                    checked={peerForm.enabled}
                    onChange={e => setPeerForm(f => ({ ...f, enabled: e.target.checked }))}
                    className="rounded border-ink-300 text-brand focus:ring-accent"
                  />
                  <label htmlFor="peer-enabled" className="text-sm font-ui text-ink-700">
                    Enabled
                  </label>
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  disabled={isSavingPeer}
                  onClick={async () => {
                    setPeerFormError('');
                    if (
                      !peerForm.peer_id.trim() ||
                      !peerForm.name.trim() ||
                      !peerForm.base_url.trim() ||
                      !peerForm.description.trim()
                    ) {
                      setPeerFormError('Peer ID, Name, Base URL, and Description are required.');
                      return;
                    }
                    setIsSavingPeer(true);
                    try {
                      const created = await createPeer({
                        peer_id: peerForm.peer_id.trim(),
                        name: peerForm.name.trim(),
                        base_url: peerForm.base_url.trim(),
                        api_key: peerForm.api_key.trim() || null,
                        description: peerForm.description.trim(),
                        enabled: peerForm.enabled,
                      });
                      setPeers(prev => [...prev, created]);
                      setPeerForm({ peer_id: '', name: '', base_url: '', api_key: '', description: '', enabled: true });
                    } catch (e) {
                      setPeerFormError(e?.response?.data?.detail || 'Failed to create peer.');
                    } finally {
                      setIsSavingPeer(false);
                    }
                  }}
                  className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSavingPeer ? 'Saving…' : 'Add Peer'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <ActivityLogModal open={showActivityLog} onClose={() => setShowActivityLog(false)} />

      {showUserExport && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setShowUserExport(false)}
        >
          <div
            className="bg-paper rounded-lg shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 border-b border-ink-200">
              <div>
                <h2 className="font-ui text-base font-semibold text-ink-900">User Export</h2>
                <p className="font-ui text-sm text-ink-500">
                  {userExportLoading
                    ? 'Loading…'
                    : `${userExportCount} user${userExportCount === 1 ? '' : 's'} — CSV (name, email, role)`}
                </p>
              </div>
              <button
                onClick={() => setShowUserExport(false)}
                className="size-[30px] flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:ring-2 focus-visible:ring-accent"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="p-5 overflow-auto">
              {userExportError ? (
                <p className="font-ui text-sm text-danger">{userExportError}</p>
              ) : (
                <textarea
                  readOnly
                  value={userExportLoading ? '' : userExportCsv}
                  onFocus={e => e.target.select()}
                  className="w-full h-72 font-mono text-xs bg-ink-50 border border-ink-200 rounded-md p-3 text-ink-900 resize-none focus-visible:ring-2 focus-visible:ring-accent"
                />
              )}
            </div>
            <div className="flex items-center justify-end gap-3 p-5 border-t border-ink-200">
              <button
                onClick={() => setShowUserExport(false)}
                className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:ring-2 focus-visible:ring-accent"
              >
                Close
              </button>
              <button
                disabled={userExportLoading || !userExportCsv}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(userExportCsv);
                    setUserExportCopied(true);
                    setTimeout(() => setUserExportCopied(false), 2000);
                  } catch {
                    // Clipboard API unavailable — user can still select the text manually.
                  }
                }}
                className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {userExportCopied ? 'Copied!' : 'Copy to clipboard'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPortal;
