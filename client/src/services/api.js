import axios from 'axios';

const API_URL = '/api';

export const getModels = async () => {
  const response = await axios.get(`${API_URL}/models`);
  return response.data;
};

export const sendMessage = (
  messages,
  model,
  num_ctx,
  onUpdate,
  signal,
  chat_mode = 'research',
  research_mode = 'legislation_only',
  filters = {}
) => {
  return new Promise(async (resolve, reject) => {
    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages,
          model,
          num_ctx,
          chat_mode,
          research_mode,
          chat_id: filters.chatId || null,
          jurisdiction: filters.jurisdiction || null,
          year_from: filters.dateFrom ? parseInt(filters.dateFrom, 10) : null,
          year_to: filters.dateTo ? parseInt(filters.dateTo, 10) : null,
          date_from: filters.dateFrom ? `${filters.dateFrom}-01-01` : null,
          date_to: filters.dateTo ? `${filters.dateTo}-12-31` : null,
          court: filters.caseLawCourt || null,
          legislation_type: filters.legislationType || null,
          current_only: filters.currentOnly || false,
          record_type: filters.recordType || null,
        }),
        signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const err = new Error(errorData.detail || errorData.error || `HTTP error! status: ${response.status}`);
        err.status = response.status;
        throw err;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let capturedTiming = null;

      const processLine = line => {
        if (!line.startsWith('data: ')) return;
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
          console.error('Error parsing SSE data:', e, 'Line:', line.slice(0, 200));
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // Flush any remaining buffered data before exiting.
          // The server may close without a trailing \n\n on the last event.
          const remaining = buffer.trim();
          if (remaining) processLine(remaining);
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // keep last incomplete chunk

        for (const line of lines) {
          processLine(line);
        }
      }

      // Stream closed without a result event (server crash, timeout, or network drop).
      // reject() is a no-op if resolve() was already called — this only fires in the error path.
      reject(new Error('The server closed the connection before returning a response.'));
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
        signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const err = new Error(errorData.detail || errorData.error || `HTTP error! status: ${response.status}`);
        err.status = response.status;
        throw err;
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

export const deleteChat = async chatId => {
  await axios.delete(`${API_URL}/chats/${chatId}`);
};

export const getChatMessages = async chatId => {
  const response = await axios.get(`${API_URL}/chats/${chatId}/messages`);
  return response.data;
};

export const saveMessage = async (
  chatId,
  role,
  content,
  model = null,
  provider = null,
  cost_usd = null,
  sources = null
) => {
  const response = await axios.post(`${API_URL}/chats/${chatId}/messages`, {
    role,
    content,
    model,
    provider,
    cost_usd,
    sources,
  });
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

export const updatePreferences = async preferences => {
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

export const testLearningRetrieval = async query => {
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

export const getEfficiencyStats = async (days = 30) => {
  const response = await axios.get(`${API_URL}/stats/efficiency`, { params: { days } });
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

export const clearFeedbackData = async () => {
  const response = await axios.post(`${API_URL}/developer/clear-feedback`);
  return response.data;
};

export const submitFeedback = async payload => {
  const response = await axios.post(`${API_URL}/feedback`, payload);
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

export const getProductFeedback = async (days = '30') => {
  const response = await axios.get(`${API_URL}/feedback`, { params: { days } });
  return response.data;
};

export const getSurveyCompliance = async () => {
  const response = await axios.get(`${API_URL}/feedback/compliance`);
  return response.data;
};

export const getMessageRatings = async (days = '30') => {
  const response = await axios.get(`${API_URL}/feedback/message-ratings`, { params: { days } });
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

export const setActiveProvider = async activeProvider => {
  const response = await axios.post(`${API_URL}/developer/active-provider`, {
    active_provider: activeProvider,
  });
  return response.data;
};

export const getOpenRouterModels = async () => {
  const response = await axios.get(`${API_URL}/developer/openrouter-models`);
  return response.data;
};

// --- MATTERS ---
export const getMatters = async (includeClosed = false) => {
  const response = await axios.get(`${API_URL}/matters`, { params: includeClosed ? { include_closed: true } : {} });
  return response.data;
};

export const createMatter = async (title, description = null, jurisdiction = null, legislation_type = null) => {
  const response = await axios.post(`${API_URL}/matters`, { title, description, jurisdiction, legislation_type });
  return response.data;
};

export const updateMatter = async (matterId, data) => {
  const response = await axios.put(`${API_URL}/matters/${matterId}`, data);
  return response.data;
};

export const deleteMatter = async matterId => {
  await axios.delete(`${API_URL}/matters/${matterId}`);
};

export const assignChatToMatter = async (chatId, matterId) => {
  const response = await axios.post(`${API_URL}/chats/${chatId}/matter`, { matter_id: matterId });
  return response.data;
};

export const getMatterNotes = async matterId => {
  const response = await axios.get(`${API_URL}/matters/${matterId}/notes`);
  return response.data;
};

export const addMatterNote = async (matterId, content, messageId = null) => {
  const response = await axios.post(`${API_URL}/matters/${matterId}/notes`, { content, message_id: messageId });
  return response.data;
};

export const deleteMatterNote = async (matterId, noteId) => {
  await axios.delete(`${API_URL}/matters/${matterId}/notes/${noteId}`);
};

export const generateMatterBrief = async (matterId, mode = 'brief') => {
  const response = await axios.post(`${API_URL}/matters/${matterId}/brief`, { mode });
  return response.data;
};

// --- DOCUMENTS ---
export const uploadDocument = async (chatId, file) => {
  const form = new FormData();
  form.append('file', file);
  const response = await axios.post(`${API_URL}/chats/${chatId}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getChatDocuments = async chatId => {
  const response = await axios.get(`${API_URL}/chats/${chatId}/documents`);
  return response.data;
};

export const deleteDocument = async docId => {
  await axios.delete(`${API_URL}/documents/${docId}`);
};

// --- FEATURE FLAGS ---
export const getFeatures = async () => {
  const response = await axios.get(`${API_URL}/developer/features`);
  return response.data;
};

export const saveFeatures = async features => {
  const response = await axios.post(`${API_URL}/developer/features`, features);
  return response.data;
};

export const getActivityLog = async (days = '7', limit = 500) => {
  const response = await axios.get(`${API_URL}/developer/activity-log`, {
    params: { days, limit },
  });
  return response.data;
};

// --- BOT IDENTITY ---
export const fetchBotInfo = () => axios.get(`${API_URL}/bot-info`).then(r => r.data);

// --- PEER REGISTRY ---
export const getPeers = () => axios.get(`${API_URL}/peers`).then(r => r.data);
export const createPeer = data => axios.post(`${API_URL}/peers`, data).then(r => r.data);
export const updatePeer = (peerId, data) => axios.put(`${API_URL}/peers/${peerId}`, data).then(r => r.data);
export const deletePeer = peerId => axios.delete(`${API_URL}/peers/${peerId}`);
