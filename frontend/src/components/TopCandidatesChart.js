import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { memo, useMemo } from 'react';
import { BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, } from 'recharts';
function TopCandidatesChartComponent({ data }) {
    const chartData = useMemo(() => Object.entries(data)
        .map(([symbol, entry]) => ({
        symbol,
        score: entry.score,
    }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 10), [data]);
    if (!chartData.length) {
        return (_jsx("div", { className: "h-full w-full rounded-2xl border border-slate-800 bg-slate-900/50 p-6 text-sm text-slate-400", children: "\u041D\u0435\u0442 \u043A\u0430\u043D\u0434\u0438\u0434\u0430\u0442\u043E\u0432 \u0434\u043B\u044F \u043E\u0442\u043E\u0431\u0440\u0430\u0436\u0435\u043D\u0438\u044F." }));
    }
    return (_jsx("div", { className: "h-72 w-full rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: _jsx(ResponsiveContainer, { width: "100%", height: "100%", children: _jsxs(BarChart, { data: chartData, children: [_jsx(CartesianGrid, { strokeDasharray: "3 3", stroke: "#2c3250" }), _jsx(XAxis, { dataKey: "symbol", stroke: "#94a3b8", tick: { fill: '#cbd5f5', fontSize: 12 } }), _jsx(YAxis, { stroke: "#94a3b8", domain: [0, 100], tick: { fill: '#cbd5f5', fontSize: 12 } }), _jsx(Tooltip, { cursor: { fill: 'rgba(79, 96, 255, 0.08)' }, contentStyle: {
                            background: '#1f253b',
                            borderRadius: '12px',
                            border: '1px solid #303652',
                            color: '#fff',
                        } }), _jsx(Bar, { dataKey: "score", fill: "#4f60ff", radius: 8 })] }) }) }));
}
export const TopCandidatesChart = memo(TopCandidatesChartComponent);
