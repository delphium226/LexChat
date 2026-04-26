import axios from 'axios';

const API_URL = '/api';

export const getModels = async () => {
    const response = await axios.get(`${API_URL}/models`);
    return response.data;
};

export const sendMessage = (messages, model, num_ctx, onUpdate, signal, deep_research = false, research_mode = 'legislation_only') => {
    return new Promise(async (resolve, reject) => {
        try {
            const response = await fetch(`${API_URL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ messages, model, num_ctx, deep_research, research_mode }),
                signal
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let capturedTiming = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep the last incomplete chunk

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.type === 'timing') {
                                capturedTiming = data;
                            } else if (data.type === 'result') {
                                resolve({ ...data.message, timing: capturedTiming });
                            } else if (data.type === 'error') {
                                reject(new Error(data.error));
                            } else {
                                if (onUpdate) onUpdate(data);
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            reject(error);
        }
    });
};

export const sendSystemMessage = (messages, model, num_ctx, onUpdate, signal) => {
    return new Promise(async (resolve, reject) => {
        try {
            const response = await fetch(`${API_URL}/system/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ messages, model, num_ctx }),
                signal
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep the last incomplete chunk

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            // For system chat, we want to bubble up EVERY event type
                            if (onUpdate) onUpdate(data);

                            if (data.type === 'result') {
                                resolve(data.message);
                            } else if (data.type === 'error') {
                                reject(new Error(data.error));
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            reject(error);
        }
    });
};

export const getChats = async () => {
    const response = await axios.get(`${API_URL}/chats`);
    return response.data;
};

export const createChat = async (title, model, provider = null) => {
    const response = await axios.post(`${API_URL}/chats`, { title, model, provider });
    return response.data;
};

export const deleteChat = async (chatId) => {
    await axios.delete(`${API_URL}/chats/${chatId}`);
};

export const getChatMessages = async (chatId) => {
    const response = await axios.get(`${API_URL}/chats/${chatId}/messages`);
    return response.data;
};

export const saveMessage = async (chatId, role, content, model = null, provider = null, cost_usd = null) => {
    const response = await axios.post(`${API_URL}/chats/${chatId}/messages`, { role, content, model, provider, cost_usd });
    return response.data;
};

export const updateChatTitle = async (chatId, title) => {
    const response = await axios.put(`${API_URL}/chats/${chatId}`, { title });
    return response.data;
};

export const rateMessage = async (messageId, rating, comment = null) => {
    const response = await axios.put(`${API_URL}/chats/messages/${messageId}/rating`, { rating, comment });
    return response.data;
};

export const updatePreferences = async (preferences) => {
    const response = await axios.put(`${API_URL}/auth/preferences`, preferences);
    return response.data;
};

export const getFeedbackStats = async () => {
    const response = await axios.get(`${API_URL}/learning/feedback`);
    return response.data;
};

export const getPerformanceStats = async (days = 30) => {
    const response = await axios.get(`${API_URL}/learning/stats`, { params: { days } });
    return response.data;
};

export const testLearningRetrieval = async (query) => {
    const response = await axios.post(`${API_URL}/learning/test`, { query });
    return response.data;
};

export const generateSyntheticData = async () => {
    const response = await axios.post(`${API_URL}/developer/seed`);
    return response.data;
};

export const getUsageStats = async (days = 30) => {
    const response = await axios.get(`${API_URL}/stats/usage`, { params: { days } });
    return response.data;
};

export const getQueryPerformanceStats = async (days = 30) => {
    const response = await axios.get(`${API_URL}/stats/performance`, { params: { days } });
    return response.data;
};

export const getCostStats = async (days = 30) => {
    const response = await axios.get(`${API_URL}/stats/cost`, { params: { days } });
    return response.data;
};

export const resetDatabase = async () => {
    const response = await axios.post(`${API_URL}/developer/reset`);
    return response.data;
};

export const clearUsageData = async () => {
    const response = await axios.post(`${API_URL}/developer/clear-usage`);
    return response.data;
};

export const clearPerformanceData = async () => {
    const response = await axios.post(`${API_URL}/developer/clear-performance`);
    return response.data;
};

// --- HEALTH STATUS APIS ---
export const getLatestHealthStatus = async () => {
    const response = await axios.get(`${API_URL}/health/status`);
    return response.data;
};

export const getHealthHistory = async (serviceName, limit = 100) => {
    const response = await axios.get(`${API_URL}/health/history`, { params: { service: serviceName, limit } });
    return response.data;
};

export const triggerHealthCheck = async () => {
    const response = await axios.post(`${API_URL}/health/trigger`);
    return response.data;
};

// --- PRODUCT FEEDBACK ---
export const submitFeedback = async (message) => {
    const response = await axios.post(`${API_URL}/feedback`, { message });
    return response.data;
};

export const getProductFeedback = async () => {
    const response = await axios.get(`${API_URL}/feedback`);
    return response.data;
};

// --- PROVIDER CONFIG ---
export const getProviderConfig = async () => {
    const response = await axios.get(`${API_URL}/developer/provider-config`);
    return response.data;
};

export const saveProviderConfig = async (provider, config) => {
    const response = await axios.post(`${API_URL}/developer/provider-config`, {
        provider,
        config,
    });
    return response.data;
};

export const setActiveProvider = async (activeProvider) => {
    const response = await axios.post(`${API_URL}/developer/active-provider`, {
        active_provider: activeProvider,
    });
    return response.data;
};

export const getOpenRouterModels = async () => {
    const response = await axios.get(`${API_URL}/developer/openrouter-models`);
    return response.data;
};
