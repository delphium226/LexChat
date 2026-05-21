import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import axios from 'axios';
import { getFeedbackStats, testLearningRetrieval, getPerformanceStats, getUsageStats, clearUsageData, clearPerformanceData, clearFeedbackData, getLatestHealthStatus, getHealthHistory, triggerHealthCheck, getQueryPerformanceStats, getProductFeedback, getSurveyCompliance, getMessageRatings, getProviderConfig, saveProviderConfig, setActiveProvider, getOpenRouterModels, getCostStats, getFeatures, saveFeatures } from '../services/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend } from 'recharts';

const Spinner = ({ size = 'md' }) => {
    const cls = size === 'sm' ? 'h-4 w-4' : 'h-8 w-8';
    return (
        <svg className={`animate-spin ${cls} text-blue-600`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 22 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
    );
};

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

const fmtMs = (ms) => {
    if (ms == null || ms === 0) return '—';
    if (ms >= 60000) return `${(ms / 60000).toFixed(1)}m`;
    if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.round(ms)}ms`;
};

const PERF_COLORS = {
    llm: '#6366f1',    // indigo
    lex: '#f59e0b',    // amber
    other: '#94a3b8',  // slate
    total: '#2563eb',  // blue
    ttft: '#10b981',   // emerald
};

// -----------------------------------------------------------------------
// Performance Tab — small info-icon tooltip helper
// -----------------------------------------------------------------------

const InfoTip = ({ text }) => (
    <span
        title={text}
        className="ml-1 inline-block text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 cursor-help text-xs select-none leading-none"
        aria-label={text}
    >ⓘ</span>
);

// -----------------------------------------------------------------------
// Performance Tab Component
// -----------------------------------------------------------------------

const PerformanceTab = ({ perfStats, perfTimeframe, setPerfTimeframe }) => {
    const { kpi, daily, llmDistribution, slowest } = perfStats;

    // Compute "other" ms = total - llm - lex (queue wait + overhead)
    const dailyWithOther = daily.map(d => ({
        ...d,
        otherMs: Math.max(0, d.avgTotalMs - d.avgLlmMs - d.avgLexMs),
        label: new Date(d.date).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }),
    }));

    const timeframeLabel = perfTimeframe === 'all' ? 'All Time' : `Last ${perfTimeframe} Days`;

    return (
        <div className="space-y-6">
            {/* HEADER WITH FILTER */}
            <div className="flex justify-between items-center bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                <h2 className="text-lg font-bold dark:text-white">Query Performance</h2>
                <div className="flex items-center space-x-2">
                    <label className="text-sm text-gray-500 dark:text-gray-400 font-medium">Timeframe:</label>
                    <select
                        value={perfTimeframe}
                        onChange={(e) => setPerfTimeframe(e.target.value)}
                        className="p-2 border rounded-md text-sm dark:bg-zinc-700 dark:border-zinc-600 dark:text-white focus:ring-2 focus:ring-blue-500"
                    >
                        <option value="1">Last 1 Day</option>
                        <option value="3">Last 3 Days</option>
                        <option value="7">Last 7 Days</option>
                        <option value="30">Last 30 Days</option>
                        <option value="90">Last 90 Days</option>
                        <option value="all">All Time</option>
                    </select>
                </div>
            </div>

            {/* KPI CARDS */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                    <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase flex items-center">
                        Queries Processed
                        <InfoTip text="The total number of chat queries processed by the system in the selected period. Each time a user sends a message and the AI generates a response counts as one query. A conversation with multiple back-and-forth exchanges counts as multiple queries — one per user message. Failed requests that never reached the AI model are not included." />
                    </h3>
                    <p className="text-2xl font-bold dark:text-white">{kpi.totalRequests}</p>
                    <p className="text-xs text-gray-400 mt-1">{timeframeLabel}</p>
                </div>
                <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                    <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase flex items-center">
                        Average Response Time
                        <InfoTip text="Mean end-to-end time from when the HTTP request arrived at the server to when the final response token was streamed to the browser. Covers all phases: queue wait, AI model inference, LEX API lookups, and server overhead. For legal research queries, 10–30 seconds is typical; complex multi-search queries can exceed a minute. A rising average over time usually points to growing concurrent load or degraded AI model performance." />
                    </h3>
                    <p className="text-2xl font-bold text-blue-600">{fmtMs(kpi.avgTotalMs)}</p>
                    <p className="text-xs text-gray-400 mt-1 flex items-center">
                        P95: {fmtMs(kpi.p95TotalMs)}
                        <InfoTip text="95th-percentile response time: 95 out of every 100 queries completed faster than this value. A useful measure of worst-case user experience that is not skewed by rare extreme outliers. If P95 is much higher than the average — e.g. average is 15s but P95 is 60s — it means a minority of queries are dramatically slower, often those involving many sequential LEX API searches or very long conversation histories fed into the AI model." />
                    </p>
                </div>
                <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                    <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase flex items-center">
                        AI Model Calls per Query
                        <InfoTip text="Average number of separate round-trips made to the AI language model (mistral-large via Ollama) per query. AILA uses a Manager-Worker agent loop: the Manager calls the model to plan a research strategy, the Worker calls it to decide which LEX API searches to run, and both call it again after each tool result to interpret findings and decide whether more research is needed. A simple factual question may need 2–3 calls; a complex research task spanning multiple statutes or case law areas may need 6 or more. Higher call counts directly increase total response time and model load." />
                    </h3>
                    <p className="text-2xl font-bold text-indigo-600">{kpi.avgLlmCalls}</p>
                    <p className="text-xs text-gray-400 mt-1 flex items-center">
                        Avg first-token delay: {fmtMs(kpi.avgTtftMs)}
                        <InfoTip text="Average Time to First Token (TTFT): how long from when the server sent the prompt to the AI model until the model produced its very first output token. Before any output appears, the model must load the full prompt into its context window (including conversation history and tool results) and begin generation. A high TTFT — e.g. over 10 seconds — usually means the AI model is under heavy concurrent load, processing an unusually large input context, or the GPU is throttling. This directly affects perceived responsiveness, since the user sees a blank screen until TTFT elapses." />
                    </p>
                </div>
                <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                    <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase flex items-center">
                        Legal Database Lookups per Query
                        <InfoTip text="Average number of HTTP calls made to the LEX API — the UK government's authoritative database of legislation, statutory instruments, and court judgments — per query. Each lookup retrieves documents the agent uses to build its answer. Simple queries about a well-known Act may need only 1–2 lookups; broad research questions spanning multiple statutes or areas of case law may trigger 5 or more. Each lookup adds latency proportional to the LEX server's response time and the size of documents returned." />
                    </h3>
                    <p className="text-2xl font-bold text-amber-600">{kpi.avgLexCalls}</p>
                    <p className="text-xs text-gray-400 mt-1 flex items-center">
                        Avg lookup time: {fmtMs(kpi.avgLexMs)}
                        <InfoTip text="Average total time spent waiting for all LEX API responses within a single query, accumulated across all lookups. Since the LEX API is an external HTTP service, its latency depends on network conditions, server load at the legal database, and the size of document payloads returned. On an air-gapped network, high values typically point to LEX server load or large result sets rather than internet issues. A query with 5 lookups each taking 500ms will show approximately 2.5s here." />
                    </p>
                </div>
            </div>

            {/* CHARTS ROW */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Response Time Trend */}
                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                    <h2 className="text-sm font-bold mb-4 dark:text-white flex items-center">
                        Response Time Trend ({timeframeLabel})
                        <InfoTip text="Line chart of daily average response times. The solid 'Total' line is the full end-to-end time; 'LLM' (dashed) shows time attributed to AI model calls; 'LEX API' (dashed) shows time attributed to legal database lookups. The gap between Total and the sum of LLM + LEX API represents queue wait and server overhead. Use this to spot dates when performance degraded — if the LLM line spikes, the AI model was under load; if the LEX API line spikes, the legal database was slow that day." />
                    </h2>
                    {dailyWithOther.length > 0 ? (
                        <div className="h-56">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={dailyWithOther} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                    <XAxis dataKey="label" stroke="#9ca3af" tick={{ fontSize: 10 }} />
                                    <YAxis stroke="#9ca3af" tick={{ fontSize: 10 }} tickFormatter={v => fmtMs(v)} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                                        formatter={(v, name) => [fmtMs(v), name]}
                                    />
                                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                                    <Line type="monotone" dataKey="avgTotalMs" name="Total" stroke={PERF_COLORS.total} strokeWidth={2} dot={false} />
                                    <Line type="monotone" dataKey="avgLlmMs" name="LLM" stroke={PERF_COLORS.llm} strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                                    <Line type="monotone" dataKey="avgLexMs" name="LEX API" stroke={PERF_COLORS.lex} strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="h-56 flex items-center justify-center text-gray-400 text-sm">No data for this period.</div>
                    )}
                </div>

                {/* Stacked Time Breakdown */}
                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                    <h2 className="text-sm font-bold mb-4 dark:text-white flex items-center">
                        Where Time Goes Each Day ({timeframeLabel})
                        <InfoTip text="Stacked bar chart showing the composition of the average response time for each day. Each bar's total height is the average end-to-end time; the coloured segments show: LLM (indigo) — time the AI model was actively generating tokens; LEX API (amber) — time waiting for legal database responses; Other (grey) — queue wait, response streaming, database writes, and other server overhead. A day where LLM dominates suggests model load is the bottleneck; a day where LEX API dominates suggests the legal database was slow." />
                    </h2>
                    {dailyWithOther.length > 0 ? (
                        <div className="h-56">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={dailyWithOther} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                    <XAxis dataKey="label" stroke="#9ca3af" tick={{ fontSize: 10 }} />
                                    <YAxis stroke="#9ca3af" tick={{ fontSize: 10 }} tickFormatter={v => fmtMs(v)} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                                        formatter={(v, name) => [fmtMs(v), name]}
                                    />
                                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                                    <Bar dataKey="avgLlmMs" name="LLM" stackId="a" fill={PERF_COLORS.llm} />
                                    <Bar dataKey="avgLexMs" name="LEX API" stackId="a" fill={PERF_COLORS.lex} />
                                    <Bar dataKey="otherMs" name="Other" stackId="a" fill={PERF_COLORS.other} radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="h-56 flex items-center justify-center text-gray-400 text-sm">No data for this period.</div>
                    )}
                </div>
            </div>

            {/* LLM Calls Distribution + Avg breakdown summary */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* LLM calls distribution */}
                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                    <h2 className="text-sm font-bold mb-1 dark:text-white flex items-center">
                        AI Model Calls per Query — Distribution
                        <InfoTip text="Frequency histogram showing how many queries required each number of AI model calls. The x-axis is the call count; the y-axis is the number of queries with that count. A cluster at low numbers (1–3) means most queries were straightforward; a long tail at 5+ means users are asking complex multi-step research questions that required many search-and-interpret cycles. This distribution helps you understand typical agent workload and anticipate scaling needs." />
                    </h2>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">Each call = one round-trip to the AI model. More calls = the agent performed more research tool loops.</p>
                    {llmDistribution.length > 0 ? (
                        <div className="h-48">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={llmDistribution} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                    <XAxis dataKey="llmCalls" stroke="#9ca3af" tick={{ fontSize: 11 }} label={{ value: 'LLM calls', position: 'insideBottom', offset: -2, fontSize: 10, fill: '#9ca3af' }} />
                                    <YAxis stroke="#9ca3af" tick={{ fontSize: 11 }} allowDecimals={false} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                                        formatter={(v) => [v, 'queries']}
                                    />
                                    <Bar dataKey="count" name="Queries" fill={PERF_COLORS.llm} radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No data.</div>
                    )}
                </div>

                {/* Time breakdown summary card */}
                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                    <h2 className="text-sm font-bold mb-4 dark:text-white flex items-center">
                        Average Time Budget per Query
                        <InfoTip text="Progress bars showing how the average query's total response time is divided among phases. The percentage shows each phase's share. Use this to identify the primary bottleneck: if 'AI Model Processing' dominates (80%+), faster hardware or a smaller model would help most; if 'Legal Database Lookups' dominates, the LEX API is the limiting factor; if 'Request Queue Wait' is significant, the server is receiving more concurrent requests than it can handle; if 'Server Overhead' is unexpectedly large, there may be a software inefficiency in the request pipeline." />
                    </h2>
                    {kpi.avgTotalMs > 0 ? (
                        <div className="space-y-4">
                            {[
                                { label: 'AI Model Processing', tooltip: 'Cumulative time waiting for mistral-large (via Ollama) to generate tokens, summed across all calls in the query. Each call sends the full prompt — conversation history, system instructions, and any tool results — and waits for a complete response. Generation time scales with input context length and output length. This is almost always the largest component on GPU-constrained hardware. A sudden increase here typically means the model has fallen back to CPU, or concurrent requests are queuing behind an ongoing generation.', ms: kpi.avgLlmMs, color: PERF_COLORS.llm },
                                { label: 'Legal Database Lookups', tooltip: 'Total time spent making HTTP requests to the LEX API — the UK government\'s database of legislation, statutory instruments, and court judgments — summed across all lookups in the query. Each request involves a network round-trip to the LEX server, query execution, and transmission of document payloads back to AILA. On the air-gapped internal network, high latency here usually points to LEX server load or large result sets rather than connectivity issues.', ms: kpi.avgLexMs, color: PERF_COLORS.lex },
                                { label: 'Request Queue Wait', tooltip: 'Time the query spent waiting in the server\'s internal queue before the agent pipeline began. AILA serialises AI model access to avoid GPU memory contention — if a query is already running, new ones queue behind it. On a single-user deployment this should be near zero. A consistently high queue wait indicates multiple users are querying simultaneously and the server cannot process them fast enough in parallel. Reducing this requires either concurrency optimisation or additional capacity.', ms: kpi.avgQueueMs, color: '#64748b' },
                                { label: 'Server Overhead', tooltip: 'Remaining response time not attributed to AI model calls, LEX API lookups, or queue wait. Covers: parsing the HTTP request and conversation history; serialising tool calls and results between agent steps; writing timing metrics and conversation logs to PostgreSQL; streaming the response to the browser; and other FastAPI/Python execution time. Under normal conditions this should be a small fraction of total time. An unexpectedly large value may indicate a slow database write, a very large payload being serialised, or a bottleneck in the Python request pipeline.', ms: Math.max(0, kpi.avgTotalMs - kpi.avgLlmMs - kpi.avgLexMs - kpi.avgQueueMs), color: PERF_COLORS.other },
                            ].map(({ label, tooltip, ms, color }) => {
                                const pct = kpi.avgTotalMs > 0 ? Math.round((ms / kpi.avgTotalMs) * 100) : 0;
                                return (
                                    <div key={label}>
                                        <div className="flex justify-between text-xs mb-1">
                                            <span className="font-medium dark:text-gray-300 flex items-center" style={{ color }}>{label}<InfoTip text={tooltip} /></span>
                                            <span className="text-gray-500 dark:text-gray-400">{fmtMs(ms)} ({pct}%)</span>
                                        </div>
                                        <div className="w-full bg-gray-100 dark:bg-zinc-700 rounded-full h-2">
                                            <div className="h-2 rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
                                        </div>
                                    </div>
                                );
                            })}
                            <div className="pt-2 border-t dark:border-zinc-700 flex justify-between text-xs font-bold dark:text-white">
                                <span>Total</span>
                                <span>{fmtMs(kpi.avgTotalMs)}</span>
                            </div>
                        </div>
                    ) : (
                        <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No data.</div>
                    )}
                </div>
            </div>

            {/* Slowest Queries Table */}
            <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                <h2 className="text-sm font-bold mb-4 dark:text-white flex items-center">
                    10 Slowest Queries ({timeframeLabel})
                    <InfoTip text="The ten individual queries with the longest total response time in the selected period, sorted slowest first. Use this table to investigate what made specific queries unusually slow — look across the row: a high 'AI Calls' count means the agent performed many research loops; a high 'DB Lookup Time' means the legal database was slow for that query; a high 'Time to First Token' means the model was heavily loaded at that moment. The Request ID can be searched in the server logs for a full trace." />
                </h2>
                {slowest.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="min-w-full text-xs">
                            <thead>
                                <tr>
                                    {[
                                        { label: 'Request ID', tip: 'Unique identifier assigned to this query when it arrived at the server. This ID is written to the uvicorn server logs alongside all timing, prompt, and error information. Search for it in the logs to retrieve a full trace: the exact prompts sent to the AI model, each LEX API request and response, and any errors that occurred.' },
                                        { label: 'Timestamp', tip: 'Date and time (your local timezone) when this query was received by the server. Useful for correlating slow queries with known events — a spike coinciding with a specific time of day may indicate peak concurrent usage, a scheduled background task competing for resources, or a transient issue with the LEX API or AI model at that moment.' },
                                        { label: 'Total Duration', tip: 'Total wall-clock time from when the server received the HTTP request to when the final response token was streamed to the user\'s browser. This is the number the user experienced as wait time. The table is sorted by this column, descending. Reviewing the AI Calls and DB Lookup Time columns for the same row usually reveals the cause of slowness.' },
                                        { label: 'AI Calls', tip: 'Number of separate round-trips made to the AI model (mistral-large via Ollama) during this query. Each call is one step in the agent reasoning loop: initial planning, each search decision, each interpretation of a LEX API result, and final answer synthesis. High values (6+) mean the query was complex and required many iterative research steps — often multi-Act statutory interpretation or broad case law searches.' },
                                        { label: 'AI Processing Time', tip: 'Total time attributed to AI model generation across all calls for this query, summed together. If this is a large share of Total Duration, the AI model was the bottleneck — either because the model was heavily loaded, the input prompts were very long (e.g. a lengthy conversation history or many tool results in context), or the model generated an unusually long response.' },
                                        { label: 'DB Lookups', tip: 'Number of HTTP requests made to the LEX API (UK legislation and case law database) during this query. Each represents the agent searching for a specific statute, statutory instrument, or court judgment. High counts suggest the query involved broad or iterative legal research — for example, tracing amendments across multiple Acts, or searching for precedents across several areas of law.' },
                                        { label: 'DB Lookup Time', tip: 'Total time spent waiting for LEX API HTTP responses during this query, summed across all lookups. If this is a large share of Total Duration, the legal database was the bottleneck for this specific query. On the air-gapped internal network, individual lookups typically take under 1 second — values significantly above that warrant checking LEX server health or network conditions at the time shown in the Timestamp column.' },
                                        { label: 'Time to First Token', tip: 'Time from when this query\'s prompt was sent to the AI model until the model produced its very first output token. Before any output appears the model must load the full context window (conversation history, system prompt, tool results) and begin generation. A high value relative to the average TTFT shown in the KPI cards above typically means this query had an unusually large input context, or the model was concurrently serving another request and this one waited.' },
                                    ].map(({ label, tip }) => (
                                        <th key={label} className="px-3 py-2 border-b-2 border-zinc-200 dark:border-zinc-700 text-left font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider whitespace-nowrap">
                                            <span className="flex items-center gap-0.5">{label}<InfoTip text={tip} /></span>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {slowest.map((row) => (
                                    <tr key={row.requestId} className="border-b border-zinc-100 dark:border-zinc-700">
                                        <td className="px-3 py-3 font-mono dark:text-gray-300">{row.requestId}</td>
                                        <td className="px-3 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">{new Date(row.createdAt).toLocaleString()}</td>
                                        <td className="px-3 py-3 font-bold text-red-600 dark:text-red-400 whitespace-nowrap">{fmtMs(row.totalMs)}</td>
                                        <td className="px-3 py-3 dark:text-gray-300">{row.llmCalls}</td>
                                        <td className="px-3 py-3 text-indigo-600 dark:text-indigo-400 whitespace-nowrap">{fmtMs(row.llmMs)}</td>
                                        <td className="px-3 py-3 dark:text-gray-300">{row.lexCalls}</td>
                                        <td className="px-3 py-3 text-amber-600 dark:text-amber-400 whitespace-nowrap">{fmtMs(row.lexMs)}</td>
                                        <td className="px-3 py-3 text-emerald-600 dark:text-emerald-400 whitespace-nowrap">{fmtMs(row.ttftMs)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="text-gray-400 text-sm">No slow queries recorded yet.</p>
                )}
            </div>
        </div>
    );
};


// -----------------------------------------------------------------------
// Cost Tab Component
// -----------------------------------------------------------------------

const fmtUsd = (v) => {
    if (!v || v <= 0) return '$0.00';
    if (v < 0.01) return '<$0.01';
    return `$${v.toFixed(2)}`;
};

const COST_COLORS = {
    spend: '#10b981',   // emerald
    user: '#6366f1',    // indigo
};

const CostTab = ({ costStats, costTimeframe, setCostTimeframe }) => {
    const { kpi, daily, perUser, priciest } = costStats;
    const timeframeLabel = costTimeframe === 'all' ? 'All Time' : `Last ${costTimeframe} Days`;
    const hasData = kpi.paidRequests > 0;

    return (
        <div className="space-y-6">
            {/* HEADER WITH FILTER */}
            <div className="flex justify-between items-center bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                <h2 className="text-lg font-bold dark:text-white">OpenRouter Spend</h2>
                <div className="flex items-center space-x-2">
                    <label className="text-sm text-gray-500 dark:text-gray-400 font-medium">Timeframe:</label>
                    <select
                        value={costTimeframe}
                        onChange={(e) => setCostTimeframe(e.target.value)}
                        className="p-2 border rounded-md text-sm dark:bg-zinc-700 dark:border-zinc-600 dark:text-white focus:ring-2 focus:ring-blue-500"
                    >
                        <option value="1">Last 1 Day</option>
                        <option value="3">Last 3 Days</option>
                        <option value="7">Last 7 Days</option>
                        <option value="30">Last 30 Days</option>
                        <option value="90">Last 90 Days</option>
                        <option value="all">All Time</option>
                    </select>
                </div>
            </div>

            {!hasData && (
                <div className="bg-white dark:bg-zinc-800 p-8 rounded-lg shadow text-center text-gray-400 dark:text-gray-500 text-sm">
                    No cost data for this period. Cost tracking is only recorded for OpenRouter queries.
                </div>
            )}

            {hasData && (
                <>
                    {/* KPI CARDS */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                            <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Total Spend</h3>
                            <p className="text-2xl font-bold text-emerald-600">{fmtUsd(kpi.totalCost)}</p>
                            <p className="text-xs text-gray-400 mt-1">{timeframeLabel}</p>
                        </div>
                        <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                            <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Avg Cost / Query</h3>
                            <p className="text-2xl font-bold text-emerald-600">{fmtUsd(kpi.avgCost)}</p>
                            <p className="text-xs text-gray-400 mt-1">{kpi.paidRequests} paid queries</p>
                        </div>
                        <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                            <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Most Expensive Query</h3>
                            <p className="text-2xl font-bold text-amber-600">{fmtUsd(kpi.maxCost)}</p>
                            <p className="text-xs text-gray-400 mt-1">single request peak</p>
                        </div>
                        <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                            <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">OpenRouter Queries</h3>
                            <p className="text-2xl font-bold dark:text-white">{kpi.paidRequests}</p>
                            <p className="text-xs text-gray-400 mt-1">{timeframeLabel}</p>
                        </div>
                    </div>

                    {/* CHARTS ROW */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Daily Spend */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-sm font-bold mb-4 dark:text-white">Daily Spend ({timeframeLabel})</h2>
                            {daily.length > 0 ? (
                                <div className="h-56">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={daily} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                            <XAxis dataKey="label" stroke="#9ca3af" tick={{ fontSize: 10 }} />
                                            <YAxis stroke="#9ca3af" tick={{ fontSize: 10 }} tickFormatter={v => `$${v.toFixed(2)}`} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                                                formatter={(v) => [fmtUsd(v), 'Spend']}
                                            />
                                            <Line type="monotone" dataKey="dailyCost" name="Daily Spend" stroke={COST_COLORS.spend} strokeWidth={2} dot={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <div className="h-56 flex items-center justify-center text-gray-400 text-sm">No data for this period.</div>
                            )}
                        </div>

                        {/* Cost by User */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-sm font-bold mb-4 dark:text-white">Top Users by Spend ({timeframeLabel})</h2>
                            {perUser.length > 0 ? (
                                <div className="h-56">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart
                                            data={perUser}
                                            layout="vertical"
                                            margin={{ top: 4, right: 40, left: 0, bottom: 0 }}
                                        >
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
                                            <XAxis type="number" stroke="#9ca3af" tick={{ fontSize: 10 }} tickFormatter={v => `$${v.toFixed(2)}`} />
                                            <YAxis type="category" dataKey="username" stroke="#9ca3af" tick={{ fontSize: 10 }} width={72} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '11px' }}
                                                formatter={(v, _name, props) => [
                                                    `${fmtUsd(v)} (${props.payload.queryCount} queries)`,
                                                    'Spend',
                                                ]}
                                            />
                                            <Bar dataKey="totalCost" name="Total Spend" fill={COST_COLORS.user} radius={[0, 4, 4, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                <div className="h-56 flex items-center justify-center text-gray-400 text-sm">No data for this period.</div>
                            )}
                        </div>
                    </div>

                    {/* PRICIEST QUERIES TABLE */}
                    <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                        <h2 className="text-sm font-bold mb-4 dark:text-white">10 Most Expensive Queries ({timeframeLabel})</h2>
                        <div className="overflow-x-auto">
                            <table className="min-w-full text-xs">
                                <thead>
                                    <tr>
                                        {['Request ID', 'Timestamp', 'Cost', 'AI Calls', 'Total Duration'].map(label => (
                                            <th key={label} className="px-3 py-2 border-b-2 border-zinc-200 dark:border-zinc-700 text-left font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider whitespace-nowrap">
                                                {label}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {priciest.map((row) => (
                                        <tr key={row.requestId} className="border-b border-zinc-100 dark:border-zinc-700">
                                            <td className="px-3 py-3 font-mono dark:text-gray-300">{row.requestId}</td>
                                            <td className="px-3 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">{new Date(row.createdAt).toLocaleString()}</td>
                                            <td className="px-3 py-3 font-bold text-emerald-600 dark:text-emerald-400 whitespace-nowrap">{fmtUsd(row.costUsd)}</td>
                                            <td className="px-3 py-3 dark:text-gray-300">{row.llmCalls}</td>
                                            <td className="px-3 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">{fmtMs(row.totalMs)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};


// -----------------------------------------------------------------------
// Provider Configuration Panel (Developer Tab)
// -----------------------------------------------------------------------

const PROVIDER_DISPLAY = {
    ollama: 'Ollama (Local)',
    openrouter: 'OpenRouter',
};

const Field = ({ label, children, hint }) => (
    <div>
        <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-1">{label}</label>
        {children}
        {hint && <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{hint}</p>}
    </div>
);

// Type-ahead combobox for selecting a model from a large list.
const ModelCombobox = ({ value, onChange, models, loading, error }) => {
    const [query, setQuery] = React.useState('');
    const [open, setOpen] = React.useState(false);
    const containerRef = React.useRef(null);

    const filtered = React.useMemo(() => {
        if (!query) return models;
        const q = query.toLowerCase();
        return models.filter(m => m.name.toLowerCase().includes(q));
    }, [models, query]);

    const handleSelect = (name) => {
        onChange(name);
        setQuery('');
        setOpen(false);
    };

    const handleBlur = (e) => {
        // Close only when focus leaves the whole container
        if (!containerRef.current?.contains(e.relatedTarget)) {
            setOpen(false);
            setQuery('');
        }
    };

    return (
        <div ref={containerRef} className="relative" onBlur={handleBlur}>
            <input
                type="text"
                value={open ? query : (value || '')}
                onChange={e => { setQuery(e.target.value); setOpen(true); }}
                onFocus={() => setOpen(true)}
                placeholder={loading ? 'Loading models…' : open ? 'Search models…' : (value || 'Select a model')}
                disabled={loading}
                className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            {loading && (
                <div className="absolute right-2.5 top-1/2 -translate-y-1/2"><Spinner size="sm" /></div>
            )}
            {open && !loading && (
                <ul
                    tabIndex={-1}
                    className="absolute z-20 mt-1 w-full max-h-64 overflow-auto bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-600 rounded-md shadow-lg text-sm"
                >
                    {error && (
                        <li className="px-3 py-2 text-red-500 dark:text-red-400">{error}</li>
                    )}
                    {!error && filtered.length === 0 && (
                        <li className="px-3 py-2 text-gray-400 dark:text-gray-500">No models match</li>
                    )}
                    {!error && filtered.map(m => (
                        <li
                            key={m.name || '__blank__'}
                            tabIndex={-1}
                            onMouseDown={() => handleSelect(m.name)}
                            className={`flex items-center justify-between px-3 py-1.5 cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/30 ${m.name === value ? 'bg-blue-50 dark:bg-blue-900/20 font-medium' : ''}`}
                        >
                            <span className={`truncate ${m.name ? 'text-gray-900 dark:text-white' : 'text-gray-400 dark:text-gray-500 italic'}`}>
                                {m.name || '— Same as Active Model —'}
                            </span>
                            {m.context_kb != null && (
                                <span className="ml-3 flex-shrink-0 text-xs text-gray-400 dark:text-gray-500">{m.context_kb}K ctx</span>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

const PROVIDER_DEFAULTS = {
    openrouter: {
        model: 'google/gemini-3.1-pro-preview',
        summarisation_model: 'google/gemini-3-flash-preview',
    },
    ollama: {
        model: 'mistral-large-3:675b-cloud',
        summarisation_model: '',
    },
};

const ProviderConfigPanel = () => {
    const [data, setData] = React.useState(null);           // full GET response
    const [selectedId, setSelectedId] = React.useState(null); // which provider card is selected for editing
    const [drafts, setDrafts] = React.useState({});          // {providerId: {config fields}}
    const [showKeys, setShowKeys] = React.useState({});      // {providerId: bool}
    const [savingConfig, setSavingConfig] = React.useState(false);
    const [switchingActive, setSwitchingActive] = React.useState(false);
    const [statusMsg, setStatusMsg] = React.useState(null);
    const [orModels, setOrModels] = React.useState([]);
    const [orModelsLoading, setOrModelsLoading] = React.useState(false);
    const [orModelsError, setOrModelsError] = React.useState(null);

    const flash = (type, text) => {
        setStatusMsg({ type, text });
        setTimeout(() => setStatusMsg(null), 4000);
    };

    React.useEffect(() => {
        getProviderConfig().then((res) => {
            setData(res);
            setSelectedId(res.active_provider);
            // Seed drafts from current config
            const d = {};
            res.providers.forEach(p => { d[p.id] = { ...p.config }; });
            setDrafts(d);
        }).catch(() => flash('error', 'Failed to load provider config.'));
    }, []);

    React.useEffect(() => {
        if (selectedId !== 'openrouter') return;
        if (orModels.length > 0) return; // already loaded
        setOrModelsLoading(true);
        setOrModelsError(null);
        getOpenRouterModels()
            .then(res => setOrModels(res.models))
            .catch(err => {
                const detail = err?.response?.data?.detail || 'Failed to load OpenRouter models.';
                setOrModelsError(detail);
            })
            .finally(() => setOrModelsLoading(false));
    }, [selectedId]);

    const updateDraft = (providerId, key, value) => {
        setDrafts(prev => ({
            ...prev,
            [providerId]: { ...prev[providerId], [key]: value },
        }));
    };

    const handleSaveConfig = async () => {
        if (!selectedId) return;
        setSavingConfig(true);
        try {
            await saveProviderConfig(selectedId, drafts[selectedId]);
            setData(prev => ({
                ...prev,
                providers: prev.providers.map(p =>
                    p.id === selectedId ? { ...p, config: { ...drafts[selectedId] } } : p
                ),
            }));
            flash('success', `${PROVIDER_DISPLAY[selectedId]} settings saved.`);
        } catch {
            flash('error', 'Failed to save settings.');
        } finally {
            setSavingConfig(false);
        }
    };

    const handleSetToDefault = () => {
        if (!selectedId) return;
        const defaults = PROVIDER_DEFAULTS[selectedId];
        if (!defaults) return;
        setDrafts(prev => {
            const current = prev[selectedId] || {};
            return {
                ...prev,
                [selectedId]: { ...current, ...defaults, api_key: current.api_key },
            };
        });
    };

    const handleSetActive = async () => {
        if (!selectedId || selectedId === data?.active_provider) return;
        setSwitchingActive(true);
        try {
            await setActiveProvider(selectedId);
            setData(prev => ({ ...prev, active_provider: selectedId }));
            flash('success', `Switched to ${PROVIDER_DISPLAY[selectedId]}. Takes effect for all new requests.`);
        } catch {
            flash('error', 'Failed to switch provider.');
        } finally {
            setSwitchingActive(false);
        }
    };

    if (!data) {
        return (
            <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow flex items-center gap-3">
                <Spinner size="sm" />
                <span className="text-sm text-gray-500 dark:text-gray-400">Loading provider config…</span>
            </div>
        );
    }

    const activeInfo = data.providers.find(p => p.id === data.active_provider);
    const selectedProvider = data.providers.find(p => p.id === selectedId);
    const draft = drafts[selectedId] || {};
    const isActive = selectedId === data.active_provider;
    const hasApiKey = !!(draft.api_key);

    return (
        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold dark:text-white">LLM Provider</h2>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300">
                    <span className="w-2 h-2 rounded-full bg-green-500 inline-block"></span>
                    Active: {activeInfo?.name ?? data.active_provider}
                </span>
            </div>

            {/* Provider picker */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {data.providers.map((provider) => {
                    const isSel = selectedId === provider.id;
                    const isAct = data.active_provider === provider.id;
                    return (
                        <button
                            key={provider.id}
                            onClick={() => setSelectedId(provider.id)}
                            className={`text-left p-4 rounded-lg border-2 transition-colors ${isSel
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                                : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'}`}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <span className="font-semibold text-sm dark:text-white">{provider.name}</span>
                                <div className="flex items-center gap-1.5">
                                    {isAct && (
                                        <span className="text-xs px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 font-medium">Active</span>
                                    )}
                                    {isSel && (
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-blue-500 flex-shrink-0">
                                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                                        </svg>
                                    )}
                                </div>
                            </div>
                            <p className="text-xs text-gray-400 dark:text-gray-500">
                                {provider.id === 'openrouter'
                                    ? 'Dynamic models'
                                    : `${provider.model_list.length} model${provider.model_list.length !== 1 ? 's' : ''}`
                                } · {drafts[provider.id]?.model || provider.config.model}
                            </p>
                        </button>
                    );
                })}
            </div>

            {/* Config fields for selected provider */}
            {selectedProvider && (
                <div className="space-y-4 pt-2 border-t border-gray-100 dark:border-zinc-700">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                        Configure: {selectedProvider.name}
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {/* Base URL */}
                        <Field label="Base URL" hint="Endpoint for this provider's API">
                            <input
                                type="text"
                                value={draft.base_url || ''}
                                onChange={e => updateDraft(selectedId, 'base_url', e.target.value)}
                                className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </Field>

                        {/* API Key */}
                        <Field label="API Key" hint="Stored in database. Leave blank to use .env value.">
                            <div className="flex gap-1.5">
                                <input
                                    type={showKeys[selectedId] ? 'text' : 'password'}
                                    value={draft.api_key || ''}
                                    onChange={e => updateDraft(selectedId, 'api_key', e.target.value)}
                                    placeholder={hasApiKey ? '••••••••' : 'Not set'}
                                    className="flex-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowKeys(prev => ({ ...prev, [selectedId]: !prev[selectedId] }))}
                                    className="px-2 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                                >
                                    {showKeys[selectedId] ? 'Hide' : 'Show'}
                                </button>
                            </div>
                        </Field>

                        {/* Active Model */}
                        <Field label="Active Model" hint="Model used for Manager and Worker agents">
                            {selectedId === 'openrouter' ? (
                                <ModelCombobox
                                    value={draft.model || ''}
                                    onChange={v => updateDraft(selectedId, 'model', v)}
                                    models={orModels}
                                    loading={orModelsLoading}
                                    error={orModelsError}
                                />
                            ) : (
                                <select
                                    value={draft.model || ''}
                                    onChange={e => updateDraft(selectedId, 'model', e.target.value)}
                                    className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                    {selectedProvider.model_list.map(m => (
                                        <option key={m.name} value={m.name}>{m.name} ({m.context_kb}K ctx)</option>
                                    ))}
                                </select>
                            )}
                        </Field>

                        {/* Summarisation Model */}
                        <Field label="Summarisation Model" hint="Faster/cheaper model for document summarisation. Leave blank to use the Active Model.">
                            {selectedId === 'openrouter' ? (
                                <ModelCombobox
                                    value={draft.summarisation_model || ''}
                                    onChange={v => updateDraft(selectedId, 'summarisation_model', v)}
                                    models={[{ name: '', context_kb: null }, ...orModels]}
                                    loading={orModelsLoading}
                                    error={orModelsError}
                                />
                            ) : (
                                <select
                                    value={draft.summarisation_model || ''}
                                    onChange={e => updateDraft(selectedId, 'summarisation_model', e.target.value)}
                                    className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                    <option value="">— Same as Active Model —</option>
                                    {selectedProvider.model_list.map(m => (
                                        <option key={m.name} value={m.name}>{m.name} ({m.context_kb}K ctx)</option>
                                    ))}
                                </select>
                            )}
                        </Field>

                        {/* Temperature */}
                        <Field label="Temperature" hint="0 = deterministic · 1 = creative (default 0.1)">
                            <input
                                type="number"
                                min="0" max="2" step="0.05"
                                value={draft.temperature ?? 0.1}
                                onChange={e => updateDraft(selectedId, 'temperature', parseFloat(e.target.value))}
                                className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </Field>

                        {/* Max Concurrent Requests */}
                        <Field label="Max Concurrent Requests" hint="Queue depth — simultaneous users served">
                            <input
                                type="number"
                                min="1" max="50" step="1"
                                value={draft.max_concurrent_requests ?? 3}
                                onChange={e => updateDraft(selectedId, 'max_concurrent_requests', parseInt(e.target.value))}
                                className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </Field>

                        {/* Max Concurrent Summarisations */}
                        <Field label="Max Concurrent Summarisations" hint="Parallel large-document jobs (keep low for local)">
                            <input
                                type="number"
                                min="1" max="20" step="1"
                                value={draft.max_summarise_concurrency ?? 1}
                                onChange={e => updateDraft(selectedId, 'max_summarise_concurrency', parseInt(e.target.value))}
                                className="w-full text-sm border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </Field>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-3 pt-1">
                        <button
                            onClick={handleSaveConfig}
                            disabled={savingConfig}
                            className="px-5 py-2 bg-brand-navy text-white rounded-md hover:bg-brand-navy-dark transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {savingConfig && <Spinner size="sm" />}
                            {savingConfig ? 'Saving…' : 'Save Settings'}
                        </button>

                        {PROVIDER_DEFAULTS[selectedId] && (
                            <button
                                onClick={handleSetToDefault}
                                className="px-5 py-2 bg-gray-100 dark:bg-zinc-700 text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-200 dark:hover:bg-zinc-600 transition-colors text-sm font-medium"
                            >
                                Set to default
                            </button>
                        )}

                        {!isActive && (
                            <button
                                onClick={handleSetActive}
                                disabled={switchingActive}
                                className="px-5 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                                {switchingActive && <Spinner size="sm" />}
                                {switchingActive ? 'Switching…' : `Set as Active`}
                            </button>
                        )}

                        {statusMsg && (
                            <span className={`text-sm font-medium ${statusMsg.type === 'success' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                {statusMsg.text}
                            </span>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};


function buildSurveyComplianceChartData(surveyCompliance) {
    if (!surveyCompliance) return [];
    const totalUsers = surveyCompliance.users.length;
    return [...surveyCompliance.weeks].reverse().map((w, ri) => {
        const i = surveyCompliance.weeks.length - 1 - ri;
        const activeCount = surveyCompliance.users.filter(u => u.weeks[i].query_count > 0).length;
        const surveyedCount = surveyCompliance.users.filter(u => u.weeks[i].survey_submitted).length;
        return { week: w.label, totalUsers, activeUsers: activeCount, surveyed: surveyedCount };
    });
}

const WeeklySurveyComplianceChart = ({ surveyCompliance }) => {
    const raw = buildSurveyComplianceChartData(surveyCompliance);
    if (raw.length === 0) return null;
    const totalUsers = raw[0]?.totalUsers || 1;
    const data = raw.map(w => ({
        week: w.week,
        totalUsers: w.totalUsers,
        surveyed: w.surveyed,
        activeOnly: Math.max(0, w.activeUsers - w.surveyed),
        inactive: Math.max(0, w.totalUsers - w.activeUsers),
    }));
    return (
        <div className="mb-6">
            <h3 className="text-sm font-bold mb-3 dark:text-white">Weekly Survey Submissions</h3>
            <ResponsiveContainer width="100%" height={180}>
                <BarChart data={data} barCategoryGap="30%">
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={28} domain={[0, totalUsers]} />
                    <Tooltip
                        contentStyle={{ fontSize: 11 }}
                        formatter={(value, name, props) => {
                            const tot = props.payload.totalUsers;
                            const pct = tot > 0 ? Math.round((value / tot) * 100) : 0;
                            return [`${value} (${pct}%)`, name];
                        }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="surveyed" name="Completed Survey" stackId="a" fill="#22c55e" />
                    <Bar dataKey="activeOnly" name="Declined response" stackId="a" fill="#3b82f6" />
                    <Bar dataKey="inactive" name="Inactive" stackId="a" fill="#94a3b8" radius={[3, 3, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

function buildDailyRatingsData(items, timeframe) {
    const numDays = (!timeframe || timeframe === 'all') ? 60 : Math.min(parseInt(timeframe, 10), 60);
    const dayKeys = [];
    const now = new Date();
    for (let i = numDays - 1; i >= 0; i--) {
        const d = new Date(now);
        d.setUTCDate(d.getUTCDate() - i);
        dayKeys.push(d.toISOString().slice(0, 10));
    }
    const counts = {};
    dayKeys.forEach(d => { counts[d] = { up: 0, down: 0 }; });
    items.forEach(item => {
        const k = item.created_at.slice(0, 10);
        if (counts[k]) {
            if (item.rating === 5) counts[k].up++;
            else if (item.rating === 1) counts[k].down++;
        }
    });
    return dayKeys.map(d => ({
        day: new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }),
        ...counts[d],
    }));
}

const AdminPortal = ({ currentUser }) => {
    const [activeTab, setActiveTab] = useState('users');
    const [isLoading, setIsLoading] = useState(false);
    const [isStatsLoading, setIsStatsLoading] = useState(false);
    const [isTestLoading, setIsTestLoading] = useState(false);

    // --- USER MANAGEMENT STATE ---
    const [users, setUsers] = useState([]);
    const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user', email: '' });
    const [editingUser, setEditingUser] = useState(null);
    const [message, setMessage] = useState('');

    // --- LEARNING DASHBOARD STATE ---
    const [feedback, setFeedback] = useState([]);
    const [stats, setStats] = useState([]);
    const [learningTimeframe, setLearningTimeframe] = useState('30');
    const [testQuery, setTestQuery] = useState('');
    const [testResults, setTestResults] = useState(null);

    // --- USAGE STATS STATE ---
    const [usageStats, setUsageStats] = useState(null);
    const [timeframe, setTimeframe] = useState('30');

    // --- PERFORMANCE STATS STATE ---
    const [perfStats, setPerfStats] = useState(null);
    const [perfTimeframe, setPerfTimeframe] = useState('30');
    const [isPerfLoading, setIsPerfLoading] = useState(false);

    // --- COST STATS STATE ---
    const [costStats, setCostStats] = useState(null);
    const [costTimeframe, setCostTimeframe] = useState('30');
    const [isCostLoading, setIsCostLoading] = useState(false);

    // --- SERVICE HEALTH STATE ---
    const [healthStatus, setHealthStatus] = useState(null);
    const [isTriggeringHealth, setIsTriggeringHealth] = useState(false);

    // --- PRODUCT FEEDBACK STATE ---
    const [productFeedback, setProductFeedback] = useState([]);
    const [isProductFeedbackLoading, setIsProductFeedbackLoading] = useState(false);
    const [surveyCompliance, setSurveyCompliance] = useState(null);
    const [messageRatings, setMessageRatings] = useState([]);
    const [isMessageRatingsLoading, setIsMessageRatingsLoading] = useState(false);
    const [ratingsFilter, setRatingsFilter] = useState('all');
    const [expandedRatingRow, setExpandedRatingRow] = useState(null);
    const [ratingViewItem, setRatingViewItem] = useState(null);
    const [productFeedbackTimeframe, setProductFeedbackTimeframe] = useState('30');

    // --- FEATURE FLAGS STATE ---
    const [features, setFeatures] = useState({ matters_enabled: true });
    const [isSavingFeatures, setIsSavingFeatures] = useState(false);

    // --- INITIAL FETCH ---
    useEffect(() => {
        if (activeTab === 'users') {
            fetchUsers();
        } else if (activeTab === 'learning') {
            fetchFeedback();
            fetchStats(learningTimeframe);
        } else if (activeTab === 'usage') {
            fetchUsageStats(timeframe);
        } else if (activeTab === 'performance') {
            fetchPerfStats(perfTimeframe);
        } else if (activeTab === 'cost') {
            fetchCostStats(costTimeframe);
        } else if (activeTab === 'health') {
            fetchHealthStatus();
        } else if (activeTab === 'product-feedback') {
            fetchProductFeedback(productFeedbackTimeframe);
        } else if (activeTab === 'developer') {
            getFeatures().then(setFeatures).catch(() => {});
        }
    }, [activeTab, timeframe, learningTimeframe, perfTimeframe, costTimeframe, productFeedbackTimeframe]);

    const fetchProductFeedback = async (days = '30') => {
        setIsProductFeedbackLoading(true);
        setIsMessageRatingsLoading(true);
        const [surveyResult, complianceResult, ratingsResult] = await Promise.allSettled([
            getProductFeedback(days), getSurveyCompliance(), getMessageRatings(days),
        ]);
        if (surveyResult.status === 'fulfilled') setProductFeedback(surveyResult.value);
        else console.error('Failed to fetch product feedback:', surveyResult.reason);
        if (complianceResult.status === 'fulfilled') setSurveyCompliance(complianceResult.value);
        else console.error('Failed to fetch survey compliance:', complianceResult.reason);
        if (ratingsResult.status === 'fulfilled') setMessageRatings(ratingsResult.value);
        else console.error('Failed to fetch message ratings:', ratingsResult.reason);
        setIsProductFeedbackLoading(false);
        setIsMessageRatingsLoading(false);
    };

    // ==========================================
    // USER MANAGEMENT LOGIC
    // ==========================================
    const fetchUsers = async () => {
        setIsLoading(true);
        try {
            const { data } = await axios.get('/api/users');
            setUsers(data);
        } catch (error) {
            console.error('Failed to fetch users', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCreateOrUpdateUser = async (e) => {
        e.preventDefault();
        try {
            if (editingUser) {
                await axios.put(`/api/users/${editingUser.id}`, newUser);
                setMessage('User updated successfully');
                setEditingUser(null);
            } else {
                await axios.post('/api/users', newUser);
                setMessage('User created successfully');
            }
            setNewUser({ username: '', password: '', role: 'user', email: '' });
            fetchUsers();
        } catch (error) {
            setMessage(error.response?.data?.message || (editingUser ? 'Error updating user' : 'Error creating user'));
        }
    };

    const startEditing = (user) => {
        setEditingUser(user);
        setNewUser({ username: user.username, password: '', role: user.role, email: user.email || '' });
        setMessage('');
    };

    const cancelEditing = () => {
        setEditingUser(null);
        setNewUser({ username: '', password: '', role: 'user', email: '' });
        setMessage('');
    };

    const handleDeleteUser = async (id) => {
        if (!window.confirm('Are you sure you want to delete this user?')) return;
        try {
            await axios.delete(`/api/users/${id}`);
            fetchUsers();
        } catch (error) {
            alert(error.response?.data?.message || 'Error deleting user');
        }
    };

    // ==========================================
    // LEARNING DASHBOARD LOGIC
    // ==========================================
    const fetchFeedback = async () => {
        setIsLoading(true);
        try {
            const data = await getFeedbackStats();
            setFeedback(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchStats = async (days) => {
        setIsStatsLoading(true);
        try {
            const rawData = await getPerformanceStats(days);

            // Transform Data for Recharts: Group by Date
            // Expected: [{ date: '...', 'llama3': 4.5, 'gpt4': 4.8 }, ...]
            const processedMap = {};
            const modelSet = new Set();

            rawData.forEach(item => {
                const dateStr = new Date(item.date).toLocaleDateString();
                if (!processedMap[dateStr]) {
                    processedMap[dateStr] = { date: dateStr, rawDate: item.date }; // Keep rawDate for sorting if needed
                }
                const rating = parseFloat(item.avg_rating).toFixed(1);
                const modelName = item.model || 'Unknown';
                processedMap[dateStr][modelName] = rating;
                modelSet.add(modelName);
            });

            // Convert to array
            const chartData = Object.values(processedMap);
            // Sort by date just in case
            chartData.sort((a, b) => new Date(a.rawDate) - new Date(b.rawDate));

            setStats({ data: chartData, models: Array.from(modelSet) });
        } catch (err) {
            console.error(err);
        } finally {
            setIsStatsLoading(false);
        }
    };

    const handleTestRetrieval = async (e) => {
        e.preventDefault();
        if (!testQuery.trim()) return;
        setIsTestLoading(true);
        try {
            const results = await testLearningRetrieval(testQuery);
            setTestResults(results);
        } catch (err) {
            console.error(err);
            alert('Failed to test retrieval');
        } finally {
            setIsTestLoading(false);
        }
    };

    const fetchUsageStats = async (days) => {
        setIsLoading(true);
        try {
            const data = await getUsageStats(days);
            setUsageStats(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchPerfStats = async (days) => {
        setIsPerfLoading(true);
        try {
            const data = await getQueryPerformanceStats(days);
            setPerfStats(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsPerfLoading(false);
        }
    };

    const fetchCostStats = async (days) => {
        setIsCostLoading(true);
        try {
            const data = await getCostStats(days);
            setCostStats(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsCostLoading(false);
        }
    };

    // ==========================================
    // SERVICE HEALTH LOGIC
    // ==========================================
    const fetchHealthStatus = async () => {
        // Only set loading on initial fetch so background polling is seamless
        if (!healthStatus) setIsLoading(true);
        try {
            const data = await getLatestHealthStatus();
            setHealthStatus(data);
        } catch (err) {
            console.error('Failed to fetch health status', err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleTriggerHealthCheck = async () => {
        setIsTriggeringHealth(true);
        try {
            const data = await triggerHealthCheck();
            setHealthStatus(data);
            setMessage('Health check triggered and updated successfully');
            setTimeout(() => setMessage(''), 3000);
        } catch (err) {
            console.error('Failed to trigger health check', err);
            setMessage(err.message || 'Error triggering health check');
        } finally {
            setIsTriggeringHealth(false);
        }
    };

    // Poll health status
    useEffect(() => {
        let intervalId;
        if (activeTab === 'health') {
            intervalId = setInterval(() => {
                fetchHealthStatus();
            }, 60000); // 60s
        }
        return () => {
            if (intervalId) clearInterval(intervalId);
        };
    }, [activeTab]);


    return (
        <div className="p-6 h-full flex flex-col">
            <div className="mb-6">
                <h1 className="text-lg font-bold dark:text-white mb-3">Admin Portal</h1>

                {/* TABS */}
                <div className="flex space-x-1 bg-gray-200 dark:bg-gray-700 p-1 rounded-lg w-full">
                    <button
                        onClick={() => setActiveTab('users')}
                        className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'users'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        User Management
                    </button>
                    <button
                        onClick={() => setActiveTab('usage')}
                        className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'usage'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Usage Stats
                    </button>
                    <button
                        onClick={() => setActiveTab('performance')}
                        className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'performance'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Performance
                    </button>
                    <button
                        onClick={() => setActiveTab('cost')}
                        className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'cost'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Cost
                    </button>
                    <button
                        onClick={() => setActiveTab('learning')}
                        className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'learning'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Learning Monitor
                    </button>
                    {currentUser?.username === 'admin' && (
                    <button
                        onClick={() => setActiveTab('developer')}
                        className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'developer'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Developer
                    </button>
                    )}
                    <button
                        onClick={() => setActiveTab('health')}
                        className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'health'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        Service Health
                    </button>
                    <button
                        onClick={() => setActiveTab('product-feedback')}
                        className={`flex-1 px-4 py-2 rounded-md text-xs font-medium transition-colors ${activeTab === 'product-feedback'
                            ? 'bg-white dark:bg-gray-600 shadow text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                    >
                        User Feedback
                    </button>
                </div>
            </div>

            {message && (
                <div className="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded mb-4">
                    {message}
                </div>
            )}

            {/* CONTENT AREA */}
            <div className="flex-1 overflow-y-auto">

                {/* USER MANAGEMENT TAB */}
                {activeTab === 'users' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* LEFT COLUMN: FORM */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow h-fit">
                            <h2 className="text-lg font-bold mb-4 dark:text-white">{editingUser ? 'Edit User' : 'Add New User'}</h2>
                            <form onSubmit={handleCreateOrUpdateUser} className="grid grid-cols-1 gap-4">
                                <input
                                    type="text"
                                    placeholder="Username"
                                    value={newUser.username}
                                    onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                                    className="p-2 border rounded dark:bg-zinc-700 dark:text-white text-sm"
                                    required
                                />
                                <input
                                    type="password"
                                    placeholder={editingUser ? "Leave blank to keep current password" : "Password"}
                                    value={newUser.password}
                                    onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                                    className="p-2 border rounded dark:bg-zinc-700 dark:text-white text-sm"
                                    required={!editingUser}
                                />
                                <input
                                    type="email"
                                    placeholder="Email"
                                    value={newUser.email}
                                    onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                                    className="p-2 border rounded dark:bg-zinc-700 dark:text-white text-sm"
                                />
                                <select
                                    value={newUser.role}
                                    onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                                    className="p-2 border rounded dark:bg-zinc-700 dark:text-white text-sm"
                                >
                                    <option value="user">User</option>
                                    <option value="admin">Admin</option>
                                </select>
                                <button
                                    type="submit"
                                    className="bg-brand-navy hover:bg-brand-navy-dark text-white font-bold py-2 px-4 rounded text-sm w-full"
                                >
                                    {editingUser ? 'Update User' : 'Create User'}
                                </button>
                                {editingUser && (
                                    <button
                                        type="button"
                                        onClick={cancelEditing}
                                        className="bg-gray-500 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded text-sm w-full"
                                    >
                                        Cancel
                                    </button>
                                )}
                            </form>
                        </div>

                        {/* RIGHT COLUMN: LIST */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow lg:col-span-2">
                            <h2 className="text-lg font-bold mb-4 dark:text-white">Existing Users</h2>
                            {isLoading ? (
                                <div className="flex justify-center items-center h-40">
                                    <Spinner />
                                </div>
                            ) : (
                            <div className="overflow-x-auto">
                                <table className="min-w-full leading-normal">
                                    <thead>
                                        <tr>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Username</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Role</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Email</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {users.map((user) => (
                                            <tr key={user.id}>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs dark:text-gray-200">{user.username}</td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs dark:text-gray-200">{user.role}</td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs dark:text-gray-200">{user.email}</td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm dark:text-gray-200">
                                                    <button onClick={() => startEditing(user)} className="text-blue-500 hover:text-blue-700 mr-3 text-xs">Edit</button>
                                                    {user.username !== 'admin' && (
                                                        <button onClick={() => handleDeleteUser(user.id)} className="text-red-500 hover:text-red-700 text-xs">Delete</button>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            )}
                        </div>
                    </div>
                )}

                {/* SERVICE HEALTH TAB */}
                {activeTab === 'health' && (
                    <div className="space-y-6">
                        <div className="flex justify-between items-center bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                            <h2 className="text-lg font-bold dark:text-white">System Service Health</h2>
                            <button
                                onClick={handleTriggerHealthCheck}
                                disabled={isTriggeringHealth}
                                className={`bg-brand-navy text-white px-4 py-2 rounded text-sm hover:bg-brand-navy-dark transition-colors ${isTriggeringHealth ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                {isTriggeringHealth ? 'Checking...' : 'Run Health Check Now'}
                            </button>
                        </div>

                        {healthStatus ? (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                {/* Database Card */}
                                <div className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.database?.is_healthy ? 'border-green-500 bg-white dark:bg-zinc-800' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}>
                                    <h3 className="text-lg font-bold mb-2 dark:text-white flex items-center justify-between">
                                        PostgreSQL Database
                                        <span className={`inline-block w-3 h-3 rounded-full ${healthStatus?.database?.is_healthy ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                    </h3>
                                    <div className="text-sm space-y-2 dark:text-gray-300">
                                        <p><strong>Status:</strong> {healthStatus?.database?.is_healthy ? 'Healthy' : 'Degraded'}</p>
                                        <p><strong>Latency:</strong> {healthStatus?.database?.latency_ms !== null ? `${healthStatus.database.latency_ms}ms` : 'N/A'}</p>
                                        {!healthStatus?.database?.is_healthy && healthStatus?.database?.error_message && (
                                            <p className="text-red-600 dark:text-red-400 text-xs mt-2 mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                                                <strong>Error:</strong> {healthStatus.database.error_message}
                                            </p>
                                        )}
                                        <p className="text-xs text-gray-500 mt-4">Last checked: {healthStatus?.database?.checked_at ? new Date(healthStatus.database.checked_at).toLocaleString() : 'Never'}</p>
                                    </div>
                                </div>
                                {/* LLM Provider Card */}
                                <div className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.llm?.is_healthy ? 'border-green-500 bg-white dark:bg-zinc-800' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}>
                                    <h3 className="text-lg font-bold mb-2 dark:text-white flex items-center justify-between">
                                        {healthStatus?.active_llm_provider === 'openrouter' ? 'OpenRouter API' : 'Ollama Reasoning Engine'}
                                        <span className={`inline-block w-3 h-3 rounded-full ${healthStatus?.llm?.is_healthy ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`}></span>
                                    </h3>
                                    <div className="text-sm space-y-2 dark:text-gray-300">
                                        <p><strong>Status:</strong> {healthStatus?.llm?.is_healthy ? 'Healthy' : 'Disconnected / Refused'}</p>
                                        <p><strong>Latency:</strong> {healthStatus?.llm?.latency_ms !== null ? `${healthStatus.llm.latency_ms}ms` : 'N/A'}</p>
                                        {!healthStatus?.llm?.is_healthy && healthStatus?.llm?.error_message && (
                                            <p className="text-red-600 dark:text-red-400 text-xs mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                                                <strong>Error:</strong> {healthStatus.llm.error_message}
                                            </p>
                                        )}
                                        <p className="text-xs text-gray-500 mt-4">Last checked: {healthStatus?.llm?.checked_at ? new Date(healthStatus.llm.checked_at).toLocaleString() : 'Never'}</p>
                                    </div>
                                </div>
                                {/* LEX API Card */}
                                <div className={`p-6 rounded-lg shadow border-l-4 ${healthStatus?.lex_api?.is_healthy ? 'border-green-500 bg-white dark:bg-zinc-800' : 'border-red-500 bg-red-50 dark:bg-red-900/20'}`}>
                                    <h3 className="text-lg font-bold mb-2 dark:text-white flex items-center justify-between">
                                        External LEX Data API
                                        <span className={`inline-block w-3 h-3 rounded-full ${healthStatus?.lex_api?.is_healthy ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                    </h3>
                                    <div className="text-sm space-y-2 dark:text-gray-300">
                                        <p><strong>Status:</strong> {healthStatus?.lex_api?.is_healthy ? 'Reachable' : 'Unreachable'}</p>
                                        <p><strong>Latency:</strong> {healthStatus?.lex_api?.latency_ms !== null ? `${healthStatus.lex_api.latency_ms}ms` : 'N/A'}</p>
                                        {!healthStatus?.lex_api?.is_healthy && healthStatus?.lex_api?.error_message && (
                                            <p className="text-red-600 dark:text-red-400 text-xs mt-2 p-2 bg-red-100 dark:bg-red-900/40 rounded">
                                                <strong>Error:</strong> {healthStatus.lex_api.error_message}
                                            </p>
                                        )}
                                        <p className="text-xs text-gray-500 mt-4">Last checked: {healthStatus?.lex_api?.checked_at ? new Date(healthStatus.lex_api.checked_at).toLocaleString() : 'Never'}</p>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex justify-center items-center h-40">
                                <Spinner />
                            </div>
                        )}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow mt-6">
                            <h3 className="text-md font-bold mb-2 dark:text-white">Note regarding Service Health</h3>
                            <p className="text-sm text-gray-600 dark:text-gray-400">Health checks execute automatically in the background every 60 seconds starting from server boot. If a component goes down, AILA will isolate the fault to its container to make proxy or downtime troubleshooting instantaneous.</p>
                        </div>
                    </div>
                )}

                {/* USAGE STATS TAB */}
                {activeTab === 'usage' && isLoading && (
                    <div className="flex justify-center items-center h-64">
                        <Spinner />
                    </div>
                )}
                {activeTab === 'usage' && !isLoading && usageStats && (
                    <div className="space-y-6">
                        {/* HEADER WITH FILTER */}
                        <div className="flex justify-between items-center bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                            <h2 className="text-lg font-bold dark:text-white">Usage Overview</h2>
                            <div className="flex items-center space-x-2">
                                <label className="text-sm text-gray-500 dark:text-gray-400 font-medium">Timeframe:</label>
                                <select
                                    value={timeframe}
                                    onChange={(e) => setTimeframe(e.target.value)}
                                    className="p-2 border rounded-md text-sm dark:bg-zinc-700 dark:border-zinc-600 dark:text-white focus:ring-2 focus:ring-blue-500"
                                >
                                    <option value="1">Last 1 Day</option>
                                    <option value="3">Last 3 Days</option>
                                    <option value="7">Last 7 Days</option>
                                    <option value="30">Last 30 Days</option>
                                    <option value="90">Last 90 Days</option>
                                    <option value="all">All Time</option>
                                </select>
                            </div>
                        </div>

                        {/* KPI CARDS */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Total Users (Global)</h3>
                                <p className="text-2xl font-bold dark:text-white">{usageStats.kpi.users}</p>
                            </div>
                            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Active Users {timeframe === 'all' ? '(All Time)' : `(${timeframe}d)`}</h3>
                                <p className="text-2xl font-bold text-green-600">{usageStats.kpi.activeUsers}</p>
                            </div>
                            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Total Chats</h3>
                                <p className="text-2xl font-bold dark:text-white">{usageStats.kpi.chats}</p>
                            </div>
                            <div className="bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h3 className="text-gray-500 dark:text-gray-400 text-xs font-bold uppercase">Total Messages</h3>
                                <p className="text-2xl font-bold dark:text-white">{usageStats.kpi.messages}</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {/* ACTIVITY CHART */}
                            <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                                <h2 className="text-lg font-bold mb-4 dark:text-white">Daily Chats {timeframe === 'all' ? '(All Time)' : `(Last ${timeframe} Days)`}</h2>
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={usageStats.activity}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                            <XAxis
                                                dataKey="date"
                                                stroke="#9ca3af"
                                                tick={{ fontSize: 10 }}
                                                tickFormatter={(str) => new Date(str).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' })}
                                            />
                                            <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
                                                itemStyle={{ color: '#374151' }}
                                            />
                                            <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* POWER USERS & MODELS */}
                            <div className="space-y-6">
                                {/* MODELS */}
                                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow h-fit">
                                    <h2 className="text-lg font-bold mb-4 dark:text-white">Model Distribution</h2>
                                    <div className="h-40 flex items-center justify-center">
                                        {/* Simple Pie Chart Placeholder or Real Implementation if easy */}
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={usageStats.models}
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={40}
                                                    outerRadius={70}
                                                    fill="#8884d8"
                                                    paddingAngle={5}
                                                    dataKey="count"
                                                    nameKey="model"
                                                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                                    labelLine={false}
                                                >
                                                    {usageStats.models.map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={['#0088FE', '#00C49F', '#FFBB28', '#FF8042'][index % 4]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                {/* TOP USERS */}
                                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                                    <h2 className="text-lg font-bold mb-4 dark:text-white">Top 5 Power Users</h2>
                                    <ul className="space-y-3">
                                        {usageStats.topUsers.map((u, i) => (
                                            <li key={i} className="flex justify-between items-center text-sm border-b dark:border-zinc-700 pb-2 last:border-0 last:pb-0">
                                                <span className="font-medium dark:text-gray-200">
                                                    {i + 1}. {u.username}
                                                </span>
                                                <span className="bg-gray-100 dark:bg-zinc-700 text-gray-800 dark:text-gray-300 px-2 py-1 rounded text-xs font-bold">
                                                    {u.msg_count} msgs
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* PERFORMANCE TAB */}
                {activeTab === 'performance' && isPerfLoading && (
                    <div className="flex justify-center items-center h-64">
                        <Spinner />
                    </div>
                )}
                {activeTab === 'performance' && !isPerfLoading && perfStats && (
                    <PerformanceTab
                        perfStats={perfStats}
                        perfTimeframe={perfTimeframe}
                        setPerfTimeframe={setPerfTimeframe}
                    />
                )}
                {activeTab === 'performance' && !isPerfLoading && !perfStats && (
                    <div className="flex justify-center items-center h-64 text-gray-500 text-sm">
                        No performance data recorded yet. Run some queries to start collecting timings.
                    </div>
                )}

                {/* COST TAB */}
                {activeTab === 'cost' && isCostLoading && (
                    <div className="flex justify-center items-center h-64">
                        <Spinner />
                    </div>
                )}
                {activeTab === 'cost' && !isCostLoading && costStats && (
                    <CostTab
                        costStats={costStats}
                        costTimeframe={costTimeframe}
                        setCostTimeframe={setCostTimeframe}
                    />
                )}
                {activeTab === 'cost' && !isCostLoading && !costStats && (
                    <div className="flex justify-center items-center h-64 text-gray-500 text-sm">
                        No cost data available yet.
                    </div>
                )}

                {/* LEARNING DASHBOARD TAB */}
                {activeTab === 'learning' && (
                    <div className="space-y-6">
                        {/* 0. PERFORMANCE TRENDS CHART */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-lg font-bold dark:text-white">Performance Trends (Avg Rating)</h2>
                                <div className="flex items-center space-x-2">
                                    <label className="text-sm text-gray-500 dark:text-gray-400 font-medium">Timeframe:</label>
                                    <select
                                        value={learningTimeframe}
                                        onChange={(e) => setLearningTimeframe(e.target.value)}
                                        className="p-2 border rounded-md text-sm dark:bg-zinc-700 dark:border-zinc-600 dark:text-white focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="1">Last 1 Day</option>
                                        <option value="3">Last 3 Days</option>
                                        <option value="7">Last 7 Days</option>
                                        <option value="30">Last 30 Days</option>
                                        <option value="90">Last 90 Days</option>
                                        <option value="all">All Time</option>
                                    </select>
                                </div>
                            </div>

                            <div className="h-64 w-full">
                                {isStatsLoading ? (
                                    <div className="h-full flex items-center justify-center">
                                        <Spinner />
                                    </div>
                                ) : stats?.data && stats.data.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart
                                            data={stats.data}
                                            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                                        >
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                            <XAxis
                                                dataKey="date"
                                                stroke="#9ca3af"
                                                tick={{ fontSize: 12 }}
                                            />
                                            <YAxis
                                                domain={[0, 5]}
                                                stroke="#9ca3af"
                                                tick={{ fontSize: 12 }}
                                            />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb' }}
                                                itemStyle={{ color: '#374151' }}
                                            />
                                            <Legend wrapperStyle={{ paddingTop: '10px' }} />
                                            {stats.models.map((model, index) => (
                                                <Line
                                                    key={model}
                                                    type="monotone"
                                                    dataKey={model}
                                                    name={model}
                                                    stroke={['#2563eb', '#db2777', '#ca8a04', '#16a34a', '#9333ea'][index % 5]}
                                                    strokeWidth={2}
                                                    activeDot={{ r: 8 }}
                                                    connectNulls
                                                />
                                            ))}
                                        </LineChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="h-full flex items-center justify-center text-gray-500 text-sm">
                                        Not enough data to display trends yet.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* 1. RECENT FEEDBACK */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-lg font-bold mb-4 dark:text-white flex justify-between items-center">
                                <span>Recent User Feedback</span>
                                <button onClick={fetchFeedback} className="text-xs text-blue-500 hover:underline">Refresh</button>
                            </h2>
                            {isLoading ? (
                                <div className="flex justify-center items-center h-40">
                                    <Spinner />
                                </div>
                            ) : (
                            <div className="overflow-x-auto max-h-96">
                                <table className="min-w-full leading-normal">
                                    <thead>
                                        <tr>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Date</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">User</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Rating</th>
                                            <th className="px-5 py-3 border-b-2 border-zinc-200 dark:border-zinc-700 text-left text-xs font-semibold text-zinc-600 dark:text-zinc-300 uppercase tracking-wider">Comment</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {feedback.map((item) => (
                                            <tr key={item.id} className={item.rating >= 4 ? 'bg-green-50 dark:bg-green-900/10' : (item.rating <= 2 ? 'bg-red-50 dark:bg-red-900/10' : '')}>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 text-xs dark:text-gray-200">
                                                    {new Date(item.created_at).toLocaleDateString()}
                                                </td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 text-xs dark:text-gray-200 font-medium">
                                                    {item.username}
                                                </td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 text-xs dark:text-gray-200">
                                                    <div className="flex text-yellow-500">
                                                        {[...Array(5)].map((_, i) => (
                                                            <svg key={i} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-4 h-4 ${i < item.rating ? '' : 'text-gray-300 dark:text-gray-600'}`}>
                                                                <path fillRule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clipRule="evenodd" />
                                                            </svg>
                                                        ))}
                                                    </div>
                                                </td>
                                                <td className="px-5 py-5 border-b border-zinc-200 dark:border-zinc-700 text-xs dark:text-gray-200 italic">
                                                    "{item.feedback_comment || 'No comment'}"
                                                </td>
                                            </tr>
                                        ))}
                                        {feedback.length === 0 && (
                                            <tr>
                                                <td colSpan="4" className="px-5 py-5 text-center text-gray-500 text-xs">No feedback data recorded yet.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                            )}
                        </div>

                        {/* 2. KNOWLEDGE BASE PLAYGROUND */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-lg font-bold mb-4 dark:text-white">Knowledge Retrieval Playground</h2>
                            <p className="mb-4 text-xs text-gray-600 dark:text-gray-400">
                                Test what "memories" the agent retrieves for a given user query.
                            </p>
                            <form onSubmit={handleTestRetrieval} className="flex gap-2 mb-6">
                                <input
                                    type="text"
                                    placeholder="Enter a test query (e.g. 'Duty of Care')..."
                                    value={testQuery}
                                    onChange={(e) => setTestQuery(e.target.value)}
                                    className="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-zinc-700 dark:border-zinc-600 dark:text-white text-sm"
                                />
                                <button
                                    type="submit"
                                    disabled={isTestLoading}
                                    className={`bg-brand-navy text-white px-6 py-3 rounded-lg hover:bg-brand-navy-dark transition-colors text-sm flex items-center gap-2 ${isTestLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                                >
                                    {isTestLoading && <Spinner size="sm" />}
                                    {isTestLoading ? 'Testing...' : 'Test'}
                                </button>
                            </form>

                            {/* RESULTS */}
                            {testResults && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* POSITIVE EXAMPLES */}
                                    <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg border border-green-200 dark:border-green-900">
                                        <h3 className="font-bold text-green-800 dark:text-green-200 mb-3 flex items-center text-sm">
                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 mr-2">
                                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                            </svg>
                                            Positive Examples ({testResults.examples.length})
                                        </h3>
                                        <div className="space-y-4">
                                            {testResults.examples.map((ex, i) => (
                                                <div key={i} className="bg-white dark:bg-zinc-900 p-3 rounded shadow-sm text-xs">
                                                    <div className="font-semibold text-gray-700 dark:text-gray-300 mb-1">Q: {ex.question}</div>
                                                    <div className="text-gray-600 dark:text-gray-400 line-clamp-3 mb-2">A: {ex.answer}</div>
                                                    {ex.feedback_comment && (
                                                        <div className="text-xs text-green-600 dark:text-green-400 italic border-l-2 border-green-400 pl-2">
                                                            User Note: "{ex.feedback_comment}"
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                            {testResults.examples.length === 0 && <p className="text-xs text-gray-500 italic">No positive examples found.</p>}
                                        </div>
                                    </div>

                                    {/* CRITIQUES */}
                                    <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg border border-red-200 dark:border-red-900">
                                        <h3 className="font-bold text-red-800 dark:text-red-200 mb-3 flex items-center text-sm">
                                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 mr-2">
                                                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                                            </svg>
                                            Past Critiques ({testResults.critiques.length})
                                        </h3>
                                        <div className="space-y-4">
                                            {testResults.critiques.map((c, i) => (
                                                <div key={i} className="bg-white dark:bg-zinc-900 p-3 rounded shadow-sm text-xs">
                                                    <div className="text-red-600 dark:text-red-400 font-medium mb-1">"{c.feedback_comment}"</div>
                                                    <div className="text-xs text-gray-500">Context: "{c.question}"</div>
                                                </div>
                                            ))}
                                            {testResults.critiques.length === 0 && <p className="text-xs text-gray-500 italic">No critiques found.</p>}
                                        </div>
                                    </div>
                                </div>
                            )}

                        </div>
                    </div>
                )}

                {/* DEVELOPER TAB */}
                {activeTab === 'developer' && (
                    <div className="space-y-6">

                        {/* LLM Provider Configuration */}
                        <ProviderConfigPanel />

                        {/* Feature Flags */}
                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                            <h2 className="text-lg font-bold mb-1 dark:text-white">Feature Flags</h2>
                            <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">
                                Toggle features on or off for all users. Changes take effect immediately.
                            </p>
                            <div className="flex items-center justify-between py-3 border-b border-gray-100 dark:border-zinc-700">
                                <div>
                                    <p className="text-sm font-medium dark:text-white">Matters</p>
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                        Lets users organise threads into named matters with notes.
                                    </p>
                                </div>
                                <button
                                    role="switch"
                                    aria-checked={features.matters_enabled}
                                    disabled={isSavingFeatures}
                                    onClick={async () => {
                                        const next = { ...features, matters_enabled: !features.matters_enabled };
                                        setIsSavingFeatures(true);
                                        try {
                                            const saved = await saveFeatures(next);
                                            setFeatures(saved.features);
                                        } catch {
                                            setMessage('Failed to save feature flags.');
                                        } finally {
                                            setIsSavingFeatures(false);
                                        }
                                    }}
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${features.matters_enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-zinc-600'} ${isSavingFeatures ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                                >
                                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${features.matters_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                                </button>
                            </div>
                        </div>



                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow border border-red-200 dark:border-red-900">
                            <h2 className="text-lg font-bold mb-4 text-red-600 dark:text-red-400">Danger Zone</h2>
                            <p className="mb-2 text-sm text-gray-600 dark:text-gray-400">
                                These actions permanently delete data and <strong>cannot be undone.</strong>
                            </p>
                            <div className="flex flex-wrap gap-3 mb-6">
                                <button
                                    onClick={async () => {
                                        if (!window.confirm('This will delete all chats and messages. User accounts will be kept.\n\nAre you sure?')) return;
                                        setIsLoading(true);
                                        try {
                                            const res = await clearUsageData();
                                            setMessage(res.message);
                                            fetchStats();
                                        } catch (err) {
                                            setMessage('Error clearing usage data: ' + err.message);
                                        } finally {
                                            setIsLoading(false);
                                        }
                                    }}
                                    disabled={isLoading}
                                    className={`bg-orange-600 text-white px-5 py-2.5 rounded-lg hover:bg-orange-700 transition-colors text-sm flex items-center gap-2 ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                                >
                                    {isLoading && <Spinner size="sm" />}
                                    Clear All Usage Data
                                </button>
                                <button
                                    onClick={async () => {
                                        if (!window.confirm('This will delete all performance timing records.\n\nAre you sure?')) return;
                                        setIsLoading(true);
                                        try {
                                            const res = await clearPerformanceData();
                                            setMessage(res.message);
                                        } catch (err) {
                                            setMessage('Error clearing performance data: ' + err.message);
                                        } finally {
                                            setIsLoading(false);
                                        }
                                    }}
                                    disabled={isLoading}
                                    className={`bg-orange-600 text-white px-5 py-2.5 rounded-lg hover:bg-orange-700 transition-colors text-sm flex items-center gap-2 ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                                >
                                    {isLoading && <Spinner size="sm" />}
                                    Clear All Performance Data
                                </button>
                                <button
                                    onClick={async () => {
                                        if (!window.confirm('This will delete all product feedback surveys and clear all message ratings and comments.\n\nAre you sure?')) return;
                                        setIsLoading(true);
                                        try {
                                            const res = await clearFeedbackData();
                                            setMessage(res.message);
                                        } catch (err) {
                                            setMessage('Error clearing feedback data: ' + err.message);
                                        } finally {
                                            setIsLoading(false);
                                        }
                                    }}
                                    disabled={isLoading}
                                    className={`bg-orange-600 text-white px-5 py-2.5 rounded-lg hover:bg-orange-700 transition-colors text-sm flex items-center gap-2 ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                                >
                                    {isLoading && <Spinner size="sm" />}
                                    Clear User Feedback
                                </button>
                            </div>
                        </div>
                    </div>
                )}
                {/* USER FEEDBACK TAB */}
                {activeTab === 'product-feedback' && (() => {
                    const timeframeLabel = productFeedbackTimeframe === 'all' ? 'All Time' : `Last ${productFeedbackTimeframe} Days`;
                    const withTime = productFeedback.filter(f => f.time_saved_hours != null && f.time_without_aila_hours != null);
                    const avgSaved = withTime.length > 0 ? (withTime.reduce((s, f) => s + f.time_saved_hours, 0) / withTime.length) : null;
                    const avgWithout = withTime.length > 0 ? (withTime.reduce((s, f) => s + f.time_without_aila_hours, 0) / withTime.length) : null;
                    const withConf = productFeedback.filter(f => f.confidence != null);
                    const avgConf = withConf.length > 0 ? (withConf.reduce((s, f) => s + f.confidence, 0) / withConf.length) : null;
                    const thCls = "px-4 py-2 border-b-2 border-zinc-200 dark:border-zinc-700 text-left font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider whitespace-nowrap";
                    return (
                        <div className="space-y-4">

                            {/* TIMEFRAME FILTER HEADER */}
                            <div className="flex justify-between items-center bg-white dark:bg-zinc-800 p-4 rounded-lg shadow">
                                <h2 className="text-lg font-bold dark:text-white">User Feedback</h2>
                                <div className="flex items-center space-x-2">
                                    <label className="text-sm text-gray-500 dark:text-gray-400 font-medium">Timeframe:</label>
                                    <select
                                        value={productFeedbackTimeframe}
                                        onChange={(e) => setProductFeedbackTimeframe(e.target.value)}
                                        className="p-2 border rounded-md text-sm dark:bg-zinc-700 dark:border-zinc-600 dark:text-white focus:ring-2 focus:ring-blue-500"
                                    >
                                        <option value="1">Last 1 Day</option>
                                        <option value="3">Last 3 Days</option>
                                        <option value="7">Last 7 Days</option>
                                        <option value="30">Last 30 Days</option>
                                        <option value="90">Last 90 Days</option>
                                        <option value="all">All Time</option>
                                    </select>
                                </div>
                            </div>

                            {/* RESPONSE RATINGS CARD */}
                            {(() => {
                                const total = messageRatings.length;
                                const upCount = messageRatings.filter(r => r.rating === 5).length;
                                const downCount = messageRatings.filter(r => r.rating === 1).length;
                                const commentedCount = messageRatings.filter(r => r.feedback_comment).length;
                                const upPct = total > 0 ? Math.round((upCount / total) * 100) : null;
                                const downPct = total > 0 ? Math.round((downCount / total) * 100) : null;
                                const filtered = messageRatings.filter(r => {
                                    if (ratingsFilter === 'up') return r.rating === 5;
                                    if (ratingsFilter === 'down') return r.rating === 1;
                                    if (ratingsFilter === 'commented') return !!r.feedback_comment;
                                    return true;
                                });
                                const thR = "px-4 py-2 border-b-2 border-zinc-200 dark:border-zinc-700 text-left font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider whitespace-nowrap text-xs";
                                return (
                                    <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                                        <div className="flex justify-between items-center mb-5">
                                            <h2 className="text-lg font-bold dark:text-white">LLM Response Ratings</h2>
                                            <button onClick={() => fetchProductFeedback(productFeedbackTimeframe)} className="text-xs text-blue-500 hover:underline">Refresh</button>
                                        </div>

                                        {/* KPIs */}
                                        {!isMessageRatingsLoading && total > 0 && (
                                            <>
                                                <h3 className="text-sm font-bold mb-3 dark:text-white">Rating Summary</h3>
                                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                                                    <div className="bg-zinc-50 dark:bg-zinc-700 rounded-lg p-4 text-center">
                                                        <div className="text-2xl font-bold text-zinc-800 dark:text-white">{total}</div>
                                                        <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Total rated</div>
                                                    </div>
                                                    <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-4 text-center">
                                                        <div className="text-2xl font-bold text-green-700 dark:text-green-300">{upCount}</div>
                                                        <div className="text-xs text-green-600 dark:text-green-400 mt-1">👍 Helpful{upPct != null ? ` (${upPct}%)` : ''}</div>
                                                    </div>
                                                    <div className="bg-red-50 dark:bg-red-900/30 rounded-lg p-4 text-center">
                                                        <div className="text-2xl font-bold text-red-700 dark:text-red-300">{downCount}</div>
                                                        <div className="text-xs text-red-600 dark:text-red-400 mt-1">👎 Unhelpful{downPct != null ? ` (${downPct}%)` : ''}</div>
                                                    </div>
                                                    <div className="bg-zinc-50 dark:bg-zinc-700 rounded-lg p-4 text-center">
                                                        <div className="text-2xl font-bold text-zinc-800 dark:text-white">{commentedCount}</div>
                                                        <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">With comments</div>
                                                    </div>
                                                </div>
                                            </>
                                        )}

                                        {/* Daily ratings chart */}
                                        {!isMessageRatingsLoading && total > 0 && (
                                            <div className="mb-6">
                                                <h3 className="text-sm font-bold mb-3 dark:text-white">Daily Ratings</h3>
                                                <ResponsiveContainer width="100%" height={160}>
                                                    <BarChart data={buildDailyRatingsData(messageRatings, productFeedbackTimeframe)} barCategoryGap="35%">
                                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                                        <XAxis dataKey="day" tick={{ fontSize: 11 }} interval={Math.max(0, Math.floor(parseInt(productFeedbackTimeframe) / 7) - 1) || 'preserveStartEnd'} />
                                                        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} width={24} />
                                                        <Tooltip />
                                                        <Legend wrapperStyle={{ fontSize: 12 }} />
                                                        <Bar dataKey="up" name="Helpful" fill="#22c55e" radius={[3, 3, 0, 0]} />
                                                        <Bar dataKey="down" name="Unhelpful" fill="#ef4444" radius={[3, 3, 0, 0]} />
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        )}

                                        {/* Filter tabs */}
                                        {!isMessageRatingsLoading && total > 0 && (
                                            <div className="flex flex-wrap gap-2 mb-4">
                                                {[
                                                    { key: 'all', label: `All (${total})` },
                                                    { key: 'down', label: `👎 Unhelpful (${downCount})` },
                                                    { key: 'up', label: `👍 Helpful (${upCount})` },
                                                    { key: 'commented', label: `💬 With comments (${commentedCount})` },
                                                ].map(f => (
                                                    <button
                                                        key={f.key}
                                                        onClick={() => setRatingsFilter(f.key)}
                                                        className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${ratingsFilter === f.key
                                                            ? 'bg-blue-600 text-white border-blue-600'
                                                            : 'bg-white dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300 border-zinc-200 dark:border-zinc-600 hover:border-zinc-400 dark:hover:border-zinc-400'
                                                        }`}
                                                    >{f.label}</button>
                                                ))}
                                            </div>
                                        )}

                                        {/* Table */}
                                        <h3 className="text-sm font-bold mb-3 mt-2 dark:text-white">Individual LLM Response Ratings</h3>
                                        {isMessageRatingsLoading ? (
                                            <div className="flex justify-center items-center h-32"><Spinner /></div>
                                        ) : total === 0 ? (
                                            <p className="text-gray-400 text-sm">No responses have been rated yet.</p>
                                        ) : filtered.length === 0 ? (
                                            <p className="text-gray-400 text-sm">No ratings match this filter.</p>
                                        ) : (
                                            <>
                                            <div className="overflow-x-auto">
                                                <table className="min-w-full text-sm">
                                                    <thead>
                                                        <tr>
                                                            <th className={`${thR} w-24`}>User</th>
                                                            <th className={`${thR} w-32`}>Date</th>
                                                            <th className={`${thR} w-24`}>Rating</th>
                                                            <th className={`${thR} w-48`}>Comment</th>
                                                            <th className={`${thR} w-40`}>Query / Response</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {filtered.map(item => (
                                                            <tr
                                                                key={item.id}
                                                                className="border-b border-zinc-100 dark:border-zinc-700 align-top"
                                                            >
                                                                <td className="px-4 py-3 font-medium text-gray-800 dark:text-gray-200 whitespace-nowrap">{item.username}</td>
                                                                <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap text-xs">
                                                                    {new Date(item.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                                                </td>
                                                                <td className="px-4 py-3">
                                                                    {item.rating === 5
                                                                        ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 text-xs font-semibold whitespace-nowrap">👍 Helpful</span>
                                                                        : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 text-xs font-semibold whitespace-nowrap">👎 Unhelpful</span>
                                                                    }
                                                                </td>
                                                                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                                                                    {item.feedback_comment
                                                                        ? <span className="italic text-xs">{item.feedback_comment}</span>
                                                                        : <span className="text-zinc-400 text-xs">—</span>
                                                                    }
                                                                </td>
                                                                <td className="px-4 py-3">
                                                                    <button
                                                                        onClick={() => setRatingViewItem(item)}
                                                                        className="px-3 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-600 transition-colors whitespace-nowrap"
                                                                    >
                                                                        View query/response
                                                                    </button>
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>

                                            {/* Query/Response modal */}
                                            {ratingViewItem && (
                                                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setRatingViewItem(null)}>
                                                    <div
                                                        className="bg-white dark:bg-zinc-800 rounded-xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col max-h-[80vh]"
                                                        onClick={e => e.stopPropagation()}
                                                    >
                                                        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
                                                            <h3 className="font-semibold text-zinc-800 dark:text-white text-sm">Query &amp; Response</h3>
                                                            <span className="text-xs text-zinc-500 dark:text-zinc-400">
                                                                {ratingViewItem.username} · {new Date(ratingViewItem.created_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                                            </span>
                                                        </div>
                                                        <div className="overflow-y-auto px-6 py-4 space-y-4 flex-1">
                                                            {(() => {
                                                                const mdComponents = {
                                                                    p: ({ node, ...p }) => <p {...p} className="mb-3 last:mb-0" />,
                                                                    ul: ({ node, ...p }) => <ul {...p} className="list-disc pl-5 mb-3" />,
                                                                    ol: ({ node, ...p }) => <ol {...p} className="list-decimal pl-5 mb-3" />,
                                                                    li: ({ node, ...p }) => <li {...p} className="mb-1" />,
                                                                    h1: ({ node, ...p }) => <h1 {...p} className="text-base font-bold mt-3 mb-2" />,
                                                                    h2: ({ node, ...p }) => <h2 {...p} className="text-sm font-bold mt-3 mb-1" />,
                                                                    h3: ({ node, ...p }) => <h3 {...p} className="text-sm font-semibold mt-2 mb-1" />,
                                                                    strong: ({ node, ...p }) => <strong {...p} className="font-semibold" />,
                                                                    blockquote: ({ node, ...p }) => <blockquote {...p} className="border-l-2 border-zinc-300 dark:border-zinc-600 pl-3 italic text-zinc-600 dark:text-zinc-400 my-2" />,
                                                                    code: ({ node, inline, ...p }) => inline
                                                                        ? <code {...p} className="bg-zinc-100 dark:bg-zinc-700 px-1 py-0.5 rounded text-xs font-mono" />
                                                                        : <code {...p} className="text-xs font-mono" />,
                                                                    pre: ({ node, ...p }) => <pre {...p} className="bg-zinc-100 dark:bg-zinc-700 rounded p-3 overflow-x-auto text-xs font-mono mb-3" />,
                                                                    a: ({ node, ...p }) => <a {...p} className="text-blue-600 dark:text-blue-400 underline" target="_blank" rel="noopener noreferrer" />,
                                                                };
                                                                return (
                                                                    <>
                                                                        <div>
                                                                            <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-2">Query</p>
                                                                            <div className="text-sm text-zinc-800 dark:text-zinc-200">
                                                                                {ratingViewItem.query
                                                                                    ? <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{ratingViewItem.query}</ReactMarkdown>
                                                                                    : <span className="italic text-zinc-400">—</span>
                                                                                }
                                                                            </div>
                                                                        </div>
                                                                        <div className="border-t border-zinc-100 dark:border-zinc-700 pt-4">
                                                                            <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-2">Response</p>
                                                                            <div className="text-sm text-zinc-800 dark:text-zinc-200">
                                                                                <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{ratingViewItem.response || '—'}</ReactMarkdown>
                                                                            </div>
                                                                        </div>
                                                                    </>
                                                                );
                                                            })()}
                                                        </div>
                                                        <div className="flex justify-end gap-3 px-6 py-4 border-t border-zinc-200 dark:border-zinc-700">
                                                            <button
                                                                onClick={() => {
                                                                    const text = `Query:\n${ratingViewItem.query || ''}\n\nResponse:\n${ratingViewItem.response || ''}`;
                                                                    navigator.clipboard.writeText(text);
                                                                }}
                                                                className="px-4 py-2 text-xs rounded border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-700 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-600 transition-colors"
                                                            >
                                                                Copy to clipboard
                                                            </button>
                                                            <button
                                                                onClick={() => setRatingViewItem(null)}
                                                                className="px-4 py-2 text-xs rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                                                            >
                                                                Close
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                            </>
                                        )}
                                    </div>
                                );
                            })()}

                            <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                                <div className="flex justify-between items-center mb-4">
                                    <h2 className="text-lg font-bold dark:text-white">Weekly User Surveys</h2>
                                    <button onClick={() => fetchProductFeedback(productFeedbackTimeframe)} className="text-xs text-blue-500 hover:underline">Refresh</button>
                                </div>

                                {!isProductFeedbackLoading && surveyCompliance && (
                                    <WeeklySurveyComplianceChart surveyCompliance={surveyCompliance} />
                                )}

                                {/* Aggregate summary */}
                                {!isProductFeedbackLoading && productFeedback.length > 0 && (
                                    <>
                                    <h3 className="text-sm font-bold mb-3 dark:text-white">Productivity Summary</h3>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                                        <div className="bg-zinc-50 dark:bg-zinc-700 rounded-lg p-4 text-center">
                                            <div className="text-2xl font-bold text-zinc-800 dark:text-white">
                                                {avgSaved != null ? avgSaved.toFixed(1) : '—'}
                                            </div>
                                            <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Avg hrs saved</div>
                                        </div>
                                        <div className="bg-zinc-50 dark:bg-zinc-700 rounded-lg p-4 text-center">
                                            <div className="text-2xl font-bold text-zinc-800 dark:text-white">
                                                {avgWithout != null ? avgWithout.toFixed(1) : '—'}
                                            </div>
                                            <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Avg hrs without AILA</div>
                                        </div>
                                        <div className="bg-zinc-50 dark:bg-zinc-700 rounded-lg p-4 text-center">
                                            <div className="text-2xl font-bold text-zinc-800 dark:text-white">
                                                {avgSaved != null && avgWithout != null && (avgWithout - avgSaved) > 0
                                                    ? `${(avgWithout / (avgWithout - avgSaved)).toFixed(1)}×`
                                                    : '—'}
                                            </div>
                                            <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Efficiency ratio</div>
                                        </div>
                                        <div className="bg-zinc-50 dark:bg-zinc-700 rounded-lg p-4 text-center">
                                            <div className="text-2xl font-bold text-zinc-800 dark:text-white">
                                                {avgConf != null ? `${avgConf.toFixed(1)}/5` : '—'}
                                            </div>
                                            <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Avg confidence</div>
                                        </div>
                                    </div>
                                    </>
                                )}

                                <h3 className="text-sm font-bold mb-3 mt-2 dark:text-white">Individual Survey Responses</h3>
                                {isProductFeedbackLoading ? (
                                    <div className="flex justify-center items-center h-32"><Spinner /></div>
                                ) : productFeedback.length === 0 ? (
                                    <p className="text-gray-400 text-sm">No feedback has been submitted yet.</p>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="min-w-full text-sm">
                                            <thead>
                                                <tr>
                                                    <th className={`${thCls} w-32`}>User</th>
                                                    <th className={`${thCls} w-44`}>Date &amp; Time</th>
                                                    <th className={`${thCls} w-28`}>Saved (hrs)</th>
                                                    <th className={`${thCls} w-36`}>Without AILA (hrs)</th>
                                                    <th className={`${thCls} w-40`}>Success</th>
                                                    <th className={`${thCls} w-24`}>Confidence</th>
                                                    <th className={thCls}>Comments</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {productFeedback.map((item) => (
                                                    <tr key={item.id} className="border-b border-zinc-100 dark:border-zinc-700 align-top">
                                                        <td className="px-4 py-3 font-medium text-gray-800 dark:text-gray-200 whitespace-nowrap">{item.username}</td>
                                                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">{new Date(item.created_at).toLocaleString()}</td>
                                                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300 text-center">{item.time_saved_hours != null ? item.time_saved_hours : '—'}</td>
                                                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300 text-center">{item.time_without_aila_hours != null ? item.time_without_aila_hours : '—'}</td>
                                                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{item.research_success || '—'}</td>
                                                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300 text-center">{item.confidence != null ? `${item.confidence}/5` : '—'}</td>
                                                        <td className="px-4 py-3 text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{item.message || ''}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>

                        {/* Survey compliance grid */}
                        {surveyCompliance && (() => {
                            const cellColor = (weekData, isCurrent) => {
                                if (weekData.survey_submitted) return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200';
                                if (weekData.query_count === 0) return 'bg-zinc-100 dark:bg-zinc-700 text-zinc-400 dark:text-zinc-400';
                                if (isCurrent) return 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200';
                                return 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200';
                            };
                            return (
                                <>
                                <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow">
                                    <h2 className="text-lg font-bold dark:text-white mb-4">Survey Completion — Last 4 Weeks</h2>
                                    <div className="overflow-x-auto">
                                        <table className="min-w-full text-sm">
                                            <thead>
                                                <tr>
                                                    <th className="px-4 py-2 border-b-2 border-zinc-200 dark:border-zinc-700 text-left font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider whitespace-nowrap w-32">User</th>
                                                    {surveyCompliance.weeks.map((w, i) => (
                                                        <th key={i} className="px-4 py-2 border-b-2 border-zinc-200 dark:border-zinc-700 text-center font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider whitespace-nowrap">
                                                            {w.label}
                                                        </th>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {surveyCompliance.users.map(u => (
                                                    <tr key={u.user_id} className="border-b border-zinc-100 dark:border-zinc-700">
                                                        <td className="px-4 py-2 font-medium text-gray-800 dark:text-gray-200 whitespace-nowrap">{u.username}</td>
                                                        {u.weeks.map((w, i) => (
                                                            <td key={i} className="px-2 py-2 text-center">
                                                                <span className={`inline-block rounded px-2 py-1 text-xs font-semibold ${cellColor(w, surveyCompliance.weeks[i].is_current)}`}>
                                                                    {w.query_count} {w.query_count === 1 ? 'query' : 'queries'}
                                                                </span>
                                                            </td>
                                                        ))}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                    <div className="flex gap-4 mt-4 text-xs text-zinc-500 dark:text-zinc-400">
                                        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-green-200"></span> Survey submitted</span>
                                        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-yellow-200"></span> Active, survey pending</span>
                                        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-red-200"></span> Active, survey missed</span>
                                        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-zinc-200"></span> No activity</span>
                                    </div>
                                </div>

                                {/* Survey Non-completion table */}
                                {(() => {
                                    const nonCompleters = surveyCompliance.users.filter(u =>
                                        u.weeks.some((w, i) => !surveyCompliance.weeks[i].is_current && w.query_count > 0 && !w.survey_submitted)
                                    );
                                    const thNC = "px-4 py-2 border-b-2 border-zinc-200 dark:border-zinc-700 text-center font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider whitespace-nowrap text-xs";
                                    return (
                                        <div className="bg-white dark:bg-zinc-800 p-6 rounded-lg shadow mt-4">
                                            <h2 className="text-lg font-bold dark:text-white mb-4">Survey Non-completion — Last 4 Weeks</h2>
                                            {nonCompleters.length === 0 ? (
                                                <p className="text-sm text-green-600 dark:text-green-400">All active users have completed their weekly surveys.</p>
                                            ) : (
                                                <>
                                                    <div className="overflow-x-auto">
                                                        <table className="min-w-full text-sm">
                                                            <thead>
                                                                <tr>
                                                                    <th className="px-4 py-2 border-b-2 border-zinc-200 dark:border-zinc-700 text-left font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider whitespace-nowrap w-32 text-xs">User</th>
                                                                    {surveyCompliance.weeks.map((w, i) => (
                                                                        <th key={i} className={thNC}>{w.label}</th>
                                                                    ))}
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {nonCompleters.map(u => (
                                                                    <tr key={u.user_id} className="border-b border-zinc-100 dark:border-zinc-700">
                                                                        <td className="px-4 py-2 font-medium text-gray-800 dark:text-gray-200 whitespace-nowrap text-xs">{u.username}</td>
                                                                        {u.weeks.map((w, i) => {
                                                                            const isMissed = !surveyCompliance.weeks[i].is_current && w.query_count > 0 && !w.survey_submitted;
                                                                            return (
                                                                                <td key={i} className="px-2 py-2 text-center">
                                                                                    {isMissed ? (
                                                                                        <span className="inline-block rounded px-2 py-1 text-xs font-semibold bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200">
                                                                                            {w.query_count} {w.query_count === 1 ? 'query' : 'queries'}
                                                                                        </span>
                                                                                    ) : w.survey_submitted ? (
                                                                                        <span className="inline-block rounded px-2 py-1 text-xs font-semibold bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">✓</span>
                                                                                    ) : (
                                                                                        <span className="text-zinc-400 dark:text-zinc-500 text-xs">—</span>
                                                                                    )}
                                                                                </td>
                                                                            );
                                                                        })}
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                    <div className="flex gap-4 mt-4 text-xs text-zinc-500 dark:text-zinc-400">
                                                        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-red-200"></span> Active, survey missed</span>
                                                        <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-green-200"></span> Survey submitted</span>
                                                        <span className="flex items-center gap-1"><span className="text-zinc-400 mr-1">—</span> No activity</span>
                                                    </div>
                                                </>
                                            )}
                                        </div>
                                    );
                                })()}
                                </>
                            );
                        })()}
                    </div>
                    );
                })()}

            </div>
        </div>
    );
};

export default AdminPortal;
