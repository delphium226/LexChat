import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  createChat,
  updatePreferences,
  getChats,
  getMatters,
  updateMatter,
  assignChatToMatter,
  uploadDocument,
  deleteDocument,
  updateChatTitle,
} from './services/api';
import ChatMessage from './components/ChatMessage';
import { LexMark } from './components/LexMark';
import SourcesRail from './components/SourcesRail';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginModal from './components/LoginModal';
import AdminPortal from './pages/AdminPortal';
import Settings from './pages/Settings';
import HistoryModal from './components/HistoryModal';
import SettingsMenuModal from './components/SettingsMenuModal';
import CreateMatterModal from './components/CreateMatterModal';
import MatterNotesModal from './components/MatterNotesModal';
import DataSourcesModal from './components/DataSourcesModal';
import AboutModal from './components/AboutModal';
import AssignMatterModal from './components/AssignMatterModal';
import ResearchFiltersModal from './components/ResearchFiltersModal';
import Composer from './components/Composer';
import Sidebar from './components/Sidebar';
import {
  HOUSE_OPTIONS,
  JURISDICTION_OPTIONS,
  COURT_GROUPS,
  getRecordTypeOptions,
  getSessionFilterLabel,
  getSessionOptions,
} from './constants/research';
import { Routes, Route } from 'react-router-dom';
import SystemChat from './pages/SystemChat';
import WeeklyFeedbackBanner from './components/WeeklyFeedbackBanner';
import SessionFeedbackModal from './components/SessionFeedbackModal';
import DataSensitivityNotice from './components/DataSensitivityNotice';
import DeepResearchPlan from './components/DeepResearchPlan';
import SuggestedQuestions from './components/SuggestedQuestions';
import { BookmarkIcon, ScalesIcon, GavelIcon, CalendarIcon, SlidersIcon, CopyIcon } from './components/ui/icons';
import { GhostBtn } from './components/ui/buttons';
import Modal from './components/ui/Modal';
import { getInitials } from './utils/format';
import { copyConversation } from './utils/exportChat';
import { useBotIdentity } from './hooks/useBotIdentity';
import { useFilters } from './hooks/useFilters';
import { usePreferences } from './hooks/usePreferences';
import { useModals } from './hooks/useModals';
import { useMatters } from './hooks/useMatters';
import { useChat } from './hooks/useChat';

// ── Main app ───────────────────────────────────────────────────

function AppContent() {
  const { user, logout, logoutWithExpiry } = useAuth();

  // ── Chat identity keys ───────────────────────────────────────
  // Shared with the filters/matters hooks as a coordination key; the rest of
  // the chat state lives in useChat, wired up below once its inputs exist.
  const [currentChatId, setCurrentChatId] = useState(null);
  const [currentChatTitle, setCurrentChatTitle] = useState(null);
  // True once the user has manually named this thread — suppresses the automatic
  // first-question title so their chosen name is never overwritten.
  const [titleUserSet, setTitleUserSet] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [editTitleValue, setEditTitleValue] = useState('');
  const { chatMode, setChatMode, researchMode, setResearchMode, darkMode, setDarkMode } = usePreferences(user);

  // ── UI state ─────────────────────────────────────────────────
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('sidebarCollapsed') === 'true');
  const [recentChats, setRecentChats] = useState([]);
  const [activeCite, setActiveCite] = useState(null);
  const [activeSourcesMsgId, setActiveSourcesMsgId] = useState(null);
  const [sourcesCollapsed, setSourcesCollapsed] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  // 'idle' | 'copied' | 'failed' — transient feedback on the copy-thread button
  const [copyState, setCopyState] = useState('idle');

  // ── Modal state ──────────────────────────────────────────────
  const modals = useModals();
  const [noticeAcknowledged, setNoticeAcknowledged] = useState(false);
  const [surveyDue, setSurveyDue] = useState(false);
  const weeklyBannerCheckedRef = useRef(false);

  // ── Matters state ────────────────────────────────────────────
  const {
    features,
    matters,
    setMatters,
    closedMatters,
    setClosedMatters,
    showClosedMatters,
    setShowClosedMatters,
    expandedMatterIds,
    setExpandedMatterIds,
    showCreateMatterModal,
    setShowCreateMatterModal,
    notesModalMatter,
    setNotesModalMatter,
    showAssignModal,
    setShowAssignModal,
    assigningChatId,
    setAssigningChatId,
    resetMatters,
  } = useMatters(user, currentChatId);

  // ── Document state ───────────────────────────────────────────
  const [chatDocuments, setChatDocuments] = useState([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  // ── Refs ─────────────────────────────────────────────────────
  const messagesEndRef = useRef(null);
  const composerRef = useRef(null);
  const fileInputRef = useRef(null);

  // ── Effects ──────────────────────────────────────────────────

  // Reload the recent chat list whenever the active chat changes or user logs in
  useEffect(() => {
    if (!user) return;
    getChats()
      .then(setRecentChats)
      .catch(err => console.warn('Failed to fetch chats:', err));
  }, [user, currentChatId]);

  // Reset on logout
  useEffect(() => {
    if (!user) {
      resetChat();
      modals.closeAll();
      setChatMode('research');
      setResearchMode('legislation_only');
      resetMatters();
      weeklyBannerCheckedRef.current = false;
      setNoticeAcknowledged(false);
    }
    // reset helpers are recreated each render; run this only on auth change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, setChatMode, setResearchMode]);

  // If an admin disables the user's active chat mode, fall back to Conversational
  // (always available) so the mode selector never sits on a hidden option.
  useEffect(() => {
    if (!user) return;
    const disabled =
      (chatMode === 'research' && !features.research_mode_enabled) ||
      (chatMode === 'deep_research' && !features.deep_research_mode_enabled);
    if (disabled) {
      setChatMode('conversational');
      updatePreferences({ chat_mode: 'conversational' }).catch(() => {});
    }
  }, [user, chatMode, features.research_mode_enabled, features.deep_research_mode_enabled, setChatMode]);

  // Weekly feedback — show banner once per week, button whenever survey not yet submitted this week.
  // Uses a ref (not state) for the checked flag so setting it doesn't trigger
  // a re-render that would cancel the timer via effect cleanup.
  // The flag check must come before the ref is set, so that enabling the flag
  // (or the flags simply arriving after this first runs) doesn't find the
  // effect permanently short-circuited.
  useEffect(() => {
    if (!user || !features.weekly_survey_enabled || weeklyBannerCheckedRef.current) return;
    weeklyBannerCheckedRef.current = true;
    const week = 7 * 24 * 60 * 60 * 1000;
    const submittedKey = `weeklyFeedbackSubmitted_${user.id}`;
    const lastSubmitted = localStorage.getItem(submittedKey);
    if (!lastSubmitted || Date.now() - parseInt(lastSubmitted, 10) > week) {
      setSurveyDue(true);
    }
    const timer = setTimeout(() => {
      const shownKey = `weeklyFeedbackLastShown_${user.id}`;
      const last = localStorage.getItem(shownKey);
      if (!last || Date.now() - parseInt(last, 10) > week) {
        modals.open('weeklyBanner');
      }
    }, 2000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, features.weekly_survey_enabled]);

  // ── Derived ──────────────────────────────────────────────────

  const researchModeLabel =
    {
      legislation_only: 'Legislation only',
      case_law_only: 'Case law only',
      legislation_and_case_law: 'Legislation & case law',
    }[researchMode] || 'Legislation only';

  const todayLabel = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

  // Has this thread already had end-of-session feedback? Nothing on the chat
  // row records it, so this is a render-time localStorage read — cheap, and
  // always current because closing the modal after a submit re-renders anyway.
  const sessionFeedbackSent =
    !!currentChatId && localStorage.getItem(`sessionFeedbackSubmitted_${currentChatId}`) === '1';

  // ── Research filters (state + persistence in useFilters) ─────
  const {
    thisYear,
    jurisdiction,
    dateFrom,
    dateTo,
    caseLawCourt,
    legislationType,
    currentOnly,
    recordType,
    sessions,
    house,
    setJurisdictionPersist,
    setDateFromPersist,
    setDateToPersist,
    setCourtPersist,
    setLegislationTypePersist,
    setCurrentOnlyPersist,
    setRecordTypePersist,
    setSessionsPersist,
    setHousePersist,
    applySessionDefault,
    saveFiltersToChatStorage,
    restoreFiltersForChat,
  } = useFilters(currentChatId);

  // ── Chat flow (messages, composer, streaming, handlers) ──────
  // Declared here, after its inputs (filters/preferences/chat keys) exist.
  const {
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
    pendingPlan,
    handleRunPlan,
    handleCancelPlan,
  } = useChat({
    user,
    logoutWithExpiry,
    chatMode,
    researchMode,
    filters: { jurisdiction, dateFrom, dateTo, caseLawCourt, legislationType, currentOnly, recordType, sessions, house },
    saveFiltersToChatStorage,
    restoreFiltersForChat,
    currentChatId,
    setCurrentChatId,
    setCurrentChatTitle,
    pendingTitle: titleUserSet ? currentChatTitle?.trim() || null : null,
    setTitleUserSet,
    setActiveCite,
    setActiveSourcesMsgId,
    setChatDocuments,
    closeHistoryModal: () => modals.close('history'),
    recentChats,
    matters,
    onDeepResearchComplete: () => {
      setChatMode('conversational');
      updatePreferences({ chat_mode: 'conversational' }).catch(() => {});
    },
  });

  // ── Bot identity (name/branding/favicon) — needs `loading` from useChat ──
  const { botInfo } = useBotIdentity(loading);

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

  // Two parliamentary bots share this client, selected by the bot's research mode:
  // Holyrood (unicameral, Sessions 1-7) and Westminster (two Houses, Parliaments).
  // `isParliament` gates everything the two have in common (narrow filter layout,
  // parliamentary chips); the specific flags gate the jurisdiction-specific labels.
  const botMode = botInfo.researchMode;
  const isHolyrood = botMode === 'parliamentary_records';
  const isWestminster = botMode === 'westminster_records';
  const isParliament = isHolyrood || isWestminster;

  // The correct session/Parliament default depends on which bot this is, which is
  // only known once /api/bot-info resolves — apply it then, and drop any persisted
  // value belonging to the other bot's vocabulary.
  useEffect(() => {
    if (botMode) applySessionDefault(botMode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botMode]);

  const jurisdictionLabel = jurisdiction
    ? JURISDICTION_OPTIONS.find(o => o.value === jurisdiction)?.label || 'All jurisdictions'
    : 'All jurisdictions';

  const courtLabel = caseLawCourt
    ? COURT_GROUPS.flatMap(g => g.courts).find(c => c.value === caseLawCourt)?.label || caseLawCourt
    : '';

  const userInitials = getInitials(user?.username);

  // ── Handlers ─────────────────────────────────────────────────

  // Commit an edited thread title. Marks the title as user-set so the automatic
  // first-question title won't overwrite it, and persists to the backend when a
  // chat already exists (a not-yet-created thread keeps the name until first send).
  const commitTitle = async () => {
    const trimmed = editTitleValue.trim();
    setEditingTitle(false);
    if (!trimmed || trimmed === currentChatTitle) return;
    setCurrentChatTitle(trimmed);
    setTitleUserSet(true);
    if (currentChatId) await updateChatTitle(currentChatId, trimmed).catch(() => {});
  };

  const handleFileUpload = async e => {
    const file = e.target.files[0];
    if (!fileInputRef.current) fileInputRef.current.value = '';
    if (!file) return;
    fileInputRef.current.value = '';

    setUploadingDoc(true);
    setUploadError(null);
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
      setUploadError(msg);
    } finally {
      setUploadingDoc(false);
    }
  };

  const handleDeleteDocument = async docId => {
    try {
      await deleteDocument(docId);
      setChatDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (err) {
      console.error('Failed to delete document:', err);
    }
  };

  // Copy the whole thread — every question, answer and source citation — to the
  // clipboard as rich text, so it can be pasted into Word or Outlook intact.
  const handleCopyConversation = async () => {
    const ok = await copyConversation({
      messages,
      title: currentChatTitle,
      botName: botInfo.name,
      userName: user?.username,
    });
    setCopyState(ok ? 'copied' : 'failed');
    setTimeout(() => setCopyState('idle'), 2500);
  };

  const toggleSidebar = () => {
    const next = !sidebarCollapsed;
    setSidebarCollapsed(next);
    localStorage.setItem('sidebarCollapsed', next);
  };

  // ── Auth gate ─────────────────────────────────────────────────

  if (!user) return <LoginModal botName={botInfo.name} botLogoEmoji={botInfo.logoEmoji} />;

  // ── Render ────────────────────────────────────────────────────

  return (
    <div
      style={{
        display: 'flex',
        height: '100dvh',
        background: 'var(--bg-app)',
        fontFamily: 'var(--font-ui)',
        color: 'var(--ink-900)',
        overflow: 'hidden',
      }}
    >
      {/* ── Sidebar ───────────────────────────────────────────── */}
      <Sidebar
        sidebarCollapsed={sidebarCollapsed}
        onToggle={toggleSidebar}
        botInfo={botInfo}
        user={user}
        userInitials={userInitials}
        onNewChat={handleNewChat}
        onOpenHistory={() => modals.open('history')}
        onOpenSettingsMenu={() => modals.open('settingsMenu')}
        chatMode={chatMode}
        onChatModeChange={value => {
          setChatMode(value);
          updatePreferences({ chat_mode: value }).catch(() => {});
        }}
        features={features}
        matters={matters}
        closedMatters={closedMatters}
        showClosedMatters={showClosedMatters}
        expandedMatterIds={expandedMatterIds}
        onToggleMatterExpanded={matterId => {
          const next = new Set(expandedMatterIds);
          if (next.has(matterId)) next.delete(matterId);
          else next.add(matterId);
          setExpandedMatterIds(next);
        }}
        recentChats={recentChats}
        currentChatId={currentChatId}
        onLoadChat={loadChat}
        onAddMatter={() => setShowCreateMatterModal(true)}
        onOpenNotes={setNotesModalMatter}
        onCloseMatter={async matter => {
          await updateMatter(matter.id, { status: 'closed' });
          setMatters(prev => prev.filter(m => m.id !== matter.id));
          if (showClosedMatters) setClosedMatters(prev => [{ ...matter, status: 'closed' }, ...prev]);
        }}
        onReopenMatter={async matter => {
          await updateMatter(matter.id, { status: 'open' });
          setClosedMatters(prev => prev.filter(m => m.id !== matter.id));
          setMatters(prev => [{ ...matter, status: 'open' }, ...prev]);
        }}
        onToggleClosedMatters={async () => {
          if (!showClosedMatters) {
            const all = await getMatters(true);
            setClosedMatters(all.filter(m => m.status === 'closed'));
          }
          setShowClosedMatters(v => !v);
        }}
      />

      {/* ── Main content ──────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 24px',
            background: 'var(--paper)',
            height: 52,
            flex: '0 0 52px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <span style={{ fontSize: 13, color: 'var(--ink-500)', flexShrink: 0 }}>Research</span>
            <span style={{ color: 'var(--ink-300)', flexShrink: 0 }}>/</span>
            {editingTitle ? (
              <input
                autoFocus
                value={editTitleValue}
                onChange={e => setEditTitleValue(e.target.value)}
                placeholder="Name this thread…"
                onKeyDown={async e => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    await commitTitle();
                  } else if (e.key === 'Escape') {
                    setEditingTitle(false);
                  }
                }}
                onBlur={commitTitle}
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'var(--ink-900)',
                  background: 'var(--ink-50)',
                  border: '1px solid var(--ink-200)',
                  borderRadius: 4,
                  padding: '2px 6px',
                  minWidth: 0,
                  width: 320,
                  maxWidth: '100%',
                  outline: 'none',
                }}
              />
            ) : (
              <span
                onClick={() => {
                  setEditTitleValue(currentChatTitle || '');
                  setEditingTitle(true);
                }}
                title="Click to rename"
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'var(--ink-900)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  cursor: 'text',
                  borderBottom: '1px dotted var(--ink-300, #9ca3af)',
                }}
              >
                {currentChatTitle || 'New thread'}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
            <GhostBtn
              icon={<CopyIcon size={14} />}
              onClick={handleCopyConversation}
              disabled={messages.length === 0 || loading}
              title={
                messages.length === 0
                  ? 'Nothing to copy yet'
                  : loading
                    ? 'Wait for the response to finish before copying'
                    : 'Copy the whole thread — questions, answers and sources — ready to paste into Word or Outlook'
              }
            >
              {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy conversation'}
            </GhostBtn>
            {features.matters_enabled && (
              <GhostBtn
                icon={<BookmarkIcon />}
                onClick={() => {
                  setAssigningChatId(currentChatId);
                  setShowAssignModal(true);
                }}
                disabled={!currentChatId}
                title={!currentChatId ? 'Open a chat to assign it to a matter' : 'Save this thread to a matter'}
              >
                Save to matter
              </GhostBtn>
            )}
            {features.weekly_survey_enabled && surveyDue && (
              <GhostBtn onClick={() => modals.open('weeklyBanner')}>Take weekly survey</GhostBtn>
            )}
          </div>
        </div>

        {/* Research context pills — part of the fixed header; stays in place as the chat scrolls */}
        <div
          style={{
            padding: '10px 24px',
            borderBottom: '1px solid var(--ink-200)',
            background: 'var(--paper)',
            flexShrink: 0,
          }}
        >
          {(() => {
            // One pill per filter category, always in the same categorical order
            // (region first). Each pill carries a single value — never a
            // concatenation of two different filters.
            const chips = [];

            // 1. Mode — always the first pill
            chips.push({
              icon: <ScalesIcon />,
              label:
                chatMode === 'conversational'
                  ? 'Conversational'
                  : chatMode === 'deep_research'
                    ? 'Deep Research'
                    : 'Research',
            });

            // 2. Region
            chips.push({
              icon: <GavelIcon />,
              label: isWestminster
                ? 'UK Parliament (Westminster)'
                : isHolyrood
                  ? 'Scottish Parliament (Holyrood)'
                  : jurisdictionLabel,
            });

            // 3. Research type (implied context in conversational mode, so omitted there)
            if (chatMode !== 'conversational') {
              chips.push({
                icon: <ScalesIcon />,
                label: isParliament ? 'Parliamentary records' : researchModeLabel,
              });
            }

            // 3b. House (Westminster only — Holyrood is unicameral)
            if (isWestminster && house) {
              chips.push({
                icon: <GavelIcon />,
                label: HOUSE_OPTIONS.find(o => o.value === house)?.label || house,
              });
            }

            // 4. Record type (Parliament)
            if (isParliament && recordType) {
              chips.push({
                icon: <GavelIcon />,
                label: getRecordTypeOptions(botMode).find(o => o.value === recordType)?.label || recordType,
              });
            }

            // 4b. Session / Parliament (Parliament bots) — multiselect
            if (isParliament && Array.isArray(sessions) && sessions.length) {
              const opts = getSessionOptions(botMode);
              const sorted = [...sessions].sort((a, b) => a - b);
              const noun = getSessionFilterLabel(botMode);
              const sessionLabel =
                sorted.length === opts.length
                  ? `All ${noun.toLowerCase()}s`
                  : sorted.length === 1
                    ? opts.find(o => o.value === sorted[0])?.label || `${noun} ${sorted[0]}`
                    : `${noun}s ${sorted.join(', ')}`;
              chips.push({ icon: <CalendarIcon />, label: sessionLabel });
            }

            // 5. Court (legislation, when case law is in scope)
            if (!isParliament && courtLabel && researchMode !== 'legislation_only') {
              chips.push({ icon: <GavelIcon />, label: courtLabel });
            }

            // 6. Date range
            if (dateFrom || dateTo !== thisYear) {
              const dr = dateFrom && dateTo ? `${dateFrom}–${dateTo}` : dateFrom ? `From ${dateFrom}` : `To ${dateTo}`;
              chips.push({ icon: <CalendarIcon />, label: `Date: ${dr}` });
            }

            // 7. In-force date (legislation)
            if (!isParliament) {
              chips.push({ icon: <CalendarIcon />, label: `In force as at ${todayLabel}` });
            }

            const filtersLabel = 'Filters';
            return (
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <button
                  onClick={() => setShowFilters(true)}
                  title="Edit research filters"
                  className="inline-flex items-center gap-1 rounded-md hover:bg-ink-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--ink-700)',
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                    padding: '4px 8px',
                    background: 'none',
                    border: '1px solid var(--ink-200)',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-ui)',
                  }}
                >
                  <SlidersIcon size={13} />
                  {filtersLabel}
                </button>
                <span style={{ width: 1, alignSelf: 'stretch', background: 'var(--ink-200)', flexShrink: 0 }} />
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', flex: 1, minWidth: 0 }}>
                {chips.map((chip, i) => (
                  <span
                    key={i}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '3px 10px',
                      borderRadius: 999,
                      fontSize: 12,
                      fontWeight: 500,
                      background: 'var(--bg-app)',
                      border: '1px solid var(--ink-200)',
                      color: 'var(--ink-800)',
                    }}
                  >
                    <span style={{ color: 'var(--ink-400)', display: 'inline-flex' }}>{chip.icon}</span>
                    {chip.label}
                  </span>
                ))}
                </div>
              </div>
            );
          })()}
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
                {/* Empty state */}
                {messages.length === 0 && !loading && (
                  <div style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--ink-400)' }}>
                    <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'center' }}>
                      {botInfo.logoEmoji ? (
                        <span
                          style={{ fontSize: 40, lineHeight: 1, opacity: 0.4, userSelect: 'none' }}
                          aria-hidden="true"
                        >
                          {botInfo.logoEmoji}
                        </span>
                      ) : (
                        <LexMark size={40} color="var(--ink-300)" />
                      )}
                    </div>
                    <p style={{ fontSize: 14, margin: 0 }}>
                      {chatMode === 'conversational'
                        ? isWestminster
                          ? 'Ask a question about UK Parliament records to begin.'
                          : isParliament
                            ? 'Ask a question about Scottish Parliament records to begin.'
                            : 'Ask a legal question to begin.'
                        : chatMode === 'deep_research'
                          ? 'Describe your research question — a plan will be drafted for your review before any research runs.'
                          : isWestminster
                            ? 'Ask about Hansard debates, committee scrutiny, or bill progress to begin.'
                            : isParliament
                              ? 'Ask about Scottish Parliament debates, committee scrutiny, or bill progress to begin.'
                              : 'Ask about UK legislation or case law to begin.'}
                    </p>
                  </div>
                )}

                {/* Messages */}
                {messages.map((msg, idx) => {
                  if (msg.role === 'tool') return null;
                  return (
                    <React.Fragment key={msg.id ?? idx}>
                    <ChatMessage
                      message={msg}
                      onResend={() => {
                        const prevUser = messages
                          .slice(0, idx)
                          .reverse()
                          .find(m => m.role === 'user');
                        setInput(prevUser ? prevUser.content : '');
                        setTimeout(() => {
                          const ta = textareaRef.current;
                          if (ta) {
                            ta.focus();
                            ta.setSelectionRange(ta.value.length, ta.value.length);
                          }
                        }, 0);
                      }}
                      onRerun={
                        msg.role === 'user'
                          ? () => {
                              setInput(msg.content);
                              setTimeout(() => {
                                const ta = textareaRef.current;
                                if (ta) {
                                  ta.focus();
                                  ta.setSelectionRange(ta.value.length, ta.value.length);
                                }
                              }, 0);
                            }
                          : undefined
                      }
                      authorInitials={userInitials}
                      matters={matters}
                      mattersEnabled={features.matters_enabled}
                      sourcesCount={msg.role === 'assistant' && msg.id ? (msg.sources?.length ?? 0) : 0}
                      onViewSources={
                        msg.role === 'assistant' && msg.id
                          ? () => {
                              setActiveSourcesMsgId(msg.id);
                              setSourcesCollapsed(false);
                            }
                          : undefined
                      }
                      sourcesActive={
                        msg.role === 'assistant' &&
                        msg.id != null &&
                        (msg.id === activeSourcesMsgId || (activeSourcesMsgId == null && msg.id === latestSourceMsgId))
                      }
                    />
                    {/* Chips only under the newest answer — a long thread must
                        not fill with stale suggestions from earlier turns. The
                        flag is belt-and-braces: with it off the backend already
                        strips the block and drops the planner's options. */}
                    {features.suggested_questions_enabled &&
                      msg.role === 'assistant' &&
                      idx === messages.length - 1 &&
                      !loading &&
                      msg.suggestions?.length > 0 && (
                        <SuggestedQuestions
                          suggestions={msg.suggestions}
                          onSelect={text => handleSend(text)}
                          disabled={loading}
                        />
                      )}
                    </React.Fragment>
                  );
                })}

                {/* Deep Research: plan review card */}
                {pendingPlan && (
                  <DeepResearchPlan
                    key={currentChatId ?? 'draft'}
                    plan={pendingPlan}
                    onRun={handleRunPlan}
                    onCancel={handleCancelPlan}
                    disabled={loading}
                  />
                )}

                {/* Loading indicator */}
                {loading &&
                  (() => {
                    let statusText = agentStatus || 'Thinking…';
                    if (activities.size > 0) {
                      const counts = new Map();
                      for (const label of activities.values()) {
                        const clean = label.replace(/…$/, '');
                        counts.set(clean, (counts.get(clean) || 0) + 1);
                      }
                      statusText = [...counts.entries()]
                        .map(([label, n]) => (n > 1 ? `${label} (${n})` : label))
                        .join(', ');
                    }
                    return (
                      <div style={{ padding: '8px 0', fontSize: 13, color: 'var(--ink-500)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div className="lex-thinking-dot" />
                          <span style={{ flex: 1 }}>{statusText}</span>
                        </div>
                      </div>
                    );
                  })()}

                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Composer — overlaps scroll area with gradient */}
            <div
              ref={composerRef}
              style={{
                padding: '12px 28px 18px',
                background: 'var(--bg-app)',
                marginTop: -120,
                position: 'relative',
                zIndex: 2,
              }}
            >
              <div style={{ maxWidth: '95%', margin: '0 auto', position: 'relative' }}>
                {/* Filters modal */}
                {showFilters && (
                  <ResearchFiltersModal
                    isParliament={isParliament}
                    isWestminster={isWestminster}
                    botMode={botMode}
                    thisYear={thisYear}
                    initial={{
                      researchMode,
                      recordType,
                      sessions,
                      house,
                      jurisdiction,
                      legislationType,
                      currentOnly,
                      dateFrom,
                      dateTo,
                      caseLawCourt,
                    }}
                    onApply={draft => {
                      if (!isParliament && draft.researchMode !== researchMode) {
                        setResearchMode(draft.researchMode);
                        updatePreferences({ research_mode: draft.researchMode }).catch(() => {});
                      }
                      setRecordTypePersist(draft.recordType);
                      setSessionsPersist(draft.sessions);
                      setHousePersist(draft.house ?? null);
                      setJurisdictionPersist(draft.jurisdiction);
                      setLegislationTypePersist(draft.legislationType);
                      setCurrentOnlyPersist(draft.currentOnly);
                      setDateFromPersist(draft.dateFrom);
                      setDateToPersist(draft.dateTo);
                      setCourtPersist(draft.caseLawCourt);
                      setShowFilters(false);
                    }}
                    onClose={() => setShowFilters(false)}
                  />
                )}

                {/* Composer card */}
                <Composer
                  fileInputRef={fileInputRef}
                  textareaRef={textareaRef}
                  onFileUpload={handleFileUpload}
                  chatDocuments={chatDocuments}
                  onDeleteDocument={handleDeleteDocument}
                  uploadingDoc={uploadingDoc}
                  uploadError={uploadError}
                  onDismissUploadError={() => setUploadError(null)}
                  input={input}
                  setInput={setInput}
                  loading={loading}
                  onSend={handleSend}
                  onStop={handleStop}
                  chatMode={chatMode}
                  isParliament={isParliament}
                  isWestminster={isWestminster}
                  showFinishedSession={features.session_feedback_enabled}
                  onFinishedSession={() => modals.open('sessionFeedback')}
                  sessionFeedbackSent={sessionFeedbackSent}
                  hasMessages={messages.length > 0}
                />
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
            isParliament={isParliament}
            isWestminster={isWestminster}
          />
        </div>
      </div>

      {/* ── Modals ───────────────────────────────────────────── */}

      {features.matters_enabled && showCreateMatterModal && (
        <CreateMatterModal
          onClose={() => setShowCreateMatterModal(false)}
          onCreated={matter => {
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
            getMatters()
              .then(setMatters)
              .catch(() => {});
          }}
        />
      )}

      {features.matters_enabled && showAssignModal && (
        <AssignMatterModal
          matters={matters}
          currentMatterId={recentChats.find(c => c.id === assigningChatId)?.matter_id}
          onClose={() => setShowAssignModal(false)}
          onAssign={async matterId => {
            await assignChatToMatter(assigningChatId, matterId);
            getChats()
              .then(setRecentChats)
              .catch(err => console.warn('Failed to fetch chats:', err));
            getMatters()
              .then(setMatters)
              .catch(() => {});
            setShowAssignModal(false);
          }}
        />
      )}

      {modals.dataSources && (
        <DataSourcesModal
          botName={botInfo.name}
          onClose={() => modals.close('dataSources')}
          isParliament={isParliament}
          isWestminster={isWestminster}
        />
      )}

      {modals.about && (
        <AboutModal
          botInfo={botInfo}
          onClose={() => modals.close('about')}
          isParliament={isParliament}
          isWestminster={isWestminster}
        />
      )}

      {modals.admin && (
        <Modal onClose={() => modals.close('admin')} className="p-6 w-[95vw] h-[95vh] overflow-y-auto relative">
            <button
              onClick={() => modals.close('admin')}
              className="absolute top-4 right-4 size-[30px] flex items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              aria-label="Close"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="w-6 h-6"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <AdminPortal currentUser={user} />
        </Modal>
      )}

      {modals.settings && (
        <Modal onClose={() => modals.close('settings')} className="p-6 max-w-lg w-full relative">
            <button
              onClick={() => modals.close('settings')}
              className="absolute top-4 right-4 size-[30px] flex items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              aria-label="Close"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="w-6 h-6"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <Settings />
        </Modal>
      )}

      {modals.weeklyBanner && (
        <WeeklyFeedbackBanner
          userId={user.id}
          botName={botInfo.name}
          onClose={() => modals.close('weeklyBanner')}
          onSubmitted={() => {
            localStorage.setItem(`weeklyFeedbackSubmitted_${user.id}`, Date.now().toString());
            setSurveyDue(false);
          }}
        />
      )}

      {modals.sessionFeedback && (
        <SessionFeedbackModal
          chatId={currentChatId}
          messageCount={messages.length}
          botName={botInfo.name}
          onClose={() => modals.close('sessionFeedback')}
          // The label flips to "Feedback sent"; the button stays clickable, as
          // a lawyer who carries on in the same thread may submit again.
          onSubmitted={() => {
            if (currentChatId) localStorage.setItem(`sessionFeedbackSubmitted_${currentChatId}`, '1');
          }}
        />
      )}

      {modals.history && (
        <Modal onClose={() => modals.close('history')} className="max-w-2xl w-full h-[80vh] relative overflow-hidden">
          <HistoryModal onClose={() => modals.close('history')} onSelectChat={loadChat} />
        </Modal>
      )}

      <SettingsMenuModal
        isOpen={modals.settingsMenu}
        onClose={() => modals.close('settingsMenu')}
        user={user}
        botName={botInfo.name}
        darkMode={darkMode}
        onToggleDarkMode={async () => {
          const next = !darkMode;
          setDarkMode(next);
          await updatePreferences({ dark_mode: next }).catch(e => console.error('Failed to save preference', e));
        }}
        onOpenAccountSettings={() => modals.open('settings')}
        onOpenAdminPortal={() => modals.open('admin')}
        onOpenAbout={() => modals.open('about')}
        onOpenDataSources={() => modals.open('dataSources')}
        onLogout={logout}
      />

      {!noticeAcknowledged && (
        <DataSensitivityNotice
          onAcknowledge={() => setNoticeAcknowledged(true)}
          botName={botInfo.name}
          botLogoEmoji={botInfo.logoEmoji}
          isParliament={isParliament}
          isWestminster={isWestminster}
        />
      )}
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
