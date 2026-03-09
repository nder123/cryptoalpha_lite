import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo } from 'react';
const BUCKET_ORDER = ['ignored', 'watch', 'candidate', 'active'];
const BUCKET_META = {
    ignored: {
        title: 'Игнорируемые',
        accent: 'from-slate-800 to-slate-900',
        description: 'Символы вне зоны интереса CTO-AI',
    },
    watch: {
        title: 'Наблюдение',
        accent: 'from-sky-900 to-indigo-900',
        description: 'Символы под пассивным контролем',
    },
    candidate: {
        title: 'Кандидаты',
        accent: 'from-amber-900 to-amber-700',
        description: 'Подготовленные гипотезы к торгам',
    },
    active: {
        title: 'Активные',
        accent: 'from-emerald-900 to-emerald-700',
        description: 'Текущие позиции и сопровождаемые сделки',
    },
};
function formatScore(score) {
    if (typeof score !== 'number')
        return '—';
    return `${Math.round(score)}`;
}
export function MarketOverview({ market }) {
    const data = useMemo(() => {
        return BUCKET_ORDER.map((key) => {
            const entries = Object.entries(market[key]);
            const sorted = entries.sort(([, a], [, b]) => b.score - a.score);
            const top = sorted.slice(0, 3);
            return {
                key,
                count: entries.length,
                top,
            };
        });
    }, [market]);
    return (_jsx("div", { className: "grid gap-4 xl:grid-cols-4", children: data.map(({ key, count, top }) => {
            const meta = BUCKET_META[key];
            return (_jsxs("div", { className: "relative overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-card", children: [_jsx("div", { className: `absolute inset-0 opacity-40`, children: _jsx("div", { className: `absolute inset-0 bg-gradient-to-br ${meta.accent}` }) }), _jsxs("div", { className: "relative space-y-4", children: [_jsxs("div", { className: "flex items-baseline justify-between", children: [_jsx("h3", { className: "text-lg font-semibold text-white", children: meta.title }), _jsx("span", { className: "text-3xl font-bold text-slate-100", children: count })] }), _jsx("p", { className: "text-sm text-slate-300", children: meta.description }), _jsx("div", { className: "space-y-3", children: top.length ? (top.map(([symbol, entry]) => (_jsxs("div", { className: "flex items-center justify-between rounded-xl bg-slate-900/70 px-3 py-2", children: [_jsxs("div", { children: [_jsx("div", { className: "text-sm font-semibold text-slate-100", children: symbol }), entry.rationale.length > 0 && (_jsx("p", { className: "text-xs text-slate-400", children: entry.rationale[0] }))] }), _jsx("span", { className: "text-sm font-semibold text-indigo-200", children: formatScore(entry.score) })] }, symbol)))) : (_jsx("p", { className: "text-sm text-slate-400", children: "\u041D\u0435\u0442 \u0437\u0430\u043F\u0438\u0441\u0435\u0439" })) })] })] }, key));
        }) }));
}
