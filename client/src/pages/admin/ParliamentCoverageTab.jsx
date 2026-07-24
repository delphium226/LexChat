import React from 'react';

const fmtDate = iso => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
const pct = (n, d) => (d > 0 ? Math.round((n / d) * 100) : 0);

// A meter bar showing captured vs missing for one dimension.
const CoverageMeter = ({ captured, total, label, capturedLabel = 'captured', missingLabel = 'missing' }) => {
  const p = pct(captured, total);
  const missing = Math.max(total - captured, 0);
  return (
    <div>
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-xs font-medium text-ink-700">{label}</span>
        <span className="text-xs text-ink-500">
          {captured.toLocaleString()} / {total.toLocaleString()} ({p}%)
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-ink-100 overflow-hidden">
        <div
          className={`h-full rounded-full ${p >= 90 ? 'bg-green-500' : p >= 60 ? 'bg-amber-500' : 'bg-red-500'}`}
          style={{ width: `${p}%` }}
        />
      </div>
      <p className="text-[11px] text-ink-400 mt-1">
        {captured.toLocaleString()} {capturedLabel} · {missing.toLocaleString()} {missingLabel}
      </p>
    </div>
  );
};

const DataTypeCard = ({ title, data, subtitleField }) => {
  const textCoverage = pct(data.itemsWithText, data.items);
  return (
    <div className="bg-paper p-6 rounded-lg shadow space-y-4">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-base font-bold">{title}</h3>
          <p className="text-xs text-ink-500 mt-0.5">
            {data.meetings.toLocaleString()} meeting{data.meetings === 1 ? '' : 's'}
            {subtitleField && data.distinctCommittees != null && (
              <> · {data.distinctCommittees} committee{data.distinctCommittees === 1 ? '' : 's'}</>
            )}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold">{data.items.toLocaleString()}</p>
          <p className="text-[11px] text-ink-400 uppercase tracking-wider">agenda items</p>
        </div>
      </div>

      <CoverageMeter
        captured={data.itemsWithText}
        total={data.items}
        label="Transcript text ingested"
        capturedLabel="with full text"
        missingLabel="awaiting Official Report / empty"
      />

      <div className="grid grid-cols-2 gap-3 pt-1 text-xs">
        <div>
          <p className="text-ink-400 uppercase tracking-wider text-[10px]">Date range</p>
          <p className="font-medium text-ink-700">
            {fmtDate(data.earliest)} – {fmtDate(data.latest)}
          </p>
        </div>
        <div>
          <p className="text-ink-400 uppercase tracking-wider text-[10px]">Missing text</p>
          <p className={`font-medium ${data.itemsEmpty > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-ink-700'}`}>
            {data.itemsEmpty.toLocaleString()} item{data.itemsEmpty === 1 ? '' : 's'} ({100 - textCoverage}%)
          </p>
        </div>
      </div>
    </div>
  );
};

export const ParliamentCoverageTab = ({ coverage, session, setSession }) => {
  const { committee, plenary, video, sessions, perSession } = coverage;
  const hasData = committee.items > 0 || plenary.items > 0 || video.events > 0;

  return (
    <div className="space-y-6">
      {/* HEADER + SESSION FILTER */}
      <div className="flex justify-between items-center bg-paper p-4 rounded-lg shadow">
        <div>
          <h2 className="text-lg font-bold">Parliamentary Data Coverage</h2>
          <p className="text-sm text-ink-500 mt-0.5">
            What the crawler has ingested from the Scottish Parliament Official Report, and where the gaps are.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-ink-500 font-medium">Session:</label>
          <select
            value={session}
            onChange={e => setSession(e.target.value)}
            className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-accent"
          >
            <option value="all">All sessions</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!hasData && (
        <div className="bg-paper p-8 rounded-lg shadow text-center text-ink-400 text-sm">
          No parliamentary data ingested for this scope. This tab reports the Scottish Parliament crawler's coverage —
          it only holds data on a bot running in <span className="font-mono">parliamentary_records</span> mode.
        </div>
      )}

      {/* DATA-TYPE CARDS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DataTypeCard title="Committee transcripts" data={committee} subtitleField />
        <DataTypeCard title="Plenary (chamber) debates" data={plenary} />
      </div>

      {/* VIDEO CAPTION COVERAGE */}
      <div className="bg-paper p-6 rounded-lg shadow space-y-5">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-base font-bold">SP TV video captions</h3>
            <p className="text-xs text-ink-500 mt-0.5">
              Cached caption tracks enable timestamped video deep links on citations. Older sittings often have no
              subtitle track available.
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold">{video.events.toLocaleString()}</p>
            <p className="text-[11px] text-ink-400 uppercase tracking-wider">events cached</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <CoverageMeter
            captured={video.captionOk}
            total={video.events}
            label="Usable caption track"
            capturedLabel="with captions"
            missingLabel="no caption track"
          />
          <CoverageMeter
            captured={video.plenaryWithVideo}
            total={video.plenaryMeetings}
            label="Plenary meetings with video"
            capturedLabel="linked"
            missingLabel="no video event"
          />
          <CoverageMeter
            captured={video.committeeWithVideo}
            total={video.committeeMeetings}
            label="Committee meetings with video"
            capturedLabel="linked"
            missingLabel="no video event"
          />
        </div>

        {video.youtube > 0 && (
          <p className="text-xs text-ink-400">
            {video.youtube} event{video.youtube === 1 ? '' : 's'} are YouTube-hosted and have no caption track (no deep
            link).
          </p>
        )}
      </div>

      {/* PER-SESSION BREAKDOWN */}
      <div className="bg-paper p-6 rounded-lg shadow">
        <h3 className="text-sm font-bold mb-4">Ingest by session</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                {['Session', 'Committee meetings', 'Committee items', 'Plenary meetings', 'Plenary items', 'Video events'].map(
                  label => (
                    <th
                      key={label}
                      className="px-3 py-2 border-b-2 border-ink-200 text-left font-semibold text-ink-500 uppercase tracking-wider whitespace-nowrap"
                    >
                      {label}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {perSession.map(row => (
                <tr
                  key={row.id}
                  className={`border-b border-ink-100 ${session === row.id ? 'bg-accent-soft' : ''}`}
                >
                  <td className="px-3 py-3 font-medium text-ink-800">{row.label}</td>
                  <td className="px-3 py-3">{row.committeeMeetings.toLocaleString()}</td>
                  <td className="px-3 py-3">{row.committeeItems.toLocaleString()}</td>
                  <td className="px-3 py-3">{row.plenaryMeetings.toLocaleString()}</td>
                  <td className="px-3 py-3">{row.plenaryItems.toLocaleString()}</td>
                  <td className="px-3 py-3">{row.videoEvents.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-ink-400 px-1">
        "Missing text" counts agenda items whose Official Report transcript has not yet been published (or came back
        empty) — the crawler re-scans a trailing window and retries these until they appear. Video-caption coverage
        skews toward recent sittings; many pre-2024 events have no subtitle track and fail soft to a plain citation.
      </p>
    </div>
  );
};

export default ParliamentCoverageTab;
