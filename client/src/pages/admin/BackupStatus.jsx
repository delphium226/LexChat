import React from 'react';
import Spinner from '../../components/ui/Spinner';

/**
 * Read-only backup status (D14 Phase 6, panel 1).
 *
 * Deliberately separate from the restore panel below it, and worth shipping on
 * its own: this is what an operator needs BEFORE deciding to go to the console
 * for a full restore. Everything here comes from the manifest.json that
 * deployment/backup_databases.ps1 writes beside each run — this panel reads, it
 * never triggers anything.
 */

export const fmtBytes = bytes => {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
};

export const fmtWhen = iso => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const ageInHours = iso => {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return (Date.now() - d.getTime()) / 36e5;
};

const Badge = ({ tone, children }) => {
  const tones = {
    success: 'bg-success-soft text-success',
    warn: 'bg-warn-soft text-warn',
    danger: 'bg-danger-soft text-danger',
    neutral: 'bg-ink-100 text-ink-600',
  };
  return (
    <span
      className={`${tones[tone] || tones.neutral} rounded-full px-2 py-0.5 font-ui text-label uppercase tracking-wide`}
    >
      {children}
    </span>
  );
};

export const BackupStatus = ({ data, error, onRefresh }) => {
  if (error) {
    return (
      <div className="bg-paper p-6 rounded-lg shadow border border-ink-100">
        <h2 className="text-lg font-bold mb-1 text-ink-900">Backup status</h2>
        <p className="font-ui text-sm text-danger">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-paper p-6 rounded-lg shadow border border-ink-100">
        <h2 className="text-lg font-bold mb-3 text-ink-900">Backup status</h2>
        <div className="flex items-center gap-2 font-ui text-sm text-ink-500">
          <Spinner size="sm" /> Reading the backup directory…
        </div>
      </div>
    );
  }

  const latest = data.latest;
  const hours = ageInHours(latest?.started_at);
  // 26h rather than 24: the nightly task runs at 02:30, so a run that has just
  // been missed should not read as stale the moment the clock ticks past a day.
  const stale = hours !== null && hours > 26;

  return (
    <div className="bg-paper p-6 rounded-lg shadow border border-ink-100">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-1">
        <h2 className="text-lg font-bold text-ink-900">Backup status</h2>
        <button
          onClick={onRefresh}
          className="bg-paper border border-ink-200 text-ink-900 font-ui text-sm font-medium rounded-md px-3 py-1.5 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          Refresh
        </button>
      </div>
      <p className="font-ui text-sm text-ink-600 mb-4">
        Nightly <code className="font-mono text-xs">pg_dump</code> runs written to{' '}
        <code className="font-mono text-xs">{data.backup_root}</code>. Read-only — a full-database
        restore is a console operation, see the backup runbook.
      </p>

      {!data.root_exists && (
        <div className="bg-danger-soft rounded-md px-4 py-3 mb-4">
          <p className="font-ui text-sm font-medium text-danger mb-1">
            The backup directory does not exist
          </p>
          <p className="font-ui text-sm text-ink-600">
            Nothing is being backed up on this machine. Run{' '}
            <code className="font-mono text-xs">deployment\install_backup_task.ps1</code> from an
            elevated PowerShell to create it and schedule the nightly run.
          </p>
        </div>
      )}

      {data.root_exists && !latest && (
        <div className="bg-warn-soft rounded-md px-4 py-3 mb-4">
          <p className="font-ui text-sm font-medium text-warn mb-1">No backup runs found</p>
          <p className="font-ui text-sm text-ink-600">
            The directory exists but holds no completed runs. The scheduled task may never have
            run — check it with{' '}
            <code className="font-mono text-xs">Get-ScheduledTaskInfo -TaskName "LexChat Database Backup"</code>.
          </p>
        </div>
      )}

      {latest && (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {latest.failed ? (
              <Badge tone="danger">Last run failed</Badge>
            ) : (
              <Badge tone="success">Last run OK</Badge>
            )}
            {stale && <Badge tone="warn">{Math.floor(hours / 24)} days old</Badge>}
            {latest.database_verify && latest.database_verify !== 'ok' && (
              <Badge tone="danger">{data.database} did not verify</Badge>
            )}
            {latest.globals_mode === 'no-role-passwords' && (
              <Badge tone="neutral">Globals without passwords</Badge>
            )}
          </div>

          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 mb-4 font-ui text-sm">
            <div className="flex justify-between gap-3 border-b border-ink-100 pb-1">
              <dt className="text-ink-600">Last run</dt>
              <dd className="text-ink-900 text-right">{fmtWhen(latest.started_at)}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-ink-100 pb-1">
              <dt className="text-ink-600">Duration</dt>
              <dd className="text-ink-900 text-right">
                {latest.duration_s != null ? `${latest.duration_s}s` : '—'}
              </dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-ink-100 pb-1">
              <dt className="text-ink-600">Total size</dt>
              <dd className="text-ink-900 text-right">{fmtBytes(latest.total_bytes)}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-ink-100 pb-1">
              <dt className="text-ink-600">PostgreSQL</dt>
              <dd className="text-ink-900 text-right">{latest.pg_version || '—'}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-ink-100 pb-1">
              <dt className="text-ink-600">Runs retained</dt>
              <dd className="text-ink-900 text-right">{data.runs.length}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-ink-100 pb-1">
              {/* The single most useful field at 2am: which code the dump's schema
                  belongs to. An older dump onto newer code is fine (startup
                  re-applies the additive ADD COLUMN migrations); the reverse is not. */}
              <dt className="text-ink-600">Commit SHA</dt>
              <dd className="text-ink-900 text-right font-mono text-xs">
                {latest.commit_sha ? latest.commit_sha.slice(0, 12) : '—'}
              </dd>
            </div>
          </dl>

          {latest.databases?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full font-ui text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="font-ui text-label uppercase tracking-wide text-ink-600 pb-2">
                      Database
                    </th>
                    <th className="font-ui text-label uppercase tracking-wide text-ink-600 pb-2 text-right">
                      Size
                    </th>
                    <th className="font-ui text-label uppercase tracking-wide text-ink-600 pb-2 text-right">
                      Objects
                    </th>
                    <th className="font-ui text-label uppercase tracking-wide text-ink-600 pb-2 text-right">
                      Verify
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {latest.databases.map(db => (
                    <tr key={db.name} className="border-t border-ink-100">
                      <td className="py-1.5 text-ink-900">
                        {db.name}
                        {db.name === data.database && (
                          <span className="text-ink-400"> — this bot</span>
                        )}
                      </td>
                      <td className="py-1.5 text-right text-ink-600">{fmtBytes(db.bytes)}</td>
                      <td className="py-1.5 text-right text-ink-600">{db.toc_entries ?? '—'}</td>
                      <td className="py-1.5 text-right">
                        {db.verify === 'ok' ? (
                          <span className="text-success">ok</span>
                        ) : (
                          <span className="text-danger">{db.verify || 'unknown'}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {latest.errors?.length > 0 && (
            <div className="bg-danger-soft rounded-md px-4 py-3 mt-4">
              <p className="font-ui text-sm font-medium text-danger mb-1">Errors from the last run</p>
              <ul className="font-ui text-sm text-ink-600 space-y-0.5">
                {latest.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="font-ui text-xs text-ink-400 mt-4">
            Dumps stay on this machine, so they protect against accidental deletion and bad
            migrations but not against loss of the server itself. Verification is two-stage — a
            full read of every archive, because a table-of-contents check passes on a truncated
            dump. Cached document summaries are excluded from every dump by design.
          </p>
        </>
      )}
    </div>
  );
};

export default BackupStatus;
