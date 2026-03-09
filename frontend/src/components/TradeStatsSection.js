import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { FiRefreshCcw, FiDownload, FiChevronDown, FiChevronUp } from 'react-icons/fi';
import { useTradeStats } from '../hooks/useTradeStats';
import { TradeStatsSummaryCards } from './TradeStatsSummaryCards';
import { TradeStatsTable } from './TradeStatsTable';
function formatMetricValue(value, fractionDigits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return '—';
    }
    return value.toLocaleString('ru-RU', {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    });
}
function SummaryBadge({ label, value, unit, fractionDigits = 2, trend }) {
    const formatted = formatMetricValue(value, fractionDigits);
    const display = formatted === '—' ? formatted : unit ? `${formatted} ${unit}` : formatted;
    let toneClass = 'text-white';
    if (value === null || value === undefined || Number.isNaN(value)) {
        toneClass = 'text-slate-300';
    }
    else if (trend === 'goodIfPositive') {
        toneClass = value >= 0 ? 'text-emerald-200' : 'text-rose-300';
    }
    else if (trend === 'goodIfNegative') {
        toneClass = value <= 0 ? 'text-emerald-200' : 'text-rose-300';
    }
    return (_jsxs("div", { className: "rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2", children: [_jsx("div", { className: "text-[11px] uppercase tracking-wide text-slate-400", children: label }), _jsx("div", { className: `text-sm font-semibold ${toneClass}`, children: display })] }));
}
function formatDateInput(value) {
    if (!value)
        return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    const iso = date.toISOString();
    return iso.slice(0, 16);
}
export function TradeStatsSection() {
    const { filters, records, total, summary, daily, weekly, loading, error, updateFilters, resetFilters, refresh, exportCsv, exporting, } = useTradeStats();
    const [expanded, setExpanded] = useState(false);
    const summaryMetrics = useMemo(() => {
        const totalPnl = summary?.total_pnl_usdt ?? null;
        const winRate = summary ? summary.win_rate * 100 : null;
        const totalTrades = summary?.total_trades ?? total;
        const avgRr = summary?.avg_rr ?? null;
        const winning = summary?.winning_trades ?? null;
        return [
            { label: 'PnL', value: totalPnl, unit: 'USDT', trend: 'goodIfPositive' },
            { label: 'Win rate', value: winRate, unit: '%', fractionDigits: 1, trend: 'goodIfPositive' },
            { label: 'Сделок всего', value: totalTrades, fractionDigits: 0 },
            { label: 'В плюсе', value: winning, fractionDigits: 0, trend: 'goodIfPositive' },
            { label: 'Средний R/R', value: avgRr, fractionDigits: 2, trend: 'goodIfPositive' },
        ];
    }, [summary, total]);
    return (_jsxs("section", { className: "space-y-6", children: [_jsxs("div", { className: "rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card", children: [_jsxs("div", { className: "flex flex-col gap-4 md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-2xl font-semibold text-white", children: "\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u0430 \u0441\u0434\u0435\u043B\u043E\u043A" }), _jsx("p", { className: "mt-1 text-sm text-slate-400", children: "\u0410\u0432\u0442\u043E\u043C\u0430\u0442\u0438\u0447\u0435\u0441\u043A\u0438\u0439 \u0436\u0443\u0440\u043D\u0430\u043B \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D\u043D\u044B\u0445 \u0441\u0434\u0435\u043B\u043E\u043A \u0441 PnL, R/R \u0438 \u043F\u043E\u043F\u0430\u0434\u0430\u043D\u0438\u044F\u043C\u0438 \u043F\u043E TP/SL. \u0424\u043E\u0440\u043C\u0438\u0440\u0443\u0435\u0442\u0441\u044F \u0438\u0437 \u043E\u0442\u0447\u0451\u0442\u043E\u0432 Execution Engine." })] }), _jsxs("div", { className: "flex flex-col items-start gap-3 md:items-end", children: [_jsx("div", { className: "flex flex-wrap gap-2", children: summaryMetrics.map((metric) => (_jsx(SummaryBadge, { ...metric }, metric.label))) }), _jsxs("div", { className: "flex flex-wrap gap-2 text-sm", children: [_jsxs("button", { type: "button", onClick: refresh, className: "inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [_jsx(FiRefreshCcw, { className: "text-base" }), "\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C"] }), _jsxs("button", { type: "button", disabled: exporting, onClick: exportCsv, className: `inline-flex items-center gap-2 rounded-full px-4 py-2 transition ${exporting
                                                    ? 'cursor-not-allowed border border-slate-700 bg-slate-800 text-slate-500'
                                                    : 'border border-emerald-400/60 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20'}`, children: [_jsx(FiDownload, { className: "text-base" }), "\u042D\u043A\u0441\u043F\u043E\u0440\u0442 CSV"] }), _jsxs("button", { type: "button", onClick: () => setExpanded((value) => !value), className: "inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [expanded ? _jsx(FiChevronUp, { className: "text-base" }) : _jsx(FiChevronDown, { className: "text-base" }), expanded ? 'Скрыть журнал' : 'Показать журнал'] })] })] })] }), _jsxs("div", { className: "mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4", children: [_jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0414\u0430\u0442\u0430 \u043D\u0430\u0447\u0430\u043B\u0430", _jsx("input", { type: "datetime-local", value: formatDateInput(filters.start), onChange: (event) => updateFilters({ start: event.target.value ? new Date(event.target.value).toISOString() : null }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0414\u0430\u0442\u0430 \u043E\u043A\u043E\u043D\u0447\u0430\u043D\u0438\u044F", _jsx("input", { type: "datetime-local", value: formatDateInput(filters.end), onChange: (event) => updateFilters({ end: event.target.value ? new Date(event.target.value).toISOString() : null }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0421\u0438\u043C\u0432\u043E\u043B", _jsx("input", { type: "text", value: filters.symbol, onChange: (event) => updateFilters({ symbol: event.target.value.toUpperCase() }), placeholder: "\u041D\u0430\u043F\u0440\u0438\u043C\u0435\u0440, BTCUSDT", className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("div", { className: "flex items-end gap-2", children: [_jsx("button", { type: "button", onClick: resetFilters, className: "rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C \u0444\u0438\u043B\u044C\u0442\u0440\u044B" }), _jsxs("div", { className: "text-xs text-slate-500", children: ["\u0421\u0434\u0435\u043B\u043E\u043A: ", total] })] })] }), error && _jsx("div", { className: "mt-4 rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200", children: error })] }), expanded ? (_jsx("div", { className: "max-h-[520px] overflow-auto rounded-2xl border border-slate-800 bg-slate-950/50 shadow-card", children: _jsx(TradeStatsTable, { records: records, loading: loading }) })) : null, _jsx(TradeStatsSummaryCards, { summary: summary, loading: loading }), _jsxs("div", { className: "grid gap-4 md:grid-cols-2", children: [_jsxs("div", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-sm font-semibold text-white", children: "PnL \u043F\u043E \u0434\u043D\u044F\u043C" }), _jsx("ul", { className: "mt-3 space-y-2 text-sm text-slate-300", children: daily.length ? (daily.map((entry, index) => {
                                    const dateLabel = entry.period_start
                                        ? new Date(entry.period_start).toLocaleDateString('ru-RU')
                                        : '—';
                                    const pnlValue = entry.pnl_usdt ?? null;
                                    const pnlClass = pnlValue === null
                                        ? 'text-slate-400'
                                        : pnlValue < 0
                                            ? 'text-rose-300'
                                            : pnlValue > 0
                                                ? 'text-emerald-300'
                                                : 'text-slate-300';
                                    return (_jsxs("li", { className: "flex items-center justify-between", children: [_jsx("span", { className: "text-xs text-slate-500", children: dateLabel }), _jsxs("span", { className: `font-medium ${pnlClass}`, children: [pnlValue !== null ? pnlValue.toFixed(2) : '—', " USDT"] })] }, entry.period_start ?? `daily-${index}`));
                                })) : (_jsx("li", { className: "text-xs text-slate-500", children: "\u041D\u0435\u0442 \u0434\u0430\u043D\u043D\u044B\u0445 \u0434\u043B\u044F \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u0433\u043E \u043F\u0435\u0440\u0438\u043E\u0434\u0430." })) })] }), _jsxs("div", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-sm font-semibold text-white", children: "PnL \u043F\u043E \u043D\u0435\u0434\u0435\u043B\u044F\u043C" }), _jsx("ul", { className: "mt-3 space-y-2 text-sm text-slate-300", children: weekly.length ? (weekly.map((entry, index) => {
                                    const dateLabel = entry.period_start
                                        ? new Date(entry.period_start).toLocaleDateString('ru-RU')
                                        : '—';
                                    const pnlValue = entry.pnl_usdt ?? null;
                                    const pnlClass = pnlValue === null
                                        ? 'text-slate-400'
                                        : pnlValue < 0
                                            ? 'text-rose-300'
                                            : pnlValue > 0
                                                ? 'text-emerald-300'
                                                : 'text-slate-300';
                                    return (_jsxs("li", { className: "flex items-center justify-between", children: [_jsx("span", { className: "text-xs text-slate-500", children: dateLabel }), _jsxs("span", { className: `font-medium ${pnlClass}`, children: [pnlValue !== null ? pnlValue.toFixed(2) : '—', " USDT"] })] }, entry.period_start ?? `weekly-${index}`));
                                })) : (_jsx("li", { className: "text-xs text-slate-500", children: "\u041D\u0435\u0442 \u0434\u0430\u043D\u043D\u044B\u0445 \u0434\u043B\u044F \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u0433\u043E \u043F\u0435\u0440\u0438\u043E\u0434\u0430." })) })] })] })] }));
}
