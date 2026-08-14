import React, { useState, useEffect, useCallback } from 'react';
import { getActivityLog } from '../services/api';
import Modal from './ui/Modal';

const DAYS_OPTIONS = [
  { label: 'Last 24h', value: '1' },
  { label: 'Last 7 days', value: '7' },
  { label: 'Last 30 days', value: '30' },
  { label: 'All time', value: 'all' },
];

const ALL_EVENT_TYPES = [
  'LOGIN',
  'QUERY',
  'RESPONSE',
  'SURVEY',
  'FEEDBACK',
  'ERROR',
  'EFFICIENCY',
  'RESTORE',
];

const BADGE_CLASSES = {
  LOGIN: 'bg-brand text-white',
  QUERY: 'bg-success-soft text-success',
  RESPONSE: 'bg-cite-soft text-cite',
  SURVEY: 'bg-warn-soft text-warn',
  FEEDBACK: 'bg-accent-soft text-accent-ink',
  ERROR: 'bg-danger-soft text-danger',
  EFFICIENCY: 'bg-warn-soft text-warn',
  RESTORE: 'bg-danger-soft text-danger',
};

const BADGE_LABELS = {
  LOGIN: 'Login',
  QUERY: 'Query',
  RESPONSE: 'Response',
  SURVEY: 'Survey',
  FEEDBACK: 'Feedback',
  ERROR: 'Error',
  EFFICIENCY: 'Efficiency',
  RESTORE: 'Restore',
};

// Bumped whenever a type is ADDED, because a selection saved before the type
// existed cannot contain it — so a returning admin would open the log with the
// new events hidden and no clue they exist. v2 was RESPONSE; v3 is RESTORE,
// where silently hiding an audit record of a data restore is the worst case.
const LS_TYPE_KEY = 'activitylog_type_filter_v3';

function loadSavedTypes() {
  try {
    const raw = localStorage.getItem(LS_TYPE_KEY);
    if (!raw) return ALL_EVENT_TYPES;
    const parsed = JSON.parse(raw);
    const valid = parsed.filter(t => ALL_EVENT_TYPES.includes(t));
    return valid.length > 0 ? valid : ALL_EVENT_TYPES;
  } catch {
    return ALL_EVENT_TYPES;
  }
}

function EventBadge({ type }) {
  const cls = BADGE_CLASSES[type] ?? 'bg-ink-100 text-ink-600';
  const label = BADGE_LABELS[type] ?? type;
  return (
    <span className={`inline-block font-ui text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${cls}`}>
      {label}
    </span>
  );
}

// A full research answer runs to thousands of characters, so Details is clamped
// to three lines and expands in place — otherwise a single RESPONSE row fills
// the viewport and buries the rest of the feed.
const CLAMP_CHARS = 220;

function DetailsCell({ text }) {
  const [expanded, setExpanded] = useState(false);

  if (!text) return <span className="text-ink-400 italic">—</span>;

  const clampable = text.length > CLAMP_CHARS;
  return (
    <div>
      <div className={`whitespace-pre-wrap break-words ${clampable && !expanded ? 'line-clamp-3' : ''}`}>
        {text}
      </div>
      {clampable && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="font-ui text-xs text-accent-ink hover:underline underline-offset-2 mt-1 focus-visible:ring-2 focus-visible:ring-accent rounded"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </div>
  );
}

function fmtTimestamp(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export default function ActivityLogModal({ open, onClose }) {
  const [entries, setEntries] = useState([]);
  const [userOptions, setUserOptions] = useState([]);
  const [days, setDays] = useState('7');
  const [selectedTypes, setSelectedTypes] = useState(loadSavedTypes);
  const [selectedUser, setSelectedUser] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const toggleType = useCallback(type => {
    setSelectedTypes(prev => {
      const next = prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type];
      if (next.length === 0) return prev;
      localStorage.setItem(LS_TYPE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const selectAllTypes = useCallback(() => {
    setSelectedTypes(ALL_EVENT_TYPES);
    localStorage.setItem(LS_TYPE_KEY, JSON.stringify(ALL_EVENT_TYPES));
  }, []);

  const fetchLog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getActivityLog(days, 500, selectedTypes, selectedUser);
      setEntries(Array.isArray(data) ? data : []);
      setLastRefreshed(new Date());
    } catch (err) {
      setError('Failed to load activity log.');
    } finally {
      setLoading(false);
    }
  }, [days, selectedTypes, selectedUser]);

  useEffect(() => {
    if (!open) return;
    fetchLog();
    const interval = setInterval(fetchLog, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [open, fetchLog]);

  // Populate the user dropdown from an unfiltered fetch (all types, all users)
  // so selecting a user never collapses the list of choices. Re-runs only when
  // the period changes.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    getActivityLog(days)
      .then(data => {
        if (cancelled) return;
        const users = [...new Set((Array.isArray(data) ? data : []).map(e => e.username).filter(Boolean))].sort();
        setUserOptions(users);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [open, days]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = e => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  // Filtering by event type and user is done server-side (in SQL), so `entries`
  // is already the filtered set — the LIMIT applies after filtering, not before.
  const filteredEntries = entries;

  return (
    <Modal onClose={onClose} className="w-[90vw] h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-ink-200 shrink-0">
          <div>
            <h2 className="font-ui text-base font-semibold text-ink-900">Activity Log</h2>
            {lastRefreshed && (
              <p className="font-ui text-xs text-ink-500 mt-0.5">
                Last refreshed: {fmtTimestamp(lastRefreshed.toISOString())}
                {' · '}auto-refreshes every 10 min
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchLog}
              disabled={loading}
              className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-3 py-1.5 hover:bg-ink-50 focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Refreshing…' : 'Refresh'}
            </button>
            <button
              onClick={onClose}
              className="size-[30px] flex items-center justify-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:ring-2 focus-visible:ring-accent"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="px-6 py-3 border-b border-ink-200 shrink-0 space-y-2">
          {/* Period row */}
          <div className="flex items-center gap-2">
            <span className="font-ui text-xs text-ink-500 w-10 shrink-0">Period:</span>
            {DAYS_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setDays(opt.value)}
                className={
                  days === opt.value
                    ? 'bg-accent text-white border-transparent rounded-full px-3 py-1 font-ui text-xs'
                    : 'border border-ink-200 text-ink-600 rounded-full px-3 py-1 font-ui text-xs hover:bg-ink-50'
                }
              >
                {opt.label}
              </button>
            ))}
          </div>
          {/* Event type row — multi-select */}
          <div className="flex items-center gap-2 flex-wrap gap-y-1">
            <span className="font-ui text-xs text-ink-500 w-10 shrink-0">Type:</span>
            {ALL_EVENT_TYPES.map(type => (
              <button
                key={type}
                onClick={() => toggleType(type)}
                className={
                  selectedTypes.includes(type)
                    ? 'bg-accent text-white border-transparent rounded-full px-3 py-1 font-ui text-xs'
                    : 'border border-ink-200 text-ink-400 rounded-full px-3 py-1 font-ui text-xs hover:bg-ink-50'
                }
              >
                {BADGE_LABELS[type]}
              </button>
            ))}
            {selectedTypes.length < ALL_EVENT_TYPES.length && (
              <button
                onClick={selectAllTypes}
                className="font-ui text-xs text-ink-400 hover:text-ink-700 underline underline-offset-2 ml-1"
              >
                All
              </button>
            )}
          </div>
          {/* User filter row */}
          <div className="flex items-center gap-2">
            <span className="font-ui text-xs text-ink-500 w-10 shrink-0">User:</span>
            <select
              value={selectedUser}
              onChange={e => setSelectedUser(e.target.value)}
              className="font-ui text-xs text-ink-800 bg-paper border border-ink-200 rounded-md px-2 py-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <option value="">All users</option>
              {userOptions.map(u => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
            {selectedUser && (
              <button
                onClick={() => setSelectedUser('')}
                className="font-ui text-xs text-ink-400 hover:text-ink-700 underline underline-offset-2"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {error && <div className="bg-danger-soft text-danger font-ui text-sm rounded-md px-4 py-3 mb-4">{error}</div>}

          {!error && filteredEntries.length === 0 && !loading && (
            <p className="font-ui text-sm text-ink-500 text-center py-12">
              {entries.length === 0
                ? 'No activity found for the selected time range.'
                : 'No events match the selected filters.'}
            </p>
          )}

          {filteredEntries.length > 0 && (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-ink-200">
                  <th className="font-ui text-xs font-semibold text-ink-500 pb-2 pr-4 whitespace-nowrap w-44">
                    Timestamp
                  </th>
                  <th className="font-ui text-xs font-semibold text-ink-500 pb-2 pr-4 w-24">Event</th>
                  <th className="font-ui text-xs font-semibold text-ink-500 pb-2 pr-4 w-36">User</th>
                  <th className="font-ui text-xs font-semibold text-ink-500 pb-2">Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntries.map((entry, i) => (
                  <tr
                    key={`${entry.event_type}-${entry.created_at}-${i}`}
                    className={`border-b border-ink-100 align-top ${i % 2 === 0 ? '' : 'bg-ink-25'}`}
                  >
                    <td className="font-mono text-xs text-ink-500 py-2 pr-4 whitespace-nowrap">
                      {fmtTimestamp(entry.created_at)}
                    </td>
                    <td className="py-2 pr-4">
                      <EventBadge type={entry.event_type} />
                    </td>
                    <td className="font-ui text-xs font-medium text-ink-800 py-2 pr-4 break-all">{entry.username}</td>
                    <td className="font-ui text-xs text-ink-600 py-2">
                      <DetailsCell text={entry.description} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-ink-200 shrink-0">
          <p className="font-ui text-xs text-ink-500">
            {filteredEntries.length !== entries.length
              ? `${filteredEntries.length} of ${entries.length} entries`
              : `${entries.length} ${entries.length === 1 ? 'entry' : 'entries'}`}
            {entries.length === 500 && ' (limit reached — narrow the time range for older records)'}
          </p>
        </div>
    </Modal>
  );
}
