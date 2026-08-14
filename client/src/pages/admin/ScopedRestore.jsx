import React, { useState, useMemo } from 'react';
import Spinner from '../../components/ui/Spinner';
import { restorePreflight, runRestore } from '../../services/api';
import { fmtBytes, fmtWhen } from './BackupStatus';

/**
 * Scoped restore (D14 Phase 6, panel 2) — the counterpart to DangerZone.jsx.
 *
 * Same six scopes, same checkbox layout, deliberately: the realistic loss on
 * this system is somebody running a pilot reset and then wanting last night's
 * feedback back, which is scope-shaped rather than database-shaped. This is the
 * inverse of the operation that caused the loss.
 *
 * Three-step flow, and the middle step is the point: pick a dump and scopes ->
 * preflight (which stages the dump and reports exactly what would change, by
 * running the real restore with the writes withheld) -> type RESTORE.
 */

const CONFIRM_PHRASE = 'RESTORE';

// Match DangerZone's rendering order so the two panels read as a pair.
const SCOPE_ORDER = ['chats', 'performance', 'feedback', 'activity', 'health', 'cache'];

const OP_LABEL = {
  insert: 'restores missing rows',
  update: 'updates rows that survived',
  relink: 'repairs severed links',
};

const fmtRows = n => `${(n ?? 0).toLocaleString()} row${n === 1 ? '' : 's'}`;

export const ScopedRestore = ({ data, onRestored, onRefresh }) => {
  const [runId, setRunId] = useState('');
  const [selected, setSelected] = useState([]);
  const [confirmText, setConfirmText] = useState('');
  const [preflight, setPreflight] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const restorable = useMemo(() => (data?.runs || []).filter(r => r.restorable), [data]);
  const labels = data?.scopes || {};
  const scopes = SCOPE_ORDER.filter(s => s in labels);

  // Default to the newest restorable run without making the operator pick.
  const effectiveRunId = runId || restorable[0]?.id || '';
  const chosen = restorable.find(r => r.id === effectiveRunId);

  const invalidate = () => {
    setPreflight(null);
    setResult(null);
    setConfirmText('');
    setError('');
  };

  const toggle = scope => {
    invalidate();
    setSelected(prev =>
      prev.includes(scope) ? prev.filter(s => s !== scope) : [...prev, scope]
    );
  };

  const handlePreflight = async () => {
    setBusy('preflight');
    setError('');
    setResult(null);
    try {
      setPreflight(await restorePreflight(effectiveRunId, selected));
    } catch (err) {
      setError('Preflight failed: ' + (err.response?.data?.detail || err.message));
      setPreflight(null);
    } finally {
      setBusy('');
    }
  };

  const handleRestore = async () => {
    setBusy('restore');
    setError('');
    try {
      const res = await runRestore(effectiveRunId, selected, confirmText);
      setResult(res);
      setPreflight(null);
      setConfirmText('');
      setSelected([]);
      if (onRestored) onRestored();
      if (onRefresh) onRefresh();
    } catch (err) {
      setError('Restore failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setBusy('');
    }
  };

  const canPreflight = selected.length > 0 && effectiveRunId && !busy;
  const canRestore = preflight && confirmText === CONFIRM_PHRASE && !busy;

  if (!data) return null;

  if (restorable.length === 0) {
    return (
      <div className="bg-paper p-6 rounded-lg shadow border border-ink-100">
        <h2 className="text-lg font-bold mb-1 text-ink-900">Restore from backup</h2>
        <p className="font-ui text-sm text-ink-600">
          No verified backup of <code className="font-mono text-xs">{data.database}</code> is
          available to restore from. Runs marked as failed are never offered.
        </p>
      </div>
    );
  }

  const renderComponents = (components, mode) => (
    <div className="overflow-x-auto">
      <table className="w-full font-ui text-sm">
        <thead>
          <tr className="text-left">
            <th className="font-ui text-label uppercase tracking-wide text-ink-600 pb-2">What</th>
            <th className="font-ui text-label uppercase tracking-wide text-ink-600 pb-2 text-right">
              In backup
            </th>
            <th className="font-ui text-label uppercase tracking-wide text-ink-600 pb-2 text-right">
              Now
            </th>
            <th className="font-ui text-label uppercase tracking-wide text-ink-600 pb-2 text-right">
              {mode === 'preflight' ? 'Would change' : 'Changed'}
            </th>
          </tr>
        </thead>
        <tbody>
          {components.map(c => {
            const n = mode === 'preflight' ? c.would_apply : c.applied;
            return (
              <tr key={c.key} className="border-t border-ink-100 align-top">
                <td className="py-1.5">
                  <span className="text-ink-900">{c.label}</span>
                  <span className="text-ink-400"> — {OP_LABEL[c.operation] || c.operation}</span>
                  {c.notes?.length > 0 && (
                    <ul className="mt-0.5 space-y-0.5">
                      {c.notes.map((note, i) => (
                        <li key={i} className="font-ui text-xs text-ink-500">
                          {note}
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
                <td className="py-1.5 text-right text-ink-600 whitespace-nowrap">
                  {c.available ? c.staging_rows.toLocaleString() : '—'}
                </td>
                <td className="py-1.5 text-right text-ink-600 whitespace-nowrap">
                  {c.available ? c.live_rows.toLocaleString() : '—'}
                </td>
                <td className="py-1.5 text-right whitespace-nowrap">
                  {!c.available ? (
                    <span className="text-ink-400">n/a</span>
                  ) : n > 0 ? (
                    <span className="text-success font-medium">{n.toLocaleString()}</span>
                  ) : (
                    <span className="text-ink-400">0</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="bg-paper p-6 rounded-lg shadow border border-ink-200">
      <h2 className="text-lg font-bold mb-1 text-ink-900">Restore from backup</h2>
      <p className="font-ui text-sm text-ink-600 mb-4">
        Puts back data one of the Danger Zone scopes removed. <strong>Additive</strong> — it only
        fills in what is missing and never overwrites anything that survived, so it is safe to run
        twice. The current contents are dumped first, so the restore itself can be undone from the
        console.
      </p>

      {/* --- Step 1: which dump --- */}
      <label
        className="block font-ui text-sm font-semibold text-ink-800 mb-1"
        htmlFor="restore-run"
      >
        1. Backup to restore from
      </label>
      <select
        id="restore-run"
        value={effectiveRunId}
        onChange={e => {
          setRunId(e.target.value);
          invalidate();
        }}
        disabled={!!busy}
        className="w-full font-ui text-sm rounded-sm px-3 py-2 bg-paper border border-ink-200 text-ink-900 focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent mb-1"
      >
        {restorable.map(r => (
          <option key={r.id} value={r.id}>
            {fmtWhen(r.started_at)} — {fmtBytes(r.dump_bytes)}
            {r.id === restorable[0].id ? ' (most recent)' : ''}
          </option>
        ))}
      </select>
      {chosen && (
        <p className="font-ui text-xs text-ink-400 mb-4">
          Schema belongs to commit{' '}
          <code className="font-mono">{(chosen.commit_sha || '?').slice(0, 12)}</code>. An older
          dump is safe against newer code — startup re-applies the additive column migrations.
          Columns the dump predates are left at their defaults.
        </p>
      )}

      {/* --- Step 2: which scopes --- */}
      <p className="font-ui text-sm font-semibold text-ink-800 mb-1">2. What to restore</p>
      <div className="space-y-1 mb-4">
        {scopes.map(scope => {
          const isCache = scope === 'cache';
          return (
            <label
              key={scope}
              className={`flex items-start gap-3 rounded-md px-3 py-2 font-ui text-sm ${
                isCache ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-ink-100'
              }`}
            >
              <input
                type="checkbox"
                className="mt-0.5 accent-accent"
                disabled={isCache || !!busy}
                checked={selected.includes(scope)}
                onChange={() => toggle(scope)}
              />
              <span className="flex-1">
                <span className="font-medium">{labels[scope]}</span>
                {/* Cached summaries have no rows in any dump: backup_databases.ps1
                    excludes them with --exclude-table-data, both because the table
                    is pure cache and because it is the only one holding plaintext
                    user queries. Saying so beats showing an unexplained zero. */}
                {isCache && (
                  <span className="block text-xs text-ink-400">
                    Excluded from every backup by design — nothing to restore. It is pure cache and
                    refills on demand.
                  </span>
                )}
                {scope === 'feedback' && (
                  <span className="block text-xs text-ink-400">
                    Surveys and end-of-session responses are re-inserted; message ratings are
                    written back onto the messages that kept them.
                  </span>
                )}
                {scope === 'chats' && (
                  <span className="block text-xs text-ink-400">
                    Chats, messages and uploaded documents, plus the matter-note links a chats
                    clear severs.
                  </span>
                )}
              </span>
            </label>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <button
          onClick={handlePreflight}
          disabled={!canPreflight}
          className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {busy === 'preflight' && <Spinner size="sm" />}
          Check what would change
        </button>
        {selected.length > 0 && (
          <button
            onClick={() => {
              setSelected([]);
              invalidate();
            }}
            disabled={!!busy}
            className="border border-ink-300 text-ink-600 font-ui text-sm font-medium rounded-md px-4 py-2 hover:bg-ink-100 focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
          >
            Clear selection
          </button>
        )}
      </div>

      {error && <p className="font-ui text-sm text-danger mb-3">{error}</p>}

      {/* --- Step 3: preflight result + confirm --- */}
      {preflight && (
        <div className="border border-ink-200 rounded-md p-4 mb-4">
          <p className="font-ui text-sm font-semibold text-ink-800 mb-2">
            3. This is what a restore would do
          </p>
          {renderComponents(preflight.components, 'preflight')}
          <p className="font-ui text-sm text-ink-600 mt-3">
            {preflight.total_rows > 0 ? (
              <>
                <strong>{fmtRows(preflight.total_rows)}</strong> would be restored. Nothing that
                currently exists will be changed or removed.
              </>
            ) : (
              <>
                Nothing would change — everything in this backup is already present. Restoring is
                safe but pointless.
              </>
            )}
          </p>

          <div className="flex flex-wrap items-center gap-3 mt-4">
            <label className="font-ui text-sm text-ink-600" htmlFor="restore-confirm">
              Type {CONFIRM_PHRASE} to confirm:
            </label>
            <input
              id="restore-confirm"
              type="text"
              value={confirmText}
              onChange={e => setConfirmText(e.target.value)}
              disabled={!!busy}
              autoComplete="off"
              className="font-ui text-sm rounded-md px-3 py-2 bg-paper border border-ink-300 text-ink-900 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent w-40"
            />
            <button
              onClick={handleRestore}
              disabled={!canRestore}
              className="bg-brand text-white px-5 py-2.5 rounded-md font-ui text-sm font-medium flex items-center gap-2 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {busy === 'restore' && <Spinner size="sm" />}
              Restore selected data
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="bg-success-soft rounded-md px-4 py-3 mb-3">
          <p className="font-ui text-sm font-medium text-success mb-2">
            Restored {fmtRows(result.total_rows)} in {result.duration_s}s
          </p>
          {renderComponents(result.components, 'result')}
          {result.safety_dump && (
            <p className="font-ui text-xs text-ink-600 mt-3">
              The previous contents were dumped to{' '}
              <code className="font-mono break-all">{result.safety_dump}</code> first. To undo this,
              restore that file from the console with{' '}
              <code className="font-mono">deployment\restore_database.ps1 -DumpFile …</code>.
            </p>
          )}
          <p className="font-ui text-xs text-ink-400 mt-2">
            Recorded on the activity log. Identity sequences were reset, so new records will not
            collide with the restored ones.
          </p>
        </div>
      )}

      <p className="font-ui text-xs text-ink-400">
        The chosen dump is loaded into a separate staging database the app never connects to, then
        copied across scope by scope — live tables are never a restore target. Never touched:
        user accounts, provider settings and feature flags, federated peers, matters, and the
        crawled Scottish Parliament corpus.
      </p>
    </div>
  );
};

export default ScopedRestore;
