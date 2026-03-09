import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';
function formatDate(value) {
    if (!value)
        return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit',
    });
}
function formatNumber(value, fractionDigits = 2) {
    if (value === null || value === undefined)
        return '—';
    return value.toFixed(fractionDigits);
}
function formatDuration(seconds) {
    if (!seconds && seconds !== 0)
        return '—';
    const mins = Math.floor(seconds / 60);
    if (mins < 60) {
        return `${mins} мин`;
    }
    const hours = Math.floor(mins / 60);
    const rem = mins % 60;
    return `${hours} ч ${rem} мин`;
}
function getPnlClass(value) {
    if (value === null || value === undefined)
        return 'text-slate-300';
    if (value > 0)
        return 'text-emerald-300';
    if (value < 0)
        return 'text-rose-300';
    return 'text-slate-300';
}
export function TradeStatsTable({ records, loading }) {
    const [expanded, setExpanded] = useState(null);
    if (loading) {
        return (_jsx("div", { className: "flex h-48 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/60 text-sm text-slate-400", children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0438 \u0441\u0434\u0435\u043B\u043E\u043A\u2026" }));
    }
    if (!records.length) {
        return (_jsx("div", { className: "flex h-48 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/60 text-sm text-slate-400", children: "\u041F\u043E\u043A\u0430 \u043D\u0435\u0442 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D\u043D\u044B\u0445 \u0441\u0434\u0435\u043B\u043E\u043A \u0432 \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u043C \u0434\u0438\u0430\u043F\u0430\u0437\u043E\u043D\u0435." }));
    }
    return (_jsx("div", { className: "overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card", children: _jsxs("table", { className: "min-w-full divide-y divide-slate-800", children: [_jsx("thead", { className: "bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400", children: _jsxs("tr", { children: [_jsx("th", { className: "px-4 py-3 text-left", children: "\u041E\u0442\u043A\u0440\u044B\u0442\u0438\u0435" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0418\u043D\u0441\u0442\u0440\u0443\u043C\u0435\u043D\u0442" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0420\u0435\u0436\u0438\u043C" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0412\u0445\u043E\u0434 / \u0412\u044B\u0445\u043E\u0434" }), _jsx("th", { className: "px-4 py-3 text-left", children: "PnL" }), _jsx("th", { className: "px-4 py-3 text-left", children: "TP / SL" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0414\u043B\u0438\u0442\u0435\u043B\u044C\u043D\u043E\u0441\u0442\u044C" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u041A\u043E\u043C\u043C\u0435\u043D\u0442\u0430\u0440\u0438\u0439" })] }) }), _jsx("tbody", { className: "divide-y divide-slate-800 text-sm", children: records.map((record) => {
                        const isOpen = expanded === record.session_id;
                        return (_jsxs(_Fragment, { children: [_jsxs("tr", { className: "cursor-pointer hover:bg-slate-800/30", onClick: () => setExpanded((prev) => (prev === record.session_id ? null : record.session_id)), children: [_jsx("td", { className: "whitespace-nowrap px-4 py-3 text-slate-300", children: _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "inline-flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800/60 text-slate-300", children: isOpen ? _jsx(FiChevronUp, {}) : _jsx(FiChevronDown, {}) }), _jsxs("div", { children: [_jsx("div", { children: formatDate(record.opened_at) }), _jsxs("div", { className: "text-xs text-slate-500", children: ["\u0417\u0430\u043A\u0440\u044B\u0442\u0438\u0435: ", formatDate(record.closed_at)] })] })] }) }), _jsxs("td", { className: "px-4 py-3 text-slate-100", children: [_jsx("div", { className: "font-semibold text-white", children: record.symbol }), _jsxs("div", { className: "text-xs text-slate-500", children: [record.direction === 'long' ? 'Лонг' : 'Шорт', " \u2022 #", record.session_id.slice(-6)] })] }), _jsx("td", { className: "px-4 py-3 text-slate-300 capitalize", children: record.mode.replace('_', ' ') }), _jsxs("td", { className: "px-4 py-3 text-slate-300", children: [_jsxs("div", { children: [formatNumber(record.entry_price), " @ ", formatNumber(record.entry_qty, 3)] }), _jsxs("div", { className: "text-xs text-slate-500", children: ["\u2192 ", formatNumber(record.exit_price), " @ ", formatNumber(record.exit_qty, 3)] })] }), _jsxs("td", { className: `px-4 py-3 font-semibold ${getPnlClass(record.pnl_usdt)}`, children: [_jsxs("div", { children: [formatNumber(record.pnl_usdt), " USDT"] }), _jsxs("div", { className: "text-xs", children: [formatNumber(record.pnl_pct), " %"] }), _jsxs("div", { className: "text-xs text-slate-500", children: ["R/R: ", formatNumber(record.risk_reward_ratio)] })] }), _jsxs("td", { className: "px-4 py-3 text-slate-300", children: [_jsxs("div", { children: ["TP: ", formatNumber(record.target_price)] }), _jsxs("div", { children: ["SL: ", formatNumber(record.stop_price)] }), _jsxs("div", { className: "text-xs text-slate-500", children: ["TP hit: ", record.tp_hit ? 'да' : 'нет', " \u2022 SL hit: ", record.sl_hit ? 'да' : 'нет'] })] }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: formatDuration(record.duration_seconds) }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: record.comment ? (_jsx("span", { className: "block max-h-10 overflow-hidden break-words text-xs text-slate-400", children: record.comment })) : (_jsx("span", { className: "text-xs text-slate-500", children: "\u2014" })) })] }, record.session_id), isOpen ? (_jsx("tr", { className: "bg-slate-950/20", children: _jsx("td", { colSpan: 8, className: "px-4 py-4", children: _jsxs("div", { className: "grid gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-xs text-slate-300 md:grid-cols-2", children: [_jsxs("div", { className: "space-y-1", children: [_jsx("div", { className: "text-slate-500", children: "TP / SL" }), _jsxs("div", { children: ["TP: ", _jsx("span", { className: "text-slate-200", children: formatNumber(record.target_price) }), ' ', "(", record.tp_hit ? 'hit' : 'нет', ")"] }), _jsxs("div", { children: ["SL: ", _jsx("span", { className: "text-slate-200", children: formatNumber(record.stop_price) }), ' ', "(", record.sl_hit ? 'hit' : 'нет', ")"] })] }), _jsxs("div", { className: "space-y-1", children: [_jsx("div", { className: "text-slate-500", children: "Directive IDs" }), _jsxs("div", { className: "font-mono text-[11px] text-slate-200", children: ["entry: ", record.entry_directive_id || '—'] }), _jsxs("div", { className: "font-mono text-[11px] text-slate-200", children: ["exit: ", record.exit_directive_id || '—'] })] }), _jsxs("div", { className: "space-y-1 md:col-span-2", children: [_jsx("div", { className: "text-slate-500", children: "\u041A\u043E\u043C\u043C\u0435\u043D\u0442\u0430\u0440\u0438\u0439" }), _jsx("div", { className: "whitespace-pre-wrap text-slate-200", children: record.comment || '—' })] })] }) }) }, `${record.session_id}-details`)) : null] }));
                    }) })] }) }));
}
