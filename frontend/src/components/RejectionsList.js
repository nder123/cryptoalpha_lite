import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';
export function RejectionsList({ rejections }) {
    const summary = useMemo(() => {
        const total = rejections.length;
        const uniqueHypotheses = new Set(rejections.map((item) => item.hypothesis_id)).size;
        const uniqueSymbols = new Set(rejections.map((item) => item.symbol)).size;
        const lastTimestamp = rejections[rejections.length - 1]?.created_at ?? null;
        return { total, uniqueHypotheses, uniqueSymbols, lastTimestamp };
    }, [rejections]);
    const [expanded, setExpanded] = useState(false);
    return (_jsxs("section", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card", children: [_jsxs("header", { className: "flex flex-col gap-3 border-b border-slate-800 px-6 py-4 md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-lg font-semibold text-white", children: "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 \u043E\u0442\u043A\u043B\u043E\u043D\u0435\u043D\u0438\u044F" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u041E\u0431\u043E\u0441\u043D\u043E\u0432\u0430\u043D\u0438\u044F \u0440\u0435\u0448\u0435\u043D\u0438\u0439 Risk/CTO-AI" })] }), _jsxs("div", { className: "flex flex-col items-start gap-3 md:items-end", children: [_jsxs("div", { className: "flex flex-wrap gap-2", children: [_jsx(SummaryBadge, { label: "\u0412\u0441\u0435\u0433\u043E", value: summary.total, fractionDigits: 0 }), _jsx(SummaryBadge, { label: "\u0413\u0438\u043F\u043E\u0442\u0435\u0437", value: summary.uniqueHypotheses, fractionDigits: 0 }), _jsx(SummaryBadge, { label: "\u0418\u043D\u0441\u0442\u0440\u0443\u043C\u0435\u043D\u0442\u043E\u0432", value: summary.uniqueSymbols, fractionDigits: 0 }), _jsx(SummaryBadge, { label: "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0435\u0435", value: summary.lastTimestamp ? Date.parse(summary.lastTimestamp) : null, render: (val) => typeof val === 'number'
                                            ? new Date(val).toLocaleTimeString('ru-RU', {
                                                hour: '2-digit',
                                                minute: '2-digit',
                                                second: '2-digit',
                                            })
                                            : '—' })] }), _jsxs("button", { type: "button", onClick: () => setExpanded((value) => !value), className: "inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [expanded ? _jsx(FiChevronUp, { className: "text-base" }) : _jsx(FiChevronDown, { className: "text-base" }), expanded ? 'Скрыть список' : 'Показать детали'] })] })] }), expanded && (_jsx("div", { className: "max-h-80 overflow-y-auto px-6 py-4", children: rejections.length === 0 ? (_jsx("p", { className: "text-sm text-slate-400", children: "\u041F\u043E\u043A\u0430 \u0432\u0441\u0451 \u0447\u0438\u0441\u0442\u043E. \u0420\u0438\u0441\u043A\u0438 \u043D\u0435 \u0437\u0430\u0431\u043B\u043E\u043A\u0438\u0440\u043E\u0432\u0430\u043B\u0438 \u0441\u0434\u0435\u043B\u043A\u0438." })) : (_jsx("ul", { className: "space-y-4", children: rejections
                        .slice(-20)
                        .reverse()
                        .map((item) => (_jsxs("li", { className: "space-y-2 rounded-xl bg-slate-900/80 p-3", children: [_jsxs("div", { className: "flex items-center justify_between text-sm text-indigo-200", children: [_jsx("span", { className: "font-semibold text-slate-100", children: item.symbol }), _jsx("span", { className: "text-xs text-slate-400", children: new Date(item.created_at).toLocaleTimeString('ru-RU', {
                                            hour: '2-digit',
                                            minute: '2-digit',
                                            second: '2-digit',
                                        }) })] }), _jsx("ul", { className: "list-disc space-y-1 pl-4 text-xs text-slate-300", children: item.reasons.map((reason, index) => (_jsx("li", { children: reason }, index))) })] }, `${item.hypothesis_id}-${item.created_at}`))) })) }))] }));
}
function SummaryBadge({ label, value, fractionDigits = 0, render }) {
    const content = render
        ? render(value)
        : value === null || Number.isNaN(value)
            ? '—'
            : value.toLocaleString('ru-RU', {
                minimumFractionDigits: fractionDigits,
                maximumFractionDigits: fractionDigits,
            });
    return (_jsxs("div", { className: "rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2", children: [_jsx("div", { className: "text-[11px] uppercase tracking-wide text-slate-400", children: label }), _jsx("div", { className: "text-sm font-semibold text-white", children: content })] }));
}
