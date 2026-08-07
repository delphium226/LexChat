import React, { useState, useEffect, useCallback } from 'react';
import Spinner from '../../components/ui/Spinner';
import { getDataCounts, clearData } from '../../services/api';

const CONFIRM_PHRASE = 'DELETE';

// Order the checkboxes are rendered in. The server decides what each scope
// actually deletes and supplies the labels; this is presentation only.
const SCOPE_ORDER = ['chats', 'performance', 'feedback', 'activity', 'health', 'cache'];

const SCOPE_HINTS = {
  chats: 'Usage, Cost per user, Activity Log, Learning and all compliance stats',
  performance: 'Performance, Cost, Efficiency and Cache dashboards',
  feedback: 'Weekly surveys, end-of-session feedback and message ratings',
  activity: 'Login and efficiency-breach records',
  health: 'Service health status and history',
  cache: 'Reused document summaries — regenerated on demand',
};

const fmtRows = n => `${n.toLocaleString()} row${n === 1 ? '' : 's'}`;

export const DangerZone = ({ onCleared }) => {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState([]);
  const [confirmText, setConfirmText] = useState('');
  const [isBusy, setIsBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      setData(await getDataCounts());
    } catch (err) {
      setError('Could not load data counts: ' + err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const counts = data?.counts || {};
  const labels = data?.scopes || {};
  const details = data?.details || {};
  const scopes = SCOPE_ORDER.filter(s => s in labels);
  const selectable = scopes.filter(s => counts[s] > 0);

  const toggle = scope =>
    setSelected(prev => (prev.includes(scope) ? prev.filter(s => s !== scope) : [...prev, scope]));

  const canDelete = selected.length > 0 && confirmText === CONFIRM_PHRASE && !isBusy;

  const handleDelete = async () => {
    setIsBusy(true);
    setError('');
    setResult(null);
    try {
      const res = await clearData(selected, confirmText);
      setResult(res.deleted || {});
      setSelected([]);
      setConfirmText('');
      await refresh();
      if (onCleared) onCleared();
    } catch (err) {
      setError('Error clearing data: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="bg-paper p-6 rounded-lg shadow border border-danger">
      <h2 className="text-lg font-bold mb-1 text-danger">Danger Zone</h2>
      <p className="mb-4 text-sm text-ink-600">
        Select what to delete, then type <code className="font-ui font-bold">{CONFIRM_PHRASE}</code> to
        confirm. These actions permanently delete data and <strong>cannot be undone.</strong>
      </p>

      {!data ? (
        <div className="flex items-center gap-2 text-sm text-ink-500">
          <Spinner size="sm" /> Loading data counts…
        </div>
      ) : (
        <>
          <div className="space-y-1 mb-4">
            {scopes.map(scope => {
              const empty = counts[scope] === 0;
              return (
                <label
                  key={scope}
                  className={`flex items-start gap-3 rounded-md px-3 py-2 font-ui text-sm ${
                    empty ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-ink-100'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-danger"
                    disabled={empty || isBusy}
                    checked={selected.includes(scope)}
                    onChange={() => toggle(scope)}
                  />
                  <span className="flex-1">
                    <span className="font-medium">{labels[scope]}</span>
                    <span className="text-ink-500"> — {fmtRows(counts[scope])}</span>
                    <span className="block text-xs text-ink-400">{SCOPE_HINTS[scope]}</span>
                    {scope === 'chats' && selected.includes('chats') && (
                      <span className="block text-xs text-danger mt-1">
                        Also deletes {details.chats?.messages ?? 0} messages and{' '}
                        {details.chats?.documents ?? 0} uploaded documents; matter notes lose their
                        message links.
                      </span>
                    )}
                  </span>
                </label>
              );
            })}
          </div>

          <div className="flex flex-wrap gap-3 mb-4">
            <button
              onClick={() => setSelected(selectable)}
              disabled={isBusy || selectable.length === 0}
              className="border border-danger text-danger font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-danger-soft focus-visible:ring-2 focus-visible:ring-danger disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Select all (pilot reset)
            </button>
            <button
              onClick={() => setSelected([])}
              disabled={isBusy || selected.length === 0}
              className="border border-ink-300 text-ink-600 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-100 focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Clear selection
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-3 mb-4">
            <label className="font-ui text-sm text-ink-600" htmlFor="danger-confirm">
              Type {CONFIRM_PHRASE} to confirm:
            </label>
            <input
              id="danger-confirm"
              type="text"
              value={confirmText}
              onChange={e => setConfirmText(e.target.value)}
              disabled={isBusy}
              autoComplete="off"
              className="font-ui text-sm rounded-md px-3 py-2 bg-paper border border-ink-300 focus:outline-none focus:border-danger focus:ring-2 focus:ring-danger-soft w-40"
            />
            <button
              onClick={handleDelete}
              disabled={!canDelete}
              className="bg-danger text-white px-5 py-2.5 rounded-md font-ui text-sm font-medium flex items-center gap-2 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isBusy && <Spinner size="sm" />}
              Delete selected data
            </button>
          </div>

          {error && <p className="font-ui text-sm text-danger mb-3">{error}</p>}

          {result && (
            <div className="bg-danger-soft rounded-md px-4 py-3 mb-3">
              <p className="font-ui text-sm font-medium text-danger mb-1">Deleted</p>
              <ul className="font-ui text-sm text-ink-600 space-y-0.5">
                {Object.entries(result).map(([scope, n]) => (
                  <li key={scope}>
                    {labels[scope] || scope}: {fmtRows(n)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="font-ui text-xs text-ink-400">
            Always preserved: user accounts, provider settings and feature flags, federated peers,
            matters, and the crawled Scottish Parliament corpus.
          </p>
        </>
      )}
    </div>
  );
};

export default DangerZone;
