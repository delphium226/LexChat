import { useState, useEffect, useRef } from 'react';
import {
  getModels,
  createChat,
  saveMessage,
  sendMessage,
  getResearchPlan,
  getChatMessages,
  getChatDocuments,
} from '../services/api';
import {
  useChatRuns,
  isActive,
  upsertDraft,
  replaceDraft,
  mergeSavedRow,
  formatSendError,
  EMPTY_ACTIVITIES,
} from './useChatRuns';

// Human-readable status for each worker tool the backend reports.
const toolLabel = tool =>
  ({
    'Research Agent': 'Researching…',
    'Worker: search_legislation': 'Querying legislation database…',
    'Worker: search_legislation_sections': 'Retrieving statutory sections…',
    'Worker: get_legislation_text': 'Reviewing statutory text…',
    'Worker: search_case_law': 'Searching case law database…',
    'Worker: get_case_law_text': 'Retrieving case law judgment…',
    // Scottish Parliament (Holyrood) bot
    'Worker: search_scottish_plenary': 'Searching chamber debates…',
    'Worker: get_scottish_plenary_debate': 'Retrieving the Official Report…',
    'Worker: search_scottish_committee_transcripts': 'Searching committee transcripts…',
    'Worker: get_scottish_committee_transcript': 'Retrieving committee transcript…',
    'Worker: search_scottish_parliament': 'Searching parliamentary records…',
    // UK Parliament (Westminster) bot
    'Worker: search_hansard': 'Searching Hansard…',
    'Worker: get_hansard_debate': 'Retrieving the Hansard debate…',
    // Both parliamentary bots
    'Worker: search_bills': 'Checking bill progress…',
    'Worker: get_member_info': 'Looking up the member…',
    'Extracting the relevant sections from a large document': 'Summarising document…',
  })[tool] || `${tool}…`;

// Core chat flow, moved from App.jsx: the message list + composer input, the
// active model/provider, streaming status, and the four handlers (send, stop,
// new chat, load chat). handleSend drives the SSE stream from `sendMessage`.
//
// Several chats can research at once. Run bookkeeping lives in `useChatRuns`;
// this hook renders only the VISIBLE chat, mirroring a run's progress into
// messages/agentStatus/activities when — and only when — that run is the one on
// screen (`isVisible`, object identity). A background run keeps streaming into
// its own `run.draft` and persists to its own chat id; nothing it produces may
// touch the visible transcript, the sources rail, or the Deep Research mode.
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
  pendingTitle,
  setTitleUserSet,
  setActiveCite,
  setActiveSourcesMsgId,
  setChatDocuments,
  closeHistoryModal,
  recentChats,
  matters,
  onDeepResearchComplete,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedModelContext, setSelectedModelContext] = useState(256 * 1024);
  const [activeProvider, setActiveProvider] = useState('ollama');
  // History fetch only — streaming state now comes from the run registry.
  const [historyLoading, setHistoryLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState('');
  const [activities, setActivities] = useState(EMPTY_ACTIVITIES);
  // Deep Research: drafted plan awaiting review/approval for the VISIBLE chat
  // (mirror of run.pendingPlan, which is the source of truth)
  const [pendingPlan, setPendingPlan] = useState(null);
  // context usage is written from the response but not currently read anywhere
  const [, setContextUsage] = useState(null);

  const chatScrollRef = useRef(null);
  const textareaRef = useRef(null);

  const runs = useChatRuns();
  const {
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
    bumpSummaries,
    rememberExtras,
    applyExtras,
  } = runs;

  // The visible chat is streaming (covers the pre-createChat window, where the
  // run exists but has no chat id yet).
  const streaming = visibleRunActive;

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

  // Stops the VISIBLE chat's run only — the Composer's Stop button can never
  // reach a background run. Sidebar rows have their own stop control.
  const handleStop = () => {
    const run = stopRun(visibleRunRef.current);
    if (run) {
      setAgentStatus('Stopped by user.');
      setActivities(EMPTY_ACTIVITIES);
    }
  };

  // Stop a background run from the sidebar (looked up by chat id).
  const handleStopChat = chatId => {
    const run = stopRun(chatId);
    if (run && isVisible(run)) {
      setAgentStatus('Stopped by user.');
      setActivities(EMPTY_ACTIVITIES);
    }
  };

  // The execution exchange shared by the standard modes and Deep Research
  // Phase B: stream /api/chat, render tokens/progress, persist the assistant
  // result (with the approved plan attached in Deep Research for audit).
  const runExchange = async (messagesToSend, run, deepResearchPlan = null) => {
    const requestStartTime = Date.now();
    const response = await sendMessage(
        messagesToSend,
        selectedModel,
        selectedModelContext,
        status => {
          // Every branch writes to the run first; the React setters are the
          // mirror, applied only when this run owns the visible transcript.
          if (status.type === 'tool_start') {
            const label = toolLabel(status.tool);
            if (status.id) run.activities.set(status.id, label);
            run.agentStatus = label;
            if (isVisible(run)) {
              setActivities(new Map(run.activities));
              setAgentStatus(label);
            }
          } else if (status.type === 'tool_end') {
            if (status.id) run.activities.delete(status.id);
            run.agentStatus = 'Analysing findings…';
            if (isVisible(run)) {
              setActivities(new Map(run.activities));
              setAgentStatus(run.agentStatus);
            }
          } else if (status.type === 'token') {
            run.draft += status.content;
            run.activities.clear();
            run.agentStatus = 'Typing…';
            if (isVisible(run)) {
              setActivities(EMPTY_ACTIVITIES);
              setAgentStatus('Typing…');
              setMessages(prev => upsertDraft(prev, run.draft));
            }
          } else if (status.type === 'queue' || status.type === 'warning') {
            run.agentStatus = status.message;
            if (isVisible(run)) setAgentStatus(status.message);
          }
        },
        run.controller.signal,
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
          sessions: filters.sessions,
          house: filters.house,
          chatId: run.chatId,
        },
        deepResearchPlan
      );

      if (isVisible(run) && response.stats) setContextUsage(response.stats);

      // Live-only by design: `suggestions` has no DB column at all, and the
      // timing/cost are measured here — so they are stashed against the saved
      // message id and re-applied by loadChat when the user comes back.
      run.extras = {
        suggestions: response.suggestions,
        responseTimeMs: Date.now() - requestStartTime,
        costUsd: response.timing?.total_cost_usd || null,
      };
      const withTiming = {
        ...response,
        ...run.extras,
        ...(deepResearchPlan ? { research_plan: deepResearchPlan } : {}),
      };
      if (isVisible(run)) setMessages(prev => replaceDraft(prev, withTiming));

      if (run.chatId) {
        const saved = await saveMessage(
          run.chatId,
          'assistant',
          response.content,
          response.model,
          response.provider,
          response.timing?.total_cost_usd ?? null,
          response.sources ?? null,
          deepResearchPlan
        ).catch(err => {
          console.error('Failed to save assistant message:', err);
          return null;
        });
        if (saved) {
          run.savedMessageId = saved.id;
          rememberExtras(saved.id, run.extras);
          if (response.sources?.length) run.sourcesMsgId = saved.id;
          if (isVisible(run)) {
            setMessages(prev => mergeSavedRow(prev, saved, run.extras));
            // Gated: a background completion must never yank the sources rail
            // out from under whatever the user is reading.
            if (response.sources?.length) setActiveSourcesMsgId(saved.id);
          }
        }
      }
  };

  // Shared error handling for handleSend / handleRunPlan. The classification is
  // pure (formatSendError); what changes here is that the error belongs to a
  // run — a background failure is recorded on the run and rendered by loadChat
  // when the user returns, never in whatever chat is on screen.
  const applySendError = (run, error) => {
    const { kind, text } = formatSendError(error);
    if (kind === 'abort') {
      if (run.status !== 'stopped') run.status = 'stopped';
      return;
    }
    if (kind === 'auth') {
      run.status = 'error';
      logoutWithExpiry();
      return;
    }
    console.error('Error sending message:', error);
    run.status = 'error';
    run.errorText = text;
    // The error bubble REPLACES the partial draft on screen, so drop the draft
    // here too — otherwise loadChat would render both on return.
    run.draft = '';
    if (isVisible(run)) {
      setMessages(prev => replaceDraft(prev, { role: 'assistant', content: text }));
    }
  };

  // Shared cleanup for handleSend / handleRunPlan. Replaces the old
  // controller-identity guard: with several controllers in flight, the run
  // object itself is the identity.
  const finalizeRun = run => {
    run.controller = null;
    if (isActive(run)) run.status = 'done';
    run.activities.clear();
    run.seen = isVisible(run);
    if (isVisible(run)) {
      setAgentStatus(run.status === 'stopped' ? 'Stopped by user.' : '');
      setActivities(EMPTY_ACTIVITIES);
      // Never steal focus back for a run the user has navigated away from.
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
    bumpSummaries();
  };

  const handleSend = async (manualContent = null) => {
    // Per-chat guard, not global: another chat streaming is no longer a reason
    // to refuse. A drafted-but-unapproved plan is still superseded, as before.
    if (isActive(visibleRunRef.current)) return;
    const contentToSend = typeof manualContent === 'string' ? manualContent : input;
    if (!contentToSend.trim() || !selectedModel) return;

    // Checked BEFORE the composer is cleared and before the user bubble is
    // pushed, so a refused send loses nothing.
    const run = createRun({
      chatId: currentChatId,
      status: chatMode === 'deep_research' ? 'planning' : 'streaming',
      controller: new AbortController(),
    });
    if (!run) return;
    setVisibleRun(run);

    const userMsg = { role: 'user', content: contentToSend };
    setMessages(prev => [...prev, userMsg]);
    if (typeof manualContent !== 'string') setInput('');
    setPendingPlan(null); // a new message supersedes any unapproved plan
    run.agentStatus = chatMode === 'deep_research' ? 'Drafting research plan…' : 'Thinking…';
    setAgentStatus(run.agentStatus);
    setActivities(EMPTY_ACTIVITIES);
    bumpSummaries();
    let activeChatId = currentChatId;

    try {
      if (!activeChatId) {
        // Honour a title the user typed before sending; otherwise derive one from
        // the first question.
        const title = pendingTitle || contentToSend.slice(0, 80) + (contentToSend.length > 80 ? '…' : '');
        const newChat = await createChat(title, selectedModel, activeProvider);
        activeChatId = newChat.id;
        adoptChatId(run, activeChatId);
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

      if (chatMode === 'deep_research') {
        // Phase A: draft the plan; execution waits for explicit user approval.
        const draft = await getResearchPlan(
          messagesToSend,
          selectedModel,
          researchMode,
          {
            jurisdiction: filters.jurisdiction,
            dateFrom: filters.dateFrom,
            dateTo: filters.dateTo,
            caseLawCourt: filters.caseLawCourt,
            legislationType: filters.legislationType,
            currentOnly: filters.currentOnly,
            recordType: filters.recordType,
            sessions: filters.sessions,
            house: filters.house,
            chatId: activeChatId,
          },
          run.controller.signal
        );
        if (draft.needs_clarification) {
          const question = draft.question;
          // The planner's clarification options render through the same chip
          // component as a manager follow-up. Not persisted — saveMessage below
          // stores the question text only, so the options are stashed against
          // the saved row to survive a chat switch.
          const options = draft.options || [];
          if (isVisible(run)) {
            setMessages(prev => [...prev, { role: 'assistant', content: question, suggestions: options }]);
          }
          if (activeChatId) {
            const saved = await saveMessage(activeChatId, 'assistant', question).catch(err => {
              console.error('Failed to save clarification message:', err);
              return null;
            });
            if (saved) rememberExtras(saved.id, { suggestions: options });
          }
        } else if (draft.plan) {
          // The run stays in the registry while awaiting approval — that is how
          // the plan card survives a switch to another chat and back.
          run.pendingPlan = draft.plan;
          setRunStatus(run, 'awaiting_approval');
          if (isVisible(run)) setPendingPlan(draft.plan);
        }
      } else {
        await runExchange(messagesToSend, run);
      }
    } catch (error) {
      applySendError(run, error);
    } finally {
      finalizeRun(run);
    }
  };

  // Deep Research Phase B: execute the user-approved (possibly edited) plan.
  // The plan card only ever renders for the visible chat, so this reuses that
  // chat's existing run entry (awaiting_approval → streaming).
  const handleRunPlan = async approvedPlan => {
    const run = visibleRunRef.current;
    if (!run || isActive(run)) return;

    run.controller = new AbortController();
    run.pendingPlan = null;
    run.draft = '';
    run.errorText = null;
    setRunStatus(run, 'streaming');

    setPendingPlan(null);
    run.agentStatus = 'Executing research plan…';
    setAgentStatus(run.agentStatus);
    setActivities(EMPTY_ACTIVITIES);

    try {
      await runExchange([...messages], run, approvedPlan);
      // Deep Research is a one-shot: once the first query/answer pair has
      // completed, drop the chat back to conversational mode. chatMode is a
      // GLOBAL preference, so flipping it from a background run would silently
      // change the mode under a user typing in a different chat — defer it to
      // the moment they come back. The visibility check has to be here rather
      // than in App's callback, which closes over a stale currentChatId.
      if (isVisible(run)) onDeepResearchComplete?.();
      else run.deepResearchOwed = true;
    } catch (error) {
      applySendError(run, error);
    } finally {
      finalizeRun(run);
    }
  };

  const handleCancelPlan = () => {
    const run = visibleRunRef.current;
    if (run?.status === 'awaiting_approval') {
      run.pendingPlan = null;
      deleteRun(run);
    }
    setPendingPlan(null);
  };

  // No abort: starting a new thread must not kill research already running in
  // another one. The outgoing run simply stops mirroring.
  const handleNewChat = () => {
    setVisibleRun(null);
    setAgentStatus('');
    setActivities(EMPTY_ACTIVITIES);
    setMessages([]);
    setInput('');
    setContextUsage(null);
    setCurrentChatId(null);
    setCurrentChatTitle(null);
    setTitleUserSet(false);
    setActiveCite(null);
    setActiveSourcesMsgId(null);
    setChatDocuments([]);
    setPendingPlan(null);
  };

  const loadChat = async chatId => {
    // Stop mirroring the outgoing chat immediately — before the await, or its
    // tokens land in the incoming transcript while the fetch is in flight.
    setVisibleRun(null);
    const seq = ++loadSeqRef.current;
    try {
      setHistoryLoading(true);
      setPendingPlan(null);
      const msgs = await getChatMessages(chatId);
      if (seq !== loadSeqRef.current) return; // a later loadChat superseded this one
      const run = getRun(chatId);

      // The in-flight USER message is already in the DB (handleSend saves it
      // before streaming), so only the assistant side is synthetic. A finished
      // run's answer IS in the DB, so its draft must NOT be appended as well —
      // unless saveMessage failed, in which case the draft is all there is.
      let next = applyExtras(msgs);
      if (run) {
        const answerPersisted = run.status === 'done' && run.savedMessageId;
        if (run.draft && !answerPersisted) next = [...next, { role: 'assistant', content: run.draft }];
        if (run.errorText) next = [...next, { role: 'assistant', content: run.errorText }];
      }
      setMessages(next);
      setCurrentChatId(chatId);
      setCurrentChatTitle(recentChats.find(c => c.id === chatId)?.title || null);
      setTitleUserSet(false);
      closeHistoryModal();
      setContextUsage(null);
      setActiveCite(null);
      setActiveSourcesMsgId(run?.sourcesMsgId ?? null);
      setAgentStatus(isActive(run) ? run.agentStatus : '');
      setActivities(isActive(run) ? new Map(run.activities) : EMPTY_ACTIVITIES);
      setPendingPlan(run?.pendingPlan ?? null);
      setVisibleRun(run);

      if (run) {
        // A Deep Research run that finished while the user was elsewhere owes a
        // mode flip; apply it now they are actually looking at the chat.
        if (run.deepResearchOwed) {
          run.deepResearchOwed = false;
          onDeepResearchComplete?.();
        }
        run.seen = true;
        // Terminal and acknowledged: the DB now holds the answer and
        // liveExtrasRef holds the live-only fields, so the entry is spent.
        if (!isActive(run) && run.status !== 'awaiting_approval') deleteRun(run);
        else bumpSummaries();
      }

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
      if (seq === loadSeqRef.current) setHistoryLoading(false);
    }
  };

  // Clear chat state on logout (called from App's reset effect). Unlike
  // handleNewChat this DOES abort — the session is dead, so nothing may keep
  // streaming (and nothing could be saved if it did).
  const resetChat = () => {
    abortAll();
    setMessages([]);
    setInput('');
    setCurrentChatId(null);
    setCurrentChatTitle(null);
    setTitleUserSet(false);
    setContextUsage(null);
    setAgentStatus('');
    setActivities(EMPTY_ACTIVITIES);
    setHistoryLoading(false);
    setPendingPlan(null);
  };

  return {
    messages,
    input,
    setInput,
    selectedModel,
    activeProvider,
    // `loading` is gone: streaming is per-chat, the history fetch is its own
    // thing, and the favicon wants "any run anywhere".
    streaming,
    historyLoading,
    anyRunActive,
    runSummaries,
    runLimitNotice,
    dismissRunLimitNotice,
    agentStatus,
    activities,
    chatScrollRef,
    textareaRef,
    handleSend,
    handleStop,
    handleStopChat,
    handleNewChat,
    loadChat,
    resetChat,
    pendingPlan,
    handleRunPlan,
    handleCancelPlan,
  };
}
