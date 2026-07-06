import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { buildSurveyComplianceChartData } from './surveyData';

export const WeeklySurveyComplianceChart = ({ surveyCompliance }) => {
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
            <h3 className="text-sm font-bold mb-3">Weekly Survey Submissions</h3>
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
