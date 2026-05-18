import React, { useState, useEffect, useRef, useMemo } from 'react';
import { sendMessage, createChat, getChatMessages, saveMessage, updatePreferences, submitFeedback, getModels, getChats, getMatters, updateMatter, assignChatToMatter, getFeatures, uploadDocument, getChatDocuments, deleteDocument, updateChatTitle } from './services/api';
import ChatMessage from './components/ChatMessage';
import { LexMark, LexWordmark } from './components/LexMark';
import SourcesRail from './components/SourcesRail';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginModal from './components/LoginModal';
import AdminPortal from './pages/AdminPortal';
import Settings from './pages/Settings';
import HistoryModal from './components/HistoryModal';
import SettingsMenuModal from './components/SettingsMenuModal';
import CreateMatterModal from './components/CreateMatterModal';
import MatterNotesModal from './components/MatterNotesModal';
import { Routes, Route } from 'react-router-dom';
import SystemChat from './pages/SystemChat';
import WeeklyFeedbackBanner from './components/WeeklyFeedbackBanner';

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

function GhostBtn({ children, icon, onClick, disabled, title }) {
  const [h, setH] = React.useState(false);
  return (
    <button
      onClick={disabled ? undefined : onClick}
      onMouseEnter={() => !disabled && setH(true)}
      onMouseLeave={() => setH(false)}
      title={title}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '6px 10px', fontSize: 13, fontWeight: 500,
        background: h ? 'var(--ink-100)' : 'transparent',
        color: disabled ? 'var(--ink-300)' : 'var(--ink-700)',
        border: '1px solid var(--ink-200)',
        borderRadius: 8, cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'background 120ms', opacity: disabled ? 0.6 : 1,
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
            <p className="text-sm text-gray-600 mb-4">Share any thoughts, suggestions, or issues with AILA.</p>
            <textarea
              className="w-full border border-gray-300 dark:border-gray-600 rounded-md p-3 text-sm text-gray-900 dark:text-white bg-white dark:bg-gray-700 placeholder-gray-400 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
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
  const [activities, setActivities] = useState(new Map());
  const [contextUsage, setContextUsage] = useState(null);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [currentChatTitle, setCurrentChatTitle] = useState(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [editTitleValue, setEditTitleValue] = useState('');
  const [researchMode, setResearchMode] = useState('legislation_only');
  const [jurisdiction, setJurisdiction] = useState(() => localStorage.getItem('filter_jurisdiction') || null);
  const [dateFrom, setDateFrom] = useState(() => localStorage.getItem('filter_dateFrom') || '');
  const [dateTo, setDateTo] = useState(() => localStorage.getItem('filter_dateTo') || String(new Date().getFullYear()));
  const [caseLawCourt, setCaseLawCourt] = useState(() => localStorage.getItem('filter_caseLawCourt') || '');
  const [legislationType, setLegislationType] = useState(() => localStorage.getItem('filter_legislationType') || null);
  const [currentOnly, setCurrentOnly] = useState(() => localStorage.getItem('filter_currentOnly') !== 'false');

  // ── UI state ─────────────────────────────────────────────────
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    localStorage.getItem('sidebarCollapsed') === 'true'
  );
  const [recentChats, setRecentChats] = useState([]);
  const [activeCite, setActiveCite] = useState(null);
  const [activeSourcesMsgId, setActiveSourcesMsgId] = useState(null);
  const [sourcesCollapsed, setSourcesCollapsed] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // ── Modal state ──────────────────────────────────────────────
  const [showSettingsMenu, setShowSettingsMenu] = useState(false);
  const [showAdminModal, setShowAdminModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [showDataSources, setShowDataSources] = useState(false);
  const [showWeeklyBanner, setShowWeeklyBanner] = useState(false);
  const weeklyBannerCheckedRef = useRef(false);

  // ── Matters state ────────────────────────────────────────────
  const [features, setFeatures] = useState({ matters_enabled: true });
  const [matters, setMatters] = useState([]);
  const [closedMatters, setClosedMatters] = useState([]);
  const [showClosedMatters, setShowClosedMatters] = useState(false);
  const [expandedMatterIds, setExpandedMatterIds] = useState(new Set());
  const [showCreateMatterModal, setShowCreateMatterModal] = useState(false);
  const [notesModalMatter, setNotesModalMatter] = useState(null);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [assigningChatId, setAssigningChatId] = useState(null);
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('darkMode');
      if (saved !== null) return saved === 'true';
    }
    return false;
  });

  // ── Document state ───────────────────────────────────────────
  const [chatDocuments, setChatDocuments] = useState([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);

  // ── Refs ─────────────────────────────────────────────────────
  const messagesEndRef = useRef(null);
  const chatScrollRef = useRef(null);
  const abortControllerRef = useRef(null);
  const sendingRef = useRef(false);
  const textareaRef = useRef(null);
  const composerRef = useRef(null);
  const fileInputRef = useRef(null);

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
    const el = chatScrollRef.current;
    if (!el) return;
    const target = el.scrollHeight - el.clientHeight;
    if (target > el.scrollTop) el.scrollTo({ top: target, behavior: 'smooth' });
  }, [messages, agentStatus]);

  // Fetch feature flags once on login
  useEffect(() => {
    if (!user) return;
    getFeatures().then(setFeatures).catch(() => {});
  }, [user]);

  // Reload chats and matters whenever active chat changes or user logs in
  useEffect(() => {
    if (!user) return;
    getChats().then(setRecentChats).catch(() => {});
    if (features.matters_enabled) getMatters().then(setMatters).catch(() => {});
  }, [user, currentChatId, features.matters_enabled]);

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
    if (!loading) { favicon.href = '/favicon.svg'; return; }

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
    return () => { cancelAnimationFrame(animId); favicon.href = '/favicon.svg'; };
  }, [loading]);

  // Reset on logout
  useEffect(() => {
    if (!user) {
      setMessages([]); setInput(''); setCurrentChatId(null); setCurrentChatTitle(null);
      setContextUsage(null); setAgentStatus(''); setActivities(new Map()); setLoading(false);
      setShowSettingsMenu(false); setShowHistoryModal(false);
      setShowAdminModal(false); setShowSettingsModal(false);
      setResearchMode('legislation_only');
      setMatters([]); setClosedMatters([]); setShowClosedMatters(false); setExpandedMatterIds(new Set());
      setShowWeeklyBanner(false); weeklyBannerCheckedRef.current = false;
    }
  }, [user]);

  // Weekly feedback banner — show once per week per user.
  // Uses a ref (not state) for the checked flag so setting it doesn't trigger
  // a re-render that would cancel the timer via effect cleanup.
  useEffect(() => {
    if (!user || weeklyBannerCheckedRef.current) return;
    weeklyBannerCheckedRef.current = true;
    const timer = setTimeout(() => {
      const key = `weeklyFeedbackLastShown_${user.id}`;
      const last = localStorage.getItem(key);
      if (!last || Date.now() - parseInt(last, 10) > 7 * 24 * 60 * 60 * 1000) {
        setShowWeeklyBanner(true);
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, [user]);

  // ── Derived ──────────────────────────────────────────────────

  // ID of the last assistant message that has sources (used for default highlight)
  const latestSourceMsgId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].sources?.length && messages[i].id) {
        return messages[i].id;
      }
    }
    return null;
  }, [messages]);

  // Sources for the rail — shows explicitly selected turn, else the latest turn
  const activeSources = useMemo(() => {
    if (activeSourcesMsgId != null) {
      const msg = messages.find(m => m.id === activeSourcesMsgId);
      if (msg?.sources?.length) return msg.sources;
    }
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].sources?.length) {
        return messages[i].sources;
      }
    }
    return [];
  }, [messages, activeSourcesMsgId]);

  const researchModeLabel = {
    legislation_only: 'Legislation only',
    case_law_only: 'Case law only',
    legislation_and_case_law: 'Legislation & case law',
  }[researchMode] || 'Legislation only';

  const todayISO = new Date().toISOString().slice(0, 10);
  const todayLabel = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

  const JURISDICTION_OPTIONS = [
    { value: null,                label: 'All jurisdictions' },
    { value: 'england_and_wales', label: 'England & Wales' },
    { value: 'scotland',          label: 'Scotland' },
    { value: 'northern_ireland',  label: 'Northern Ireland' },
    { value: 'wales',             label: 'Wales' },
    { value: 'uk_wide',           label: 'UK-wide only' },
  ];
  const JURISDICTION_SHORT = {
    england_and_wales: 'E&W', scotland: 'SCO', northern_ireland: 'NI', wales: 'WAL', uk_wide: 'UK',
  };
  const jurisdictionLabel = jurisdiction ? (JURISDICTION_OPTIONS.find(o => o.value === jurisdiction)?.label || 'All jurisdictions') : 'All jurisdictions';
  const jurisdictionShort = jurisdiction ? (JURISDICTION_SHORT[jurisdiction] || 'All UK') : 'All UK';

  const LEGISLATION_TYPE_OPTIONS = [
    { value: null,        label: 'All types' },
    { value: 'primary',   label: 'Acts (primary)' },
    { value: 'secondary', label: 'SIs & Rules (secondary)' },
    { value: 'draft',     label: 'Draft instruments' },
  ];

  const thisYear = String(new Date().getFullYear());
  const COURT_GROUPS = [
    { group: 'UK-wide', courts: [
      { value: 'uksc',      label: 'UK Supreme Court' },
      { value: 'ukpc',      label: 'Privy Council' },
    ]},
    { group: 'Court of Appeal', courts: [
      { value: 'ewca/civ',  label: 'Civil Division' },
      { value: 'ewca/crim', label: 'Criminal Division' },
    ]},
    { group: 'High Court', courts: [
      { value: 'ewhc/admin', label: 'Administrative Court' },
      { value: 'ewhc/qb',   label: "King's Bench" },
      { value: 'ewhc/ch',   label: 'Chancery' },
      { value: 'ewhc/fam',  label: 'Family' },
      { value: 'ewhc/comm', label: 'Commercial' },
      { value: 'ewhc/pat',  label: 'Patents' },
      { value: 'ewhc/tcc',  label: 'Technology & Construction' },
    ]},
    { group: 'Tribunals', courts: [
      { value: 'ukut',      label: 'Upper Tribunal' },
      { value: 'ukut/iac',  label: 'Immigration & Asylum' },
      { value: 'ukut/lc',   label: 'Lands Chamber' },
      { value: 'eat',       label: 'Employment Appeal' },
    ]},
  ];
  const courtLabel = caseLawCourt
    ? COURT_GROUPS.flatMap(g => g.courts).find(c => c.value === caseLawCourt)?.label || caseLawCourt
    : '';

  const saveFiltersToChatStorage = (chatId, overrides = {}) => {
    if (!chatId) return;
    const filters = { dateFrom, dateTo, jurisdiction, court: caseLawCourt, legislationType, currentOnly, ...overrides };
    localStorage.setItem(`filter_chat_${chatId}`, JSON.stringify(filters));
  };
  const setJurisdictionPersist = (v) => {
    setJurisdiction(v);
    if (v) localStorage.setItem('filter_jurisdiction', v);
    else localStorage.removeItem('filter_jurisdiction');
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { jurisdiction: v });
  };
  const setDateFromPersist = (v) => { setDateFrom(v); localStorage.setItem('filter_dateFrom', v); if (currentChatId) saveFiltersToChatStorage(currentChatId, { dateFrom: v }); };
  const setDateToPersist = (v) => { setDateTo(v); localStorage.setItem('filter_dateTo', v); if (currentChatId) saveFiltersToChatStorage(currentChatId, { dateTo: v }); };
  const setCourtPersist = (v) => { setCaseLawCourt(v); localStorage.setItem('filter_caseLawCourt', v); if (currentChatId) saveFiltersToChatStorage(currentChatId, { court: v }); };
  const setLegislationTypePersist = (v) => {
    setLegislationType(v);
    if (v) localStorage.setItem('filter_legislationType', v);
    else localStorage.removeItem('filter_legislationType');
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { legislationType: v });
  };
  const setCurrentOnlyPersist = (v) => {
    setCurrentOnly(v);
    localStorage.setItem('filter_currentOnly', String(v));
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { currentOnly: v });
  };
  const clearAllFilters = () => {
    setJurisdictionPersist(null);
    setDateFromPersist(''); setDateToPersist(thisYear);
    setCourtPersist('');
    setLegislationTypePersist(null);
    setCurrentOnlyPersist(false);
  };
  const hasActiveFilters = jurisdiction || dateFrom || dateTo !== thisYear || caseLawCourt || legislationType || currentOnly;

  const showScotlandNINote = (jurisdiction === 'scotland' || jurisdiction === 'northern_ireland')
    && researchMode !== 'legislation_only';

  const userInitials = getInitials(user?.username);

  // ── Handlers ─────────────────────────────────────────────────

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!fileInputRef.current) fileInputRef.current.value = '';
    if (!file) return;
    fileInputRef.current.value = '';

    setUploadingDoc(true);
    try {
      let activeChatId = currentChatId;
      if (!activeChatId) {
        const newChat = await createChat(file.name.slice(0, 80), selectedModel, activeProvider);
        activeChatId = newChat.id;
        setCurrentChatId(activeChatId);
        setCurrentChatTitle(newChat.title);
        saveFiltersToChatStorage(activeChatId);
      }
      const doc = await uploadDocument(activeChatId, file);
      setChatDocuments(prev => [...prev, doc]);
    } catch (err) {
      console.error('Document upload failed:', err);
      const msg = err.response?.data?.detail || err.message || 'Upload failed.';
      alert(msg);
    } finally {
      setUploadingDoc(false);
    }
  };

  const handleDeleteDocument = async (docId) => {
    try {
      await deleteDocument(docId);
      setChatDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (err) {
      console.error('Failed to delete document:', err);
    }
  };

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
        await saveMessage(activeChatId, 'user', contentToSend).catch(err => console.error('Failed to save user message:', err));
      }

      const messagesToSend = [...messages, userMsg];
      const response = await sendMessage(
        messagesToSend, selectedModel, selectedModelContext,
        (status) => {
          const toolLabel = (tool) => ({
            'Research Agent': 'Researching…',
            'Worker: search_legislation': 'Querying legislation database…',
            'Worker: search_legislation_sections': 'Retrieving statutory sections…',
            'Worker: get_legislation_text': 'Reviewing statutory text…',
            'Worker: search_case_law': 'Searching case law database…',
            'Extracting the relevant sections from a large document': 'Summarising document…',
          }[tool] || `${tool}…`);

          if (status.type === 'tool_start') {
            const label = toolLabel(status.tool);
            if (status.id) {
              setActivities(prev => new Map(prev).set(status.id, label));
            }
            setAgentStatus(label);
          } else if (status.type === 'tool_end') {
            if (status.id) {
              setActivities(prev => { const next = new Map(prev); next.delete(status.id); return next; });
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
        controller.signal, false, researchMode,
        { jurisdiction, dateFrom, dateTo, caseLawCourt, legislationType, currentOnly, chatId: activeChatId }
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
        const saved = await saveMessage(activeChatId, 'assistant', response.content, response.model, response.provider, response.timing?.total_cost_usd ?? null, response.sources ?? null).catch(err => { console.error('Failed to save assistant message:', err); return null; });
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
          if (response.sources?.length) setActiveSourcesMsgId(saved.id);
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
        setActivities(new Map());
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
    setActiveSourcesMsgId(null);
    setChatDocuments([]);
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
      setActiveSourcesMsgId(null);
      setChatDocuments([]);
      getChatDocuments(chatId).then(setChatDocuments).catch(() => {});
      const saved = localStorage.getItem(`filter_chat_${chatId}`);
      const savedFilters = saved ? (() => { try { return JSON.parse(saved); } catch { return {}; } })() : {};
      if (saved) {
        const f = savedFilters;
        if (f.dateFrom !== undefined) { setDateFrom(f.dateFrom); localStorage.setItem('filter_dateFrom', f.dateFrom); }
        if (f.dateTo !== undefined) { setDateTo(f.dateTo); localStorage.setItem('filter_dateTo', f.dateTo); }
        if (f.jurisdiction !== undefined) {
          setJurisdiction(f.jurisdiction);
          if (f.jurisdiction) localStorage.setItem('filter_jurisdiction', f.jurisdiction);
          else localStorage.removeItem('filter_jurisdiction');
        }
        if (f.court !== undefined) { setCaseLawCourt(f.court); localStorage.setItem('filter_caseLawCourt', f.court); }
        if (f.legislationType !== undefined) {
          setLegislationType(f.legislationType);
          if (f.legislationType) localStorage.setItem('filter_legislationType', f.legislationType);
          else localStorage.removeItem('filter_legislationType');
        }
        if (f.currentOnly !== undefined) {
          setCurrentOnly(f.currentOnly);
          localStorage.setItem('filter_currentOnly', String(f.currentOnly));
        }
      }
      // Apply matter-level defaults for any filter not already saved for this chat
      const chatMatterId = recentChats.find(c => c.id === chatId)?.matter_id;
      if (chatMatterId) {
        const chatMatter = matters.find(m => m.id === chatMatterId);
        if (chatMatter) {
          if (chatMatter.jurisdiction && savedFilters.jurisdiction === undefined) {
            setJurisdiction(chatMatter.jurisdiction);
            localStorage.setItem('filter_jurisdiction', chatMatter.jurisdiction);
          }
          if (chatMatter.legislation_type && savedFilters.legislationType === undefined) {
            setLegislationType(chatMatter.legislation_type);
            localStorage.setItem('filter_legislationType', chatMatter.legislation_type);
          }
        }
      }
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
      background: 'var(--bg-app)',
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
                  cursor: 'pointer', fontSize: 13,
                  boxShadow: 'var(--shadow-sm)', fontFamily: 'var(--font-ui)',
                }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <PlusIcon /> New research
                </span>
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
            {features.matters_enabled && (<>
            <div style={{ padding: '8px 16px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-500)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Matters</span>
              <IBtn label="Add matter" size={22} onClick={() => setShowCreateMatterModal(true)}><PlusIcon /></IBtn>
            </div>
            <div style={{ padding: '0 8px 4px', flexShrink: 0 }}>
              {matters.length === 0 ? (
                <div style={{ padding: '8px 10px', color: 'var(--ink-400)', fontSize: 12, fontStyle: 'italic' }}>No matters yet</div>
              ) : matters.map(matter => {
                const isExpanded = expandedMatterIds.has(matter.id);
                const matterChats = recentChats.filter(c => c.matter_id === matter.id);
                return (
                  <div key={matter.id}>
                    <div
                      onClick={() => {
                        const next = new Set(expandedMatterIds);
                        if (next.has(matter.id)) next.delete(matter.id); else next.add(matter.id);
                        setExpandedMatterIds(next);
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--ink-50)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 4,
                        padding: '5px 6px', borderRadius: 6, cursor: 'pointer',
                        color: 'var(--ink-700)',
                      }}
                    >
                      <span style={{
                        display: 'inline-flex', flexShrink: 0,
                        transform: isExpanded ? 'rotate(90deg)' : 'none',
                        transition: 'transform 150ms',
                      }}><ChevRightIcon /></span>
                      <span style={{ flexShrink: 0, display: 'inline-flex', color: 'var(--ink-500)' }}><FolderIcon /></span>
                      <span style={{
                        flex: 1, overflow: 'hidden', textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap', fontSize: 13,
                      }}>{matter.title}</span>
                      {matter.note_count > 0 && (
                        <span style={{
                          fontSize: 10, fontWeight: 600, color: 'var(--accent)',
                          background: 'var(--accent-soft)', borderRadius: 10,
                          padding: '1px 5px', flexShrink: 0,
                        }}>{matter.note_count}</span>
                      )}
                      <IBtn size={20} label="Notes" onClick={e => { e.stopPropagation(); setNotesModalMatter(matter); }}>
                        <BookmarkIcon />
                      </IBtn>
                      <IBtn size={20} label="Close matter" onClick={async e => {
                        e.stopPropagation();
                        await updateMatter(matter.id, { status: 'closed' });
                        setMatters(prev => prev.filter(m => m.id !== matter.id));
                        if (showClosedMatters) setClosedMatters(prev => [{ ...matter, status: 'closed' }, ...prev]);
                      }}>
                        <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </IBtn>
                    </div>
                    {isExpanded && (
                      matterChats.length === 0
                        ? <div style={{ paddingLeft: 28, fontSize: 12, color: 'var(--ink-400)', fontStyle: 'italic', padding: '3px 6px 3px 28px' }}>No threads assigned</div>
                        : matterChats.map(chat => {
                          const active = chat.id === currentChatId;
                          return (
                            <div
                              key={chat.id}
                              onClick={() => loadChat(chat.id, chat.model)}
                              style={{
                                padding: '5px 6px 5px 26px', borderRadius: 6, marginBottom: 1,
                                background: active ? 'var(--ink-100)' : 'transparent',
                                color: active ? 'var(--ink-900)' : 'var(--ink-700)',
                                cursor: 'pointer', fontSize: 13,
                                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              }}
                            >{chat.title}</div>
                          );
                        })
                    )}
                  </div>
                );
              })}
              {/* Closed matters toggle */}
              <div
                onClick={async () => {
                  if (!showClosedMatters) {
                    const all = await getMatters(true);
                    setClosedMatters(all.filter(m => m.status === 'closed'));
                  }
                  setShowClosedMatters(v => !v);
                }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '5px 6px', borderRadius: 6, cursor: 'pointer',
                  color: 'var(--ink-400)', fontSize: 12,
                }}
                onMouseEnter={e => e.currentTarget.style.color = 'var(--ink-600)'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--ink-400)'}
              >
                <span style={{ display: 'inline-flex', transform: showClosedMatters ? 'rotate(90deg)' : 'none', transition: 'transform 150ms' }}><ChevRightIcon /></span>
                Closed matters
              </div>
              {showClosedMatters && closedMatters.map(matter => (
                <div
                  key={matter.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    padding: '5px 6px', borderRadius: 6,
                    color: 'var(--ink-400)', opacity: 0.7,
                  }}
                >
                  <span style={{ flexShrink: 0, display: 'inline-flex' }}><FolderIcon /></span>
                  <span style={{
                    flex: 1, overflow: 'hidden', textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap', fontSize: 13,
                    textDecoration: 'line-through',
                  }}>{matter.title}</span>
                  <IBtn size={20} label="Reopen matter" onClick={async () => {
                    await updateMatter(matter.id, { status: 'open' });
                    setClosedMatters(prev => prev.filter(m => m.id !== matter.id));
                    setMatters(prev => [{ ...matter, status: 'open' }, ...prev]);
                  }}>
                    <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.48"/></svg>
                  </IBtn>
                </div>
              ))}
              {showClosedMatters && closedMatters.length === 0 && (
                <div style={{ padding: '4px 6px 4px 22px', color: 'var(--ink-400)', fontSize: 12, fontStyle: 'italic' }}>No closed matters</div>
              )}
            </div>
            </>)}

            {/* Divider */}
            <div style={{ height: 1, background: 'var(--ink-200)', margin: '4px 14px', flexShrink: 0 }} />

            {/* Recent section */}
            <div style={{ padding: '8px 16px 4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-500)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>Recent</span>
            </div>

            <div className="lex-scroll" style={{ flex: 1, overflow: 'auto', padding: '0 8px' }}>
              {recentChats.filter(c => !c.matter_id).length === 0 && (
                <div style={{ padding: '8px 8px', color: 'var(--ink-400)', fontSize: 12, fontStyle: 'italic' }}>No recent threads</div>
              )}
              {recentChats.filter(c => !c.matter_id).slice(0, 12).map(chat => {
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
            {editingTitle ? (
              <input
                autoFocus
                value={editTitleValue}
                onChange={e => setEditTitleValue(e.target.value)}
                onKeyDown={async e => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    const trimmed = editTitleValue.trim();
                    if (trimmed && trimmed !== currentChatTitle && currentChatId) {
                      await updateChatTitle(currentChatId, trimmed).catch(() => {});
                      setCurrentChatTitle(trimmed);
                    }
                    setEditingTitle(false);
                  } else if (e.key === 'Escape') {
                    setEditingTitle(false);
                  }
                }}
                onBlur={async () => {
                  const trimmed = editTitleValue.trim();
                  if (trimmed && trimmed !== currentChatTitle && currentChatId) {
                    await updateChatTitle(currentChatId, trimmed).catch(() => {});
                    setCurrentChatTitle(trimmed);
                  }
                  setEditingTitle(false);
                }}
                style={{
                  fontSize: 14, fontWeight: 500, color: 'var(--ink-900)',
                  background: 'var(--surface-1, #f5f5f5)', border: '1px solid var(--ink-200, #d1d5db)',
                  borderRadius: 4, padding: '2px 6px', minWidth: 0, width: 320, maxWidth: '100%',
                  outline: 'none',
                }}
              />
            ) : (
              <span
                onClick={() => {
                  if (!currentChatId) return;
                  setEditTitleValue(currentChatTitle || '');
                  setEditingTitle(true);
                }}
                title={currentChatId ? 'Click to rename' : undefined}
                style={{
                  fontSize: 14, fontWeight: 500, color: 'var(--ink-900)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  cursor: currentChatId ? 'text' : 'default',
                  borderBottom: currentChatId ? '1px dotted var(--ink-300, #9ca3af)' : 'none',
                }}
              >
                {currentChatTitle || 'New thread'}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            {features.matters_enabled && <GhostBtn
              icon={<BookmarkIcon />}
              onClick={() => { setAssigningChatId(currentChatId); setShowAssignModal(true); }}
              disabled={!currentChatId}
              title={!currentChatId ? 'Open a chat to assign it to a matter' : 'Save this thread to a matter'}
            >Save to matter</GhostBtn>}
            <GhostBtn onClick={() => setShowFeedbackModal(true)}>Give Feedback</GhostBtn>
          </div>
        </div>

        {/* Content area: chat column + sources rail */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>

          {/* Chat column */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>

            {/* Scroll area */}
            <div
              ref={chatScrollRef}
              className="lex-scroll"
              style={{ flex: 1, overflow: 'auto', padding: '20px 28px 140px' }}
            >
              <div style={{ maxWidth: '95%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 18 }}>

                {showWeeklyBanner && (
                  <WeeklyFeedbackBanner
                    userId={user.id}
                    onClose={() => setShowWeeklyBanner(false)}
                  />
                )}

                {/* Research context chips */}
                {(() => {
                  const chips = [
                    { icon: <ScalesIcon />, label: researchModeLabel },
                    { icon: <GavelIcon />, label: jurisdictionLabel },
                    { icon: <CalendarIcon />, label: `In force · ${todayLabel}` },
                  ];
                  if (dateFrom || dateTo !== thisYear) {
                    const dr = dateFrom && dateTo ? `${dateFrom}–${dateTo}` : dateFrom ? `From ${dateFrom}` : `To ${dateTo}`;
                    chips.push({ icon: <CalendarIcon />, label: `Date: ${dr}` });
                  }
                  if (courtLabel && researchMode !== 'legislation_only') {
                    chips.push({ icon: <GavelIcon />, label: courtLabel });
                  }
                  return (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', paddingBottom: 4 }}>
                      {chips.map((chip, i) => (
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
                  );
                })()}

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
                      onResend={() => {
                        const prevUser = messages.slice(0, idx).reverse().find(m => m.role === 'user');
                        setInput(prevUser ? prevUser.content : '');
                        setTimeout(() => {
                          const ta = textareaRef.current;
                          if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
                        }, 0);
                      }}
                      onRerun={msg.role === 'user' ? () => {
                        setInput(msg.content);
                        setTimeout(() => {
                          const ta = textareaRef.current;
                          if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
                        }, 0);
                      } : undefined}
                      authorInitials={userInitials}
                      matters={matters}
                      mattersEnabled={features.matters_enabled}
                      sourcesCount={msg.role === 'assistant' && msg.id ? (msg.sources?.length ?? 0) : 0}
                      onViewSources={msg.role === 'assistant' && msg.id ? () => { setActiveSourcesMsgId(msg.id); setSourcesCollapsed(false); } : undefined}
                      sourcesActive={msg.role === 'assistant' && msg.id != null && (
                        msg.id === activeSourcesMsgId ||
                        (activeSourcesMsgId == null && msg.id === latestSourceMsgId)
                      )}
                    />
                  );
                })}

                {/* Loading indicator */}
                {loading && (
                  <div style={{ padding: '8px 0', fontSize: 13, color: 'var(--ink-500)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div className="lex-thinking-dot" />
                      <span style={{ flex: 1 }}>{agentStatus || 'Thinking…'}</span>
                    </div>
                    {activities.size > 0 && (
                      <div style={{ marginTop: 6, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {[...activities.entries()].map(([id, label]) => (
                          <div key={id} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: 'var(--ink-400)' }}>
                            <div style={{
                              width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
                              background: 'var(--accent)', opacity: 0.7,
                              animation: 'lex-pulse 1.4s ease-in-out infinite',
                            }} />
                            <span>{label}</span>
                          </div>
                        ))}
                      </div>
                    )}
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
                background: 'var(--bg-app)',
                marginTop: -120, position: 'relative', zIndex: 2,
              }}
            >
              <div style={{ maxWidth: '95%', margin: '0 auto', position: 'relative' }}>

                {/* Filters popover */}
                {showFilters && (() => {
                  const secHead = (label) => (
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '4px 8px 6px' }}>{label}</div>
                  );
                  const divider = () => (
                    <div style={{ height: 1, background: 'var(--ink-100)', margin: '6px 0' }} />
                  );
                  const optBtn = (isActive, onClick, label) => (
                    <button onClick={onClick} style={{
                      display: 'block', width: '100%', textAlign: 'left',
                      padding: '6px 10px', borderRadius: 6, border: 'none',
                      background: isActive ? 'var(--accent-soft)' : 'transparent',
                      color: isActive ? 'var(--accent-ink)' : 'var(--ink-700)',
                      fontSize: 13, fontWeight: isActive ? 600 : 400,
                      cursor: 'pointer', fontFamily: 'var(--font-ui)',
                    }}>{label}</button>
                  );
                  const inputRow = (labelA, valA, setA, labelB, valB, setB) => (
                    <div style={{ display: 'flex', gap: 6, padding: '0 8px 6px', alignItems: 'center' }}>
                      <input type="text" placeholder={labelA} value={valA} maxLength={4}
                        onChange={e => setA(e.target.value.replace(/\D/g, '').slice(0, 4))}
                        style={{ flex: 1, padding: '4px 7px', borderRadius: 6, border: '1px solid var(--ink-200)', fontSize: 12, fontFamily: 'var(--font-ui)', background: 'var(--paper)', color: 'var(--ink-700)', outline: 'none' }}
                      />
                      <span style={{ fontSize: 11, color: 'var(--ink-400)' }}>–</span>
                      <input type="text" placeholder={labelB} value={valB} maxLength={4}
                        onChange={e => setB(e.target.value.replace(/\D/g, '').slice(0, 4))}
                        style={{ flex: 1, padding: '4px 7px', borderRadius: 6, border: '1px solid var(--ink-200)', fontSize: 12, fontFamily: 'var(--font-ui)', background: 'var(--paper)', color: 'var(--ink-700)', outline: 'none' }}
                      />
                    </div>
                  );

                  return (
                    <div style={{
                      position: 'absolute', bottom: '100%', left: 0, marginBottom: 8,
                      background: 'var(--paper)', border: '1px solid var(--ink-200)',
                      borderRadius: 10, boxShadow: 'var(--shadow-md)',
                      paddingTop: 8, paddingBottom: 4, minWidth: 300, zIndex: 10,
                      maxHeight: '80vh', overflowY: 'auto',
                    }}>

                      {/* § Research mode */}
                      {secHead('Research mode')}
                      {[
                        { value: 'legislation_only', label: 'Legislation only' },
                        { value: 'case_law_only', label: 'Case law only' },
                        { value: 'legislation_and_case_law', label: 'Legislation & case law' },
                      ].map(opt => optBtn(
                        researchMode === opt.value,
                        () => { setResearchMode(opt.value); updatePreferences({ research_mode: opt.value }).catch(() => {}); },
                        opt.label,
                      ))}

                      {divider()}

                      {/* § Jurisdiction */}
                      {secHead('Jurisdiction')}
                      {JURISDICTION_OPTIONS.map(opt => optBtn(
                        jurisdiction === opt.value,
                        () => setJurisdictionPersist(opt.value),
                        opt.label,
                      ))}
                      {showScotlandNINote && (
                        <div style={{ margin: '2px 8px 4px', padding: '5px 8px', borderRadius: 6, background: 'var(--accent-soft)', fontSize: 11, color: 'var(--accent-ink)', lineHeight: 1.4 }}>
                          Case law database covers E&amp;W and UK-wide courts only — Scottish and NI courts are not indexed.
                        </div>
                      )}

                      {/* § Legislation type */}
                      {researchMode !== 'case_law_only' && (<>
                        {divider()}
                        {secHead('Legislation type')}
                        {LEGISLATION_TYPE_OPTIONS.map(opt => optBtn(
                          legislationType === opt.value,
                          () => setLegislationTypePersist(opt.value),
                          opt.label,
                        ))}
                        {divider()}
                        {secHead('Status')}
                        <div
                          style={{ padding: '4px 8px 8px', display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
                          onClick={() => setCurrentOnlyPersist(!currentOnly)}
                        >
                          <div style={{
                            width: 30, height: 17, borderRadius: 9,
                            background: currentOnly ? 'var(--accent)' : 'var(--ink-200)',
                            position: 'relative', flexShrink: 0, transition: 'background 120ms',
                          }}>
                            <span style={{
                              position: 'absolute', top: 2,
                              left: currentOnly ? 15 : 2,
                              width: 13, height: 13, borderRadius: '50%',
                              background: 'white', transition: 'left 120ms',
                              display: 'block',
                            }} />
                          </div>
                          <span style={{ fontSize: 13, color: 'var(--ink-700)', fontFamily: 'var(--font-ui)', userSelect: 'none' }}>
                            Current legislation only
                          </span>
                        </div>
                      </>)}

                      {/* § Date range */}
                      {divider()}
                      {secHead('Date range')}
                      {inputRow('From', dateFrom, setDateFromPersist, 'To', dateTo, setDateToPersist)}

                      {/* § Case law court */}
                      {researchMode !== 'legislation_only' && (<>
                        {divider()}
                        {secHead('Case law court')}
                        <div style={{ padding: '0 8px 6px' }}>
                          <select value={caseLawCourt} onChange={e => setCourtPersist(e.target.value)}
                            style={{ width: '100%', padding: '5px 7px', borderRadius: 6, border: '1px solid var(--ink-200)', fontSize: 12, fontFamily: 'var(--font-ui)', background: 'var(--paper)', color: 'var(--ink-700)', cursor: 'pointer', outline: 'none' }}>
                            <option value=''>All courts</option>
                            {COURT_GROUPS.map(g => (
                              <optgroup key={g.group} label={g.group}>
                                {g.courts.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                              </optgroup>
                            ))}
                          </select>
                        </div>
                      </>)}

                      {/* Clear */}
                      {hasActiveFilters && (<>
                        {divider()}
                        <div style={{ padding: '2px 8px 4px', textAlign: 'right' }}>
                          <button onClick={clearAllFilters} style={{
                            background: 'none', border: 'none', fontSize: 12, color: 'var(--ink-500)',
                            cursor: 'pointer', fontFamily: 'var(--font-ui)', textDecoration: 'underline',
                          }}>Clear filters</button>
                        </div>
                      </>)}
                    </div>
                  );
                })()}

                {/* Composer card */}
                <div style={{
                  background: 'var(--paper)',
                  border: '1px solid var(--ink-200)',
                  borderRadius: 12, padding: 12,
                  boxShadow: 'var(--shadow-sm)',
                }}>
                  {/* Hidden file input */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    style={{ display: 'none' }}
                    onChange={handleFileUpload}
                  />

                  {/* Document chips */}
                  {chatDocuments.length > 0 && (
                    <div style={{
                      display: 'flex', flexWrap: 'wrap', gap: 4,
                      paddingBottom: 8, marginBottom: 6,
                      borderBottom: '1px solid var(--ink-100)',
                    }}>
                      {chatDocuments.map(doc => (
                        <div key={doc.id} style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          padding: '2px 8px', background: 'var(--ink-100)',
                          borderRadius: 6, fontSize: 12, color: 'var(--ink-600)',
                          maxWidth: 220,
                        }}>
                          <PaperclipIcon style={{ width: 11, height: 11, flexShrink: 0 }} />
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={doc.filename}>{doc.filename}</span>
                          <button
                            onClick={() => handleDeleteDocument(doc.id)}
                            style={{
                              background: 'none', border: 'none', padding: '0 0 0 2px',
                              cursor: 'pointer', color: 'var(--ink-400)', fontSize: 14,
                              lineHeight: 1, flexShrink: 0,
                            }}
                            title="Remove document"
                          >×</button>
                        </div>
                      ))}
                      {uploadingDoc && (
                        <div style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          padding: '2px 8px', background: 'var(--ink-100)',
                          borderRadius: 6, fontSize: 12, color: 'var(--ink-400)',
                        }}>Uploading…</div>
                      )}
                    </div>
                  )}
                  {uploadingDoc && chatDocuments.length === 0 && (
                    <div style={{
                      fontSize: 12, color: 'var(--ink-400)', paddingBottom: 6,
                      borderBottom: '1px solid var(--ink-100)', marginBottom: 6,
                    }}>Uploading…</div>
                  )}

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
                      <IBtn label="Attach file (PDF, DOCX, TXT)" onClick={() => fileInputRef.current?.click()} disabled={uploadingDoc}><PaperclipIcon /></IBtn>
                      <IBtn label="Research filters" onClick={() => setShowFilters(f => !f)}>
                        <SlidersIcon />
                      </IBtn>
<span style={{ fontSize: 12, color: 'var(--ink-500)', marginLeft: 6, fontFamily: 'var(--font-mono)' }}>
                        {jurisdictionShort} · {todayISO}
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
            collapsed={sourcesCollapsed}
            onCollapsedChange={setSourcesCollapsed}
          />
        </div>
      </div>

      {/* ── Modals ───────────────────────────────────────────── */}

      {showFeedbackModal && <FeedbackModal onClose={() => setShowFeedbackModal(false)} />}

      {features.matters_enabled && showCreateMatterModal && (
        <CreateMatterModal
          onClose={() => setShowCreateMatterModal(false)}
          onCreated={(matter) => {
            setMatters(prev => [matter, ...prev]);
            setExpandedMatterIds(prev => new Set([...prev, matter.id]));
          }}
        />
      )}

      {features.matters_enabled && notesModalMatter && (
        <MatterNotesModal
          matter={notesModalMatter}
          onClose={() => {
            setNotesModalMatter(null);
            getMatters().then(setMatters).catch(() => {});
          }}
        />
      )}

      {features.matters_enabled && showAssignModal && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(11,18,32,0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 50, padding: 16,
          }}
          onMouseDown={e => { if (e.target === e.currentTarget) setShowAssignModal(false); }}
        >
          <div style={{
            background: 'var(--paper)', borderRadius: 'var(--r-lg)',
            width: '100%', maxWidth: 380,
            boxShadow: '0 8px 32px rgba(11,18,32,0.14)',
            fontFamily: 'var(--font-ui)',
          }}>
            <div style={{
              padding: '16px 20px 12px',
              borderBottom: '1px solid var(--ink-200)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--ink-900)' }}>Save thread to matter</span>
              <button onClick={() => setShowAssignModal(false)} style={{
                width: 28, height: 28, border: 'none', background: 'transparent',
                cursor: 'pointer', color: 'var(--ink-500)', display: 'grid', placeItems: 'center', borderRadius: 6,
              }}>
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
              </button>
            </div>
            <div style={{ padding: '8px 12px' }}>
              {matters.length === 0 ? (
                <div style={{ padding: '12px 8px', color: 'var(--ink-400)', fontSize: 13, fontStyle: 'italic' }}>
                  No matters yet. Create one first.
                </div>
              ) : matters.map(m => {
                const currentMatterId = recentChats.find(c => c.id === assigningChatId)?.matter_id;
                const isAssigned = currentMatterId === m.id;
                return (
                  <div
                    key={m.id}
                    onClick={async () => {
                      await assignChatToMatter(assigningChatId, isAssigned ? null : m.id);
                      getChats().then(setRecentChats).catch(() => {});
                      getMatters().then(setMatters).catch(() => {});
                      setShowAssignModal(false);
                    }}
                    style={{
                      padding: '9px 10px', borderRadius: 6, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 8,
                      background: isAssigned ? 'var(--accent-soft)' : 'transparent',
                      color: isAssigned ? 'var(--accent-ink)' : 'var(--ink-800)',
                      marginBottom: 2,
                    }}
                  >
                    <FolderIcon />
                    <span style={{ flex: 1, fontSize: 13 }}>{m.title}</span>
                    {isAssigned && <span style={{ fontSize: 11, color: 'var(--accent)' }}>✓ Assigned</span>}
                  </div>
                );
              })}
              {recentChats.find(c => c.id === assigningChatId)?.matter_id && (
                <div
                  onClick={async () => {
                    await assignChatToMatter(assigningChatId, null);
                    getChats().then(setRecentChats).catch(() => {});
                    getMatters().then(setMatters).catch(() => {});
                    setShowAssignModal(false);
                  }}
                  style={{
                    padding: '8px 10px', borderRadius: 6, cursor: 'pointer',
                    fontSize: 13, color: 'var(--danger)', marginTop: 4,
                    borderTop: '1px solid var(--ink-200)', paddingTop: 10,
                  }}
                >Remove from matter</div>
              )}
            </div>
            <div style={{ height: 8 }} />
          </div>
        </div>
      )}

      {showDataSources && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" onClick={() => setShowDataSources(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center p-6 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">Data Sources</h2>
              <button onClick={() => setShowDataSources(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 focus:outline-none">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="overflow-y-auto p-6 space-y-6 text-sm text-gray-700 dark:text-gray-300">

              {/* Legislation API */}
              <section>
                <h3 className="text-base font-bold text-gray-900 dark:text-white mb-2">Source Overview: The National Archives "Legislation" API</h3>
                <p>AILA connects to the official API for legislation.gov.uk, operated by The National Archives. This database serves as the official, government-maintained statute book for the United Kingdom. Through this integration, AILA can retrieve and analyze the text of laws, regulations, and statutory rules.</p>
              </section>

              <section>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-2">Jurisdictions and Parliaments Covered</h4>
                <p className="mb-2">Unlike the Case Law database, the Legislation API provides comprehensive coverage across all four nations of the UK. AILA can retrieve legislation from:</p>
                <ul className="list-disc list-inside space-y-1 pl-2">
                  <li>The UK Parliament (Westminster)</li>
                  <li>The Scottish Parliament (Holyrood)</li>
                  <li>The Welsh Parliament / Senedd Cymru</li>
                  <li>The Northern Ireland Assembly</li>
                </ul>
              </section>

              <section>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-2">Types of Legislation Included</h4>
                <p className="mb-2">AILA has access to both primary laws (the main Acts) and secondary legislation (the detailed rules and regulations):</p>
                <ul className="list-disc list-inside space-y-1 pl-2">
                  <li><strong>Primary Legislation:</strong> Public General Acts of the UK Parliament, Acts of the Scottish Parliament (ASPs), Acts/Measures of the Senedd Cymru, and Acts of the Northern Ireland Assembly.</li>
                  <li><strong>Secondary Legislation:</strong> Statutory Instruments (SIs), Scottish Statutory Instruments (SSIs), and Welsh Statutory Instruments.</li>
                  <li><strong>Historical EU Law:</strong> "Retained EU legislation" that was incorporated into UK domestic law following Brexit.</li>
                </ul>
              </section>

              <section>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-2">Versioning: "As Enacted" vs. "Revised"</h4>
                <p className="mb-2">One of the most powerful features of this database is how it handles the timeline of the law. AILA can distinguish between:</p>
                <ul className="list-disc list-inside space-y-1 pl-2">
                  <li><strong>As Enacted:</strong> The original text of the law exactly as it was originally passed by Parliament.</li>
                  <li><strong>Latest Available (Revised):</strong> The current, up-to-date version of the law, reflecting any amendments, insertions, or repeals made by subsequent legislation.</li>
                </ul>
              </section>

              <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md p-4">
                <h4 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">Important Limitations (The "Revision Gap")</h4>
                <p className="mb-2 text-amber-900 dark:text-amber-200">To ensure users interpret the law correctly, it is important to understand a key limitation of the official UK statute book:</p>
                <ul className="list-disc list-inside space-y-1 pl-2 text-amber-900 dark:text-amber-200">
                  <li><strong>Delayed Revisions:</strong> While the National Archives team works constantly to update the database, there is often a "revision gap." When a new law amends an old law, it can take time (sometimes months or, for obscure legislation, years) for those changes to be officially applied to the "Revised" text on the database.</li>
                  <li><strong>Repealed Text:</strong> AILA may retrieve legislation that has been entirely repealed or is no longer in force if you specifically ask for historical context, so always verify the current legal status of older statutes.</li>
                </ul>
              </section>

              <div className="border-t border-gray-200 dark:border-gray-700 pt-6">
                <h3 className="text-base font-bold text-gray-900 dark:text-white mb-2">Source Overview: The National Archives "Find Case Law" API</h3>
                <p>Alongside legislation, AILA integrates with The National Archives (TNA) "Find Case Law" API. This is the official, government-backed repository for court judgments and tribunal decisions in the United Kingdom. By connecting directly to this source, AILA ensures that the case law it references is authoritative, unmodified, and publicly verifiable.</p>
              </div>

              <section>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-2">Courts and Tribunals Covered</h4>
                <p className="mb-2">The API primarily covers the higher courts of England and Wales, alongside the highest appellate courts for the entire UK. Through this integration, AILA can retrieve judgments from:</p>
                <div className="space-y-3 pl-2">
                  <div>
                    <p className="font-medium text-gray-800 dark:text-gray-200">UK-Wide Appellate Courts:</p>
                    <ul className="list-disc list-inside space-y-1 pl-4">
                      <li>The UK Supreme Court (UKSC)</li>
                      <li>The Judicial Committee of the Privy Council (JCPC)</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-gray-800 dark:text-gray-200">England &amp; Wales Higher Courts:</p>
                    <ul className="list-disc list-inside space-y-1 pl-4">
                      <li>Court of Appeal (Civil and Criminal Divisions)</li>
                      <li>High Court of Justice (King's Bench, Chancery, and Family Divisions)</li>
                      <li>Courts Martial Appeal Court</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-gray-800 dark:text-gray-200">UK Tribunals:</p>
                    <ul className="list-disc list-inside space-y-1 pl-4">
                      <li>Upper Tribunal (Administrative Appeals, Immigration and Asylum, Lands, and Tax and Chancery Chambers)</li>
                      <li>Employment Appeal Tribunal (EAT)</li>
                    </ul>
                  </div>
                </div>
              </section>

              <section>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-2">Temporal Coverage (Dates)</h4>
                <ul className="list-disc list-inside space-y-1 pl-2">
                  <li><strong>Modern Judgments:</strong> The database is highly comprehensive for cases handed down from 2003 onwards.</li>
                  <li><strong>Recent Cases:</strong> Newly published judgments are added to the database shortly after being handed down by the courts.</li>
                  <li><strong>Historical Cases:</strong> While not a complete historical archive, the database is continually expanding to include significant landmark judgments from before 2003.</li>
                </ul>
              </section>

              <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md p-4">
                <h4 className="font-semibold text-amber-800 dark:text-amber-300 mb-2">Important Limitations (What is NOT Covered)</h4>
                <p className="mb-2 text-amber-900 dark:text-amber-200">To ensure you get the most out of AILA, it is important to know which jurisdictions and courts are not currently available through this official API:</p>
                <ul className="list-disc list-inside space-y-1 pl-2 text-amber-900 dark:text-amber-200">
                  <li><strong>Scotland and Northern Ireland:</strong> The API does not host judgments from the domestic courts of Scotland (e.g., Court of Session, High Court of Justiciary) or Northern Ireland, except when those cases are appealed to the UK Supreme Court.</li>
                  <li><strong>Lower Courts:</strong> Judgments from the Crown Court, County Courts, Magistrates' Courts, and Family Court are generally not published or available through this API.</li>
                  <li><strong>First-Tier Tribunals:</strong> Decisions from lower-level tribunals (like the Employment Tribunal or First-tier Immigration Tribunals) are currently excluded.</li>
                </ul>
              </section>

            </div>
            <div className="flex justify-end p-4 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
              <button onClick={() => setShowDataSources(false)} className="bg-brand-navy text-white px-4 py-2 rounded-md hover:bg-brand-navy-dark transition-colors">Close</button>
            </div>
          </div>
        </div>
      )}

      {showAbout && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-2xl w-full shadow-xl">
            <div className="flex items-center justify-center gap-2 mb-4">
              <LexMark size={32} color="var(--accent)" />
              <h1 className="text-3xl font-bold" style={{ color: 'var(--accent)' }}>AILA</h1>
            </div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">About AILA</h2>
              <button onClick={() => setShowAbout(false)} className="text-gray-400 hover:text-gray-600 focus:outline-none">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4 text-gray-700 dark:text-gray-300 text-sm">
              <p><strong>AILA</strong> is an intelligent legal research assistant for UK legislation and case law.</p>
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
        onOpenDataSources={() => setShowDataSources(true)}
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
