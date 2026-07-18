import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { fmtUsd } from './chartConfig';

const CACHE_COLORS = {
  memo: '#6366f1', // indigo
  local: '#0ea5e9', // sky
  tokens: '#10b981', // emerald
  discount: '#f59e0b', // amber
};

const fmtUsdFine = v => {
  if (!v || v <= 0) return '$0.00';
  if (v < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
};

const fmtChars = v => {
  if (!v || v <= 0) return '0 chars';
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)} MB`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)} KB`;
  return `${v} chars`;
};

const FlagBadge = ({ label, on }) => (
  <span
    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-ui text-xs font-medium ${
      on ? 'bg-accent-soft text-accent-ink' : 'bg-ink-100 text-ink-500'
    }`}
  >
    <span className={`inline-block h-1.5 w-1.5 rounded-full ${on ? 'bg-accent' : 'bg-ink-400'}`} />
    {label}: {on ? 'ON' : 'OFF'}
  </span>
);

export const CacheTab = ({ cacheStats, cacheTimeframe, setCacheTimeframe }) => {
  const { kpi, daily, recentHits, flags } = cacheStats;
  const localCache = cacheStats.localCache || { entries: 0, distinctDocuments: 0, totalHitsServed: 0, oldestEntry: null };
  const localCacheTop = cacheStats.localCacheTop || [];
  const timeframeLabel = cacheTimeframe === 'all' ? 'All Time' : `Last ${cacheTimeframe} Days`;
  const hasData = kpi.memoHits > 0 || kpi.cachedPromptTokens > 0 || kpi.localCacheHits > 0;
  const discountPct = kpi.totalCostUsd > 0 ? (kpi.cacheDiscountUsd / kpi.totalCostUsd) * 100 : 0;
  const chartData = daily.map(d => ({
    ...d,
    label: `${new Date(d.date).getDate()} ${new Date(d.date).toLocaleString('en-GB', { month: 'short' })}`,
  }));

  return (
    <div className="space-y-6">
      {/* HEADER WITH FLAG STATE + FILTER */}
      <div className="flex justify-between items-center bg-paper p-4 rounded-lg shadow">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-lg font-bold">Cache Savings</h2>
          <FlagBadge label="Prompt caching" on={flags.prompt_caching_enabled} />
          <FlagBadge label="Tool-call cache" on={flags.tool_memo_enabled} />
          <FlagBadge label="Local cache" on={flags.local_prompt_cache_enabled} />
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-ink-500 font-medium">Timeframe:</label>
          <select
            value={cacheTimeframe}
            onChange={e => setCacheTimeframe(e.target.value)}
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

      {!hasData && (
        <div className="bg-paper p-8 rounded-lg shadow text-center text-ink-400 text-sm">
          No cache activity for this period. Cached tool calls come from multi-step Deep Research runs;
          cached prompt tokens are only reported for Anthropic models on OpenRouter; local-cache hits
          appear when the same oversized document is researched with the same question twice.
          {(!flags.prompt_caching_enabled || !flags.tool_memo_enabled || !flags.local_prompt_cache_enabled) && (
            <span className="block mt-2 text-amber-600 dark:text-amber-400">
              Note: one or both caching mechanisms are currently switched off (Developer tab → Feature Flags).
            </span>
          )}
        </div>
      )}

      {/* KPI CARDS — shown even without hits so the denominators are visible */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-paper p-4 rounded-lg shadow">
          <h3 className="text-ink-500 text-xs font-bold uppercase">Cached Tool Calls</h3>
          <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{kpi.memoHits}</p>
          <p className="text-xs text-ink-400 mt-1">
            repeat retrievals served from memory — {kpi.memoHitRequests} of {kpi.deepResearchRequests} Deep
            Research requests
          </p>
        </div>
        <div className="bg-paper p-4 rounded-lg shadow">
          <h3 className="text-ink-500 text-xs font-bold uppercase">Cached Prompt Tokens</h3>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
            {kpi.cachedPromptTokens.toLocaleString()}
          </p>
          <p className="text-xs text-ink-400 mt-1">provider-reported, {timeframeLabel}</p>
        </div>
        <div className="bg-paper p-4 rounded-lg shadow">
          <h3 className="text-ink-500 text-xs font-bold uppercase">Cache Discount</h3>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">{fmtUsdFine(kpi.cacheDiscountUsd)}</p>
          <p className="text-xs text-ink-400 mt-1">
            {discountPct > 0 ? `${discountPct.toFixed(1)}% of ${fmtUsd(kpi.totalCostUsd)} spend` : `of ${fmtUsd(kpi.totalCostUsd)} spend`}
          </p>
        </div>
        <div className="bg-paper p-4 rounded-lg shadow">
          <h3 className="text-ink-500 text-xs font-bold uppercase">Provider Cache Hit Rate</h3>
          <p className="text-2xl font-bold">
            {kpi.openrouterEligibleRequests > 0
              ? `${Math.round((kpi.cacheHitRequests / kpi.openrouterEligibleRequests) * 100)}%`
              : '—'}
          </p>
          <p className="text-xs text-ink-400 mt-1">
            {kpi.cacheHitRequests} of {kpi.openrouterEligibleRequests} OpenRouter requests
          </p>
        </div>
      </div>

      {hasData && (
        <>
          {/* CHARTS ROW */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Daily memo + local cache hits (grouped) */}
            <div className="bg-paper p-6 rounded-lg shadow">
              <h2 className="text-sm font-bold mb-4">Daily Cache Hits — Tool Calls &amp; Local ({timeframeLabel})</h2>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="label" stroke="#9ca3af" tick={{ fontSize: 10 }} />
                    <YAxis stroke="#9ca3af" tick={{ fontSize: 10 }} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#fff',
                        borderRadius: '8px',
                        border: '1px solid #e5e7eb',
                        fontSize: '11px',
                      }}
                    />
                    <Bar dataKey="memoHits" name="Cached tool calls" fill={CACHE_COLORS.memo} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="localCacheHits" name="Local cache hits" fill={CACHE_COLORS.local} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Daily cached tokens + discount */}
            <div className="bg-paper p-6 rounded-lg shadow">
              <h2 className="text-sm font-bold mb-4">Daily Cached Tokens &amp; Discount ({timeframeLabel})</h2>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="label" stroke="#9ca3af" tick={{ fontSize: 10 }} />
                    <YAxis yAxisId="tokens" stroke="#9ca3af" tick={{ fontSize: 10 }} />
                    <YAxis
                      yAxisId="usd"
                      orientation="right"
                      stroke="#9ca3af"
                      tick={{ fontSize: 10 }}
                      tickFormatter={v => `$${v.toFixed(2)}`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#fff',
                        borderRadius: '8px',
                        border: '1px solid #e5e7eb',
                        fontSize: '11px',
                      }}
                      formatter={(v, name) =>
                        name === 'Cache discount' ? [fmtUsdFine(v), name] : [v.toLocaleString(), name]
                      }
                    />
                    <Line
                      yAxisId="tokens"
                      type="monotone"
                      dataKey="cachedPromptTokens"
                      name="Cached tokens"
                      stroke={CACHE_COLORS.tokens}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      yAxisId="usd"
                      type="monotone"
                      dataKey="cacheDiscountUsd"
                      name="Cache discount"
                      stroke={CACHE_COLORS.discount}
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* RECENT HITS TABLE */}
          <div className="bg-paper p-6 rounded-lg shadow">
            <h2 className="text-sm font-bold mb-4">Recent Cache Hits ({timeframeLabel})</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr>
                    {['Timestamp', 'Request ID', 'Chat Mode', 'Cached Calls', 'Local Hits', 'Cached Tokens', 'Discount', 'Request Cost'].map(
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
                  {recentHits.map(row => (
                    <tr key={row.requestId + row.createdAt} className="border-b border-ink-100">
                      <td className="px-3 py-3 text-ink-500 whitespace-nowrap">
                        {new Date(row.createdAt).toLocaleString()}
                      </td>
                      <td className="px-3 py-3 font-mono">{row.requestId}</td>
                      <td className="px-3 py-3">{row.chatMode || '—'}</td>
                      <td className="px-3 py-3 font-bold text-indigo-600 dark:text-indigo-400">{row.memoHits}</td>
                      <td className="px-3 py-3 font-bold text-sky-600 dark:text-sky-400">{row.localCacheHits}</td>
                      <td className="px-3 py-3 text-emerald-600 dark:text-emerald-400">
                        {row.cachedPromptTokens.toLocaleString()}
                      </td>
                      <td className="px-3 py-3 text-amber-600 dark:text-amber-400 whitespace-nowrap">
                        {fmtUsdFine(row.cacheDiscountUsd)}
                      </td>
                      <td className="px-3 py-3 text-ink-500 whitespace-nowrap">{fmtUsdFine(row.totalCostUsd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* LOCAL PROMPT CACHING (D7) — cross-user/cross-provider summary reuse */}
      <div className="space-y-4">
        <div className="bg-paper p-4 rounded-lg shadow">
          <h2 className="text-lg font-bold">Local prompt caching</h2>
          <p className="text-sm text-ink-500 mt-1">
            Cross-user, cross-provider reuse of document summaries — the second lawyer asking the same
            question of the same text skips the summarisation call entirely. Exact-match only.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-paper p-4 rounded-lg shadow">
            <h3 className="text-ink-500 text-xs font-bold uppercase">Local Cache Hits</h3>
            <p className="text-2xl font-bold text-sky-600 dark:text-sky-400">{kpi.localCacheHits}</p>
            <p className="text-xs text-ink-400 mt-1">
              across {kpi.localCacheHitRequests} request{kpi.localCacheHitRequests === 1 ? '' : 's'}, {timeframeLabel}
            </p>
          </div>
          <div className="bg-paper p-4 rounded-lg shadow">
            <h3 className="text-ink-500 text-xs font-bold uppercase">Hit Rate</h3>
            <p className="text-2xl font-bold">{`${(kpi.localCacheHitRate * 100).toFixed(1)}%`}</p>
            <p className="text-xs text-ink-400 mt-1">hits vs summarisations performed</p>
          </div>
          <div className="bg-paper p-4 rounded-lg shadow">
            <h3 className="text-ink-500 text-xs font-bold uppercase">Summarisation Avoided</h3>
            <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {fmtChars(kpi.localCacheCharsSaved)}
            </p>
            <p className="text-xs text-ink-400 mt-1">input never sent to the summarisation model</p>
          </div>
          <div className="bg-paper p-4 rounded-lg shadow">
            <h3 className="text-ink-500 text-xs font-bold uppercase">Cached Summaries</h3>
            <p className="text-2xl font-bold">{localCache.entries}</p>
            <p className="text-xs text-ink-400 mt-1">
              {localCache.distinctDocuments} document{localCache.distinctDocuments === 1 ? '' : 's'} ·{' '}
              {localCache.totalHitsServed} hit{localCache.totalHitsServed === 1 ? '' : 's'} all-time
            </p>
          </div>
        </div>

        {/* Top reused summaries */}
        <div className="bg-paper p-6 rounded-lg shadow">
          <h2 className="text-sm font-bold mb-4">Top Reused Summaries (all-time)</h2>
          {localCacheTop.length === 0 ? (
            <p className="text-sm text-ink-400 text-center py-4">
              No cached summaries yet — entries appear after the first oversized document is summarised.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr>
                    {['Document', 'Query', 'Hits', 'Input Size', 'Last Hit'].map(label => (
                      <th
                        key={label}
                        className="px-3 py-2 border-b-2 border-ink-200 text-left font-semibold text-ink-500 uppercase tracking-wider whitespace-nowrap"
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {localCacheTop.map((row, i) => (
                    <tr key={`${row.docName}-${i}`} className="border-b border-ink-100">
                      <td className="px-3 py-3 max-w-xs truncate" title={row.docName}>{row.docName || '—'}</td>
                      <td className="px-3 py-3 max-w-sm truncate text-ink-500" title={row.queryText}>
                        {row.queryText}
                      </td>
                      <td className="px-3 py-3 font-bold text-sky-600 dark:text-sky-400">{row.hitCount}</td>
                      <td className="px-3 py-3 text-ink-500 whitespace-nowrap">{fmtChars(row.charsIn)}</td>
                      <td className="px-3 py-3 text-ink-500 whitespace-nowrap">
                        {row.lastHitAt ? new Date(row.lastHitAt).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <p className="text-xs text-ink-400 px-1">
        Per-request total prompt tokens are not persisted, so a cached-token ratio cannot be shown — only absolute
        cached tokens and the provider-reported discount. Note: OpenRouter itemises an explicit cache discount for
        Anthropic models only; for Gemini/OpenAI models the saving is applied inside the billed cost, so Cache
        Discount reads $0.00 there even when Cached Prompt Tokens shows hits.
      </p>
    </div>
  );
};

export default CacheTab;
