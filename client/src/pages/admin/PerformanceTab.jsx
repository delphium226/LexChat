import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend } from 'recharts';
import Spinner from '../../components/ui/Spinner';
import InfoTip from '../../components/ui/InfoTip';
import { fmtMs, PERF_COLORS } from './chartConfig';

export const PerformanceTab = ({ perfStats, perfTimeframe, setPerfTimeframe }) => {
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
            <div className="flex justify-between items-center bg-paper p-4 rounded-lg shadow">
                <h2 className="text-lg font-bold">Query Performance</h2>
                <div className="flex items-center space-x-2">
                    <label className="text-sm text-ink-500 font-medium">Timeframe:</label>
                    <select
                        value={perfTimeframe}
                        onChange={(e) => setPerfTimeframe(e.target.value)}
                        className="p-2 border rounded-md text-sm focus:ring-2 focus:ring-blue-500"
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
                <div className="bg-paper p-4 rounded-lg shadow">
                    <h3 className="text-ink-500 text-xs font-bold uppercase flex items-center">
                        Queries Processed
                        <InfoTip text="The total number of chat queries processed by the system in the selected period. Each time a user sends a message and the AI generates a response counts as one query. A conversation with multiple back-and-forth exchanges counts as multiple queries — one per user message. Failed requests that never reached the AI model are not included." />
                    </h3>
                    <p className="text-2xl font-bold">{kpi.totalRequests}</p>
                    <p className="text-xs text-ink-400 mt-1">{timeframeLabel}</p>
                </div>
                <div className="bg-paper p-4 rounded-lg shadow">
                    <h3 className="text-ink-500 text-xs font-bold uppercase flex items-center">
                        Average Response Time
                        <InfoTip text="Mean end-to-end time from when the HTTP request arrived at the server to when the final response token was streamed to the browser. Covers all phases: queue wait, AI model inference, LEX API lookups, and server overhead. For legal research queries, 10–30 seconds is typical; complex multi-search queries can exceed a minute. A rising average over time usually points to growing concurrent load or degraded AI model performance." />
                    </h3>
                    <p className="text-2xl font-bold text-accent">{fmtMs(kpi.avgTotalMs)}</p>
                    <p className="text-xs text-ink-400 mt-1 flex items-center">
                        P95: {fmtMs(kpi.p95TotalMs)}
                        <InfoTip text="95th-percentile response time: 95 out of every 100 queries completed faster than this value. A useful measure of worst-case user experience that is not skewed by rare extreme outliers. If P95 is much higher than the average — e.g. average is 15s but P95 is 60s — it means a minority of queries are dramatically slower, often those involving many sequential LEX API searches or very long conversation histories fed into the AI model." />
                    </p>
                </div>
                <div className="bg-paper p-4 rounded-lg shadow">
                    <h3 className="text-ink-500 text-xs font-bold uppercase flex items-center">
                        AI Model Calls per Query
                        <InfoTip text="Average number of separate round-trips made to the AI language model (mistral-large via Ollama) per query. AILA uses a Manager-Worker agent loop: the Manager calls the model to plan a research strategy, the Worker calls it to decide which LEX API searches to run, and both call it again after each tool result to interpret findings and decide whether more research is needed. A simple factual question may need 2–3 calls; a complex research task spanning multiple statutes or case law areas may need 6 or more. Higher call counts directly increase total response time and model load." />
                    </h3>
                    <p className="text-2xl font-bold text-indigo-600">{kpi.avgLlmCalls}</p>
                    <p className="text-xs text-ink-400 mt-1 flex items-center">
                        Avg first-token delay: {fmtMs(kpi.avgTtftMs)}
                        <InfoTip text="Average Time to First Token (TTFT): how long from when the server sent the prompt to the AI model until the model produced its very first output token. Before any output appears, the model must load the full prompt into its context window (including conversation history and tool results) and begin generation. A high TTFT — e.g. over 10 seconds — usually means the AI model is under heavy concurrent load, processing an unusually large input context, or the GPU is throttling. This directly affects perceived responsiveness, since the user sees a blank screen until TTFT elapses." />
                    </p>
                </div>
                <div className="bg-paper p-4 rounded-lg shadow">
                    <h3 className="text-ink-500 text-xs font-bold uppercase flex items-center">
                        Legal Database Lookups per Query
                        <InfoTip text="Average number of HTTP calls made to the LEX API — the UK government's authoritative database of legislation, statutory instruments, and court judgments — per query. Each lookup retrieves documents the agent uses to build its answer. Simple queries about a well-known Act may need only 1–2 lookups; broad research questions spanning multiple statutes or areas of case law may trigger 5 or more. Each lookup adds latency proportional to the LEX server's response time and the size of documents returned." />
                    </h3>
                    <p className="text-2xl font-bold text-amber-600">{kpi.avgLexCalls}</p>
                    <p className="text-xs text-ink-400 mt-1 flex items-center">
                        Avg lookup time: {fmtMs(kpi.avgLexMs)}
                        <InfoTip text="Average total time spent waiting for all LEX API responses within a single query, accumulated across all lookups. Since the LEX API is an external HTTP service, its latency depends on network conditions, server load at the legal database, and the size of document payloads returned. On an air-gapped network, high values typically point to LEX server load or large result sets rather than internet issues. A query with 5 lookups each taking 500ms will show approximately 2.5s here." />
                    </p>
                </div>
            </div>

            {/* CHARTS ROW */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Response Time Trend */}
                <div className="bg-paper p-6 rounded-lg shadow">
                    <h2 className="text-sm font-bold mb-4 flex items-center">
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
                        <div className="h-56 flex items-center justify-center text-ink-400 text-sm">No data for this period.</div>
                    )}
                </div>

                {/* Stacked Time Breakdown */}
                <div className="bg-paper p-6 rounded-lg shadow">
                    <h2 className="text-sm font-bold mb-4 flex items-center">
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
                        <div className="h-56 flex items-center justify-center text-ink-400 text-sm">No data for this period.</div>
                    )}
                </div>
            </div>

            {/* LLM Calls Distribution + Avg breakdown summary */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* LLM calls distribution */}
                <div className="bg-paper p-6 rounded-lg shadow">
                    <h2 className="text-sm font-bold mb-1 flex items-center">
                        AI Model Calls per Query — Distribution
                        <InfoTip text="Frequency histogram showing how many queries required each number of AI model calls. The x-axis is the call count; the y-axis is the number of queries with that count. A cluster at low numbers (1–3) means most queries were straightforward; a long tail at 5+ means users are asking complex multi-step research questions that required many search-and-interpret cycles. This distribution helps you understand typical agent workload and anticipate scaling needs." />
                    </h2>
                    <p className="text-xs text-ink-500 mb-4">Each call = one round-trip to the AI model. More calls = the agent performed more research tool loops.</p>
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
                        <div className="h-48 flex items-center justify-center text-ink-400 text-sm">No data.</div>
                    )}
                </div>

                {/* Time breakdown summary card */}
                <div className="bg-paper p-6 rounded-lg shadow">
                    <h2 className="text-sm font-bold mb-4 flex items-center">
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
                                            <span className="font-medium flex items-center" style={{ color }}>{label}<InfoTip text={tooltip} /></span>
                                            <span className="text-ink-500">{fmtMs(ms)} ({pct}%)</span>
                                        </div>
                                        <div className="w-full bg-ink-100 rounded-full h-2">
                                            <div className="h-2 rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
                                        </div>
                                    </div>
                                );
                            })}
                            <div className="pt-2 border-t flex justify-between text-xs font-bold">
                                <span>Total</span>
                                <span>{fmtMs(kpi.avgTotalMs)}</span>
                            </div>
                        </div>
                    ) : (
                        <div className="h-48 flex items-center justify-center text-ink-400 text-sm">No data.</div>
                    )}
                </div>
            </div>

            {/* Slowest Queries Table */}
            <div className="bg-paper p-6 rounded-lg shadow">
                <h2 className="text-sm font-bold mb-4 flex items-center">
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
                                        <th key={label} className="px-3 py-2 border-b-2 border-ink-200 text-left font-semibold text-ink-500 uppercase tracking-wider whitespace-nowrap">
                                            <span className="flex items-center gap-0.5">{label}<InfoTip text={tip} /></span>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {slowest.map((row) => (
                                    <tr key={row.requestId} className="border-b border-ink-100">
                                        <td className="px-3 py-3 font-mono">{row.requestId}</td>
                                        <td className="px-3 py-3 text-ink-500 whitespace-nowrap">{new Date(row.createdAt).toLocaleString()}</td>
                                        <td className="px-3 py-3 font-bold text-red-600 dark:text-red-400 whitespace-nowrap">{fmtMs(row.totalMs)}</td>
                                        <td className="px-3 py-3">{row.llmCalls}</td>
                                        <td className="px-3 py-3 text-indigo-600 dark:text-indigo-400 whitespace-nowrap">{fmtMs(row.llmMs)}</td>
                                        <td className="px-3 py-3">{row.lexCalls}</td>
                                        <td className="px-3 py-3 text-amber-600 dark:text-amber-400 whitespace-nowrap">{fmtMs(row.lexMs)}</td>
                                        <td className="px-3 py-3 text-emerald-600 dark:text-emerald-400 whitespace-nowrap">{fmtMs(row.ttftMs)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <p className="text-ink-400 text-sm">No slow queries recorded yet.</p>
                )}
            </div>
        </div>
    );
};


export default PerformanceTab;
