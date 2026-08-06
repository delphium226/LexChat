// Shared research-filter option lists. Used by App.jsx (context chips + label
// derivation) and ResearchFiltersModal (the filter popover). Static — kept at
// module scope so they aren't rebuilt on every render.

export const RECORD_TYPE_OPTIONS = [
  { value: null, label: 'All records' },
  { value: 'debates', label: 'Chamber debates' },
  { value: 'written_answers', label: 'Written answers' },
  { value: 'committee', label: 'Committee transcripts' },
];

// Scottish Parliament (Holyrood) sessions — each spans one parliamentary term
// between elections. `value` is the session number sent to the backend, which
// maps it onto a meeting-date window (see SP_SESSIONS in parliament.py).
// Newest-first for display. The session filter is multiselect and defaults to
// the latest session (LATEST_SESSION).
export const SESSION_OPTIONS = [
  { value: 7, label: 'Session 7 (2026–current)' },
  { value: 6, label: 'Session 6 (2021–2026)' },
  { value: 5, label: 'Session 5 (2016–2021)' },
  { value: 4, label: 'Session 4 (2011–2016)' },
  { value: 3, label: 'Session 3 (2007–2011)' },
  { value: 2, label: 'Session 2 (2003–2007)' },
  { value: 1, label: 'Session 1 (1999–2003)' },
];

export const LATEST_SESSION = 7;

// ── Westminster (UK Parliament) filter options ───────────────────────────────
// The Westminster bot runs the same client from a separate deployment, selected
// by the bot's research_mode (GET /api/bot-info). Its filter vocabulary is
// disjoint from Holyrood's: a House dimension (Holyrood is unicameral), a
// different record taxonomy (Hansard's own section types), and Parliaments
// rather than fixed-term sessions.

export const HOUSE_OPTIONS = [
  { value: null, label: 'Both Houses' },
  { value: 'commons', label: 'House of Commons' },
  { value: 'lords', label: 'House of Lords' },
];

export const WM_RECORD_TYPE_OPTIONS = [
  { value: null, label: 'All records' },
  { value: 'chamber', label: 'Chamber debates' },
  { value: 'westminster_hall', label: 'Westminster Hall' },
  { value: 'public_bill_committee', label: 'Public Bill Committees' },
  { value: 'written_statements', label: 'Written statements' },
  { value: 'written_answers', label: 'Written answers' },
];

// `value` is the Parliament number sent to the backend, which maps it onto a
// sitting-date window (see WM_PARLIAMENTS in westminster.py). Newest first.
export const WM_SESSION_OPTIONS = [
  { value: 6, label: '2024– Parliament' },
  { value: 5, label: '2019–2024 Parliament' },
  { value: 4, label: '2017–2019 Parliament' },
  { value: 3, label: '2015–2017 Parliament' },
  { value: 2, label: '2010–2015 Parliament' },
  { value: 1, label: '2005–2010 Parliament' },
];

export const LATEST_WM_SESSION = 6;

export const WESTMINSTER_MODE = 'westminster_records';
export const DRAFTING_MODE = 'drafting';

// Mode-keyed selectors. The filter set is fixed per deployment (one bot = one
// research mode), so these resolve once from botInfo rather than branching on
// per-query user state.
//
// These were two-way (Westminster vs everything else), which meant a third mode
// silently inherited the Holyrood session vocabulary. The drafting bot exposes no
// research filters at all, so it gets an explicit empty answer rather than a
// borrowed one — a Holyrood "Session 7" has no meaning there and must never be
// persisted or sent. Callers that can receive `null` from getLatestSession are
// getLatestSession's own consumers in useFilters.js; both guard for it.
export const getRecordTypeOptions = mode =>
  mode === DRAFTING_MODE ? [] : mode === WESTMINSTER_MODE ? WM_RECORD_TYPE_OPTIONS : RECORD_TYPE_OPTIONS;

export const getSessionOptions = mode =>
  mode === DRAFTING_MODE ? [] : mode === WESTMINSTER_MODE ? WM_SESSION_OPTIONS : SESSION_OPTIONS;

export const getLatestSession = mode =>
  mode === DRAFTING_MODE ? null : mode === WESTMINSTER_MODE ? LATEST_WM_SESSION : LATEST_SESSION;

// Holyrood calls its terms "sessions"; Westminster calls them "Parliaments".
export const getSessionFilterLabel = mode =>
  mode === WESTMINSTER_MODE ? 'Parliament' : 'Session';

export const JURISDICTION_OPTIONS = [
  { value: null, label: 'All jurisdictions' },
  { value: 'england_and_wales', label: 'England & Wales' },
  { value: 'scotland', label: 'Scotland' },
  { value: 'northern_ireland', label: 'Northern Ireland' },
  { value: 'wales', label: 'Wales' },
  { value: 'uk_wide', label: 'UK-wide only' },
];

export const JURISDICTION_SHORT = {
  england_and_wales: 'E&W',
  scotland: 'SCO',
  northern_ireland: 'NI',
  wales: 'WAL',
  uk_wide: 'UK',
};

export const LEGISLATION_TYPE_OPTIONS = [
  { value: null, label: 'All types' },
  { value: 'primary', label: 'Acts (primary)' },
  { value: 'secondary', label: 'SIs & Rules (secondary)' },
  { value: 'draft', label: 'Draft instruments' },
];

export const COURT_GROUPS = [
  {
    group: 'UK-wide',
    courts: [
      { value: 'uksc', label: 'UK Supreme Court' },
      { value: 'ukpc', label: 'Privy Council' },
    ],
  },
  {
    group: 'Court of Appeal',
    courts: [
      { value: 'ewca/civ', label: 'Civil Division' },
      { value: 'ewca/crim', label: 'Criminal Division' },
    ],
  },
  {
    group: 'High Court',
    courts: [
      { value: 'ewhc/admin', label: 'Administrative Court' },
      { value: 'ewhc/qb', label: "King's Bench" },
      { value: 'ewhc/ch', label: 'Chancery' },
      { value: 'ewhc/fam', label: 'Family' },
      { value: 'ewhc/comm', label: 'Commercial' },
      { value: 'ewhc/pat', label: 'Patents' },
      { value: 'ewhc/tcc', label: 'Technology & Construction' },
    ],
  },
  {
    group: 'Tribunals',
    courts: [
      { value: 'ukut', label: 'Upper Tribunal' },
      { value: 'ukut/iac', label: 'Immigration & Asylum' },
      { value: 'ukut/lc', label: 'Lands Chamber' },
      { value: 'eat', label: 'Employment Appeal' },
    ],
  },
];
