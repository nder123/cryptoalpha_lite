import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';
function formatNumber(value, fractionDigits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return '—';
    }
    return value.toLocaleString('ru-RU', {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    });
}
function SummaryBadge({ label, value, unit, fractionDigits = 2, trend }) {
    const formatted = value === null ? '—' : formatNumber(value, fractionDigits);
    const display = formatted === '—' ? formatted : unit ? `${formatted} ${unit}` : formatted;
    let toneClass = 'text-white';
    if (value === null) {
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
export function ExchangePositionsTable({ positions }) {
    if (!positions.length) {
        return (_jsxs("section", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card", children: [_jsx("h3", { className: "text-lg font-semibold text-white", children: "\u041E\u0442\u043A\u0440\u044B\u0442\u044B\u0435 \u043F\u043E\u0437\u0438\u0446\u0438\u0438 (\u0431\u0438\u0440\u0436\u0430)" }), _jsx("p", { className: "mt-3 text-sm text-slate-400", children: "\u041D\u0430 \u0431\u0438\u0440\u0436\u0435 \u043D\u0435\u0442 \u0430\u043A\u0442\u0438\u0432\u043D\u044B\u0445 \u043F\u043E\u0437\u0438\u0446\u0438\u0439. \u041F\u043E\u0440\u0442\u0444\u0435\u043B\u044C \u0432 \u043D\u0443\u043B\u0435." })] }));
    }
    const summary = useMemo(() => {
        const totalNotional = positions.reduce((acc, position) => acc + (position.notional_usdt ?? 0), 0);
        const netExposure = positions.reduce((acc, position) => {
            const factor = position.side === 'short' ? -1 : 1;
            return acc + factor * (position.notional_usdt ?? 0);
        }, 0);
        const totalUnrealized = positions.reduce((acc, position) => acc + (position.unrealized_pnl ?? 0), 0);
        const avgLeverageRaw = positions.reduce((acc, position) => acc + (position.leverage ?? 0), 0) / positions.length;
        return {
            totalNotional,
            netExposure,
            totalUnrealized,
            avgLeverage: Number.isFinite(avgLeverageRaw) ? avgLeverageRaw : null,
        };
    }, [positions]);
    const metrics = useMemo(() => [
        {
            label: 'Позиции',
            value: positions.length,
            fractionDigits: 0,
        },
        {
            label: 'Номинал',
            value: summary.totalNotional,
            unit: 'USDT',
            trend: 'goodIfPositive',
        },
        {
            label: 'Чистое плечо',
            value: summary.netExposure,
            unit: 'USDT',
        },
        {
            label: 'Нереализ. PnL',
            value: summary.totalUnrealized,
            unit: 'USDT',
            trend: 'goodIfPositive',
        },
        {
            label: 'Средний левередж',
            value: summary.avgLeverage,
            fractionDigits: 1,
        },
    ], [positions.length, summary.avgLeverage, summary.netExposure, summary.totalNotional, summary.totalUnrealized]);
    const [expanded, setExpanded] = useState(false);
    return (_jsxs("section", { className: "rounded-2xl border border-emerald-700/60 bg-emerald-950/20 shadow-card", children: [_jsxs("div", { className: "flex flex-col gap-4 border-b border-emerald-800/40 bg-emerald-900/20 px-6 py-5 md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h3", { className: "text-lg font-semibold text-white", children: "\u041E\u0442\u043A\u0440\u044B\u0442\u044B\u0435 \u043F\u043E\u0437\u0438\u0446\u0438\u0438 (\u0431\u0438\u0440\u0436\u0430)" }), _jsx("p", { className: "mt-1 text-sm text-emerald-200/80", children: "\u0421\u0438\u043D\u0445\u0440\u043E\u043D\u0438\u0437\u0430\u0446\u0438\u044F \u0432\u044B\u043F\u043E\u043B\u043D\u044F\u0435\u0442\u0441\u044F \u043A\u0430\u0436\u0434\u044B\u0435 5 \u0441\u0435\u043A\u0443\u043D\u0434." })] }), _jsxs("div", { className: "flex flex-col items-start gap-3 md:items-end", children: [_jsx("div", { className: "flex flex-wrap gap-2", children: metrics.map((metric) => (_jsx(SummaryBadge, { ...metric }, metric.label))) }), _jsxs("button", { type: "button", onClick: () => setExpanded((value) => !value), className: "inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 transition hover:bg-emerald-500/20", children: [expanded ? _jsx(FiChevronUp, { className: "text-base" }) : _jsx(FiChevronDown, { className: "text-base" }), expanded ? 'Скрыть позиции' : 'Показать список'] })] })] }), expanded && (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "min-w-full divide-y divide-emerald-800/60", children: [_jsx("thead", { className: "bg-emerald-900/40", children: _jsxs("tr", { children: [_jsx("th", { className: "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u0418\u043D\u0441\u0442\u0440\u0443\u043C\u0435\u043D\u0442" }), _jsx("th", { className: "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u0421\u0442\u043E\u0440\u043E\u043D\u0430" }), _jsx("th", { className: "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u0420\u0430\u0437\u043C\u0435\u0440" }), _jsx("th", { className: "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u0426\u0435\u043D\u0430 \u0432\u0445\u043E\u0434\u0430" }), _jsx("th", { className: "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u041C\u0430\u0440\u043A\u0435\u0442" }), _jsx("th", { className: "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u041D\u043E\u043C\u0438\u043D\u0430\u043B" }), _jsx("th", { className: "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "PnL / %" }), _jsx("th", { className: "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u041B\u0438\u043A\u0432. \u0446\u0435\u043D\u0430" }), _jsx("th", { className: "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u041F\u043B\u0435\u0447\u043E" }), _jsx("th", { className: "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200", children: "\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u043E" })] }) }), _jsx("tbody", { className: "divide-y divide-emerald-800/40", children: positions.map((position) => {
                                const sideBadgeClass = position.side === 'short'
                                    ? 'bg-rose-500/20 text-rose-200 border border-rose-500/40'
                                    : 'bg-emerald-500/20 text-emerald-100 border border-emerald-500/40';
                                return (_jsxs("tr", { className: "hover:bg-emerald-900/20", children: [_jsxs("td", { className: "whitespace-nowrap px-4 py-3 text-sm text-white", children: [_jsx("div", { className: "font-semibold text-white", children: position.symbol }), _jsxs("div", { className: "text-xs text-emerald-300/70", children: [position.take_profit ? `TP ${formatNumber(position.take_profit)}` : 'TP —', " \u2022", ' ', position.stop_loss ? `SL ${formatNumber(position.stop_loss)}` : 'SL —'] })] }), _jsx("td", { className: "px-4 py-3 text-sm", children: _jsx("span", { className: `inline-flex rounded-full px-3 py-1 text-xs font-medium ${sideBadgeClass}`, children: position.side === 'short' ? 'Шорт' : 'Лонг' }) }), _jsx("td", { className: "px-4 py-3 text-right text-sm text-emerald-100", children: formatNumber(position.size, 3) }), _jsx("td", { className: "px-4 py-3 text-right text-sm text-emerald-100", children: formatNumber(position.entry_price) }), _jsx("td", { className: "px-4 py-3 text-right text-sm text-emerald-100", children: formatNumber(position.mark_price) }), _jsx("td", { className: "px-4 py-3 text-right text-sm text-emerald-100", children: formatNumber(position.notional_usdt) }), _jsxs("td", { className: "px-4 py-3 text-right text-sm", children: [_jsx("div", { className: position.unrealized_pnl && position.unrealized_pnl < 0 ? 'text-rose-300' : 'text-emerald-200', children: formatNumber(position.unrealized_pnl) }), _jsxs("div", { className: "text-xs text-emerald-200/70", children: [formatNumber(position.unrealized_pnl_pct), "%"] })] }), _jsx("td", { className: "px-4 py-3 text-right text-sm text-emerald-100", children: formatNumber(position.liquidation_price) }), _jsx("td", { className: "px-4 py-3 text-right text-sm text-emerald-100", children: formatNumber(position.leverage, 1) }), _jsx("td", { className: "px-4 py-3 text-right text-sm text-emerald-200/80", children: position.updated_at
                                                ? new Date(position.updated_at).toLocaleTimeString('ru-RU', {
                                                    hour: '2-digit',
                                                    minute: '2-digit',
                                                })
                                                : '—' })] }, `${position.symbol}-${position.side}`));
                            }) })] }) }))] }));
}
