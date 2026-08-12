import React from 'react';
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import Spinner from '../../components/ui/Spinner';

// Analytics for the end-of-session feedback form (the pre-pilot questionnaire).
//
// Two jobs, in this order: how is the assistant doing on the three accuracy
// questions, and — the operational one — who is using the system without
// filling the form in, so they can be chased.
//
// Every statistic here describes one population: threads a lawyer submitted a
// feedback form for. Threads with no form are excluded by the backend (both
// /feedback/session and /feedback/session/durations), so the session-length
// medians are no longer dominated by abandoned threads whose end had to be
// inferred. The exception is the coverage pair below, which exists precisely
// to count what is missing.

// The operator's own login: smoke tests, demos and support reproductions, not
// legal research. The backend drops it from the responses and the durations;
// this set is what keeps it out of the two compliance-derived tiles, whose
// endpoint still returns every account so the chase list stays complete.
const EXCLUDED_USERNAMES = new Set(['admin']);

const ANSWER_LABELS = {
  yes: 'Yes',
  partially: 'Partially',
  no: 'No',
  unsure: 'Unsure',
  one_go: 'In one go',
  not_one_go: 'Not in one go',
};

// Green / amber / red / slate, matching the survey compliance chart's palette.
const ANSWER_COLORS = { yes: '#22c55e', partially: '#f59e0b', no: '#ef4444', unsure: '#94a3b8' };
const SCALE_COLOR = '#6366f1';

// `good` names the answer that counts as a positive result. It is 'yes' for
// three of the four, but 7a asks whether the assistant got something WRONG, so
// there 'no' is the good answer. Every read of these questions — the tiles, the
// chart colours — goes through `good` rather than assuming yes-is-good, which
// would report the pre-pilot's accuracy exactly backwards on 7a.
const ACCURACY_QUESTIONS = [
  { field: 'found_right_law', label: 'Found right law', answers: ['yes', 'partially', 'no'], good: 'yes' },
  { field: 'right_jurisdiction', label: 'Right jurisdiction', answers: ['yes', 'partially', 'no'], good: 'yes' },
  {
    field: 'references_accurate',
    label: 'Accurate references',
    // 'unsure' is a legacy value: it was 6a's third option before the users
    // revised the question to yes/partially/no. It can no longer be submitted,
    // but rows written before the change still hold it and must still stack.
    answers: ['yes', 'partially', 'no', 'unsure'],
    good: 'yes',
  },
  { field: 'refers_incorrectly', label: 'Referred incorrectly', answers: ['yes', 'partially', 'no'], good: 'no' },
];

// Colour for one answer segment, resolved against its question's polarity: the
// good answer is green and its opposite red, whichever literal word that is.
const answerColor = (answer, good) => {
  if (answer === 'partially') return ANSWER_COLORS.partially;
  if (answer === 'unsure') return ANSWER_COLORS.unsure;
  return answer === good ? ANSWER_COLORS.yes : ANSWER_COLORS.no;
};

const mean = (rows, field) => {
  const answered = rows.filter(r => r[field] != null);
  return answered.length > 0 ? answered.reduce((s, r) => s + r[field], 0) / answered.length : null;
};

const sum = (rows, field) => rows.reduce((s, r) => s + (r[field] ?? 0), 0);

// Share of answers to `field` that were `value`, as a percentage of everyone who
// answered the question at all (a legacy 'unsure' is not a 'yes', and counts in
// the denominator).
const answerShare = (rows, field, value) => {
  const answered = rows.filter(r => r[field] != null);
  return answered.length > 0 ? (answered.filter(r => r[field] === value).length / answered.length) * 100 : null;
};

const fmtDate = iso => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : null);

const fmtDuration = secs => {
  if (secs == null) return '—';
  if (secs < 60) return `${Math.round(secs)}s`;
  if (secs < 3600) return `${Math.round(secs / 60)}m`;
  const h = Math.floor(secs / 3600);
  const m = Math.round((secs % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
};

// Buckets for the session-length histogram. Open-ended at the top: the metric
// is raw elapsed time with no idle-gap splitting, so a thread resumed the next
// day lands in "4h+" rather than stretching the axis.
const DURATION_BUCKETS = [
  { label: '<5m', max: 300 },
  { label: '5–15m', max: 900 },
  { label: '15–30m', max: 1800 },
  { label: '30–60m', max: 3600 },
  { label: '1–2h', max: 7200 },
  { label: '2–4h', max: 14400 },
  { label: '4h+', max: Infinity },
];

const daysSince = iso => (iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000) : null);

const Tile = ({ label, value, tone = 'ink' }) => (
  <div className="bg-ink-50 rounded-lg p-4 text-center">
    <div className={`text-2xl font-bold ${tone === 'danger' ? 'text-danger' : 'text-ink-800'}`}>{value}</div>
    <div className="text-xs text-ink-500 mt-1">{label}</div>
  </div>
);

const thCls =
  'px-4 py-2 border-b-2 border-ink-200 text-left font-semibold text-ink-500 uppercase tracking-wider whitespace-nowrap';

export const SessionFeedbackTab = ({
  sessionFeedback,
  compliance,
  durations,
  isLoading,
  timeframe,
  setTimeframe,
  refetch,
}) => {
  const timeframeLabel = timeframe === 'all' ? 'All Time' : `Last ${timeframe} Days`;
  const rows = sessionFeedback || [];

  const avgConf = mean(rows, 'confidence');
  const avgEase = mean(rows, 'ease_of_use');
  const avgSaved = mean(rows, 'time_saved_hours');
  const totalSaved = sum(rows, 'time_saved_hours');
  const avgVerif = mean(rows, 'verification_hours');

  // Coverage is responses per thread worked in: the form is asked for once per
  // session, so a lawyer with 6 threads and 1 response is 17% covered. This is
  // the one pair of numbers that still counts threads with no feedback — that
  // is what it measures, and excluding them would pin it at 100%.
  //
  // Recomputed from `compliance.users` rather than read off `compliance.totals`
  // so the operator account can be dropped without changing the endpoint, which
  // also backs the chase list below.
  const complianceUsers = (compliance?.users || []).filter(u => !EXCLUDED_USERNAMES.has(u.username));
  const activeUsers = complianceUsers.filter(u => u.threads > 0);
  const totals = compliance
    ? {
        active_users: activeUsers.length,
        responding_users: activeUsers.filter(u => u.responses > 0).length,
        threads: complianceUsers.reduce((s, u) => s + u.threads, 0),
        responses: complianceUsers.reduce((s, u) => s + u.responses, 0),
      }
    : null;
  const coverage = totals && totals.threads > 0 ? (totals.responses / totals.threads) * 100 : null;

  // `good` rides along on each row so the chart's per-category <Cell>s can colour
  // by sentiment rather than by literal answer word.
  const accuracyData = ACCURACY_QUESTIONS.map(q => {
    const answered = rows.filter(r => r[q.field] != null);
    const entry = { label: q.label, answered: answered.length, good: q.good };
    q.answers.forEach(a => {
      entry[a] = answered.filter(r => r[q.field] === a).length;
    });
    return entry;
  });
  const allAnswerKeys = [...new Set(ACCURACY_QUESTIONS.flatMap(q => q.answers))];

  // --- Session length ---
  const dur = durations?.summary;
  const durSessions = durations?.sessions || [];
  const closedShare = dur && dur.sessions > 0 ? (dur.closed_properly / dur.sessions) * 100 : null;
  const durationHistogram = DURATION_BUCKETS.map((b, i) => {
    const min = i === 0 ? 0 : DURATION_BUCKETS[i - 1].max;
    return {
      bucket: b.label,
      closed: durSessions.filter(
        s => s.end_signal === 'finished_button' && s.duration_seconds >= min && s.duration_seconds < b.max
      ).length,
      inferred: durSessions.filter(
        s => s.end_signal === 'last_response' && s.duration_seconds >= min && s.duration_seconds < b.max
      ).length,
    };
  });
  const longestSessions = [...durSessions].sort((a, b) => b.duration_seconds - a.duration_seconds).slice(0, 8);

  const scaleData = [1, 2, 3, 4, 5].map(n => ({
    score: `${n}`,
    confidence: rows.filter(r => r.confidence === n).length,
    ease: rows.filter(r => r.ease_of_use === n).length,
  }));

  // Chase list: anyone who worked in at least one thread this period. Sorted
  // by threads left un-reviewed, so the biggest gaps sit at the top.
  const chaseRows = (compliance?.users || [])
    .filter(u => u.threads > 0)
    .map(u => ({ ...u, gap: Math.max(0, u.threads - u.responses) }))
    .sort((a, b) => b.gap - a.gap || b.threads - a.threads);
  const neverResponded = chaseRows.filter(u => u.responses === 0).length;

  return (
    <div className="space-y-4">
      {/* TIMEFRAME FILTER HEADER */}
      <div className="flex justify-between items-center bg-paper p-4 rounded-lg shadow">
        <div>
          <h2 className="text-lg font-bold">Session Feedback</h2>
          <p className="text-sm text-ink-500">
            The end-of-session form, submitted from the &ldquo;Finished session&rdquo; button — {timeframeLabel}.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-ink-500 font-medium">Timeframe:</label>
          <select
            value={timeframe}
            onChange={e => setTimeframe(e.target.value)}
            className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-accent"
          >
            <option value="1">Last 1 Day</option>
            <option value="3">Last 3 Days</option>
            <option value="7">Last 7 Days</option>
            <option value="30">Last 30 Days</option>
            <option value="90">Last 90 Days</option>
            <option value="all">All Time</option>
          </select>
          <button onClick={() => refetch(timeframe)} className="text-xs text-accent hover:underline font-ui">
            Refresh
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="bg-paper p-6 rounded-lg shadow flex justify-center items-center h-40">
          <Spinner />
        </div>
      ) : (
        <>
          {/* HEADLINE NUMBERS */}
          <div className="bg-paper p-6 rounded-lg shadow">
            <h3 className="text-sm font-bold mb-3">Overview</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
              <Tile label="Responses" value={rows.length} />
              <Tile
                label="Threads covered"
                value={coverage != null ? `${coverage.toFixed(0)}%` : '—'}
                tone={coverage != null && coverage < 50 ? 'danger' : 'ink'}
              />
              <Tile
                label="Users responding"
                value={totals ? `${totals.responding_users}/${totals.active_users}` : '—'}
                tone={totals && totals.responding_users < totals.active_users ? 'danger' : 'ink'}
              />
              <Tile label="Avg confidence" value={avgConf != null ? `${avgConf.toFixed(1)}/5` : '—'} />
              <Tile label="Avg ease of use" value={avgEase != null ? `${avgEase.toFixed(1)}/5` : '—'} />
              <Tile label="Avg hrs saved" value={avgSaved != null ? avgSaved.toFixed(1) : '—'} />
              <Tile label="Total hrs saved" value={totalSaved > 0 ? totalSaved.toFixed(1) : '—'} />
            </div>
            {avgVerif != null && (
              <p className="text-xs text-ink-500 mt-3">
                Lawyers spent an average of {avgVerif.toFixed(1)} hrs checking outputs per session.
              </p>
            )}
          </div>

          {/* SESSION LENGTH */}
          <div className="bg-paper p-6 rounded-lg shadow">
            <h3 className="text-sm font-bold mb-1">Session length</h3>
            <p className="text-xs text-ink-500 mb-4">
              From the first question in a thread to the moment the lawyer pressed &ldquo;Finished session&rdquo; —
              or, where the press was not timed, to the last answer the assistant gave. Elapsed time, not split on
              breaks, so a thread picked up the next day counts as one long session. Only threads with a submitted
              feedback form are measured.
            </p>
            {!dur || dur.sessions === 0 ? (
              <p className="text-ink-400 text-sm">No sessions with feedback in this period.</p>
            ) : (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
                  <Tile label="Median session" value={fmtDuration(dur.median_seconds)} />
                  <Tile label="Mean session" value={fmtDuration(dur.mean_seconds)} />
                  <Tile label="Total time" value={fmtDuration(dur.total_seconds)} />
                  <Tile label="Sessions measured" value={dur.sessions} />
                  <Tile
                    label="Ended by button"
                    value={closedShare != null ? `${closedShare.toFixed(0)}%` : '—'}
                    tone={closedShare != null && closedShare < 50 ? 'danger' : 'ink'}
                  />
                  <Tile label="Median, in one go" value={fmtDuration(dur.median_one_go)} />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={durationHistogram} barCategoryGap="25%">
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
                        <Tooltip contentStyle={{ fontSize: 11 }} />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Bar dataKey="closed" name="Ended by button" stackId="a" fill="#22c55e" />
                        <Bar dataKey="inferred" name="Inferred from last answer" stackId="a" fill="#94a3b8" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div className="bg-ink-50 rounded-lg p-3">
                        <div className="text-lg font-bold text-ink-800">{fmtDuration(dur.median_closed)}</div>
                        <div className="text-xs text-ink-500">
                          Median when ended by button ({dur.closed_properly})
                        </div>
                      </div>
                      <div className="bg-ink-50 rounded-lg p-3">
                        <div className="text-lg font-bold text-ink-800">{fmtDuration(dur.median_inferred)}</div>
                        <div className="text-xs text-ink-500">Median when inferred ({dur.inferred})</div>
                      </div>
                      <div className="bg-ink-50 rounded-lg p-3">
                        <div className="text-lg font-bold text-ink-800">{fmtDuration(dur.median_one_go)}</div>
                        <div className="text-xs text-ink-500">Median, done in one go ({dur.one_go_sessions})</div>
                      </div>
                      <div className="bg-ink-50 rounded-lg p-3">
                        <div className="text-lg font-bold text-ink-800">{fmtDuration(dur.median_not_one_go)}</div>
                        <div className="text-xs text-ink-500">
                          Median, with breaks ({dur.not_one_go_sessions})
                        </div>
                      </div>
                    </div>
                    <p className="text-xs text-ink-400">
                      Inferred sessions undercount — they stop when the assistant finished writing and ignore however
                      long the answer was then read for. The &ldquo;in one go&rdquo; split comes from question 3, so a
                      form that skipped it counts in neither half.
                    </p>
                  </div>
                </div>

                {longestSessions.length > 0 && (
                  <div className="mt-5">
                    <h4 className="text-xs font-bold text-ink-600 uppercase tracking-wider mb-2">Longest sessions</h4>
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr>
                            <th className={`${thCls} w-24`}>Length</th>
                            <th className={`${thCls} w-32`}>User</th>
                            <th className={thCls}>Thread</th>
                            <th className={`${thCls} w-24`}>Queries</th>
                            <th className={`${thCls} w-40`}>Ended by</th>
                            <th className={`${thCls} w-32`}>Started</th>
                          </tr>
                        </thead>
                        <tbody>
                          {longestSessions.map(s => (
                            <tr key={s.chat_id} className="border-b border-ink-100">
                              <td className="px-4 py-2 font-medium text-ink-800 whitespace-nowrap">
                                {fmtDuration(s.duration_seconds)}
                              </td>
                              <td className="px-4 py-2 text-ink-700 whitespace-nowrap">{s.username}</td>
                              <td className="px-4 py-2 text-ink-700">{s.chat_title || `#${s.chat_id}`}</td>
                              <td className="px-4 py-2 text-ink-500 text-center">{s.queries}</td>
                              <td className="px-4 py-2 whitespace-nowrap">
                                {s.end_signal === 'finished_button' ? (
                                  <span className="text-ink-700">Finished session</span>
                                ) : (
                                  <span className="text-ink-400">Last answer (inferred)</span>
                                )}
                                {s.session_continuity === 'not_one_go' && (
                                  <span className="text-ink-400"> · with breaks</span>
                                )}
                              </td>
                              <td className="px-4 py-2 text-ink-500 whitespace-nowrap">{fmtDate(s.started_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* ACCURACY + SCALES */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-paper p-6 rounded-lg shadow">
              <h3 className="text-sm font-bold mb-1">Accuracy</h3>
              <p className="text-xs text-ink-500 mb-4">
                Questions 5a, 5c, 6a and 7a — the four the pre-pilot exists to answer. Each tile shows the share who
                gave the <em>good</em> answer, which for &ldquo;Referred incorrectly&rdquo; is <strong>no</strong>.
              </p>
              {rows.length === 0 ? (
                <p className="text-ink-400 text-sm">No responses yet.</p>
              ) : (
                <>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                    {ACCURACY_QUESTIONS.map(q => {
                      const share = answerShare(rows, q.field, q.good);
                      return (
                        <Tile
                          key={q.field}
                          label={`${q.label} — ${ANSWER_LABELS[q.good].toLowerCase()}`}
                          value={share != null ? `${share.toFixed(0)}%` : '—'}
                          tone={share != null && share < 75 ? 'danger' : 'ink'}
                        />
                      );
                    })}
                  </div>
                  <ResponsiveContainer width="100%" height={190}>
                    <BarChart data={accuracyData} barCategoryGap="30%">
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
                      <Tooltip contentStyle={{ fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {allAnswerKeys.map((a, i) => (
                        <Bar
                          key={a}
                          dataKey={a}
                          name={ANSWER_LABELS[a]}
                          stackId="a"
                          fill={ANSWER_COLORS[a]}
                          radius={i === allAnswerKeys.length - 1 ? [3, 3, 0, 0] : undefined}
                        >
                          {/* Cells map to the x-categories, so one answer series can
                              be green in three questions and red in the fourth. The
                              Bar's own fill stays the legend swatch. */}
                          {accuracyData.map(entry => (
                            <Cell key={entry.label} fill={answerColor(a, entry.good)} />
                          ))}
                        </Bar>
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                  <p className="text-xs text-ink-400 mt-2">
                    Colour follows the result, not the word: for &ldquo;Referred incorrectly&rdquo;, <em>No</em> is the
                    good answer and is shown green.
                  </p>
                </>
              )}
            </div>

            <div className="bg-paper p-6 rounded-lg shadow">
              <h3 className="text-sm font-bold mb-1">Confidence and ease of use</h3>
              <p className="text-xs text-ink-500 mb-4">Questions 8 and 9a — how many responses gave each score.</p>
              {rows.length === 0 ? (
                <p className="text-ink-400 text-sm">No responses yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={252}>
                  <BarChart data={scaleData} barCategoryGap="25%">
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="score" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} />
                    <Tooltip contentStyle={{ fontSize: 11 }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="confidence" name="Confidence" fill={SCALE_COLOR} radius={[3, 3, 0, 0]} />
                    <Bar dataKey="ease" name="Ease of use" fill="#0ea5e9" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* CHASE LIST */}
          <div className="bg-paper p-6 rounded-lg shadow">
            <h3 className="text-sm font-bold mb-1">Who to chase</h3>
            <p className="text-xs text-ink-500 mb-4">
              Everyone who used the system in this period, ordered by how many threads they finished without leaving
              feedback.
              {neverResponded > 0 && (
                <>
                  {' '}
                  <span className="text-danger font-medium">
                    {neverResponded} {neverResponded === 1 ? 'user has' : 'users have'} submitted nothing at all.
                  </span>
                </>
              )}
            </p>
            {chaseRows.length === 0 ? (
              <p className="text-ink-400 text-sm">Nobody used the system in this period.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr>
                      <th className={thCls}>User</th>
                      <th className={`${thCls} w-24`}>Threads</th>
                      <th className={`${thCls} w-24`}>Queries</th>
                      <th className={`${thCls} w-28`}>Responses</th>
                      <th className={`${thCls} w-32`}>Missing</th>
                      <th className={`${thCls} w-32`}>Last active</th>
                      <th className={`${thCls} w-40`}>Last feedback</th>
                    </tr>
                  </thead>
                  <tbody>
                    {chaseRows.map(u => {
                      const since = daysSince(u.last_feedback);
                      return (
                        <tr
                          key={u.user_id}
                          className={`border-b border-ink-100 ${u.responses === 0 ? 'bg-danger/5' : ''}`}
                        >
                          <td className="px-4 py-3 font-medium text-ink-800 whitespace-nowrap">{u.username}</td>
                          <td className="px-4 py-3 text-ink-700 text-center">{u.threads}</td>
                          <td className="px-4 py-3 text-ink-500 text-center">{u.queries}</td>
                          <td className="px-4 py-3 text-center">
                            <span className={u.responses === 0 ? 'text-danger font-semibold' : 'text-ink-700'}>
                              {u.responses}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-center">
                            {u.gap === 0 ? (
                              <span className="text-ink-400">—</span>
                            ) : (
                              <span className={u.responses === 0 ? 'text-danger font-semibold' : 'text-ink-700'}>
                                {u.gap} {u.gap === 1 ? 'thread' : 'threads'}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-ink-500 whitespace-nowrap">{fmtDate(u.last_active) || '—'}</td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {u.last_feedback ? (
                              <span className="text-ink-500">
                                {fmtDate(u.last_feedback)}
                                {since != null && since > 0 && (
                                  <span className="text-ink-400"> · {since}d ago</span>
                                )}
                              </span>
                            ) : (
                              <span className="text-danger font-medium">Never</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* INDIVIDUAL RESPONSES */}
          <div className="bg-paper p-6 rounded-lg shadow">
            <h3 className="text-sm font-bold mb-4">Individual responses</h3>
            {rows.length === 0 ? (
              <p className="text-ink-400 text-sm">
                No session feedback yet. Enable &ldquo;Session feedback form&rdquo; on the Developer tab to show the
                button to users.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr>
                      <th className={`${thCls} w-32`}>User</th>
                      <th className={`${thCls} w-44`}>Date &amp; Time</th>
                      <th className={thCls}>Thread</th>
                      <th className={`${thCls} w-28`}>Manual (hrs)</th>
                      <th className={`${thCls} w-28`}>Saved (hrs)</th>
                      <th className={`${thCls} w-28`}>Checking (hrs)</th>
                      <th className={`${thCls} w-32`}>Right law</th>
                      <th className={`${thCls} w-32`}>Jurisdiction</th>
                      <th className={`${thCls} w-28`}>References</th>
                      <th className={`${thCls} w-32`}>Referred incorrectly</th>
                      <th className={`${thCls} w-24`}>Confidence</th>
                      <th className={`${thCls} w-24`}>Ease</th>
                      <th className={thCls}>Observations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(item => {
                      const notes = [
                        ['5b', item.found_right_law_notes],
                        ['5d', item.right_jurisdiction_notes],
                        ['6b', item.references_notes],
                        ['7b', item.refers_incorrectly_notes],
                        ['9b', item.ease_of_use_reason],
                        ['10', item.other_comments],
                      ].filter(([, text]) => text);
                      return (
                        <tr key={item.id} className="border-b border-ink-100 align-top">
                          <td className="px-4 py-3 font-medium text-ink-800 whitespace-nowrap">{item.username}</td>
                          <td className="px-4 py-3 text-ink-500 whitespace-nowrap">
                            {new Date(item.created_at).toLocaleString()}
                          </td>
                          <td className="px-4 py-3 text-ink-700">
                            {item.chat_title || (item.chat_id ? `#${item.chat_id}` : '—')}
                            <div className="text-xs text-ink-400">
                              {[
                                item.message_count != null ? `${item.message_count} msgs` : null,
                                ANSWER_LABELS[item.session_continuity] || null,
                              ]
                                .filter(Boolean)
                                .join(' · ')}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-ink-700 text-center">{item.manual_time_hours ?? '—'}</td>
                          <td className="px-4 py-3 text-ink-700 text-center">{item.time_saved_hours ?? '—'}</td>
                          <td className="px-4 py-3 text-ink-700 text-center">{item.verification_hours ?? '—'}</td>
                          <td className="px-4 py-3 text-ink-700 text-center">
                            {ANSWER_LABELS[item.found_right_law] || '—'}
                          </td>
                          <td className="px-4 py-3 text-ink-700 text-center">
                            {ANSWER_LABELS[item.right_jurisdiction] || '—'}
                          </td>
                          <td className="px-4 py-3 text-ink-700 text-center">
                            {ANSWER_LABELS[item.references_accurate] || '—'}
                          </td>
                          <td className="px-4 py-3 text-ink-700 text-center">
                            {ANSWER_LABELS[item.refers_incorrectly] || '—'}
                          </td>
                          <td className="px-4 py-3 text-ink-700 text-center">
                            {item.confidence != null ? `${item.confidence}/5` : '—'}
                          </td>
                          <td className="px-4 py-3 text-ink-700 text-center">
                            {item.ease_of_use != null ? `${item.ease_of_use}/5` : '—'}
                          </td>
                          <td className="px-4 py-3 text-ink-700 whitespace-pre-wrap min-w-[18rem]">
                            {notes.map(([q, text]) => (
                              <div key={q} className="mb-1 last:mb-0">
                                <span className="text-ink-400">{q}.</span> {text}
                              </div>
                            ))}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default SessionFeedbackTab;
