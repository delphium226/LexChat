import React, { useState, useEffect, useCallback } from 'react';
import { getActivityLog } from '../services/api';

const DAYS_OPTIONS = [
    { label: 'Last 24h', value: '1' },
    { label: 'Last 7 days', value: '7' },
    { label: 'Last 30 days', value: '30' },
    { label: 'All time', value: 'all' },
];

const BADGE_CLASSES = {
    LOGIN:    'bg-brand text-white',
    QUERY:    'bg-success-soft text-success',
    SURVEY:   'bg-warn-soft text-warn',
    FEEDBACK: 'bg-accent-soft text-accent-ink',
    ERROR:    'bg-danger-soft text-danger',
};

const BADGE_LABELS = {
    LOGIN:    'Login',
    QUERY:    'Query',
    SURVEY:   'Survey',
    FEEDBACK: 'Feedback',
    ERROR:    'Error',
};

function EventBadge({ type }) {
    const cls = BADGE_CLASSES[type] ?? 'bg-ink-100 text-ink-600';
    const label = BADGE_LABELS[type] ?? type;
    return (
        <span className={`inline-block font-ui text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${cls}`}>
            {label}
        </span>
    );
}

function fmtTimestamp(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
}

export default function ActivityLogModal({ open, onClose }) {
    const [entries, setEntries] = useState([]);
    const [days, setDays] = useState('7');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [lastRefreshed, setLastRefreshed] = useState(null);

    const fetchLog = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getActivityLog(days);
            setEntries(Array.isArray(data) ? data : []);
            setLastRefreshed(new Date());
        } catch (err) {
            setError('Failed to load activity log.');
        } finally {
            setLoading(false);
        }
    }, [days]);

    useEffect(() => {
        if (!open) return;
        fetchLog();
        const interval = setInterval(fetchLog, 10 * 60 * 1000);
        return () => clearInterval(interval);
    }, [open, fetchLog]);

    // Close on Escape
    useEffect(() => {
        if (!open) return;
        const handler = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-paper rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">

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

                {/* Filter pills */}
                <div className="flex items-center gap-2 px-6 py-3 border-b border-ink-200 shrink-0">
                    <span className="font-ui text-xs text-ink-500 mr-1">Show:</span>
                    {DAYS_OPTIONS.map((opt) => (
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

                    {/* Legend */}
                    <div className="ml-auto flex items-center gap-3">
                        {Object.entries(BADGE_LABELS).map(([type, label]) => (
                            <span key={type} className="flex items-center gap-1">
                                <span className={`inline-block font-ui text-xs font-semibold px-2 py-0.5 rounded-full ${BADGE_CLASSES[type]}`}>
                                    {label}
                                </span>
                            </span>
                        ))}
                    </div>
                </div>

                {/* Body */}
                <div className="flex-1 overflow-y-auto px-6 py-4">
                    {error && (
                        <div className="bg-danger-soft text-danger font-ui text-sm rounded-md px-4 py-3 mb-4">
                            {error}
                        </div>
                    )}

                    {!error && entries.length === 0 && !loading && (
                        <p className="font-ui text-sm text-ink-500 text-center py-12">
                            No activity found for the selected time range.
                        </p>
                    )}

                    {entries.length > 0 && (
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-ink-200">
                                    <th className="font-ui text-xs font-semibold text-ink-500 pb-2 pr-4 whitespace-nowrap w-44">Timestamp</th>
                                    <th className="font-ui text-xs font-semibold text-ink-500 pb-2 pr-4 w-24">Event</th>
                                    <th className="font-ui text-xs font-semibold text-ink-500 pb-2 pr-4 w-36">User</th>
                                    <th className="font-ui text-xs font-semibold text-ink-500 pb-2">Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                {entries.map((entry, i) => (
                                    <tr
                                        key={i}
                                        className={`border-b border-ink-100 align-top ${i % 2 === 0 ? '' : 'bg-ink-25'}`}
                                    >
                                        <td className="font-mono text-xs text-ink-500 py-2 pr-4 whitespace-nowrap">
                                            {fmtTimestamp(entry.created_at)}
                                        </td>
                                        <td className="py-2 pr-4">
                                            <EventBadge type={entry.event_type} />
                                        </td>
                                        <td className="font-ui text-xs font-medium text-ink-800 py-2 pr-4 break-all">
                                            {entry.username}
                                        </td>
                                        <td className="font-ui text-xs text-ink-600 py-2 break-words max-w-md">
                                            {entry.description || <span className="text-ink-400 italic">—</span>}
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
                        {entries.length} {entries.length === 1 ? 'entry' : 'entries'}
                        {entries.length === 500 && ' (limit reached — narrow the time range for older records)'}
                    </p>
                </div>
            </div>
        </div>
    );
}
