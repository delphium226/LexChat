import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import InfoTip from '../../components/ui/InfoTip';
import { PERF_COLORS } from './chartConfig';

// Red/amber/green styling for a health-band status.
const STATUS_STYLE = {
  ok: { dot: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-400', label: 'Healthy' },
  warn: { dot: 'bg-amber-500', text: 'text-amber-600 dark:text-amber-400', label: 'Watch' },
  bad: { dot: 'bg-red-500', text: 'text-red-600 dark:text-red-400', label: 'Breach' },
};

export const EfficiencyTab = ({ effStats, effTimeframe, setEffTimeframe }) => {
  const { kpi, indicators, daily, worst } = effStats;
  const timeframeLabel = effTimeframe === 'all' ? 'All Time' : `Last ${effTimeframe} Days`;

  const dailyChart = (daily || []).map(d => ({
    ...d,
    label: new Date(d.date).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }),
  }));

  return (
    <div className="space-y-6">
      {/* HEADER WITH FILTER */}
      <div className="flex justify-between items-center bg-paper p-4 rounded-lg shadow">
        <div>
          <h2 className="text-lg font-bold">Agent Loop Efficiency</h2>
          <p className="text-xs text-ink-500 mt-0.5">
            Is the Manager→Worker research loop behaving correctly? Scoped to research queries (those that delegated).
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-ink-500 font-medium">Timeframe:</label>
          <select
            value={effTimeframe}
            onChange={e => setEffTimeframe(e.target.value)}
            className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-accent"
          >
            <option value="1">Last 1 Day</option>
            <option value="7">Last 7 Days</option>
            <option value="30">Last 30 Days</option>
            <option value="90">Last 90 Days</option>
            <option value="all">All Time</option>
          </select>
        </div>
      </div>

      {/* HEALTH-BAND TABLE — the "is it performing correctly?" at-a-glance view */}
      <div className="bg-paper p-6 rounded-lg shadow">
        <h2 className="text-sm font-bold mb-4 flex items-center">
          Health Indicators ({timeframeLabel})
          <InfoTip text="Derived indicators of the agent loop's health, each compared against a target band. Green = behaving as designed (delegate once, retrieve focused provisions, no fan-out or duplication). Amber = drifting. Red = a regression to investigate — e.g. a prompt change or a weaker model causing the Worker to fan out its Phase-2 retrievals across many Acts." />
        </h2>
        {indicators && indicators.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {indicators.map(ind => {
              const s = STATUS_STYLE[ind.status] || STATUS_STYLE.ok;
              return (
                <div key={ind.key} className="border border-ink-100 rounded-lg p-3 flex items-start justify-between">
                  <div>
                    <div className="text-xs font-semibold text-ink-700">{ind.label}</div>
                    <div className="text-2xl font-bold mt-1">{ind.value}</div>
                    <div className="text-xs text-ink-400 mt-0.5">
                      {ind.unit} · target {ind.target}
                    </div>
                  </div>
                  <span className={`flex items-center gap-1.5 text-xs font-medium ${s.text}`}>
                    <span className={`inline-block w-2 h-2 rounded-full ${s.dot}`} />
                    {s.label}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-ink-400 text-sm">No research queries recorded in this period.</div>
        )}
      </div>

      {/* KPI CARDS — raw per-request counters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-paper p-4 rounded-lg shadow">
          <h3 className="text-ink-500 text-xs font-bold uppercase flex items-center">
            Research Queries
            <InfoTip text="Number of queries in this period that delegated to the Worker research agent at least once. Pure-chat turns and clarifying questions (no delegation) are excluded, since the efficiency indicators only describe the research loop." />
          </h3>
          <p className="text-2xl font-bold">{kpi.totalRequests}</p>
          <p className="text-xs text-ink-400 mt-1">{timeframeLabel}</p>
        </div>
        <div className="bg-paper p-4 rounded-lg shadow">
          <h3 className="text-ink-500 text-xs font-bold uppercase flex items-center">
            Worker Tool Calls / Query
            <InfoTip text="Average number of tools the Worker invoked per research query (searches + retrievals). The healthy pattern is a small number of Phase-1 searches followed by one focused Phase-2 retrieval per relevant Act. A rising average signals the Worker is doing more work per answer — often fan-out across tangential legislation." />
          </h3>
          <p className="text-2xl font-bold text-indigo-600">{kpi.avgWorkerTools}</p>
          <p className="text-xs text-ink-400 mt-1">
            {kpi.avgPhase1} search · {kpi.avgPhase2} retrieve
          </p>
        </div>
        <div className="bg-paper p-4 rounded-lg shadow">
          <h3 className="text-ink-500 text-xs font-bold uppercase flex items-center">
            Avg Fan-out
            <InfoTip text="Average Phase-2 retrievals divided by sources actually kept in the answer. ≈1 means the Worker retrieved only what it cited. A high value means it pulled full text for many Acts/cases it never used — the dominant cost/latency regression this metric was built to catch." />
          </h3>
          <p className="text-2xl font-bold text-amber-600">{kpi.avgFanout}</p>
          <p className="text-xs text-ink-400 mt-1">retrievals / kept source</p>
        </div>
        <div className="bg-paper p-4 rounded-lg shadow">
          <h3 className="text-ink-500 text-xs font-bold uppercase flex items-center">
            Summarisations / Query
            <InfoTip text="Average number of large tool results that were summarised before the Worker could use them, per query. Summarisation adds LLM calls and latency; a rising value with a big-context model may indicate the summarise threshold needs tuning. Compression shows the average summarised size as a fraction of the original." />
          </h3>
          <p className="text-2xl font-bold text-emerald-600">{kpi.avgSummCalls}</p>
          <p className="text-xs text-ink-400 mt-1">
            compression {kpi.summCompression || '—'} · {kpi.avgTruncations} trunc/query
          </p>
        </div>
      </div>

      {/* TREND CHART */}
      <div className="bg-paper p-6 rounded-lg shadow">
        <h2 className="text-sm font-bold mb-4 flex items-center">
          Efficiency Trend ({timeframeLabel})
          <InfoTip text="Daily averages of the three behaviours most predictive of a regression: delegations per query (should sit at 1), fan-out ratio (should sit near 1), and redundant tool calls (should sit at 0). A sustained rise in any line marks the day behaviour changed — cross-reference with prompt or model changes." />
        </h2>
        {dailyChart.length > 0 ? (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dailyChart} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="label" stroke="#9ca3af" tick={{ fontSize: 10 }} />
                <YAxis stroke="#9ca3af" tick={{ fontSize: 10 }} allowDecimals />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                    fontSize: '11px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Line type="monotone" dataKey="avgDelegations" name="Delegations" stroke={PERF_COLORS.total} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="avgFanout" name="Fan-out" stroke={PERF_COLORS.lex} strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="avgRedundant" name="Redundant calls" stroke={PERF_COLORS.llm} strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-56 flex items-center justify-center text-ink-400 text-sm">No data for this period.</div>
        )}
      </div>

      {/* WORST OFFENDERS TABLE */}
      <div className="bg-paper p-6 rounded-lg shadow">
        <h2 className="text-sm font-bold mb-4 flex items-center">
          Worst Offenders ({timeframeLabel})
          <InfoTip text="The research queries with the most redundant tool calls and highest fan-out, for drill-down. A row with high Phase-2 and low Kept, or Redundant > 0, is a query where the Worker over-retrieved. Search the Request ID in the agent log (grep '[Efficiency] req=<id>') for the full trace." />
        </h2>
        {worst && worst.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr>
                  {['Request ID', 'Timestamp', 'Delegations', 'Worker Tools', 'Phase-2', 'Kept', 'Fan-out', 'Redundant', 'Truncations'].map(h => (
                    <th
                      key={h}
                      className="px-3 py-2 border-b-2 border-ink-200 text-left font-semibold text-ink-500 uppercase tracking-wider whitespace-nowrap"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {worst.map(row => (
                  <tr key={row.requestId} className="border-b border-ink-100">
                    <td className="px-3 py-3 font-mono">{row.requestId}</td>
                    <td className="px-3 py-3 text-ink-500 whitespace-nowrap">{new Date(row.createdAt).toLocaleString()}</td>
                    <td className={`px-3 py-3 font-bold ${row.delegations > 1 ? 'text-red-600 dark:text-red-400' : ''}`}>{row.delegations}</td>
                    <td className="px-3 py-3">{row.workerTools}</td>
                    <td className="px-3 py-3">{row.phase2}</td>
                    <td className="px-3 py-3">{row.kept}/{row.extracted}</td>
                    <td className={`px-3 py-3 font-bold ${row.fanout >= 3 ? 'text-red-600 dark:text-red-400' : row.fanout >= 2 ? 'text-amber-600 dark:text-amber-400' : ''}`}>{row.fanout}</td>
                    <td className={`px-3 py-3 font-bold ${row.redundant > 0 ? 'text-red-600 dark:text-red-400' : ''}`}>{row.redundant}</td>
                    <td className="px-3 py-3">{row.truncations}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-ink-400 text-sm">No research queries recorded yet.</p>
        )}
      </div>
    </div>
  );
};

export default EfficiencyTab;
