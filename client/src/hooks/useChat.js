import { useState, useEffect, useRef } from 'react';
import {
  getModels,
  createChat,
  saveMessage,
  sendMessage,
  getChatMessages,
  getChatDocuments,
} from '../services/api';

// Core chat flow, moved from App.jsx: the message list + composer input, the
// active model/provider, streaming status, and the four handlers (send, stop,
// new chat, load chat). handleSend drives the SSE stream from `sendMessage`.
//
// The hook owns chat state but coordinates with adjacent concerns it cannot own
// — research filters (read at send time), preferences (chatMode/researchMode),
// the sources highlight, the document list, and the history modal — which are
// passed in. Handlers stay plain functions (recreated each render) so their
// closures see the current values, matching the original component behaviour.
// currentChatId/currentChatTitle are owned by App (shared with the filters and
// matters hooks as a coordination key) and passed in with their setters.
export function useChat({
  user,
  logoutWithExpiry,
  chatMode,
  researchMode,
  filters,
  saveFiltersToChatStorage,
  restoreFiltersForChat,
  currentChatId,
  setCurrentChatId,
  setCurrentChatTitle,
  setActiveCite,
  setActiveSourcesMsgId,
  setChatDocuments,
  closeHistoryModal,
  recentChats,
  matters,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedModelContext, setSelectedModelContext] = useState(256 * 1024);
  const [activeProvider, setActiveProvider] = useState('ollama');
  const [loading, setLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState('');
  const [activities, setActivities] = useState(new Map());
  // context usage is written from the response but not currently read anywhere
  const [, setContextUsage] = useState(null);

  const chatScrollRef = useRef(null);
  const textareaRef = useRef(null);
  const abortControllerRef = useRef(null);
  const sendingRef = useRef(false);

  // Fetch the model list once logged in (/api/models requires auth)
  useEffect(() => {
    if (!user) return;
    getModels()
      .then(models => {
        if (models?.length) {
          const active = models.find(m => m.active) || models[0];
          setSelectedModel(active.name);
          setSelectedModelContext(active.context_length || 256 * 1024);
          setActiveProvider(active.provider || 'ollama');
        }
      })
      .catch(err => {
        console.warn('Failed to fetch model list, using fallback:', err);
        setSelectedModel('mistral-large-3:675b-cloud');
      });
  }, [user]);

  // Keep the transcript scrolled to the newest content
  useEffect(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    const target = el.scrollHeight - el.clientHeight;
    if (target > el.scrollTop) el.scrollTo({ top: target, behavior: 'smooth' });
  }, [messages, agentStatus]);

  // Auto-resize the composer textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px';
  }, [input]);

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setLoading(false);
      sendingRef.current = false;
      setAgentStatus('Stopped by user.');
      setActivities(new Map());
    }
  };

  const handleSend = async (manualContent = null) => {
    if (sendingRef.current) return;
    const contentToSend = typeof manualContent === 'string' ? manualContent : input;
    if (!contentToSend.trim() || !selectedModel) return;
    sendingRef.current = true;

    if (abortControllerRef.current) abortControllerRef.current.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const userMsg = { role: 'user', content: contentToSend };
    setMessages(prev => [...prev, userMsg]);
    if (typeof manualContent !== 'string') setInput('');
    setLoading(true);
    setAgentStatus('Thinking…');
    setActivities(new Map());
    const requestStartTime = Date.now();
    let activeChatId = currentChatId;

    try {
      if (!activeChatId) {
        const title = contentToSend.slice(0, 80) + (contentToSend.length > 80 ? '…' : '');
        const newChat = await createChat(title, selectedModel, activeProvider);
        activeChatId = newChat.id;
        setCurrentChatId(activeChatId);
        setCurrentChatTitle(title);
        saveFiltersToChatStorage(activeChatId);
      }

      if (activeChatId) {
        await saveMessage(activeChatId, 'user', contentToSend).catch(err =>
          console.error('Failed to save user message:', err)
        );
      }

      const messagesToSend = [...messages, userMsg];
      const response = await sendMessage(
        messagesToSend,
        selectedModel,
        selectedModelContext,
        status => {
          const toolLabel = tool =>
            ({
              'Research Agent': 'Researching…',
              'Worker: search_legislation': 'Querying legislation database…',
              'Worker: search_legislation_sections': 'Retrieving statutory sections…',
              'Worker: get_legislation_text': 'Reviewing statutory text…',
              'Worker: search_case_law': 'Searching case law database…',
              'Worker: get_case_law_text': 'Retrieving case law judgment…',
              'Extracting the relevant sections from a large document': 'Summarising document…',
            })[tool] || `${tool}…`;

          if (status.type === 'tool_start') {
            const label = toolLabel(status.tool);
            if (status.id) {
              setActivities(prev => new Map(prev).set(status.id, label));
            }
            setAgentStatus(label);
          } else if (status.type === 'tool_end') {
            if (status.id) {
              setActivities(prev => {
                const next = new Map(prev);
                next.delete(status.id);
                return next;
              });
            }
            setAgentStatus('Analysing findings…');
          } else if (status.type === 'token') {
            setActivities(new Map());
            setAgentStatus('Typing…');
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last.role === 'assistant') {
                updated[updated.length - 1] = { ...last, content: last.content + status.content };
              } else {
                updated.push({ role: 'assistant', content: status.content });
              }
              return updated;
            });
          } else if (status.type === 'queue') {
            setAgentStatus(status.message);
          } else if (status.type === 'warning') {
            setAgentStatus(status.message);
          }
        },
        controller.signal,
        chatMode,
        researchMode,
        {
          jurisdiction: filters.jurisdiction,
          dateFrom: filters.dateFrom,
          dateTo: filters.dateTo,
          caseLawCourt: filters.caseLawCourt,
          legislationType: filters.legislationType,
          currentOnly: filters.currentOnly,
          recordType: filters.recordType,
          chatId: activeChatId,
        }
      );

      if (response.stats) setContextUsage(response.stats);

      const withTiming = {
        ...response,
        responseTimeMs: Date.now() - requestStartTime,
        costUsd: response.timing?.total_cost_usd || null,
      };
      setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === 'assistant') {
          updated[updated.length - 1] = withTiming;
          return updated;
        }
        return [...updated, withTiming];
      });

      if (activeChatId) {
        const saved = await saveMessage(
          activeChatId,
          'assistant',
          response.content,
          response.model,
          response.provider,
          response.timing?.total_cost_usd ?? null,
          response.sources ?? null
        ).catch(err => {
          console.error('Failed to save assistant message:', err);
          return null;
        });
        if (saved) {
          setMessages(prev => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === 'assistant' && !updated[i].id) {
                updated[i] = {
                  ...saved,
                  responseTimeMs: updated[i].responseTimeMs,
                  costUsd: updated[i].costUsd,
                  sources: updated[i].sources,
                };
                break;
              }
            }
            return updated;
          });
          if (response.sources?.length) setActiveSourcesMsgId(saved.id);
        }
      }
    } catch (error) {
      if (error.name === 'AbortError' || error.message.includes('aborted') || error.message.includes('canceled')) {
        // stopped by user
      } else if (error.status === 401) {
        logoutWithExpiry();
      } else {
        console.error('Error sending message:', error);
        const match = error.message.match(/status code (\d{3})/);
        const errText = match
          ? `Error: ${{ 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 408: 'Request Timeout', 429: 'Too Many Requests', 500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable', 504: 'Gateway Timeout' }[parseInt(match[1])] || 'Unknown Error'} (${match[1]})`
          : `Error: ${error.message}`;
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          const errMsg = { role: 'assistant', content: errText };
          if (last.role === 'assistant') {
            updated[updated.length - 1] = errMsg;
            return updated;
          }
          return [...updated, errMsg];
        });
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
        setAgentStatus('');
        setActivities(new Map());
        abortControllerRef.current = null;
        sendingRef.current = false;
        setTimeout(() => textareaRef.current?.focus(), 0);
      }
    }
  };

  const handleNewChat = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setMessages([]);
    setInput('');
    setContextUsage(null);
    setCurrentChatId(null);
    setCurrentChatTitle(null);
    setActiveCite(null);
    setActiveSourcesMsgId(null);
    setChatDocuments([]);
  };

  const loadChat = async chatId => {
    try {
      setLoading(true);
      const msgs = await getChatMessages(chatId);
      setMessages(msgs);
      setCurrentChatId(chatId);
      setCurrentChatTitle(recentChats.find(c => c.id === chatId)?.title || null);
      closeHistoryModal();
      setContextUsage(null);
      setActiveCite(null);
      setActiveSourcesMsgId(null);
      setChatDocuments([]);
      getChatDocuments(chatId)
        .then(setChatDocuments)
        .catch(err => console.warn('Failed to fetch chat documents:', err));
      const chatMatterId = recentChats.find(c => c.id === chatId)?.matter_id;
      const chatMatter = chatMatterId ? matters.find(m => m.id === chatMatterId) : null;
      restoreFiltersForChat(chatId, chatMatter);
    } catch (err) {
      console.error('Failed to load chat', err);
    } finally {
      setLoading(false);
    }
  };

  // Clear chat state on logout (called from App's reset effect). Mirrors the
  // original inline reset — does not abort the controller (handleNewChat does).
  const resetChat = () => {
    setMessages([]);
    setInput('');
    setCurrentChatId(null);
    setCurrentChatTitle(null);
    setContextUsage(null);
    setAgentStatus('');
    setActivities(new Map());
    setLoading(false);
  };

  return {
    messages,
    input,
    setInput,
    selectedModel,
    activeProvider,
    loading,
    agentStatus,
    activities,
    chatScrollRef,
    textareaRef,
    handleSend,
    handleStop,
    handleNewChat,
    loadChat,
    resetChat,
  };
}
