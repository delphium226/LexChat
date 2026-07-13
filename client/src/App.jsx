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
  RECORD_TYPE_OPTIONS,
  JURISDICTION_OPTIONS,
  JURISDICTION_SHORT,
  COURT_GROUPS,
} from './constants/research';
import { Routes, Route } from 'react-router-dom';
import SystemChat from './pages/SystemChat';
import WeeklyFeedbackBanner from './components/WeeklyFeedbackBanner';
import DataSensitivityNotice from './components/DataSensitivityNotice';
import { BookmarkIcon, ScalesIcon, GavelIcon, CalendarIcon } from './components/ui/icons';
import { GhostBtn } from './components/ui/buttons';
import Modal from './components/ui/Modal';
import { getInitials } from './utils/format';
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

  // Weekly feedback — show banner once per week, button whenever survey not yet submitted this week.
  // Uses a ref (not state) for the checked flag so setting it doesn't trigger
  // a re-render that would cancel the timer via effect cleanup.
  useEffect(() => {
    if (!user || weeklyBannerCheckedRef.current) return;
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
  }, [user]);

  // ── Derived ──────────────────────────────────────────────────

  const researchModeLabel =
    {
      legislation_only: 'Legislation only',
      case_law_only: 'Case law only',
      legislation_and_case_law: 'Legislation & case law',
    }[researchMode] || 'Legislation only';

  const todayISO = new Date().toISOString().slice(0, 10);
  const todayLabel = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

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
    setJurisdictionPersist,
    setDateFromPersist,
    setDateToPersist,
    setCourtPersist,
    setLegislationTypePersist,
    setCurrentOnlyPersist,
    setRecordTypePersist,
    saveFiltersToChatStorage,
    clearAllFilters,
    hasActiveFilters,
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
  } = useChat({
    user,
    logoutWithExpiry,
    chatMode,
    researchMode,
    filters: { jurisdiction, dateFrom, dateTo, caseLawCourt, legislationType, currentOnly, recordType },
    saveFiltersToChatStorage,
    restoreFiltersForChat,
    currentChatId,
    setCurrentChatId,
    setCurrentChatTitle,
    setActiveCite,
    setActiveSourcesMsgId,
    setChatDocuments,
    closeHistoryModal: () => modals.close('history'),
    recentChats,
    matters,
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

  const isParliament = botInfo.researchMode === 'parliamentary_records';
  const jurisdictionLabel = jurisdiction
    ? JURISDICTION_OPTIONS.find(o => o.value === jurisdiction)?.label || 'All jurisdictions'
    : 'All jurisdictions';
  const jurisdictionShort = jurisdiction ? JURISDICTION_SHORT[jurisdiction] || 'All UK' : 'All UK';

  const courtLabel = caseLawCourt
    ? COURT_GROUPS.flatMap(g => g.courts).find(c => c.value === caseLawCourt)?.label || caseLawCourt
    : '';

  const showScotlandNINote =
    (jurisdiction === 'scotland' || jurisdiction === 'northern_ireland') && researchMode !== 'legislation_only';

  const userInitials = getInitials(user?.username);

  // ── Handlers ─────────────────────────────────────────────────

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
            borderBottom: '1px solid var(--ink-200)',
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
                  if (!currentChatId) return;
                  setEditTitleValue(currentChatTitle || '');
                  setEditingTitle(true);
                }}
                title={currentChatId ? 'Click to rename' : undefined}
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  color: 'var(--ink-900)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  cursor: currentChatId ? 'text' : 'default',
                  borderBottom: currentChatId ? '1px dotted var(--ink-300, #9ca3af)' : 'none',
                }}
              >
                {currentChatTitle || 'New thread'}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
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
            {surveyDue && <GhostBtn onClick={() => modals.open('weeklyBanner')}>Take weekly survey</GhostBtn>}
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
                {/* Research context chips */}
                {(() => {
                  const chips = isParliament
                    ? [
                        {
                          icon: <ScalesIcon />,
                          label: chatMode === 'conversational' ? 'Conversational' : 'Parliamentary records',
                        },
                        {
                          icon: <GavelIcon />,
                          label: 'Scottish Parliament (Holyrood)',
                        },
                      ]
                    : [
                        {
                          icon: <ScalesIcon />,
                          label: chatMode === 'conversational' ? 'Conversational' : researchModeLabel,
                        },
                        { icon: <GavelIcon />, label: jurisdictionLabel },
                        { icon: <CalendarIcon />, label: `In force · ${todayLabel}` },
                      ];
                  if (isParliament && recordType) {
                    chips.push({
                      icon: <GavelIcon />,
                      label: RECORD_TYPE_OPTIONS.find(o => o.value === recordType)?.label || recordType,
                    });
                  }
                  if (dateFrom || dateTo !== thisYear) {
                    const dr =
                      dateFrom && dateTo ? `${dateFrom}–${dateTo}` : dateFrom ? `From ${dateFrom}` : `To ${dateTo}`;
                    chips.push({ icon: <CalendarIcon />, label: `Date: ${dr}` });
                  }
                  if (!isParliament && courtLabel && researchMode !== 'legislation_only') {
                    chips.push({ icon: <GavelIcon />, label: courtLabel });
                  }
                  return (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', paddingBottom: 4 }}>
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
                            background: 'var(--paper)',
                            border: '1px solid var(--ink-200)',
                            color: 'var(--ink-600)',
                          }}
                        >
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
                        ? 'Ask a legal question to begin.'
                        : 'Ask about UK legislation or case law to begin.'}
                    </p>
                  </div>
                )}

                {/* Messages */}
                {messages.map((msg, idx) => {
                  if (msg.role === 'tool') return null;
                  return (
                    <ChatMessage
                      key={msg.id ?? idx}
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
                  );
                })}

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
                {/* Filters popover */}
                {showFilters && (
                  <ResearchFiltersModal
                    isParliament={isParliament}
                    researchMode={researchMode}
                    onResearchModeChange={value => {
                      setResearchMode(value);
                      updatePreferences({ research_mode: value }).catch(() => {});
                    }}
                    showScotlandNINote={showScotlandNINote}
                    filters={{
                      recordType,
                      setRecordTypePersist,
                      jurisdiction,
                      setJurisdictionPersist,
                      legislationType,
                      setLegislationTypePersist,
                      currentOnly,
                      setCurrentOnlyPersist,
                      dateFrom,
                      setDateFromPersist,
                      dateTo,
                      setDateToPersist,
                      caseLawCourt,
                      setCourtPersist,
                      hasActiveFilters,
                      clearAllFilters,
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
                  jurisdictionShort={jurisdictionShort}
                  todayISO={todayISO}
                  onToggleFilters={() => setShowFilters(f => !f)}
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
        <DataSourcesModal botName={botInfo.name} onClose={() => modals.close('dataSources')} />
      )}

      {modals.about && <AboutModal botInfo={botInfo} onClose={() => modals.close('about')} />}

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
