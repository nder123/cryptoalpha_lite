import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
function formatSigned(value, fractionDigits = 2) {
    if (value === null || value === undefined) {
        return '—';
    }
    const fixed = value.toFixed(fractionDigits);
    return value > 0 ? `+${fixed}` : fixed;
}
function formatTimestamp(value) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return '—';
    }
    return date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}
function valueTone(value) {
    if (value === null || value === undefined)
        return 'text-slate-200';
    if (value > 0)
        return 'text-emerald-300';
    if (value < 0)
        return 'text-rose-300';
    return 'text-slate-200';
}
function sumUnrealized(positions) {
    return positions.reduce((total, position) => total + (position.unrealized_pnl ?? 0), 0);
}
function computeDailyPnl(tradeStats) {
    if (!tradeStats)
        return null;
    const today = new Date();
    const dayKey = today.toISOString().slice(0, 10);
    const total = tradeStats.recent.reduce((acc, entry) => {
        if (!entry.closed_at)
            return acc;
        const entryDay = entry.closed_at.slice(0, 10);
        if (entryDay !== dayKey)
            return acc;
        return acc + (entry.pnl_usdt ?? 0);
    }, 0);
    return total;
}
export function TradeOverviewSummary({ tradeStats, positions }) {
    const [expanded, setExpanded] = useState(false);
    const summary = tradeStats?.summary ?? null;
    const lastTrade = tradeStats?.last_trade ?? null;
    const openPositions = useMemo(() => positions.filter((entry) => Math.abs(entry.size ?? 0) > 0), [positions]);
    const unrealizedPnl = useMemo(() => sumUnrealized(openPositions), [openPositions]);
    const realizedPnlGross = summary?.total_pnl_usdt ?? null;
    const realizedPnlNet = summary?.total_pnl_usdt_net ?? null;
    const realizedFees = summary?.total_fees_usdt ?? null;
    const realizedPnl = realizedPnlNet ?? realizedPnlGross;
    const overallPnl = realizedPnl === null ? unrealizedPnl : unrealizedPnl + realizedPnl;
    const lastTradePnl = lastTrade?.pnl_usdt ?? null;
    const dailyPnl = useMemo(() => computeDailyPnl(tradeStats), [tradeStats]);
    return (_jsxs("section", { className: "rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card", children: [_jsxs("header", { className: "flex flex-col gap-2 md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-xl font-semibold text-white", children: "\u0418\u0442\u043E\u0433\u0438 \u0442\u043E\u0440\u0433\u043E\u0432\u043B\u0438" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u0421\u0432\u043E\u0434\u043A\u0430 dry-run \u0437\u0430 \u043F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 \u043E\u043F\u0435\u0440\u0430\u0446\u0438\u0438." })] }), _jsxs("div", { className: "flex items-center gap-3 text-xs text-slate-500", children: [_jsxs("span", { children: ["\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u043E: ", formatTimestamp(tradeStats?.updated_at)] }), _jsx("button", { type: "button", onClick: () => setExpanded((value) => !value), className: "rounded-full border border-slate-700 px-3 py-1 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: expanded ? 'Свернуть детали' : 'Раскрыть детали' })] })] }), _jsxs("div", { className: "mt-5 grid gap-4 md:grid-cols-3", children: [_jsxs("article", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-xs uppercase tracking-wide text-slate-400", children: "\u041E\u0431\u0449\u0438\u0439 PnL" }), _jsxs("p", { className: `mt-3 text-3xl font-semibold ${valueTone(overallPnl)}`, children: [formatSigned(overallPnl), " ", _jsx("span", { className: "text-base text-slate-400", children: "USDT" })] }), _jsx("p", { className: "mt-1 text-xs text-slate-500", children: "\u0423\u0447\u0442\u0435\u043D\u044B \u0437\u0430\u043A\u0440\u044B\u0442\u044B\u0435 \u0441\u0434\u0435\u043B\u043A\u0438 + \u0442\u0435\u043A\u0443\u0449\u0430\u044F \u043D\u0435\u0440\u0435\u0430\u043B\u0438\u0437\u043E\u0432\u0430\u043D\u043D\u0430\u044F \u043F\u0440\u0438\u0431\u044B\u043B\u044C." })] }), _jsxs("article", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-xs uppercase tracking-wide text-slate-400", children: "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0439 PnL" }), _jsxs("p", { className: `mt-3 text-3xl font-semibold ${valueTone(lastTradePnl)}`, children: [formatSigned(lastTradePnl), " ", _jsx("span", { className: "text-base text-slate-400", children: "USDT" })] }), _jsx("p", { className: "mt-1 text-xs text-slate-500", children: "\u0420\u0435\u0437\u0443\u043B\u044C\u0442\u0430\u0442 \u043F\u043E\u0441\u043B\u0435\u0434\u043D\u0435\u0439 \u0437\u0430\u043A\u0440\u044B\u0442\u043E\u0439 \u0441\u0434\u0435\u043B\u043A\u0438." })] }), _jsxs("article", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-xs uppercase tracking-wide text-slate-400", children: "\u041E\u0442\u043A\u0440\u044B\u0442\u044B\u0435 \u043F\u043E\u0437\u0438\u0446\u0438\u0438" }), _jsx("p", { className: "mt-3 text-3xl font-semibold text-sky-300", children: openPositions.length }), _jsx("p", { className: "mt-1 text-xs text-slate-500", children: "\u0421\u043E\u0432\u043F\u0430\u0434\u0430\u0435\u0442 \u0441 \u0442\u0430\u0431\u043B\u0438\u0446\u0435\u0439 \u00AB\u041F\u043E\u0437\u0438\u0446\u0438\u0438\u00BB." })] })] }), expanded && (_jsxs("div", { className: "mt-6 space-y-6", children: [_jsxs("div", { className: "grid gap-4 md:grid-cols-2", children: [_jsxs("article", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-xs uppercase tracking-wide text-slate-400", children: "PnL (\u0434\u0435\u043D\u044C)" }), _jsxs("p", { className: `mt-3 text-2xl font-semibold ${valueTone(dailyPnl)}`, children: [formatSigned(dailyPnl), " ", _jsx("span", { className: "text-base text-slate-400", children: "USDT" })] }), _jsx("p", { className: "mt-1 text-xs text-slate-500", children: "\u0421\u0443\u043C\u043C\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D\u043D\u044B\u0445 \u0441\u0434\u0435\u043B\u043E\u043A \u0437\u0430 \u0441\u0435\u0433\u043E\u0434\u043D\u044F." })] }), _jsxs("article", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-xs uppercase tracking-wide text-slate-400", children: "PnL (\u0432\u0441\u0435\u0433\u043E)" }), _jsxs("p", { className: `mt-3 text-2xl font-semibold ${valueTone(realizedPnl)}`, children: [formatSigned(realizedPnl), " ", _jsx("span", { className: "text-base text-slate-400", children: "USDT" })] }), _jsx("p", { className: "mt-1 text-xs text-slate-500", children: "\u0420\u0435\u0430\u043B\u0438\u0437\u043E\u0432\u0430\u043D\u043D\u044B\u0439 \u0440\u0435\u0437\u0443\u043B\u044C\u0442\u0430\u0442 \u0432\u0441\u0435\u0445 \u0437\u0430\u043A\u0440\u044B\u0442\u044B\u0445 \u0441\u0434\u0435\u043B\u043E\u043A (\u043F\u043E\u0441\u043B\u0435 \u043A\u043E\u043C\u0438\u0441\u0441\u0438\u0439, \u0435\u0441\u043B\u0438 \u0434\u043E\u0441\u0442\u0443\u043F\u043D\u044B)." })] })] }), realizedPnlNet !== null || realizedFees !== null ? (_jsxs("div", { className: "grid gap-4 md:grid-cols-2", children: [_jsxs("article", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-xs uppercase tracking-wide text-slate-400", children: "PnL (\u0431\u0440\u0443\u0442\u0442\u043E)" }), _jsxs("p", { className: `mt-3 text-2xl font-semibold ${valueTone(realizedPnlGross)}`, children: [formatSigned(realizedPnlGross), " ", _jsx("span", { className: "text-base text-slate-400", children: "USDT" })] }), _jsx("p", { className: "mt-1 text-xs text-slate-500", children: "\u0411\u0435\u0437 \u0432\u044B\u0447\u0435\u0442\u0430 \u043A\u043E\u043C\u0438\u0441\u0441\u0438\u0439." })] }), _jsxs("article", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-xs uppercase tracking-wide text-slate-400", children: "\u041A\u043E\u043C\u0438\u0441\u0441\u0438\u0438" }), _jsxs("p", { className: "mt-3 text-2xl font-semibold text-slate-200", children: [formatSigned(realizedFees), " ", _jsx("span", { className: "text-base text-slate-400", children: "USDT" })] }), _jsx("p", { className: "mt-1 text-xs text-slate-500", children: "\u0421\u0443\u043C\u043C\u0430 \u043A\u043E\u043C\u0438\u0441\u0441\u0438\u0439 \u043F\u043E \u0437\u0430\u043A\u0440\u044B\u0442\u044B\u043C \u0441\u0434\u0435\u043B\u043A\u0430\u043C." })] })] })) : null, _jsxs("div", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("h3", { className: "text-sm font-semibold text-white", children: "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u044F\u044F \u0441\u0434\u0435\u043B\u043A\u0430" }), lastTrade ? (_jsxs("dl", { className: "mt-3 grid gap-3 text-sm text-slate-300 sm:grid-cols-2 lg:grid-cols-4", children: [_jsxs("div", { children: [_jsx("dt", { className: "text-xs uppercase tracking-wide text-slate-400", children: "\u0418\u043D\u0441\u0442\u0440\u0443\u043C\u0435\u043D\u0442" }), _jsxs("dd", { className: "mt-1 font-semibold text-white", children: [lastTrade.symbol, ' ', _jsxs("span", { className: "text-slate-400", children: ["(", lastTrade.direction, ")"] })] })] }), _jsxs("div", { children: [_jsx("dt", { className: "text-xs uppercase tracking-wide text-slate-400", children: "PnL" }), _jsxs("dd", { className: `mt-1 font-semibold ${valueTone(lastTradePnl)}`, children: [formatSigned(lastTradePnl), " USDT"] })] }), _jsxs("div", { children: [_jsx("dt", { className: "text-xs uppercase tracking-wide text-slate-400", children: "\u0414\u043B\u0438\u0442\u0435\u043B\u044C\u043D\u043E\u0441\u0442\u044C" }), _jsx("dd", { className: "mt-1 text-white", children: lastTrade.duration_seconds !== null && lastTrade.duration_seconds !== undefined
                                                    ? `${Math.round(lastTrade.duration_seconds / 60)} мин`
                                                    : '—' })] }), _jsxs("div", { children: [_jsx("dt", { className: "text-xs uppercase tracking-wide text-slate-400", children: "\u0417\u0430\u043A\u0440\u044B\u0442\u0430" }), _jsx("dd", { className: "mt-1 text-white", children: formatTimestamp(lastTrade.closed_at) })] })] })) : (_jsx("p", { className: "mt-3 text-sm text-slate-400", children: "\u041F\u043E\u043A\u0430 \u043D\u0435\u0442 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043D\u043D\u044B\u0445 \u0441\u0434\u0435\u043B\u043E\u043A." }))] })] }))] }));
}
