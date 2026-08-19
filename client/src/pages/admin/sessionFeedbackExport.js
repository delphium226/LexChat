// The session-feedback CSV export, shared by the two places that offer it:
// the Session Feedback tab (the responses on their own) and the Developer tab
// (the same rows with the thread's transcript attached, one row per message).
//
// One definition of the columns, deliberately. The transcript export is
// specified as "the feedback export, plus the chat", and two hand-maintained
// column lists would drift the moment a question is added to the form — the
// wider file would quietly stop being a superset of the narrower one, which is
// the property that lets the two be compared at all.
//
// Every field of every response, in question order — the on-screen table shows
// a readable subset, and the point of the export is that nothing is left
// behind. Three groups, in this order:
//
//   1. the form itself, exactly as `SessionFeedbackOut` returns it — including
//      the derived `session_mode`, which says whether the thread was worked
//      conversationally, in research mode, or in Deep Research;
//   2. the derived session length, joined from /session/durations on chat_id —
//      it is the tab's headline metric and cannot be recomputed from the form;
//   3. the filter panel's state at submit time, flattened one column per
//      filter rather than a single JSON blob, so the sheet can be pivoted on
//      jurisdiction or record type without unpacking anything first.
//
// Closed answers are exported RAW ('one_go', 'partially'), not as the display
// labels. The raw values are what the database holds and what any later
// analysis will group by; the labels are a rendering decision belonging to the
// tab, and freezing them into an exported dataset would make the two drift.
//
// Dates stay as the ISO strings the API returned, for the same reason: a
// localised "13/08/2026, 14:32:07" is ambiguous across locales and sorts
// alphabetically in a spreadsheet.

// The pre-pilot's fixed run. Unlike every other option this is a closed date
// range rather than a trailing window, and the dates themselves live in
// `PREPILOT_START` / `PREPILOT_END` in routers/feedback.py — the backend
// resolves them against UK local days, so nothing here needs to know about
// BST. Change them there; these strings are display only.
export const PREPILOT = 'prepilot';
export const PREPILOT_LABEL = 'Pre-pilot (11–19 Aug)';
export const PREPILOT_LABEL_LONG = 'the pre-pilot, 11–19 Aug 2026';

// Offered by both exports, so a pair taken at the same setting cover the same
// sessions and can be joined on Session ID.
export const TIMEFRAME_OPTIONS = [
  { value: PREPILOT, label: PREPILOT_LABEL },
  { value: '1', label: 'Last 1 Day' },
  { value: '3', label: 'Last 3 Days' },
  { value: '7', label: 'Last 7 Days' },
  { value: '30', label: 'Last 30 Days' },
  { value: '90', label: 'Last 90 Days' },
  { value: 'all', label: 'All Time' },
];

const FILTER_COLUMNS = [
  ['Research mode', 'research_mode'],
  ['Chat mode', 'chat_mode'],
  ['Jurisdiction', 'jurisdiction'],
  ['Date from', 'date_from'],
  ['Date to', 'date_to'],
  ['Court', 'court'],
  ['Legislation type', 'legislation_type'],
  ['Current only', 'current_only'],
  ['Record type', 'record_type'],
  ['Sessions', 'sessions'],
  ['House', 'house'],
];

const filterValue = (row, key) => {
  const value = row.filters?.[key];
  if (value === undefined || value === null) return '';
  return Array.isArray(value) ? value.join(' ') : value;
};

export const SESSION_EXPORT_COLUMNS = [
  // The session's identifier, first because it is what the other tabs, the
  // database and any follow-up question about a response all key on. It is
  // `chats.id` — a session IS a thread here, and the two names are used
  // interchangeably on this tab. Blank where the form was submitted outside a
  // thread, or where the thread has since been deleted (`chat_id` is SET NULL
  // on delete, so the response survives its session).
  //
  // Distinct from "Response ID" below, which identifies the form: a lawyer who
  // resubmits corrects their answer, giving two response IDs for one session ID
  // — though only the latest is exported.
  { label: 'Session ID', value: r => r.chat_id },
  { label: 'Response ID', value: r => r.id },
  { label: 'User', value: r => r.username },
  { label: 'Submitted at', value: r => r.created_at },
  { label: 'Finished session at', value: r => r.finished_at },
  { label: 'Thread', value: r => r.chat_title },
  { label: 'Messages in thread', value: r => r.message_count },
  // Conversational / research / deep_research, derived server-side and NOT the
  // same value as "Filter: Chat mode" further right: this one prefers what the
  // thread is observed to have done (a stored research plan proves Deep
  // Research ran) over the mode toggle's state at submit time. Both are
  // exported — where they disagree, the lawyer changed mode mid-thread.
  { label: 'Session mode', value: r => r.session_mode },
  { label: 'Q1 manual time (hrs)', value: r => r.manual_time_hours },
  { label: 'Q2 time saved (hrs)', value: r => r.time_saved_hours },
  { label: 'Q3 session continuity', value: r => r.session_continuity },
  { label: 'Q4 checking time (hrs)', value: r => r.verification_hours },
  { label: 'Q5a found right law', value: r => r.found_right_law },
  { label: 'Q5b observations', value: r => r.found_right_law_notes },
  { label: 'Q5c right jurisdiction', value: r => r.right_jurisdiction },
  { label: 'Q5d observations', value: r => r.right_jurisdiction_notes },
  { label: 'Q6a references accurate', value: r => r.references_accurate },
  { label: 'Q6b observations', value: r => r.references_notes },
  { label: 'Q7a referred incorrectly', value: r => r.refers_incorrectly },
  { label: 'Q7b observations', value: r => r.refers_incorrectly_notes },
  { label: 'Q8 confidence (1-5)', value: r => r.confidence },
  { label: 'Q9a ease of use (1-5)', value: r => r.ease_of_use },
  { label: 'Q9b reason', value: r => r.ease_of_use_reason },
  { label: 'Q10 other comments', value: r => r.other_comments },
  // Session length. Blank where the thread was not measured — the form was
  // submitted outside a thread, or the thread has neither a timed press nor an
  // answer to measure to. Blank rather than 0, which would read as an instant
  // session and pull any average computed over the column down.
  { label: 'Session started at', value: r => r.session?.started_at },
  { label: 'Session ended at', value: r => r.session?.ended_at },
  { label: 'Session end signal', value: r => r.session?.end_signal },
  { label: 'Session length (secs, capped)', value: r => r.session?.duration_seconds },
  { label: 'Session length (secs, raw)', value: r => r.session?.elapsed_seconds },
  { label: 'Session was capped', value: r => (r.session ? r.session.capped : '') },
  { label: 'Queries in session', value: r => r.session?.queries },
  ...FILTER_COLUMNS.map(([label, key]) => ({
    label: `Filter: ${label}`,
    value: r => filterValue(r, key),
  })),
];

// The transcript block, appended to the columns above by the Developer tab's
// export. At the END rather than next to the thread's other identity columns:
// message content is by far the longest value in the file, and a spreadsheet is
// only readable if the long free text sits to the right of everything a reader
// scans. (Session ID, Message #) is what makes a row unique.
//
// `_msg` is attached by `buildTranscriptRows`, so a row whose session has no
// transcript renders these as blanks rather than throwing.
export const TRANSCRIPT_COLUMNS = [
  { label: 'Message #', value: r => r._msg?.seq },
  { label: 'Message role', value: r => r._msg?.role },
  { label: 'Message sent at', value: r => r._msg?.created_at },
  { label: 'Message model', value: r => r._msg?.model },
  { label: 'Message provider', value: r => r._msg?.provider },
  { label: 'Message cost (USD)', value: r => r._msg?.cost_usd },
  // The per-message thumbs rating, which is a different instrument from the
  // end-of-session form — worth having beside it, since a session rated well
  // overall can still contain the one answer the lawyer marked down.
  { label: 'Message rating', value: r => r._msg?.rating },
  { label: 'Message rating comment', value: r => r._msg?.feedback_comment },
  { label: 'Message content', value: r => r._msg?.content },
];

/**
 * Attach each response's measured session, for the length columns.
 *
 * Both endpoints are filtered on when the form arrived, so the two sides
 * describe the same population and the join is on chat_id alone — a response
 * with no chat_id, or a thread with no end signal, simply has no session and
 * its length columns come out blank.
 */
export function buildExportRows(rows, durationSessions) {
  const sessionByChat = new Map((durationSessions || []).map(s => [s.chat_id, s]));
  return rows.map(r => ({ ...r, session: r.chat_id ? sessionByChat.get(r.chat_id) : undefined }));
}

/**
 * Explode the responses to one row per message, for the transcript export.
 *
 * A response whose thread has no messages — no chat_id, a cleared thread —
 * still yields exactly one row, with the message columns blank. Dropping it
 * would mean the wider file silently held fewer responses than the narrower
 * one, so a count taken from either would disagree with the other.
 *
 * `seq` is 1-based and per session, so it reads as "the 3rd turn of this
 * thread" rather than as a database id.
 */
export function buildTranscriptRows(rows, durationSessions, transcripts) {
  const messagesByChat = new Map((transcripts || []).map(t => [t.chat_id, t.messages || []]));
  return buildExportRows(rows, durationSessions).flatMap(row => {
    const messages = row.chat_id ? messagesByChat.get(row.chat_id) : null;
    if (!messages || messages.length === 0) return [{ ...row, _msg: null }];
    return messages.map((message, i) => ({ ...row, _msg: { ...message, seq: i + 1 } }));
  });
}

// `prepilot` / `all` / a day count → a filename fragment that says what the
// file actually contains, so two exports taken at different scopes on the same
// day do not overwrite each other in the downloads folder.
export const timeframeSlug = timeframe =>
  timeframe === PREPILOT ? 'prepilot' : timeframe === 'all' ? 'all-time' : `last-${timeframe}-days`;
