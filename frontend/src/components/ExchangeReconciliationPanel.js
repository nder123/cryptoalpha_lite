import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { FiRefreshCcw, FiChevronDown, FiChevronUp } from 'react-icons/fi';
import { fetchTradeStatsSummary } from '../api';
import { useExchangeTrades } from '../hooks/useExchangeTrades';
import { useExchangeTransactions } from '../hooks/useExchangeTransactions';
import { useEquitySnapshots } from '../hooks/useEquitySnapshots';
import { useHypothesisPnl } from '../hooks/useHypothesisPnl';
const DEFAULT_EQUITY_LIMIT = 200;
function formatDateInput(value) {
    if (!value)
        return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime()))
        return value;
    return date.toISOString().slice(0, 16);
}
function formatNumber(value, fractionDigits = 2) {
    if (value === null || value === undefined)
        return '—';
    return value.toFixed(fractionDigits);
}
function getPnlClass(value) {
    if (value === null || value === undefined)
        return 'text-slate-200';
    if (value > 0)
        return 'text-emerald-300';
    if (value < 0)
        return 'text-rose-300';
    return 'text-slate-200';
}
function SummaryBadge({ label, value, unit, fractionDigits = 2, mode }) {
    const formatted = formatNumber(value, fractionDigits);
    const display = formatted === '—' ? formatted : unit ? `${formatted} ${unit}` : formatted;
    const valueClass = mode === 'pnl' ? getPnlClass(value) : 'text-white';
    return (_jsxs("div", { className: "rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2", children: [_jsx("div", { className: "text-[11px] uppercase tracking-wide text-slate-400", children: label }), _jsx("div", { className: `text-sm font-semibold ${valueClass}`, children: display })] }));
}
export function ExchangeReconciliationPanel() {
    const { filters: tradeFilters, records: tradeRecords, total: tradeTotal, summary: tradeSummary, loading: tradesLoading, error: tradesError, updateFilters: updateTradeFilters, resetFilters: resetTradeFilters, refresh: refreshTrades, } = useExchangeTrades(100);
    const { filters: transactionFilters, records: transactionRecords, total: transactionTotal, summary: transactionSummary, loading: transactionsLoading, error: transactionsError, updateFilters: updateTransactionFilters, resetFilters: resetTransactionFilters, refresh: refreshTransactions, } = useExchangeTransactions(100);
    const { filters: equityFilters, snapshots, latest, latestEquity, latestAvailable, averageEquity, loading: equityLoading, error: equityError, updateFilters: updateEquityFilters, resetFilters: resetEquityFilters, refresh: refreshEquity, } = useEquitySnapshots();
    const { filters: hypothesisFilters, entries: hypothesisPnlEntries, loading: hypothesisLoading, error: hypothesisError, updateFilters: updateHypothesisFilters, resetFilters: resetHypothesisFilters, refresh: refreshHypothesis, } = useHypothesisPnl(25);
    const [tradesExpanded, setTradesExpanded] = useState(false);
    const [transactionsExpanded, setTransactionsExpanded] = useState(false);
    const [equityExpanded, setEquityExpanded] = useState(false);
    const [hypothesisExpanded, setHypothesisExpanded] = useState(false);
    const [internalSummary, setInternalSummary] = useState(null);
    const [internalLoading, setInternalLoading] = useState(true);
    const [internalError, setInternalError] = useState(null);
    useEffect(() => {
        let cancelled = false;
        const loadSummary = async () => {
            setInternalLoading(true);
            setInternalError(null);
            try {
                const bundle = await fetchTradeStatsSummary({});
                if (cancelled)
                    return;
                setInternalSummary(bundle.summary);
            }
            catch (err) {
                if (cancelled)
                    return;
                setInternalError(err instanceof Error ? err.message : 'Не удалось получить внутреннюю статистику');
            }
            finally {
                if (!cancelled)
                    setInternalLoading(false);
            }
        };
        loadSummary();
        return () => {
            cancelled = true;
        };
    }, []);
    const deltas = useMemo(() => {
        const bybitPnl = tradeSummary?.realized_pnl ?? null;
        const internalPnl = internalSummary?.total_pnl_usdt ?? null;
        const deltaPnl = bybitPnl !== null && internalPnl !== null ? bybitPnl - internalPnl : null;
        return [
            {
                label: 'PnL Bybit',
                bybitValue: bybitPnl,
                internalValue: null,
                delta: null,
                unit: 'USDT',
            },
            {
                label: 'PnL системы',
                bybitValue: null,
                internalValue: internalPnl,
                delta: null,
                unit: 'USDT',
            },
            {
                label: 'Дельта PnL',
                bybitValue: bybitPnl,
                internalValue: internalPnl,
                delta: deltaPnl,
                unit: 'USDT',
            },
            {
                label: 'Комиссии Bybit',
                bybitValue: tradeSummary?.fees ?? null,
                internalValue: null,
                delta: null,
                unit: 'USDT',
            },
            {
                label: 'Сделок Bybit',
                bybitValue: tradeSummary?.count ?? null,
                internalValue: internalSummary?.total_trades ?? null,
                delta: tradeSummary?.count !== undefined && internalSummary
                    ? tradeSummary.count - internalSummary.total_trades
                    : null,
            },
        ];
    }, [internalSummary, tradeSummary]);
    const tradeSummaryMetrics = useMemo(() => [
        {
            label: 'PnL Bybit',
            value: tradeSummary?.realized_pnl ?? null,
            unit: 'USDT',
            mode: 'pnl',
        },
        {
            label: 'Комиссии',
            value: tradeSummary?.fees ?? null,
            unit: 'USDT',
        },
        {
            label: 'Сделок всего',
            value: tradeTotal,
            fractionDigits: 0,
        },
        {
            label: 'В таблице',
            value: tradeRecords.length,
            fractionDigits: 0,
        },
    ], [tradeSummary, tradeTotal, tradeRecords.length]);
    const transactionSummaryMetrics = useMemo(() => [
        {
            label: 'Оборот',
            value: transactionSummary?.amount ?? null,
            unit: 'USDT',
            mode: 'pnl',
        },
        {
            label: 'Комиссии',
            value: transactionSummary?.fees ?? null,
            unit: 'USDT',
        },
        {
            label: 'Записей всего',
            value: transactionTotal,
            fractionDigits: 0,
        },
    ], [transactionSummary, transactionTotal]);
    const equitySummaryMetrics = useMemo(() => [
        {
            label: 'Текущее equity',
            value: latestEquity,
            unit: 'USDT',
            mode: 'pnl',
        },
        {
            label: 'Доступно',
            value: latestAvailable,
            unit: 'USDT',
        },
        {
            label: 'Среднее equity',
            value: averageEquity,
            unit: 'USDT',
        },
        {
            label: 'Срезов',
            value: snapshots.length,
            fractionDigits: 0,
        },
    ], [latestEquity, latestAvailable, averageEquity, snapshots.length]);
    const hypothesisSummary = useMemo(() => {
        if (!hypothesisPnlEntries.length) {
            return {
                totalPnl: null,
                avgPct: null,
                winners: 0,
                losers: 0,
            };
        }
        let totalPnl = 0;
        let pnlCount = 0;
        let totalPct = 0;
        let pctCount = 0;
        let winners = 0;
        let losers = 0;
        for (const entry of hypothesisPnlEntries) {
            if (entry.total_pnl_usdt !== null && entry.total_pnl_usdt !== undefined) {
                totalPnl += entry.total_pnl_usdt;
                pnlCount += 1;
                if (entry.total_pnl_usdt > 0)
                    winners += 1;
                else if (entry.total_pnl_usdt < 0)
                    losers += 1;
            }
            if (entry.avg_pnl_pct !== null && entry.avg_pnl_pct !== undefined) {
                totalPct += entry.avg_pnl_pct;
                pctCount += 1;
            }
        }
        return {
            totalPnl: pnlCount ? totalPnl : 0,
            avgPct: pctCount ? totalPct / pctCount : null,
            winners,
            losers,
        };
    }, [hypothesisPnlEntries]);
    const hypothesisSummaryMetrics = useMemo(() => [
        {
            label: 'PnL всего',
            value: hypothesisSummary.totalPnl,
            unit: 'USDT',
            mode: 'pnl',
        },
        {
            label: 'Средний %',
            value: hypothesisSummary.avgPct,
            unit: '%',
            fractionDigits: 1,
        },
        {
            label: 'Гипотез в списке',
            value: hypothesisPnlEntries.length,
            fractionDigits: 0,
        },
        {
            label: 'В плюсе',
            value: hypothesisSummary.winners,
            fractionDigits: 0,
        },
        {
            label: 'В минусе',
            value: hypothesisSummary.losers,
            fractionDigits: 0,
        },
    ], [hypothesisSummary, hypothesisPnlEntries.length]);
    const refreshAll = () => {
        refreshTrades();
        refreshTransactions();
        refreshEquity();
        refreshHypothesis();
    };
    return (_jsxs("section", { className: "space-y-6", children: [_jsxs("div", { className: "rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card", children: [_jsxs("div", { className: "flex flex-col gap-4 md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h2", { className: "text-2xl font-semibold text-white", children: "\u0421\u0432\u0435\u0440\u043A\u0430 \u0441 Bybit" }), _jsx("p", { className: "mt-1 text-sm text-slate-400", children: "\u0420\u0435\u0430\u043B\u0438\u0437\u043E\u0432\u0430\u043D\u043D\u044B\u0439 PnL, \u043A\u043E\u043C\u0438\u0441\u0441\u0438\u0438 \u0438 equity \u043D\u0430\u043F\u0440\u044F\u043C\u0443\u044E \u0441 \u0431\u0438\u0440\u0436\u0438. \u0421\u0440\u0430\u0432\u043D\u0438\u0432\u0430\u0435\u043C \u0441 \u0432\u043D\u0443\u0442\u0440\u0435\u043D\u043D\u0435\u0439 \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043A\u043E\u0439 CTO-AI." })] }), _jsxs("button", { type: "button", onClick: refreshAll, className: "inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [_jsx(FiRefreshCcw, { className: "text-base" }), "\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C \u0432\u0441\u0435"] })] }), (tradesError || transactionsError || equityError || internalError || hypothesisError) && (_jsxs("div", { className: "mt-4 space-y-2 text-sm text-rose-200", children: [tradesError && _jsx("div", { className: "rounded-xl border border-rose-500/40 bg-rose-500/10 p-2", children: tradesError }), transactionsError && (_jsx("div", { className: "rounded-xl border border-rose-500/40 bg-rose-500/10 p-2", children: transactionsError })), equityError && _jsx("div", { className: "rounded-xl border border-rose-500/40 bg-rose-500/10 p-2", children: equityError }), internalError && _jsx("div", { className: "rounded-xl border border-rose-500/40 bg-rose-500/10 p-2", children: internalError }), hypothesisError && _jsx("div", { className: "rounded-xl border border-rose-500/40 bg-rose-500/10 p-2", children: hypothesisError })] }))] }), _jsx("div", { className: "grid gap-4 md:grid-cols-2 xl:grid-cols-5", children: deltas.map((item) => {
                    const hasDelta = item.delta !== null && item.delta !== undefined;
                    const deltaClass = hasDelta
                        ? item.delta > 0
                            ? 'text-emerald-300'
                            : item.delta < 0
                                ? 'text-rose-300'
                                : 'text-slate-300'
                        : 'text-slate-300';
                    return (_jsxs("div", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-card", children: [_jsx("div", { className: "text-xs uppercase tracking-wide text-slate-400", children: item.label }), _jsxs("div", { className: "mt-3 space-y-1 text-sm text-slate-300", children: [item.bybitValue !== null && (_jsxs("div", { children: ["Bybit: ", _jsxs("span", { className: "font-semibold text-white", children: [formatNumber(item.bybitValue), " ", item.unit ?? ''] })] })), item.internalValue !== null && (_jsxs("div", { children: ["CTO-AI: ", _jsxs("span", { className: "font-semibold text-white", children: [formatNumber(item.internalValue), " ", item.unit ?? ''] })] })), hasDelta && (_jsxs("div", { className: `text-base font-semibold ${deltaClass}`, children: ["\u0394 ", formatNumber(item.delta), " ", item.unit ?? ''] }))] })] }, item.label));
                }) }), _jsxs("div", { className: "rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card", children: [_jsxs("header", { className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between", children: [_jsxs("div", { className: "grid gap-3 md:grid-cols-2 lg:grid-cols-4", children: [_jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0414\u0430\u0442\u0430 \u043D\u0430\u0447\u0430\u043B\u0430", _jsx("input", { type: "datetime-local", value: formatDateInput(tradeFilters.start), onChange: (event) => updateTradeFilters({
                                                    start: event.target.value ? new Date(event.target.value).toISOString() : null,
                                                }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0414\u0430\u0442\u0430 \u043E\u043A\u043E\u043D\u0447\u0430\u043D\u0438\u044F", _jsx("input", { type: "datetime-local", value: formatDateInput(tradeFilters.end), onChange: (event) => updateTradeFilters({
                                                    end: event.target.value ? new Date(event.target.value).toISOString() : null,
                                                }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0421\u0438\u043C\u0432\u043E\u043B", _jsx("input", { type: "text", value: tradeFilters.symbol, onChange: (event) => updateTradeFilters({ symbol: event.target.value.toUpperCase() }), placeholder: "BTCUSDT", className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("div", { className: "flex items-end gap-2 text-xs text-slate-400", children: [_jsx("button", { type: "button", onClick: resetTradeFilters, className: "rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C" }), _jsxs("span", { children: ["\u0421\u0434\u0435\u043B\u043E\u043A: ", tradeTotal] })] })] }), _jsxs("div", { className: "flex flex-col gap-3", children: [_jsx("div", { className: "flex flex-wrap gap-2", children: tradeSummaryMetrics.map((metric) => (_jsx(SummaryBadge, { ...metric }, metric.label))) }), _jsxs("button", { type: "button", onClick: () => setTradesExpanded((value) => !value), className: "inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [tradesExpanded ? _jsx(FiChevronUp, { className: "text-base" }) : _jsx(FiChevronDown, { className: "text-base" }), tradesExpanded ? 'Скрыть таблицу' : 'Показать сделки'] })] })] }), tradesExpanded && (_jsx("div", { className: "mt-4 overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60", children: tradesLoading ? (_jsx("div", { className: "flex h-40 items-center justify-center text-sm text-slate-400", children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0441\u0434\u0435\u043B\u043E\u043A Bybit\u2026" })) : tradeRecords.length ? (_jsxs("table", { className: "min-w-full divide-y divide-slate-800 text-sm", children: [_jsx("thead", { className: "bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400", children: _jsxs("tr", { children: [_jsx("th", { className: "px-4 py-3 text-left", children: "\u0412\u0440\u0435\u043C\u044F" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0418\u043D\u0441\u0442\u0440\u0443\u043C\u0435\u043D\u0442" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0421\u0442\u043E\u0440\u043E\u043D\u0430" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0426\u0435\u043D\u0430" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u041A\u043E\u043B\u0438\u0447\u0435\u0441\u0442\u0432\u043E" }), _jsx("th", { className: "px-4 py-3 text-left", children: "PnL" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u041A\u043E\u043C\u0438\u0441\u0441\u0438\u044F" })] }) }), _jsx("tbody", { className: "divide-y divide-slate-800", children: tradeRecords.map((trade) => (_jsxs("tr", { className: "hover:bg-slate-800/30", children: [_jsx("td", { className: "px-4 py-3 text-slate-300", children: trade.trade_time ? new Date(trade.trade_time).toLocaleString('ru-RU') : '—' }), _jsxs("td", { className: "px-4 py-3 text-white", children: [_jsx("div", { className: "font-semibold", children: trade.symbol }), _jsx("div", { className: "text-xs text-slate-500", children: trade.exec_id.slice(-8) })] }), _jsx("td", { className: "px-4 py-3 capitalize text-slate-300", children: trade.side?.toLowerCase() ?? '—' }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: formatNumber(trade.price) }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: formatNumber(trade.quantity, 4) }), _jsxs("td", { className: `px-4 py-3 font-semibold ${trade.realized_pnl
                                                    ? trade.realized_pnl > 0
                                                        ? 'text-emerald-300'
                                                        : trade.realized_pnl < 0
                                                            ? 'text-rose-300'
                                                            : 'text-slate-300'
                                                    : 'text-slate-300'}`, children: [formatNumber(trade.realized_pnl), " USDT"] }), _jsxs("td", { className: "px-4 py-3 text-slate-300", children: [formatNumber(trade.fee), " ", trade.fee_currency ?? ''] })] }, trade.exec_id))) })] })) : (_jsx("div", { className: "flex h-40 items-center justify-center text-sm text-slate-400", children: "\u041D\u0435\u0442 \u0441\u0434\u0435\u043B\u043E\u043A \u0432 \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u043C \u0434\u0438\u0430\u043F\u0430\u0437\u043E\u043D\u0435." })) }))] }), _jsxs("div", { className: "rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card", children: [_jsxs("header", { className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between", children: [_jsxs("div", { className: "grid gap-3 md:grid-cols-2 lg:grid-cols-4", children: [_jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0414\u0430\u0442\u0430 \u043D\u0430\u0447\u0430\u043B\u0430", _jsx("input", { type: "datetime-local", value: formatDateInput(transactionFilters.start), onChange: (event) => updateTransactionFilters({
                                                    start: event.target.value ? new Date(event.target.value).toISOString() : null,
                                                }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0414\u0430\u0442\u0430 \u043E\u043A\u043E\u043D\u0447\u0430\u043D\u0438\u044F", _jsx("input", { type: "datetime-local", value: formatDateInput(transactionFilters.end), onChange: (event) => updateTransactionFilters({
                                                    end: event.target.value ? new Date(event.target.value).toISOString() : null,
                                                }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0422\u0438\u043F \u043E\u043F\u0435\u0440\u0430\u0446\u0438\u0438", _jsx("input", { type: "text", value: transactionFilters.txType, onChange: (event) => updateTransactionFilters({ txType: event.target.value.toUpperCase() }), placeholder: "FUNDING", className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("div", { className: "flex items-end gap-2 text-xs text-slate-400", children: [_jsx("button", { type: "button", onClick: resetTransactionFilters, className: "rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C" }), _jsxs("span", { children: ["\u0422\u0440\u0430\u043D\u0437\u0430\u043A\u0446\u0438\u0439: ", transactionTotal] })] })] }), _jsxs("div", { className: "flex flex-col gap-3", children: [_jsx("div", { className: "flex flex-wrap gap-2", children: transactionSummaryMetrics.map((metric) => (_jsx(SummaryBadge, { ...metric }, metric.label))) }), _jsx("p", { className: "text-xs text-slate-400", children: "\u0421\u0432\u043E\u0434\u043A\u0430 \u0440\u0430\u0441\u0441\u0447\u0438\u0442\u044B\u0432\u0430\u0435\u0442\u0441\u044F \u043F\u043E \u0434\u0430\u043D\u043D\u044B\u043C Bybit transaction log." }), _jsxs("button", { type: "button", onClick: () => setTransactionsExpanded((value) => !value), className: "inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [transactionsExpanded ? _jsx(FiChevronUp, { className: "text-base" }) : _jsx(FiChevronDown, { className: "text-base" }), transactionsExpanded ? 'Скрыть таблицу' : 'Показать транзакции'] })] })] }), transactionsExpanded && (_jsx("div", { className: "mt-6 overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60", children: transactionsLoading ? (_jsx("div", { className: "flex h-40 items-center justify-center text-sm text-slate-400", children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0442\u0440\u0430\u043D\u0437\u0430\u043A\u0446\u0438\u0439 Bybit\u2026" })) : transactionRecords.length ? (_jsxs("table", { className: "min-w-full divide-y divide-slate-800 text-sm", children: [_jsx("thead", { className: "bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400", children: _jsxs("tr", { children: [_jsx("th", { className: "px-4 py-3 text-left", children: "\u0412\u0440\u0435\u043C\u044F" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0422\u0438\u043F" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0421\u0443\u043C\u043C\u0430" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u041A\u043E\u043C\u0438\u0441\u0441\u0438\u044F" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u041F\u0440\u0438\u0432\u044F\u0437\u043A\u0430" })] }) }), _jsx("tbody", { className: "divide-y divide-slate-800", children: transactionRecords.map((item) => (_jsxs("tr", { className: "hover:bg-slate-800/30", children: [_jsx("td", { className: "px-4 py-3 text-slate-300", children: item.created_time ? new Date(item.created_time).toLocaleString('ru-RU') : '—' }), _jsxs("td", { className: "px-4 py-3 text-white", children: [_jsx("div", { className: "font-semibold", children: item.type }), item.sub_type && _jsx("div", { className: "text-xs text-slate-500", children: item.sub_type })] }), _jsxs("td", { className: `px-4 py-3 font-semibold ${item.amount
                                                    ? item.amount > 0
                                                        ? 'text-emerald-300'
                                                        : item.amount < 0
                                                            ? 'text-rose-300'
                                                            : 'text-slate-300'
                                                    : 'text-slate-300'}`, children: [formatNumber(item.amount), " ", item.currency ?? ''] }), _jsxs("td", { className: "px-4 py-3 text-slate-300", children: [formatNumber(item.fee), " ", item.currency ?? ''] }), _jsx("td", { className: "px-4 py-3 text-xs text-slate-300", children: item.reference_id ?? '—' })] }, item.transaction_id))) })] })) : (_jsx("div", { className: "flex h-40 items-center justify-center text-sm text-slate-400", children: "\u041D\u0435\u0442 \u0442\u0440\u0430\u043D\u0437\u0430\u043A\u0446\u0438\u0439 \u0432 \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u043C \u0434\u0438\u0430\u043F\u0430\u0437\u043E\u043D\u0435." })) }))] }), _jsxs("div", { className: "rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card", children: [_jsxs("header", { className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between", children: [_jsxs("div", { className: "grid gap-3 md:grid-cols-2 lg:grid-cols-[repeat(4,minmax(0,1fr))]", children: [_jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0414\u0430\u0442\u0430 \u043D\u0430\u0447\u0430\u043B\u0430", _jsx("input", { type: "datetime-local", value: formatDateInput(equityFilters.start), onChange: (event) => updateEquityFilters({
                                                    start: event.target.value ? new Date(event.target.value).toISOString() : null,
                                                }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0414\u0430\u0442\u0430 \u043E\u043A\u043E\u043D\u0447\u0430\u043D\u0438\u044F", _jsx("input", { type: "datetime-local", value: formatDateInput(equityFilters.end), onChange: (event) => updateEquityFilters({
                                                    end: event.target.value ? new Date(event.target.value).toISOString() : null,
                                                }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("label", { className: "flex flex-col gap-2 text-xs text-slate-400", children: ["\u0421\u0440\u0435\u0437\u043E\u0432", _jsx("input", { type: "number", min: 20, max: 500, value: equityFilters.limit, onChange: (event) => updateEquityFilters({
                                                    limit: Math.max(20, Math.min(500, Number(event.target.value) || DEFAULT_EQUITY_LIMIT)),
                                                }), className: "rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsxs("div", { className: "flex items-end gap-2 text-xs text-slate-400", children: [_jsx("button", { type: "button", onClick: resetEquityFilters, className: "rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C" }), _jsxs("span", { children: ["\u0421\u0440\u0435\u0437\u043E\u0432: ", snapshots.length] })] })] }), _jsxs("div", { className: "flex flex-col gap-3", children: [_jsx("div", { className: "flex flex-wrap gap-2", children: equitySummaryMetrics.map((metric) => (_jsx(SummaryBadge, { ...metric }, metric.label))) }), _jsxs("p", { className: "text-xs text-slate-400", children: ["\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0439 \u0441\u043D\u0438\u043C\u043E\u043A: ", latest?.captured_at ? new Date(latest.captured_at).toLocaleString('ru-RU') : '—'] }), _jsxs("button", { type: "button", onClick: () => setEquityExpanded((value) => !value), className: "inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [equityExpanded ? _jsx(FiChevronUp, { className: "text-base" }) : _jsx(FiChevronDown, { className: "text-base" }), equityExpanded ? 'Скрыть таблицу' : 'Показать equity-срезы'] })] })] }), equityExpanded && (_jsx("div", { className: "mt-6 overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60", children: equityLoading ? (_jsx("div", { className: "flex h-40 items-center justify-center text-sm text-slate-400", children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 equity Bybit\u2026" })) : snapshots.length ? (_jsxs("table", { className: "min-w-full divide-y divide-slate-800 text-sm", children: [_jsx("thead", { className: "bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400", children: _jsxs("tr", { children: [_jsx("th", { className: "px-4 py-3 text-left", children: "\u0412\u0440\u0435\u043C\u044F" }), _jsx("th", { className: "px-4 py-3 text-left", children: "Equity" }), _jsx("th", { className: "px-4 py-3 text-left", children: "Wallet" }), _jsx("th", { className: "px-4 py-3 text-left", children: "Available" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0412\u0430\u043B\u044E\u0442\u0430" })] }) }), _jsx("tbody", { className: "divide-y divide-slate-800", children: snapshots.map((snapshot, index) => (_jsxs("tr", { className: "hover:bg-slate-800/30", children: [_jsx("td", { className: "px-4 py-3 text-slate-300", children: snapshot.captured_at ? new Date(snapshot.captured_at).toLocaleString('ru-RU') : '—' }), _jsx("td", { className: "px-4 py-3 text-white", children: formatNumber(snapshot.total_equity) }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: formatNumber(snapshot.wallet_balance) }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: formatNumber(snapshot.available_balance) }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: snapshot.currency ?? 'USDT' })] }, snapshot.captured_at ?? `equity-${index}`))) })] })) : (_jsx("div", { className: "flex h-40 items-center justify-center text-sm text-slate-400", children: "\u041D\u0435\u0442 equity-\u0441\u0440\u0435\u0437\u043E\u0432 \u0432 \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u043C \u0434\u0438\u0430\u043F\u0430\u0437\u043E\u043D\u0435." })) }))] }), _jsxs("div", { className: "rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card", children: [_jsxs("header", { className: "flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between", children: [_jsxs("div", { className: "space-y-2", children: [_jsx("h3", { className: "text-xl font-semibold text-white", children: "PnL \u043F\u043E \u0433\u0438\u043F\u043E\u0442\u0435\u0437\u0430\u043C" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u0421\u0443\u043C\u043C\u0438\u0440\u0443\u0435\u043C \u0432\u0441\u0435 \u0437\u0430\u043A\u0440\u044B\u0442\u044B\u0435 \u0441\u0434\u0435\u043B\u043A\u0438, \u0441\u0432\u044F\u0437\u0430\u043D\u043D\u044B\u0435 \u0441 \u043A\u0430\u0436\u0434\u043E\u0439 \u0433\u0438\u043F\u043E\u0442\u0435\u0437\u043E\u0439. \u0412\u0438\u0434\u043D\u043E, \u043D\u0430 \u0447\u0451\u043C \u0438\u0434\u0435\u044F \u0437\u0430\u0440\u0430\u0431\u0430\u0442\u044B\u0432\u0430\u0435\u0442 \u0438\u043B\u0438 \u0442\u0435\u0440\u044F\u0435\u0442." })] }), _jsxs("div", { className: "flex flex-col gap-3", children: [_jsx("div", { className: "flex flex-wrap gap-2", children: hypothesisSummaryMetrics.map((metric) => (_jsx(SummaryBadge, { ...metric }, metric.label))) }), _jsxs("div", { className: "flex flex-wrap items-center gap-3 text-xs text-slate-400", children: [_jsxs("label", { className: "flex items-center gap-2", children: ["\u041F\u043E\u043A\u0430\u0437\u044B\u0432\u0430\u0442\u044C", _jsx("input", { type: "number", min: 5, max: 500, value: hypothesisFilters.limit, onChange: (event) => updateHypothesisFilters({ limit: Math.max(5, Math.min(500, Number(event.target.value) || hypothesisFilters.limit)) }), className: "w-20 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" })] }), _jsx("button", { type: "button", onClick: resetHypothesisFilters, className: "rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: "\u0421\u0431\u0440\u043E\u0441\u0438\u0442\u044C" }), _jsxs("button", { type: "button", onClick: refreshHypothesis, className: "inline-flex items-center gap-2 rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [_jsx(FiRefreshCcw, { className: "text-base" }), " \u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C"] }), _jsxs("button", { type: "button", onClick: () => setHypothesisExpanded((value) => !value), className: "inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", children: [hypothesisExpanded ? _jsx(FiChevronUp, { className: "text-base" }) : _jsx(FiChevronDown, { className: "text-base" }), hypothesisExpanded ? 'Скрыть таблицу' : 'Показать список'] })] })] })] }), hypothesisExpanded && (_jsx("div", { className: "mt-6 overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60", children: hypothesisLoading ? (_jsx("div", { className: "flex h-40 items-center justify-center text-sm text-slate-400", children: "\u0421\u0447\u0438\u0442\u0430\u0435\u043C PnL \u043F\u043E \u0433\u0438\u043F\u043E\u0442\u0435\u0437\u0430\u043C\u2026" })) : hypothesisPnlEntries.length ? (_jsxs("table", { className: "min-w-full divide-y divide-slate-800 text-sm", children: [_jsx("thead", { className: "bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400", children: _jsxs("tr", { children: [_jsx("th", { className: "px-4 py-3 text-left", children: "\u0413\u0438\u043F\u043E\u0442\u0435\u0437\u0430" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0418\u043D\u0441\u0442\u0440\u0443\u043C\u0435\u043D\u0442" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u041D\u0430\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u0435" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0421\u0434\u0435\u043B\u043E\u043A" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0418\u0442\u043E\u0433\u043E PnL" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u0421\u0440\u0435\u0434\u043D\u0438\u0439 %" }), _jsx("th", { className: "px-4 py-3 text-left", children: "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0435\u0435 \u0437\u0430\u043A\u0440\u044B\u0442\u0438\u0435" })] }) }), _jsx("tbody", { className: "divide-y divide-slate-800", children: hypothesisPnlEntries.map((entry) => (_jsxs("tr", { className: "hover:bg-slate-800/30", children: [_jsxs("td", { className: "px-4 py-3 text-white", children: [_jsx("div", { className: "font-semibold", children: entry.hypothesis_id }), _jsx("div", { className: "text-xs text-slate-500", children: entry.last_closed_at ? 'Закрыто' : 'Ещё открыта' })] }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: entry.symbol ?? '—' }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: entry.direction ?? '—' }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: entry.trades }), _jsxs("td", { className: `px-4 py-3 font-semibold ${entry.total_pnl_usdt
                                                    ? entry.total_pnl_usdt > 0
                                                        ? 'text-emerald-300'
                                                        : entry.total_pnl_usdt < 0
                                                            ? 'text-rose-300'
                                                            : 'text-slate-300'
                                                    : 'text-slate-300'}`, children: [formatNumber(entry.total_pnl_usdt), " USDT"] }), _jsxs("td", { className: "px-4 py-3 text-slate-300", children: [formatNumber(entry.avg_pnl_pct), " %"] }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: entry.last_closed_at ? new Date(entry.last_closed_at).toLocaleString('ru-RU') : '—' })] }, entry.hypothesis_id))) })] })) : (_jsx("div", { className: "flex h-40 items-center justify-center text-sm text-slate-400", children: "\u041F\u043E\u043A\u0430 \u043D\u0435\u0442 \u0437\u0430\u043A\u0440\u044B\u0442\u044B\u0445 \u0441\u0434\u0435\u043B\u043E\u043A \u043F\u043E \u0433\u0438\u043F\u043E\u0442\u0435\u0437\u0430\u043C." })) }))] })] }));
}
