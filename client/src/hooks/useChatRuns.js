import { useState, useRef, useCallback, useEffect } from 'react';

// Per-chat run registry — the bookkeeping that lets several chats research at
// once. A "run" is one /api/chat exchange: its AbortController, its accumulated
// assistant draft, its tool activity, and the live-only artefacts (suggestion
// chips, response time) that have no DB column and would otherwise be lost the
// moment the user switches away.
//
// Storage is deliberately asymmetric. Token-level mutation for a BACKGROUND run
// must cost zero React renders, while run start/stop must re-render the Sidebar.
// So the runs themselves live in a mutable Map in a ref (free mutation) and a
// coarse `runSummaries` object is published at the handful of moments the UI
// actually cares about. The VISIBLE chat still renders through useChat's
// existing messages/agentStatus/activities state, mirrored by useChat — so its
// render path is unchanged from before this feature.
//
// Keys: the numeric chatId, or the string `draft:N` for the window between
// clicking Send and createChat resolving. Numbers and strings never collide, so
// `runs.get(chatId)` needs no coercion.

// The server-side RequestQueue is shared across ALL users (Ollama allows 3
// concurrent requests in total, OpenRouter 10). Three saturates the Ollama
// deployment for a single lawyer; more would just be client-side queueing that
// starves everyone else. /api/research/plan takes a slot on the same queue, so
// Deep Research Phase A counts against this too.
export const MAX_CONCURRENT_RUNS = 3;

const MAX_RUN_ENTRIES = 20;
const MAX_LIVE_EXTRAS = 100;
const RUN_LIMIT_NOTICE_MS = 6000;

export const RUN_LIMIT_MESSAGE =
  'Three research runs are already in progress. Wait for one to finish — or stop one from the sidebar — before starting another.';

// Shared frozen empty Map so a cleared activity set is referentially stable.
export const EMPTY_ACTIVITIES = new Map();

const ACTIVE_STATUSES = new Set(['planning', 'streaming']);

export const isActive = run => !!run && ACTIVE_STATUSES.has(run.status);
export const isActiveStatus = status => ACTIVE_STATUSES.has(status);

// ── Pure transcript helpers ────────────────────────────────────────────────
// Shared by the streaming path and the rehydrate path so both agree on what
// "the draft bubble" is.

// The trailing un-saved assistant bubble, set ABSOLUTELY from the run's
// accumulated draft rather than by appending a delta — re-entering a chat
// mid-stream then cannot produce a doubled or truncated bubble. `!last.id`
// keeps tokens off a *saved* DB row when the loaded history already ends in a
// completed answer.
export const upsertDraft = (prev, text) => {
  const last = prev[prev.length - 1];
  if (last?.role === 'assistant' && !last.id) {
    const next = [...prev];
    next[next.length - 1] = { ...last, content: text };
    return next;
  }
  return [...prev, { role: 'assistant', content: text }];
};

// Swap the draft bubble for the finished message (or append if there is none).
export const replaceDraft = (prev, message) => {
  const last = prev[prev.length - 1];
  if (last?.role === 'assistant' && !last.id) {
    const next = [...prev];
    next[next.length - 1] = message;
    return next;
  }
  return [...prev, message];
};

// Rebuild the assistant message from the saved DB row, preserving the
// client-side fields the row cannot carry (suggestions have no DB column at
// all; responseTimeMs/costUsd are measured here).
export const mergeSavedRow = (prev, saved, extras) => {
  const next = [...prev];
  for (let i = next.length - 1; i >= 0; i--) {
    if (next[i].role === 'assistant' && !next[i].id) {
      next[i] = {
        ...saved,
        responseTimeMs: extras?.responseTimeMs ?? next[i].responseTimeMs,
        costUsd: extras?.costUsd ?? next[i].costUsd,
        sources: next[i].sources ?? saved.sources,
        suggestions: extras?.suggestions ?? next[i].suggestions,
      };
      break;
    }
  }
  return next;
};

// Classify a send failure. Pure — the caller decides what to do with it.
export const formatSendError = error => {
  if (
    error.name === 'AbortError' ||
    error.message?.includes('aborted') ||
    error.message?.includes('canceled')
  ) {
    return { kind: 'abort', text: '' };
  }
  if (error.status === 401 || error.response?.status === 401) {
    return { kind: 'auth', text: '' };
  }
  const detail = error.response?.data?.detail;
  const match = error.message?.match(/status code (\d{3})/);
  const text = detail
    ? `Error: ${detail}`
    : match
      ? `Error: ${
          {
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            408: 'Request Timeout',
            429: 'Too Many Requests',
            500: 'Internal Server Error',
            502: 'Bad Gateway',
            503: 'Service Unavailable',
            504: 'Gateway Timeout',
          }[parseInt(match[1])] || 'Unknown Error'
        } (${match[1]})`
      : `Error: ${error.message}`;
  return { kind: 'error', text };
};

export function useChatRuns() {
  const runsRef = useRef(new Map());
  // savedMessageId -> { suggestions, responseTimeMs, costUsd }. Keyed by
  // message id rather than by run, so it outlives the run entry and also fixes
  // the pre-existing wart where re-opening a chat you just finished drops the
  // suggestion chips.
  const liveExtrasRef = useRef(new Map());
  // The run whose output belongs in the visible transcript. Compared by OBJECT
  // IDENTITY, never by chatId: while createChat is in flight currentChatId is
  // null, so an id comparison would call a brand-new blank thread "visible" and
  // stream the old run's tokens into it.
  const visibleRunRef = useRef(null);
  const loadSeqRef = useRef(0);
  const draftSeqRef = useRef(0);
  const noticeTimerRef = useRef(null);

  const [runSummaries, setRunSummaries] = useState({});
  const [visibleRunActive, setVisibleRunActive] = useState(false);
  const [runLimitNotice, setRunLimitNotice] = useState(null);

  // Publish the coarse view the Sidebar and the loading flags read. Called at
  // run created / chatId adopted / phase change / terminal / seen / deleted —
  // roughly six renders per run, versus one per token if runs were state.
  const bumpSummaries = useCallback(() => {
    const next = {};
    for (const [key, run] of runsRef.current) {
      if (typeof key !== 'number') continue; // draft runs have no sidebar row yet
      next[key] = { status: run.status, seen: run.seen, startedAt: run.startedAt };
    }
    setRunSummaries(next);
    setVisibleRunActive(isActive(visibleRunRef.current));
  }, []);

  const isVisible = useCallback(run => visibleRunRef.current === run, []);
  const getRun = useCallback(chatId => runsRef.current.get(chatId) || null, []);

  const activeRunCount = useCallback(() => {
    let n = 0;
    for (const run of runsRef.current.values()) if (isActive(run)) n++;
    return n;
  }, []);

  // Drop the oldest terminal entries once the registry grows. Active runs and
  // plans awaiting approval are never evicted.
  const pruneRuns = useCallback(() => {
    if (runsRef.current.size <= MAX_RUN_ENTRIES) return;
    const evictable = [...runsRef.current.entries()]
      .filter(([, r]) => !isActive(r) && r.status !== 'awaiting_approval')
      .sort((a, b) => a[1].startedAt - b[1].startedAt);
    let over = runsRef.current.size - MAX_RUN_ENTRIES;
    for (const [key] of evictable) {
      if (over-- <= 0) break;
      runsRef.current.delete(key);
    }
  }, []);

  const rememberExtras = useCallback((messageId, extras) => {
    if (!messageId || !extras) return;
    liveExtrasRef.current.set(messageId, extras);
    if (liveExtrasRef.current.size > MAX_LIVE_EXTRAS) {
      const excess = liveExtrasRef.current.size - MAX_LIVE_EXTRAS;
      let i = 0;
      for (const key of liveExtrasRef.current.keys()) {
        if (i++ >= excess) break;
        liveExtrasRef.current.delete(key);
      }
    }
  }, []);

  // Re-apply the live-only fields onto rows loaded back from the DB.
  const applyExtras = useCallback(
    msgs =>
      msgs.map(m =>
        m.id && liveExtrasRef.current.has(m.id) ? { ...m, ...liveExtrasRef.current.get(m.id) } : m
      ),
    []
  );

  const showRunLimitNotice = useCallback(() => {
    setRunLimitNotice(RUN_LIMIT_MESSAGE);
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    noticeTimerRef.current = setTimeout(() => setRunLimitNotice(null), RUN_LIMIT_NOTICE_MS);
  }, []);

  const dismissRunLimitNotice = useCallback(() => {
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    setRunLimitNotice(null);
  }, []);

  useEffect(() => () => noticeTimerRef.current && clearTimeout(noticeTimerRef.current), []);

  // Create a run for `chatId` (null when the chat row does not exist yet).
  // Returns null and raises the notice when the concurrency cap is hit — the
  // caller must check this BEFORE clearing the composer or pushing a bubble.
  const createRun = useCallback(
    ({ chatId = null, status = 'streaming', controller }) => {
      if (activeRunCount() >= MAX_CONCURRENT_RUNS) {
        showRunLimitNotice();
        return null;
      }
      const existing = chatId != null ? runsRef.current.get(chatId) : null;
      if (isActive(existing)) return null; // one run per chat

      const key = chatId != null ? chatId : `draft:${++draftSeqRef.current}`;
      const run = {
        key,
        chatId,
        controller,
        status,
        agentStatus: '',
        activities: new Map(),
        draft: '',
        pendingPlan: null,
        errorText: null,
        savedMessageId: null,
        extras: null,
        sourcesMsgId: null,
        deepResearchOwed: false,
        seen: true,
        startedAt: Date.now(),
      };
      runsRef.current.set(key, run);
      pruneRuns();
      return run;
    },
    [activeRunCount, pruneRuns, showRunLimitNotice]
  );

  // Re-key a draft run once its chat row exists.
  const adoptChatId = useCallback(
    (run, chatId) => {
      if (!run || run.chatId === chatId) return;
      runsRef.current.delete(run.key);
      run.key = chatId;
      run.chatId = chatId;
      runsRef.current.set(chatId, run);
      bumpSummaries();
    },
    [bumpSummaries]
  );

  const setRunStatus = useCallback(
    (run, status) => {
      if (!run) return;
      run.status = status;
      bumpSummaries();
    },
    [bumpSummaries]
  );

  const deleteRun = useCallback(
    run => {
      if (!run) return;
      runsRef.current.delete(run.key);
      if (visibleRunRef.current === run) visibleRunRef.current = null;
      bumpSummaries();
    },
    [bumpSummaries]
  );

  const setVisibleRun = useCallback(
    run => {
      visibleRunRef.current = run || null;
      setVisibleRunActive(isActive(run));
    },
    []
  );

  // Explicit stop. The abort genuinely cancels the run server-side
  // (_watch_disconnect in routers/ai.py), which is what an explicit stop means.
  const stopRun = useCallback(
    target => {
      const run = typeof target === 'object' && target !== null ? target : runsRef.current.get(target);
      if (!isActive(run)) return null;
      run.controller?.abort();
      run.controller = null;
      run.status = 'stopped';
      run.agentStatus = 'Stopped by user.';
      run.activities.clear();
      run.seen = visibleRunRef.current === run;
      bumpSummaries();
      return run;
    },
    [bumpSummaries]
  );

  // Logout: the session is dead, so nothing may keep streaming.
  const abortAll = useCallback(() => {
    for (const run of runsRef.current.values()) run.controller?.abort();
    runsRef.current.clear();
    liveExtrasRef.current.clear();
    visibleRunRef.current = null;
    setVisibleRunActive(false);
    setRunSummaries({});
    dismissRunLimitNotice();
  }, [dismissRunLimitNotice]);

  const anyRunActive = visibleRunActive || Object.values(runSummaries).some(s => isActiveStatus(s.status));

  // The tab is the ONLY thing that persists an answer — routers/ai.py never
  // writes a Message row — so closing it mid-run destroys work that has already
  // cost money and queue time.
  useEffect(() => {
    if (!anyRunActive) return;
    const onBeforeUnload = e => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [anyRunActive]);

  return {
    runsRef,
    liveExtrasRef,
    visibleRunRef,
    loadSeqRef,
    runSummaries,
    visibleRunActive,
    anyRunActive,
    runLimitNotice,
    dismissRunLimitNotice,
    createRun,
    adoptChatId,
    setRunStatus,
    deleteRun,
    setVisibleRun,
    stopRun,
    abortAll,
    getRun,
    isVisible,
    activeRunCount,
    bumpSummaries,
    rememberExtras,
    applyExtras,
  };
}
