import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';
function formatTimestamp(value) {
    if (!value)
        return '—';
    const date = new Date(value);
    return date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}
function formatNumber(value, fractionDigits = 2) {
    const num = typeof value === 'number' ? value : value === null || value === undefined ? null : Number(value);
    if (num === null || Number.isNaN(num))
        return '—';
    return num.toFixed(fractionDigits);
}
function isRecord(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
function snapshotSummary(payload) {
    const symbol = typeof payload.symbol === 'string' ? payload.symbol : null;
    const score = payload.market_score ?? payload.score;
    const status = typeof payload.status === 'string' ? payload.status : null;
    const timestamp = typeof payload.timestamp === 'string' ? payload.timestamp : null;
    const metrics = isRecord(payload.metrics) ? payload.metrics : null;
    if (!symbol && !metrics)
        return null;
    const lastPrice = metrics?.last_price;
    const funding = metrics?.funding_rate;
    const volume = metrics?.volume_24h;
    const openInterest = metrics?.open_interest;
    return {
        symbol,
        score,
        status,
        timestamp,
        lastPrice,
        funding,
        volume,
        openInterest,
    };
}
export function AuditLog({ events }) {
    const summary = useMemo(() => {
        const total = events.length;
        const uniqueStreams = new Set(events.map((event) => event.stream)).size;
        const latest = events[0]?.created_at ?? null;
        return { total, uniqueStreams, latest };
    }, [events]);
    const [expanded, setExpanded] = useState(false);
    return (_jsxs("section", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card", children: [_jsxs("header", { className: "flex flex-col gap-3 border-b border-slate-800 px-6 py-4 md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-lg font-semibold text-white", children: "\u0410\u0443\u0434\u0438\u0442 \u0441\u043E\u0431\u044B\u0442\u0438\u0439" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u0425\u0440\u043E\u043D\u043E\u043B\u043E\u0433\u0438\u044F \u0441\u0438\u0433\u043D\u0430\u043B\u043E\u0432 \u0438 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0439 \u0441\u0438\u0441\u0442\u0435\u043C\u044B" })] }), _jsxs("div", { className: "flex flex-col items-start gap-3 md:items-end", children: [_jsxs("div", { className: "flex flex-wrap gap-2", children: [_jsx(SummaryBadge, { label: "\u0417\u0430\u043F\u0438\u0441\u0435\u0439", value: summary.total }), _jsx(SummaryBadge, { label: "\u041F\u043E\u0442\u043E\u043A\u043E\u0432", value: summary.uniqueStreams }), _jsx(SummaryBadge, { label: "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0435\u0435", value: summary.latest ? Date.parse(summary.latest) : null, render: (val) => typeof val === 'number'
                                            ? formatTimestamp(new Date(val).toISOString())
                                            : '—' })] }), _jsxs("button", { type: "button", onClick: () => setExpanded((value) => !value), className: "inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [expanded ? _jsx(FiChevronUp, { className: "text-base" }) : _jsx(FiChevronDown, { className: "text-base" }), expanded ? 'Скрыть журнал' : 'Показать журнал'] })] })] }), expanded && (_jsx("div", { className: "max-h-[28rem] overflow-y-auto", children: events.length === 0 ? (_jsx("p", { className: "px-6 py-4 text-sm text-slate-400", children: "\u0416\u0443\u0440\u043D\u0430\u043B \u043F\u0443\u0441\u0442." })) : (_jsx("ul", { className: "divide-y divide-slate-800", children: events.slice(0, 50).map((event) => {
                        const summary = snapshotSummary(event.payload);
                        const headerSymbol = summary?.symbol;
                        const headerTime = summary?.timestamp ?? event.created_at;
                        return (_jsx("li", { className: "px-6 py-4", children: _jsxs("details", { className: "group rounded-2xl bg-slate-950/30 p-3", children: [_jsxs("summary", { className: "flex cursor-pointer list-none flex-col gap-2", children: [_jsxs("div", { className: "flex items-center justify-between text-xs text-slate-400", children: [_jsx("span", { className: "rounded-full bg-slate-800 px-2 py-1 font-mono text-[11px] uppercase tracking-wide text-indigo-300", children: event.stream }), _jsx("span", { children: formatTimestamp(headerTime) })] }), _jsxs("div", { className: "flex flex-wrap items-center justify-between gap-2", children: [_jsx("div", { className: "text-sm font-semibold text-white", children: headerSymbol ? `${headerSymbol} • ${event.event_type}` : event.event_type }), _jsxs("div", { className: "flex items-center gap-2 text-xs text-slate-400", children: [_jsx("span", { className: "hidden group-open:inline-flex", children: _jsx(FiChevronUp, { className: "text-base" }) }), _jsx("span", { className: "inline-flex group-open:hidden", children: _jsx(FiChevronDown, { className: "text-base" }) })] })] }), summary ? (_jsxs("div", { className: "grid gap-2 text-xs text-slate-400 sm:grid-cols-2 lg:grid-cols-4", children: [_jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: "Score:" }), ' ', _jsx("span", { className: "text-slate-200", children: formatNumber(summary.score, 2) })] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: "\u0421\u0442\u0430\u0442\u0443\u0441:" }), ' ', _jsx("span", { className: "text-slate-200", children: summary.status ?? '—' })] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: "\u0426\u0435\u043D\u0430:" }), ' ', _jsx("span", { className: "text-slate-200", children: formatNumber(summary.lastPrice, 4) })] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: "Funding:" }), ' ', _jsx("span", { className: "text-slate-200", children: formatNumber(summary.funding, 6) })] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: "Volume 24h:" }), ' ', _jsx("span", { className: "text-slate-200", children: formatNumber(summary.volume, 2) })] }), _jsxs("div", { children: [_jsx("span", { className: "text-slate-500", children: "OI:" }), ' ', _jsx("span", { className: "text-slate-200", children: formatNumber(summary.openInterest, 2) })] })] })) : null] }), _jsx("pre", { className: "mt-3 overflow-x-auto rounded-xl bg-slate-950/60 p-3 text-xs text-slate-300", children: JSON.stringify(event.payload, null, 2) })] }) }, event.id));
                    }) })) }))] }));
}
function SummaryBadge({ label, value, render }) {
    const content = render
        ? render(value)
        : value === null || Number.isNaN(value)
            ? '—'
            : value.toLocaleString('ru-RU', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
            });
    return (_jsxs("div", { className: "rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2", children: [_jsx("div", { className: "text-[11px] uppercase tracking-wide text-slate-400", children: label }), _jsx("div", { className: "text-sm font-semibold text-white", children: content })] }));
}
