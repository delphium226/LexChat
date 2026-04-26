import React, { useState, useEffect, useRef, useMemo } from 'react';
import { sendMessage, createChat, getChatMessages, saveMessage, updatePreferences, submitFeedback, getModels, getChats } from './services/api';
import ChatMessage from './components/ChatMessage';
import { LexMark, LexWordmark } from './components/LexMark';
import SourcesRail from './components/SourcesRail';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginModal from './components/LoginModal';
import AdminPortal from './pages/AdminPortal';
import Settings from './pages/Settings';
import HistoryModal from './components/HistoryModal';
import SettingsMenuModal from './components/SettingsMenuModal';
import { Routes, Route } from 'react-router-dom';
import SystemChat from './pages/SystemChat';

// ── Helpers ────────────────────────────────────────────────────

function getInitials(username) {
  if (!username) return '?';
  const parts = username.trim().split(/[\s._-]+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return username.slice(0, 2).toUpperCase();
}

function formatRelativeTime(isoDate) {
  if (!isoDate) return '';
  const now = new Date();
  const date = new Date(isoDate);
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 5) return 'Just now';
  if (diffMins < 60) return `${diffMins}m`;
  if (diffHours < 24) return `${diffHours}h`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return date.toLocaleDateString('en-GB', { weekday: 'short' });
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

// ── Icons ──────────────────────────────────────────────────────

const PlusIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14M5 12h14" />
  </svg>
);

const SearchIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="7" /><path d="M16.5 16.5 21 21" />
  </svg>
);

const FolderIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
  </svg>
);

const SettingsIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </svg>
);

const SidebarIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" />
  </svg>
);

const BookmarkIcon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 3h12v18l-6-4-6 4z" />
  </svg>
);

const Share2Icon = () => (
  <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="18" cy="5" r="2.5" /><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="19" r="2.5" />
    <path d="M8.2 10.8 15.8 6.2M8.2 13.2l7.6 4.6" />
  </svg>
);

const ScalesIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v18M5 21h14M6 7h12M6 7l-3 7a3 3 0 0 0 6 0z" />
    <path d="M18 7l-3 7a3 3 0 0 0 6 0z" />
  </svg>
);

const GavelIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 3l7 7-4 4-7-7z" />
    <path d="M10 7 3 14l4 4 7-7" />
    <path d="M5 21h10" />
  </svg>
);

const CalendarIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" />
  </svg>
);

const PaperclipIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.5 12.5 21a5.5 5.5 0 0 1-7.8-7.8l9-9a3.7 3.7 0 0 1 5.2 5.2l-9 9a1.8 1.8 0 1 1-2.6-2.6l8-8" />
  </svg>
);

const SlidersIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 5h18l-7 9v5l-4 2v-7L3 5z" />
  </svg>
);

const SendIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 12l18-8-8 18-2-8-8-2z" />
  </svg>
);

const StopIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <rect x="5" y="5" width="14" height="14" rx="2" />
  </svg>
);

const ChevRightIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 6l6 6-6 6" />
  </svg>
);

// ── Small reusable button primitives ───────────────────────────

function IBtn({ children, label, onClick, size = 30 }) {
  const [h, setH] = React.useState(false);
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        width: size, height: size, borderRadius: 8, border: 'none',
        background: h ? 'var(--ink-100)' : 'transparent',
        color: 'var(--ink-600)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', transition: 'background 120ms', flexShrink: 0,
      }}
    >{children}</button>
  );
}

function GhostBtn({ children, icon, onClick }) {
  const [h, setH] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '6px 10px', fontSize: 13, fontWeight: 500,
        background: h ? 'var(--ink-100)' : 'transparent',
        color: 'var(--ink-700)', border: '1px solid var(--ink-200)',
        borderRadius: 8, cursor: 'pointer', transition: 'background 120ms',
        fontFamily: 'var(--font-ui)',
      }}
    >{icon}{children}</button>
  );
}

// ── Feedback Modal ─────────────────────────────────────────────

const FeedbackModal = ({ onClose }) => {
  const [text, setText] = React.useState('');
  const [status, setStatus] = React.useState('idle');

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setStatus('submitting');
    try {
      await submitFeedback(text.trim());
      setStatus('success');
    } catch {
      setStatus('error');
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-lg w-full shadow-xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">Give Feedback</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 focus:outline-none text-xl leading-none">&times;</button>
        </div>
        {status === 'success' ? (
          <div className="text-center py-6">
            <p className="text-green-600 font-medium text-lg mb-2">Thank you for your feedback!</p>
            <p className="text-gray-500 text-sm mb-6">Your response has been recorded.</p>
            <button onClick={onClose} className="px-6 py-2 bg-brand-navy text-white rounded-md hover:bg-brand-navy-dark transition-colors text-sm font-medium">Close</button>
          </div>
        ) : (
          <>
            <p className="text-sm text-gray-600 mb-4">Share any thoughts, suggestions, or issues with LexChat.</p>
            <textarea
              className="w-full border border-gray-300 rounded-md p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={6}
              placeholder="Describe your experience, suggest a feature, or report a problem..."
              value={text}
              onChange={e => setText(e.target.value)}
              disabled={status === 'submitting'}
              autoFocus
            />
            {status === 'error' && <p className="text-red-500 text-xs mt-2">Something went wrong. Please try again.</p>}
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">Cancel</button>
              <button
                onClick={handleSubmit}
                disabled={!text.trim() || status === 'submitting'}
                className="px-5 py-2 bg-brand-navy text-white rounded-md hover:bg-brand-navy-dark transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status === 'submitting' ? 'Submitting…' : 'Submit Feedback'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

// ── Main app ───────────────────────────────────────────────────

function AppContent() {
  const { user, logout } = useAuth();

  // ── Chat state ───────────────────────────────────────────────
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedModelContext, setSelectedModelContext] = useState(256 * 1024);
  const [activeProvider, setActiveProvider] = useState('ollama');
  const [loading, setLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState('');
  const [contextUsage, setContextUsage] = useState(null);
  const [showThinking] = useState(false);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [currentChatTitle, setCurrentChatTitle] = useState(null);
  const [researchMode, setResearchMode] = useState('legislation_only');

  // ── UI state ─────────────────────────────────────────────────
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    localStorage.getItem('sidebarCollapsed') === 'true'
  );
  const [recentChats, setRecentChats] = useState([]);
  const [activeCite, setActiveCite] = useState(null);
  const [showFilters, setShowFilters] = useState(false);

  // ── Modal state ──────────────────────────────────────────────
  const [showSettingsMenu, setShowSettingsMenu] = useState(false);
  const [showAdminModal, setShowAdminModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('darkMode');
      if (saved !== null) return saved === 'true';
    }
    return false;
  });

  // ── Refs ─────────────────────────────────────────────────────
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  const sendingRef = useRef(false);
  const textareaRef = useRef(null);
  const composerRef = useRef(null);

  // ── Effects ──────────────────────────────────────────────────

  useEffect(() => {
    getModels().then(models => {
      if (models?.length) {
        const active = models.find(m => m.active) || models[0];
        setSelectedModel(active.name);
        setSelectedModelContext(active.context_length || 256 * 1024);
        setActiveProvider(active.provider || 'ollama');
      }
    }).catch(() => setSelectedModel('mistral-large-3:675b-cloud'));
  }, []);

  useEffect(() => {
    if (!user) return;
    if (user.dark_mode !== undefined) setDarkMode(user.dark_mode);
    if (user.research_mode) setResearchMode(user.research_mode);
  }, [user]);

  useEffect(() => {
    if (darkMode) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentStatus]);

  // Reload recent chats whenever active chat changes or user logs in
  useEffect(() => {
    if (!user) return;
    getChats().then(chats => setRecentChats(chats.slice(0, 12))).catch(() => {});
  }, [user, currentChatId]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 180) + 'px';
  }, [input]);

  // Close filters popover on outside click
  useEffect(() => {
    if (!showFilters) return;
    const handler = e => {
      if (composerRef.current && !composerRef.current.contains(e.target)) {
        setShowFilters(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showFilters]);

  // Favicon animation while loading
  useEffect(() => {
    const favicon = document.querySelector("link[rel='icon']");
    if (!favicon) return;
    if (!loading) { favicon.href = '/favicon.png'; return; }

    const canvas = document.createElement('canvas');
    canvas.width = 32; canvas.height = 32;
    const ctx = canvas.getContext('2d');
    let animId, startTime = null;

    const draw = (ts) => {
      if (!startTime) startTime = ts;
      const angle = ((ts - startTime) / 700) * Math.PI * 2;
      ctx.clearRect(0, 0, 32, 32);
      ctx.beginPath(); ctx.arc(16, 16, 12, 0, Math.PI * 2);
      ctx.strokeStyle = '#dbeafe'; ctx.lineWidth = 3.5; ctx.stroke();
      ctx.beginPath(); ctx.arc(16, 16, 12, angle, angle + Math.PI * 1.25);
      ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 3.5; ctx.lineCap = 'round'; ctx.stroke();
      favicon.href = canvas.toDataURL('image/png');
      animId = requestAnimationFrame(draw);
    };

    animId = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(animId); favicon.href = '/favicon.png'; };
  }, [loading]);

  // Reset on logout
  useEffect(() => {
    if (!user) {
      setMessages([]); setInput(''); setCurrentChatId(null); setCurrentChatTitle(null);
      setContextUsage(null); setAgentStatus(''); setLoading(false);
      setShowSettingsMenu(false); setShowHistoryModal(false);
      setShowAdminModal(false); setShowSettingsModal(false);
      setResearchMode('legislation_only');
    }
  }, [user]);

  // ── Derived ──────────────────────────────────────────────────

  // Sources from the last assistant message that carries them
  const activeSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].sources?.length) {
        return messages[i].sources;
      }
    }
    return [];
  }, [messages]);

  const researchModeLabel = {
    legislation_only: 'Legislation only',
    case_law_only: 'Case law only',
    legislation_and_case_law: 'Legislation & case law',
  }[researchMode] || 'Legislation only';

  const todayISO = new Date().toISOString().slice(0, 10);
  const todayLabel = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

  const userInitials = getInitials(user?.username);

  // ── Handlers ─────────────────────────────────────────────────

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setLoading(false);
      sendingRef.current = false;
      setAgentStatus('Stopped by user.');
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
    const requestStartTime = Date.now();
    let activeChatId = currentChatId;

    try {
      if (!activeChatId) {
        const title = contentToSend.slice(0, 80) + (contentToSend.length > 80 ? '…' : '');
        const newChat = await createChat(title, selectedModel, activeProvider);
        activeChatId = newChat.id;
        setCurrentChatId(activeChatId);
        setCurrentChatTitle(title);
      }

      if (activeChatId) {
        await saveMessage(activeChatId, 'user', contentToSend).catch(err => console.error('Failed to save user message:', err));
      }

      const messagesToSend = [...messages, userMsg];
      const response = await sendMessage(
        messagesToSend, selectedModel, selectedModelContext,
        (status) => {
          if (status.type === 'tool_start') {
            const labels = {
              'Research Agent': 'Delegating to research agent…',
              'Worker: search_legislation': 'Querying legislation database…',
              'Worker: get_legislation_text': 'Reviewing statutory text…',
              'Worker: search_case_law': 'Searching case law database…',
              'search_legislation': 'Querying legislation database…',
              'get_legislation_text': 'Reviewing statutory text…',
              'search_case_law': 'Searching case law database…',
            };
            setAgentStatus(labels[status.tool] || `${status.tool}…`);
          } else if (status.type === 'tool_end') {
            setAgentStatus('Analysing findings…');
          } else if (status.type === 'token') {
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
        controller.signal, false, researchMode
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
        if (last.role === 'assistant') { updated[updated.length - 1] = withTiming; return updated; }
        return [...updated, withTiming];
      });

      if (activeChatId) {
        const saved = await saveMessage(activeChatId, 'assistant', response.content, response.model, response.provider, response.timing?.total_cost_usd ?? null).catch(err => { console.error('Failed to save assistant message:', err); return null; });
        if (saved) {
          setMessages(prev => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === 'assistant' && !updated[i].id) {
                updated[i] = { ...saved, responseTimeMs: updated[i].responseTimeMs, costUsd: updated[i].costUsd, sources: updated[i].sources };
                break;
              }
            }
            return updated;
          });
        }
      }
    } catch (error) {
      if (error.name === 'AbortError' || error.message.includes('aborted') || error.message.includes('canceled')) {
        // stopped by user
      } else {
        console.error('Error sending message:', error);
        const match = error.message.match(/status code (\d{3})/);
        const errText = match
          ? `Error: ${({ 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 408: 'Request Timeout', 429: 'Too Many Requests', 500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable', 504: 'Gateway Timeout' }[parseInt(match[1])] || 'Unknown Error')} (${match[1]})`
          : `Error: ${error.message}`;
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          const errMsg = { role: 'assistant', content: errText };
          if (last.role === 'assistant') { updated[updated.length - 1] = errMsg; return updated; }
          return [...updated, errMsg];
        });
      }
    } finally {
      if (abortControllerRef.current === controller) {
        setLoading(false);
        setAgentStatus('');
        abortControllerRef.current = null;
        sendingRef.current = false;
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
  };

  const loadChat = async (chatId, model) => {
    try {
      setLoading(true);
      const msgs = await getChatMessages(chatId);
      setMessages(msgs);
      setCurrentChatId(chatId);
      setCurrentChatTitle(recentChats.find(c => c.id === chatId)?.title || null);
      setShowHistoryModal(false);
      setContextUsage(null);
      setActiveCite(null);
    } catch (err) {
      console.error('Failed to load chat', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleSidebar = () => {
    const next = !sidebarCollapsed;
    setSidebarCollapsed(next);
    localStorage.setItem('sidebarCollapsed', next);
  };

  // ── Auth gate ─────────────────────────────────────────────────

  if (!user) return <LoginModal />;

  // ── Render ────────────────────────────────────────────────────

  return (
    <div style={{
      display: 'flex', height: '100dvh',
      background: 'var(--ink-50)',
      fontFamily: 'var(--font-ui)',
      color: 'var(--ink-900)',
      overflow: 'hidden',
    }}>

      {/* ── Sidebar ───────────────────────────────────────────── */}
      <aside style={{
        width: sidebarCollapsed ? 52 : 244,
        flex: `0 0 ${sidebarCollapsed ? 52 : 244}px`,
        height: '100%',
        background: 'var(--paper)',
        borderRight: '1px solid var(--ink-200)',
        display: 'flex', flexDirection: 'column',
        fontSize: 13,
        transition: 'width 200ms ease, flex-basis 200ms ease',
        overflow: 'hidden',
      }}>
        {/* Brand row */}
        <div style={{
          padding: sidebarCollapsed ? '14px 0 10px' : '14px 14px 10px',
          display: 'flex', alignItems: 'center',
          justifyContent: sidebarCollapsed ? 'center' : 'space-between',
          flexShrink: 0,
        }}>
          {sidebarCollapsed
            ? <LexMark size={20} color="var(--accent)" />
            : <LexWordmark size={16} />
          }
          {!sidebarCollapsed && (
            <IBtn label="Collapse sidebar" onClick={toggleSidebar}><SidebarIcon /></IBtn>
          )}
        </div>

        {sidebarCollapsed ? (
          /* Icon-only collapsed state */
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '4px 0', flex: 1 }}>
            <IBtn label="Expand sidebar" onClick={toggleSidebar}><SidebarIcon /></IBtn>
            <IBtn label="New research thread" onClick={handleNewChat}><PlusIcon /></IBtn>
            <IBtn label="Search threads" onClick={() => setShowHistoryModal(true)}><SearchIcon /></IBtn>
            <div style={{ flex: 1 }} />
            <div
              onClick={() => setShowSettingsMenu(true)}
              style={{
                width: 28, height: 28, borderRadius: '50%',
                background: 'var(--accent-ink)', color: 'white',
                display: 'grid', placeItems: 'center',
                fontSize: 11, fontWeight: 600, cursor: 'pointer', marginBottom: 12,
              }}
            >{userInitials}</div>
          </div>
        ) : (
          /* Full expanded state */
          <>
            {/* New research thread */}
            <div style={{ padding: '4px 10px 8px', flexShrink: 0 }}>
              <button
                onClick={handleNewChat}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 10px', borderRadius: 8, border: '1px solid var(--ink-200)',
                  background: 'var(--paper)', color: 'var(--ink-800)', fontWeight: 500,
                  cursor: 'pointer', fontSize: 13, justifyContent: 'space-between',
                  boxShadow: 'var(--shadow-sm)', fontFamily: 'var(--font-ui)',
                }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <PlusIcon /> New research thread
                </span>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 11,
                  padding: '1px 5px', borderRadius: 4,
                  background: 'var(--ink-100)', color: 'var(--ink-600)',
                  border: '1px solid var(--ink-200)',
                }}>⌘K</span>
              </button>
            </div>

            {/* Search threads */}
            <div style={{ padding: '0 10px 10px', flexShrink: 0 }}>
              <div
                onClick={() => setShowHistoryModal(true)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 10px', borderRadius: 8,
                  background: 'var(--ink-50)', color: 'var(--ink-500)',
                  fontSize: 13, cursor: 'pointer',
                }}
              >
                <SearchIcon /><span>Search threads…</span>
              </div>
            </div>

            {/* Matters section */}
            <div style={{ padding: '8px 16px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-500)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Matters</span>
              <IBtn label="Add matter" size={22}><PlusIcon /></IBtn>
            </div>
            <div style={{ padding: '0 8px 4px', flexShrink: 0 }}>
              <div style={{ padding: '8px 10px', color: 'var(--ink-400)', fontSize: 12, fontStyle: 'italic' }}>
                No matters yet
              </div>
            </div>

            {/* Divider */}
            <div style={{ height: 1, background: 'var(--ink-200)', margin: '4px 14px', flexShrink: 0 }} />

            {/* Recent section */}
            <div style={{ padding: '8px 16px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-500)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Recent</span>
            </div>

            <div className="lex-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 8px' }}>
              {recentChats.length === 0 && (
                <div style={{ padding: '8px 8px', color: 'var(--ink-400)', fontSize: 12, fontStyle: 'italic' }}>No recent threads</div>
              )}
              {recentChats.map(chat => {
                const active = chat.id === currentChatId;
                return (
                  <div
                    key={chat.id}
                    onClick={() => loadChat(chat.id, chat.model)}
                    style={{
                      padding: '6px 8px', borderRadius: 6, marginBottom: 1,
                      background: active ? 'var(--ink-100)' : 'transparent',
                      color: active ? 'var(--ink-900)' : 'var(--ink-700)',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{
                      fontSize: 13, fontWeight: active ? 500 : 400,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>{chat.title}</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-400)', marginTop: 1 }}>
                      {formatRelativeTime(chat.created_at)}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Footer */}
            <div style={{ height: 1, background: 'var(--ink-200)', flexShrink: 0 }} />
            <div style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
              <div style={{
                width: 26, height: 26, borderRadius: '50%',
                background: 'var(--accent-ink)', color: 'white',
                display: 'grid', placeItems: 'center',
                fontSize: 11, fontWeight: 600, flexShrink: 0,
              }}>{userInitials}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-900)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.username}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-500)' }}>{user.role === 'admin' ? 'Admin' : 'Lawyer'}</div>
              </div>
              <IBtn label="Settings" onClick={() => setShowSettingsMenu(true)}><SettingsIcon /></IBtn>
            </div>
          </>
        )}
      </aside>

      {/* ── Main content ──────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {/* Top bar */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 24px',
          borderBottom: '1px solid var(--ink-200)',
          background: 'var(--paper)',
          height: 52, flex: '0 0 52px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <span style={{ fontSize: 13, color: 'var(--ink-500)', flexShrink: 0 }}>Research</span>
            <span style={{ color: 'var(--ink-300)', flexShrink: 0 }}>/</span>
            <span style={{
              fontSize: 14, fontWeight: 500, color: 'var(--ink-900)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {currentChatTitle || 'New thread'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <GhostBtn icon={<BookmarkIcon />}>Save to matter</GhostBtn>
            <GhostBtn icon={<Share2Icon />}>Share</GhostBtn>
          </div>
        </div>

        {/* Content area: chat column + sources rail */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>

          {/* Chat column */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>

            {/* Scroll area */}
            <div
              className="lex-scroll"
              style={{ flex: 1, overflow: 'auto', padding: '20px 28px 140px' }}
            >
              <div style={{ maxWidth: 680, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 18 }}>

                {/* Research context chips */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', paddingBottom: 4 }}>
                  {[
                    { icon: <ScalesIcon />, label: researchModeLabel },
                    { icon: <GavelIcon />, label: 'England & Wales' },
                    { icon: <CalendarIcon />, label: `In force · ${todayLabel}` },
                  ].map((chip, i) => (
                    <span key={i} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '3px 10px', borderRadius: 999, fontSize: 12, fontWeight: 500,
                      background: 'var(--paper)', border: '1px solid var(--ink-200)',
                      color: 'var(--ink-600)',
                    }}>
                      <span style={{ color: 'var(--ink-400)', display: 'inline-flex' }}>{chip.icon}</span>
                      {chip.label}
                    </span>
                  ))}
                </div>

                {/* Empty state */}
                {messages.length === 0 && !loading && (
                  <div style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--ink-400)' }}>
                    <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'center' }}>
                      <LexMark size={40} color="var(--ink-300)" />
                    </div>
                    <p style={{ fontSize: 14, margin: 0 }}>Ask about UK legislation or case law to begin.</p>
                  </div>
                )}

                {/* Messages */}
                {messages.map((msg, idx) => {
                  if (msg.role === 'tool') return null;
                  return (
                    <ChatMessage
                      key={idx}
                      message={msg}
                      onResend={() => handleSend(msg.content)}
                      showThinking={showThinking}
                      authorInitials={userInitials}
                    />
                  );
                })}

                {/* Loading indicator */}
                {loading && (
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 0', fontSize: 13, color: 'var(--ink-500)',
                  }}>
                    <div className="lex-thinking-dot" />
                    <span style={{ flex: 1 }}>{agentStatus || 'Thinking…'}</span>
                    <button
                      onClick={handleStop}
                      style={{
                        fontSize: 12, fontWeight: 500, padding: '4px 10px',
                        borderRadius: 6, border: '1px solid var(--ink-200)',
                        background: 'var(--paper)', color: 'var(--ink-600)',
                        cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5,
                        fontFamily: 'var(--font-ui)',
                      }}
                    >
                      <StopIcon /> Stop
                    </button>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Composer — overlaps scroll area with gradient */}
            <div
              ref={composerRef}
              style={{
                padding: '12px 28px 18px',
                background: 'linear-gradient(180deg, transparent, var(--ink-50) 36%)',
                marginTop: -120, position: 'relative', zIndex: 2,
              }}
            >
              <div style={{ maxWidth: 680, margin: '0 auto', position: 'relative' }}>

                {/* Filters popover */}
                {showFilters && (
                  <div style={{
                    position: 'absolute', bottom: '100%', left: 0, marginBottom: 8,
                    background: 'var(--paper)', border: '1px solid var(--ink-200)',
                    borderRadius: 10, boxShadow: 'var(--shadow-md)',
                    padding: 8, minWidth: 210, zIndex: 10,
                  }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '4px 8px 6px' }}>Research mode</div>
                    {[
                      { value: 'legislation_only', label: 'Legislation only' },
                      { value: 'case_law_only', label: 'Case law only' },
                      { value: 'legislation_and_case_law', label: 'Legislation & case law' },
                    ].map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => {
                          setResearchMode(opt.value);
                          updatePreferences({ research_mode: opt.value }).catch(() => {});
                          setShowFilters(false);
                        }}
                        style={{
                          display: 'block', width: '100%', textAlign: 'left',
                          padding: '7px 10px', borderRadius: 6, border: 'none',
                          background: researchMode === opt.value ? 'var(--accent-soft)' : 'transparent',
                          color: researchMode === opt.value ? 'var(--accent-ink)' : 'var(--ink-700)',
                          fontSize: 13, fontWeight: researchMode === opt.value ? 600 : 400,
                          cursor: 'pointer', fontFamily: 'var(--font-ui)',
                        }}
                      >{opt.label}</button>
                    ))}
                  </div>
                )}

                {/* Composer card */}
                <div style={{
                  background: 'var(--paper)',
                  border: '1px solid var(--ink-200)',
                  borderRadius: 12, padding: 12,
                  boxShadow: 'var(--shadow-sm)',
                }}>
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        if (!loading && input.trim()) handleSend();
                      }
                    }}
                    disabled={loading}
                    rows={1}
                    placeholder="Ask about UK legislation or case law…"
                    style={{
                      width: '100%', resize: 'none', border: 'none', outline: 'none',
                      fontSize: 14, lineHeight: 1.5, color: 'var(--ink-800)',
                      background: 'transparent', minHeight: 44, maxHeight: 180,
                      overflow: 'auto', fontFamily: 'var(--font-ui)',
                      padding: '8px 0 4px',
                    }}
                  />
                  <div style={{
                    display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between', marginTop: 6,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 2, color: 'var(--ink-500)' }}>
                      <IBtn label="Attach file"><PaperclipIcon /></IBtn>
                      <IBtn label="Research filters" onClick={() => setShowFilters(f => !f)}>
                        <SlidersIcon />
                      </IBtn>
                      <IBtn label="Point in time"><CalendarIcon /></IBtn>
                      <span style={{ fontSize: 12, color: 'var(--ink-500)', marginLeft: 6, fontFamily: 'var(--font-mono)' }}>
                        E&amp;W · {todayISO}
                      </span>
                    </div>

                    {loading ? (
                      <button
                        onClick={handleStop}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          padding: '7px 14px', fontSize: 13, fontWeight: 600,
                          background: 'var(--danger)', color: 'white',
                          border: 'none', borderRadius: 8, cursor: 'pointer',
                          fontFamily: 'var(--font-ui)',
                        }}
                      >
                        <StopIcon /> Stop
                      </button>
                    ) : (
                      <button
                        onClick={() => { if (input.trim()) handleSend(); }}
                        disabled={!input.trim()}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          padding: '7px 14px', fontSize: 13, fontWeight: 600,
                          background: input.trim() ? 'var(--accent)' : 'var(--ink-200)',
                          color: input.trim() ? 'white' : 'var(--ink-400)',
                          border: 'none', borderRadius: 8,
                          cursor: input.trim() ? 'pointer' : 'not-allowed',
                          transition: 'background 120ms',
                          fontFamily: 'var(--font-ui)',
                        }}
                      >
                        <SendIcon /> Send
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Sources rail */}
          <SourcesRail
            sources={activeSources}
            activeCite={activeCite}
            onCiteClick={setActiveCite}
          />
        </div>
      </div>

      {/* ── Modals ───────────────────────────────────────────── */}

      {showFeedbackModal && <FeedbackModal onClose={() => setShowFeedbackModal(false)} />}

      {showAbout && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-2xl w-full shadow-xl">
            <div className="flex items-center justify-center gap-2 mb-4">
              <LexMark size={32} color="var(--accent)" />
              <h1 className="text-3xl font-bold" style={{ color: 'var(--accent)' }}>LexChat</h1>
            </div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">About LexChat</h2>
              <button onClick={() => setShowAbout(false)} className="text-gray-400 hover:text-gray-600 focus:outline-none">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4 text-gray-700 dark:text-gray-300 text-sm">
              <p><strong>LexChat</strong> is an intelligent legal research assistant for UK legislation and case law.</p>
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-1">Data Sources</h3>
                <ul className="list-disc list-inside"><li><strong>The National Archives</strong> (legislation.gov.uk)</li></ul>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-1">AI Approach</h3>
                <p>Agentic RAG architecture — the system queries the LEX API and uses an LLM to provide accurate, context-aware answers.</p>
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <button onClick={() => setShowAbout(false)} className="bg-brand-navy text-white px-4 py-2 rounded-md hover:bg-brand-navy-dark transition-colors">Close</button>
            </div>
          </div>
        </div>
      )}

      {showAdminModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-[95vw] h-[95vh] overflow-y-auto shadow-xl relative">
            <button onClick={() => setShowAdminModal(false)} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 focus:outline-none">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <AdminPortal currentUser={user} />
          </div>
        </div>
      )}

      {showSettingsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-lg w-full shadow-xl relative">
            <button onClick={() => setShowSettingsModal(false)} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 focus:outline-none">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <Settings />
          </div>
        </div>
      )}

      {showHistoryModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full h-[80vh] shadow-xl relative overflow-hidden">
            <HistoryModal onClose={() => setShowHistoryModal(false)} onSelectChat={loadChat} />
          </div>
        </div>
      )}

      <SettingsMenuModal
        isOpen={showSettingsMenu}
        onClose={() => setShowSettingsMenu(false)}
        user={user}
        darkMode={darkMode}
        onToggleDarkMode={async () => {
          const next = !darkMode;
          setDarkMode(next);
          await updatePreferences({ dark_mode: next }).catch(e => console.error('Failed to save preference', e));
        }}
        onOpenAccountSettings={() => setShowSettingsModal(true)}
        onOpenAdminPortal={() => setShowAdminModal(true)}
        onOpenAbout={() => setShowAbout(true)}
        onGiveFeedback={() => setShowFeedbackModal(true)}
        onLogout={logout}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<AppContent />} />
        <Route path="/systemchat" element={<SystemChat />} />
      </Routes>
    </AuthProvider>
  );
}
