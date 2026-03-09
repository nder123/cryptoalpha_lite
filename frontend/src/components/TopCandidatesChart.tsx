import { memo, useMemo } from 'react';
import {
    BarChart,
    Bar,
    CartesianGrid,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
} from 'recharts';

import type { MarketBucketEntry } from '../types';

type Props = {
    data: Record<string, MarketBucketEntry>;
};

function TopCandidatesChartComponent({ data }: Props) {
    const chartData = useMemo(
        () =>
            Object.entries(data)
                .map(([symbol, entry]) => ({
                    symbol,
                    score: entry.score,
                }))
                .sort((a, b) => b.score - a.score)
                .slice(0, 10),
        [data]
    );

    if (!chartData.length) {
        return (
            <div className="h-full w-full rounded-2xl border border-slate-800 bg-slate-900/50 p-6 text-sm text-slate-400">
                Нет кандидатов для отображения.
            </div>
        );
    }

    return (
        <div className="h-72 w-full rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2c3250" />
                    <XAxis dataKey="symbol" stroke="#94a3b8" tick={{ fill: '#cbd5f5', fontSize: 12 }} />
                    <YAxis stroke="#94a3b8" domain={[0, 100]} tick={{ fill: '#cbd5f5', fontSize: 12 }} />
                    <Tooltip
                        cursor={{ fill: 'rgba(79, 96, 255, 0.08)' }}
                        contentStyle={{
                            background: '#1f253b',
                            borderRadius: '12px',
                            border: '1px solid #303652',
                            color: '#fff',
                        }}
                    />
                    <Bar dataKey="score" fill="#4f60ff" radius={8} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}

export const TopCandidatesChart = memo(TopCandidatesChartComponent);
