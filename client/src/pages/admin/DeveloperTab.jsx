import React, { useState } from 'react';
import Spinner from '../../components/ui/Spinner';
import { Card, SectionHeader } from '../../components/ui/Card';
import { FeatureToggleList } from './FeatureToggleList';
import { flagsInGroup } from './featureFlagDefs';
import ProviderConfigPanel from './ProviderConfigPanel';
import TranscriptExport from './TranscriptExport';
import BackupStatus from './BackupStatus';
import DangerZone from './DangerZone';
import ScopedRestore from './ScopedRestore';
import { triggerParliamentRefresh, getParliamentRefresh } from '../../services/api';

/**
 * The Developer tab.
 *
 * Was nine flat cards in one scroll inside AdminPortal.jsx, ordered by when each
 * was added. They are the same nine panels, grouped by what an operator is
 * trying to do. Sub-tabs rather than another top-level tab: the portal's tab bar
 * already carries thirteen flex-1 buttons at text-xs and has no room.
 */

const SUBTABS = [
  { id: 'configuration', label: 'Configuration' },
  { id: 'operations', label: 'Operations' },
  { id: 'exports', label: 'Exports' },
  { id: 'backup', label: 'Backup & Restore' },
];

const SUBTAB_KEY = 'developer_subtab';

export const DeveloperTab = ({
  features,
  setFeatures,
  isSavingFeatures,
  setIsSavingFeatures,
  parliamentRefresh,
  setParliamentRefresh,
  backups,
  backupsError,
  fetchBackups,
  fetchStats,
  onOpenActivityLog,
  onOpenUserExport,
  setMessage,
}) => {
  const [subTab, setSubTab] = useState(() => {
    const saved = localStorage.getItem(SUBTAB_KEY);
    return SUBTABS.some(t => t.id === saved) ? saved : 'configuration';
  });
  const [refreshSession, setRefreshSession] = useState('all');
  const [isTriggeringRefresh, setIsTriggeringRefresh] = useState(false);

  const selectSubTab = id => {
    setSubTab(id);
    localStorage.setItem(SUBTAB_KEY, id);
  };

  return (
    <div>
      {/* SUB-TABS */}
      <div className="flex flex-wrap gap-1 border-b border-ink-200 mb-6">
        {SUBTABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => selectSubTab(tab.id)}
            className={`px-4 py-2 -mb-px border-b-2 font-ui text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              subTab === tab.id
                ? 'border-accent text-ink-900'
                : 'border-transparent text-ink-500 hover:text-ink-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* CONFIGURATION */}
      {subTab === 'configuration' && (
        <div className="space-y-6">
          <ProviderConfigPanel />

          <Card>
            <SectionHeader
              title="Feature Flags"
              description="Toggle features on or off for all users. Changes take effect immediately. Caching flags live on the Cache tab, beside the metrics they affect."
            />
            <FeatureToggleList
              flags={flagsInGroup('features')}
              features={features}
              setFeatures={setFeatures}
              isSaving={isSavingFeatures}
              setIsSaving={setIsSavingFeatures}
              onError={setMessage}
            />
          </Card>
        </div>
      )}

      {/* OPERATIONS */}
      {subTab === 'operations' && (
        <div className="space-y-6">
          {/* Parliamentary Data Refresh — parliament bot only */}
          {parliamentRefresh?.supported && (
            <Card>
              <SectionHeader
                title="Parliamentary Data Refresh"
                description="Re-crawl the Scottish Parliament Official Report for a Holyrood session. Reprocesses every meeting in the session's date range, ingesting new sittings, late-published transcripts, and newly-added agenda items. Runs in the background — completed transcripts are skipped, so a re-run is cheap."
              />

              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-xs font-medium text-ink-500 mb-1">Session</label>
                  <select
                    value={refreshSession}
                    onChange={e => setRefreshSession(e.target.value)}
                    disabled={parliamentRefresh?.status?.running}
                    className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-accent disabled:opacity-50"
                  >
                    {(parliamentRefresh.sessions || []).map(s => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  disabled={isTriggeringRefresh || parliamentRefresh?.status?.running}
                  onClick={async () => {
                    setIsTriggeringRefresh(true);
                    try {
                      await triggerParliamentRefresh(refreshSession);
                      const status = await getParliamentRefresh();
                      setParliamentRefresh(status);
                    } catch (err) {
                      setMessage(err?.response?.data?.detail || 'Failed to start data refresh.');
                    } finally {
                      setIsTriggeringRefresh(false);
                    }
                  }}
                  className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {parliamentRefresh?.status?.running ? 'Refresh running…' : 'Refresh now'}
                </button>
              </div>

              {/* The 5s status poll lives in AdminPortal and is keyed on the
                  TOP-LEVEL tab, not this sub-tab — a refresh takes minutes and
                  the operator will move between sub-tabs while it runs. */}
              {parliamentRefresh?.status &&
                (parliamentRefresh.status.running || parliamentRefresh.status.finished_at) && (
                  <div className="mt-4 text-sm">
                    {parliamentRefresh.status.running ? (
                      <div className="flex items-center gap-2 text-ink-600">
                        <Spinner />
                        <span>
                          Refreshing session {parliamentRefresh.status.session}… this can take
                          several minutes. You can leave this tab.
                        </span>
                      </div>
                    ) : parliamentRefresh.status.error ? (
                      <p className="text-danger">
                        Last refresh (session {parliamentRefresh.status.session}) failed:{' '}
                        {parliamentRefresh.status.error}
                      </p>
                    ) : parliamentRefresh.status.result ? (
                      <p className="text-ink-600">
                        Last refresh (session {parliamentRefresh.status.session}) stored{' '}
                        <span className="font-medium">
                          {parliamentRefresh.status.result.committee}
                        </span>{' '}
                        committee and{' '}
                        <span className="font-medium">{parliamentRefresh.status.result.plenary}</span>{' '}
                        plenary items
                        {parliamentRefresh.status.result.captions > 0 && (
                          <> · {parliamentRefresh.status.result.captions} video-caption meetings cached</>
                        )}
                        .
                      </p>
                    ) : null}
                  </div>
                )}
            </Card>
          )}

          <Card>
            <SectionHeader
              title="Activity Log"
              description="Live feed of user logins, queries submitted, feedback, surveys, and service errors. Auto-refreshes every 10 minutes while open."
            />
            <button
              onClick={onOpenActivityLog}
              className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
            >
              View Activity Log
            </button>
          </Card>
        </div>
      )}

      {/* EXPORTS */}
      {subTab === 'exports' && (
        <div className="space-y-6">
          <Card>
            <SectionHeader
              title="Export Users"
              description="Generate a CSV list of all user accounts (name, email, role) to copy and paste."
            />
            <button
              onClick={onOpenUserExport}
              className="bg-brand hover:bg-brand-hover text-white font-ui text-sm font-medium rounded-md px-4 py-2 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
            >
              Export Users (CSV)
            </button>
          </Card>

          {/* Beside the user export, the other thing an operator leaves this
              tab with as a file. */}
          <TranscriptExport />
        </div>
      )}

      {/* BACKUP & RESTORE */}
      {subTab === 'backup' && (
        <div className="space-y-6">
          <BackupStatus data={backups} error={backupsError} onRefresh={fetchBackups} />

          <DangerZone onCleared={fetchStats} />

          {/* Deliberately AFTER the Danger Zone: it is the inverse of the
              operation above it, and reads as its counterpart. */}
          <ScopedRestore data={backups} onRestored={fetchStats} onRefresh={fetchBackups} />
        </div>
      )}
    </div>
  );
};

export default DeveloperTab;
