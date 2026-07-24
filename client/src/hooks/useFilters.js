import { useState } from 'react';
import { LATEST_SESSION } from '../constants/research';

// Parse the persisted `filter_sessions` JSON array; fall back to the latest
// session so the parliament session filter defaults to the current term.
function readSessions() {
  const raw = localStorage.getItem('filter_sessions');
  if (!raw) return [LATEST_SESSION];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [LATEST_SESSION];
  } catch {
    return [LATEST_SESSION];
  }
}

// Research filter state (jurisdiction, dates, court, legislation type,
// current-only), moved from App.jsx. Filters persist in two layers:
// - global defaults under localStorage `filter_*` keys
// - per-chat snapshots under `filter_chat_<id>` (written on every change while
//   a chat is active, restored by restoreFiltersForChat when a chat is opened)
export function useFilters(currentChatId) {
  const thisYear = String(new Date().getFullYear());

  const [jurisdiction, setJurisdiction] = useState(() => localStorage.getItem('filter_jurisdiction') || null);
  const [dateFrom, setDateFrom] = useState(() => localStorage.getItem('filter_dateFrom') || '');
  const [dateTo, setDateTo] = useState(() => localStorage.getItem('filter_dateTo') || String(new Date().getFullYear()));
  const [caseLawCourt, setCaseLawCourt] = useState(() => localStorage.getItem('filter_caseLawCourt') || '');
  const [legislationType, setLegislationType] = useState(() => localStorage.getItem('filter_legislationType') || null);
  const [currentOnly, setCurrentOnly] = useState(() => localStorage.getItem('filter_currentOnly') !== 'false');
  // Parliament-mode filters (only surfaced when the bot is in parliamentary_records mode)
  const [recordType, setRecordType] = useState(() => localStorage.getItem('filter_recordType') || null);
  // Session filter — multiselect array of Holyrood session numbers; defaults to
  // the latest session. Empty array = no session restriction (all sessions).
  const [sessions, setSessions] = useState(readSessions);

  const saveFiltersToChatStorage = (chatId, overrides = {}) => {
    if (!chatId) return;
    const filters = {
      dateFrom,
      dateTo,
      jurisdiction,
      court: caseLawCourt,
      legislationType,
      currentOnly,
      recordType,
      sessions,
      ...overrides,
    };
    localStorage.setItem(`filter_chat_${chatId}`, JSON.stringify(filters));
  };
  const setJurisdictionPersist = v => {
    setJurisdiction(v);
    if (v) localStorage.setItem('filter_jurisdiction', v);
    else localStorage.removeItem('filter_jurisdiction');
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { jurisdiction: v });
  };
  const setDateFromPersist = v => {
    setDateFrom(v);
    localStorage.setItem('filter_dateFrom', v);
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { dateFrom: v });
  };
  const setDateToPersist = v => {
    setDateTo(v);
    localStorage.setItem('filter_dateTo', v);
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { dateTo: v });
  };
  const setCourtPersist = v => {
    setCaseLawCourt(v);
    localStorage.setItem('filter_caseLawCourt', v);
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { court: v });
  };
  const setLegislationTypePersist = v => {
    setLegislationType(v);
    if (v) localStorage.setItem('filter_legislationType', v);
    else localStorage.removeItem('filter_legislationType');
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { legislationType: v });
  };
  const setCurrentOnlyPersist = v => {
    setCurrentOnly(v);
    localStorage.setItem('filter_currentOnly', String(v));
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { currentOnly: v });
  };
  const setRecordTypePersist = v => {
    setRecordType(v);
    if (v) localStorage.setItem('filter_recordType', v);
    else localStorage.removeItem('filter_recordType');
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { recordType: v });
  };
  const setSessionsPersist = v => {
    const arr = Array.isArray(v) ? v : [];
    setSessions(arr);
    localStorage.setItem('filter_sessions', JSON.stringify(arr));
    if (currentChatId) saveFiltersToChatStorage(currentChatId, { sessions: arr });
  };
  const clearAllFilters = () => {
    setJurisdictionPersist(null);
    setDateFromPersist('');
    setDateToPersist(thisYear);
    setCourtPersist('');
    setLegislationTypePersist(null);
    setCurrentOnlyPersist(false);
    setRecordTypePersist(null);
    setSessionsPersist([LATEST_SESSION]);
  };
  const sessionsAreDefault = sessions.length === 1 && sessions[0] === LATEST_SESSION;
  const hasActiveFilters =
    jurisdiction ||
    dateFrom ||
    dateTo !== thisYear ||
    caseLawCourt ||
    legislationType ||
    currentOnly ||
    recordType ||
    !sessionsAreDefault;

  // Restore the per-chat filter snapshot when opening a chat; any filter not in
  // the snapshot falls back to the chat's matter-level defaults (if provided).
  const restoreFiltersForChat = (chatId, chatMatter = null) => {
    const saved = localStorage.getItem(`filter_chat_${chatId}`);
    const savedFilters = saved
      ? (() => {
          try {
            return JSON.parse(saved);
          } catch {
            return {};
          }
        })()
      : {};
    if (saved) {
      const f = savedFilters;
      if (f.dateFrom !== undefined) {
        setDateFrom(f.dateFrom);
        localStorage.setItem('filter_dateFrom', f.dateFrom);
      }
      if (f.dateTo !== undefined) {
        setDateTo(f.dateTo);
        localStorage.setItem('filter_dateTo', f.dateTo);
      }
      if (f.jurisdiction !== undefined) {
        setJurisdiction(f.jurisdiction);
        if (f.jurisdiction) localStorage.setItem('filter_jurisdiction', f.jurisdiction);
        else localStorage.removeItem('filter_jurisdiction');
      }
      if (f.court !== undefined) {
        setCaseLawCourt(f.court);
        localStorage.setItem('filter_caseLawCourt', f.court);
      }
      if (f.legislationType !== undefined) {
        setLegislationType(f.legislationType);
        if (f.legislationType) localStorage.setItem('filter_legislationType', f.legislationType);
        else localStorage.removeItem('filter_legislationType');
      }
      if (f.currentOnly !== undefined) {
        setCurrentOnly(f.currentOnly);
        localStorage.setItem('filter_currentOnly', String(f.currentOnly));
      }
      if (f.recordType !== undefined) {
        setRecordType(f.recordType);
        if (f.recordType) localStorage.setItem('filter_recordType', f.recordType);
        else localStorage.removeItem('filter_recordType');
      }
      if (Array.isArray(f.sessions)) {
        setSessions(f.sessions);
        localStorage.setItem('filter_sessions', JSON.stringify(f.sessions));
      }
    }
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
  };

  return {
    thisYear,
    jurisdiction,
    dateFrom,
    dateTo,
    caseLawCourt,
    legislationType,
    currentOnly,
    recordType,
    sessions,
    setJurisdiction,
    setDateFrom,
    setDateTo,
    setCaseLawCourt,
    setLegislationType,
    setCurrentOnly,
    setJurisdictionPersist,
    setDateFromPersist,
    setDateToPersist,
    setCourtPersist,
    setLegislationTypePersist,
    setCurrentOnlyPersist,
    setRecordTypePersist,
    setSessionsPersist,
    saveFiltersToChatStorage,
    clearAllFilters,
    hasActiveFilters,
    restoreFiltersForChat,
  };
}
