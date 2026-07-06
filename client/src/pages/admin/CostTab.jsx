import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend } from 'recharts';
import Spinner from '../../components/ui/Spinner';
import InfoTip from '../../components/ui/InfoTip';
import { fmtMs, fmtUsd, COST_COLORS } from './chartConfig';

export const CostTab = ({ costStats, costTimeframe, setCostTimeframe }) => {
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


export default CostTab;
