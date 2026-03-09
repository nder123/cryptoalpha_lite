import { useEffect, useMemo, useState } from 'react';
import { FiRefreshCcw, FiChevronDown, FiChevronUp } from 'react-icons/fi';

import { fetchTradeStatsSummary } from '../api';
import { useExchangeTrades } from '../hooks/useExchangeTrades';
import { useExchangeTransactions } from '../hooks/useExchangeTransactions';
import { useEquitySnapshots } from '../hooks/useEquitySnapshots';
import { useHypothesisPnl } from '../hooks/useHypothesisPnl';
import type { HypothesisPnlEntry, ReconciliationDelta, TradeStatsSummary } from '../types';

const DEFAULT_EQUITY_LIMIT = 200;

function formatDateInput(value: string | null) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toISOString().slice(0, 16);
}

function formatNumber(value: number | null | undefined, fractionDigits = 2) {
    if (value === null || value === undefined) return '—';
    return value.toFixed(fractionDigits);
}

type SummaryMetric = {
    label: string;
    value: number | null;
    unit?: string;
    fractionDigits?: number;
    mode?: 'pnl';
};

function getPnlClass(value: number | null | undefined) {
    if (value === null || value === undefined) return 'text-slate-200';
    if (value > 0) return 'text-emerald-300';
    if (value < 0) return 'text-rose-300';
    return 'text-slate-200';
}

function SummaryBadge({ label, value, unit, fractionDigits = 2, mode }: SummaryMetric) {
    const formatted = formatNumber(value, fractionDigits);
    const display = formatted === '—' ? formatted : unit ? `${formatted} ${unit}` : formatted;
    const valueClass = mode === 'pnl' ? getPnlClass(value) : 'text-white';
    return (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
            <div className={`text-sm font-semibold ${valueClass}`}>{display}</div>
        </div>
    );
}

export function ExchangeReconciliationPanel() {
    const {
        filters: tradeFilters,
        records: tradeRecords,
        total: tradeTotal,
        summary: tradeSummary,
        loading: tradesLoading,
        error: tradesError,
        updateFilters: updateTradeFilters,
        resetFilters: resetTradeFilters,
        refresh: refreshTrades,
    } = useExchangeTrades(100);

    const {
        filters: transactionFilters,
        records: transactionRecords,
        total: transactionTotal,
        summary: transactionSummary,
        loading: transactionsLoading,
        error: transactionsError,
        updateFilters: updateTransactionFilters,
        resetFilters: resetTransactionFilters,
        refresh: refreshTransactions,
    } = useExchangeTransactions(100);

    const {
        filters: equityFilters,
        snapshots,
        latest,
        latestEquity,
        latestAvailable,
        averageEquity,
        loading: equityLoading,
        error: equityError,
        updateFilters: updateEquityFilters,
        resetFilters: resetEquityFilters,
        refresh: refreshEquity,
    } = useEquitySnapshots();

    const {
        filters: hypothesisFilters,
        entries: hypothesisPnlEntries,
        loading: hypothesisLoading,
        error: hypothesisError,
        updateFilters: updateHypothesisFilters,
        resetFilters: resetHypothesisFilters,
        refresh: refreshHypothesis,
    } = useHypothesisPnl(25);

    const [tradesExpanded, setTradesExpanded] = useState(false);
    const [transactionsExpanded, setTransactionsExpanded] = useState(false);
    const [equityExpanded, setEquityExpanded] = useState(false);
    const [hypothesisExpanded, setHypothesisExpanded] = useState(false);

    const [internalSummary, setInternalSummary] = useState<TradeStatsSummary | null>(null);
    const [internalLoading, setInternalLoading] = useState(true);
    const [internalError, setInternalError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        const loadSummary = async () => {
            setInternalLoading(true);
            setInternalError(null);
            try {
                const bundle = await fetchTradeStatsSummary({});
                if (cancelled) return;
                setInternalSummary(bundle.summary);
            } catch (err) {
                if (cancelled) return;
                setInternalError(err instanceof Error ? err.message : 'Не удалось получить внутреннюю статистику');
            } finally {
                if (!cancelled) setInternalLoading(false);
            }
        };
        loadSummary();
        return () => {
            cancelled = true;
        };
    }, []);

    const deltas = useMemo<ReconciliationDelta[]>(() => {
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
                delta:
                    tradeSummary?.count !== undefined && internalSummary
                        ? tradeSummary.count - internalSummary.total_trades
                        : null,
            },
        ];
    }, [internalSummary, tradeSummary]);

    const tradeSummaryMetrics = useMemo<SummaryMetric[]>(
        () => [
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
        ],
        [tradeSummary, tradeTotal, tradeRecords.length]
    );

    const transactionSummaryMetrics = useMemo<SummaryMetric[]>(
        () => [
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
        ],
        [transactionSummary, transactionTotal]
    );

    const equitySummaryMetrics = useMemo<SummaryMetric[]>(
        () => [
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
        ],
        [latestEquity, latestAvailable, averageEquity, snapshots.length]
    );

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
                if (entry.total_pnl_usdt > 0) winners += 1;
                else if (entry.total_pnl_usdt < 0) losers += 1;
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

    const hypothesisSummaryMetrics = useMemo<SummaryMetric[]>(
        () => [
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
        ],
        [hypothesisSummary, hypothesisPnlEntries.length]
    );

    const refreshAll = () => {
        refreshTrades();
        refreshTransactions();
        refreshEquity();
        refreshHypothesis();
    };

    return (
        <section className="space-y-6">
            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h2 className="text-2xl font-semibold text-white">Сверка с Bybit</h2>
                        <p className="mt-1 text-sm text-slate-400">
                            Реализованный PnL, комиссии и equity напрямую с биржи. Сравниваем с внутренней статистикой CTO-AI.
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={refreshAll}
                        className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                    >
                        <FiRefreshCcw className="text-base" />
                        Обновить все
                    </button>
                </div>
                {(tradesError || transactionsError || equityError || internalError || hypothesisError) && (
                    <div className="mt-4 space-y-2 text-sm text-rose-200">
                        {tradesError && <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-2">{tradesError}</div>}
                        {transactionsError && (
                            <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-2">{transactionsError}</div>
                        )}
                        {equityError && <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-2">{equityError}</div>}
                        {internalError && <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-2">{internalError}</div>}
                        {hypothesisError && <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-2">{hypothesisError}</div>}
                    </div>
                )}
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                {deltas.map((item) => {
                    const hasDelta = item.delta !== null && item.delta !== undefined;
                    const deltaClass = hasDelta
                        ? item.delta! > 0
                            ? 'text-emerald-300'
                            : item.delta! < 0
                                ? 'text-rose-300'
                                : 'text-slate-300'
                        : 'text-slate-300';
                    return (
                        <div key={item.label} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-card">
                            <div className="text-xs uppercase tracking-wide text-slate-400">{item.label}</div>
                            <div className="mt-3 space-y-1 text-sm text-slate-300">
                                {item.bybitValue !== null && (
                                    <div>Bybit: <span className="font-semibold text-white">{formatNumber(item.bybitValue)} {item.unit ?? ''}</span></div>
                                )}
                                {item.internalValue !== null && (
                                    <div>CTO-AI: <span className="font-semibold text-white">{formatNumber(item.internalValue)} {item.unit ?? ''}</span></div>
                                )}
                                {hasDelta && (
                                    <div className={`text-base font-semibold ${deltaClass}`}>
                                        Δ {formatNumber(item.delta)} {item.unit ?? ''}
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
                <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Дата начала
                            <input
                                type="datetime-local"
                                value={formatDateInput(tradeFilters.start)}
                                onChange={(event) =>
                                    updateTradeFilters({
                                        start: event.target.value ? new Date(event.target.value).toISOString() : null,
                                    })
                                }
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Дата окончания
                            <input
                                type="datetime-local"
                                value={formatDateInput(tradeFilters.end)}
                                onChange={(event) =>
                                    updateTradeFilters({
                                        end: event.target.value ? new Date(event.target.value).toISOString() : null,
                                    })
                                }
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Символ
                            <input
                                type="text"
                                value={tradeFilters.symbol}
                                onChange={(event) => updateTradeFilters({ symbol: event.target.value.toUpperCase() })}
                                placeholder="BTCUSDT"
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <div className="flex items-end gap-2 text-xs text-slate-400">
                            <button
                                type="button"
                                onClick={resetTradeFilters}
                                className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                            >
                                Сбросить
                            </button>
                            <span>Сделок: {tradeTotal}</span>
                        </div>
                    </div>
                    <div className="flex flex-col gap-3">
                        <div className="flex flex-wrap gap-2">
                            {tradeSummaryMetrics.map((metric) => (
                                <SummaryBadge key={metric.label} {...metric} />
                            ))}
                        </div>
                        <button
                            type="button"
                            onClick={() => setTradesExpanded((value) => !value)}
                            className="inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                        >
                            {tradesExpanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                            {tradesExpanded ? 'Скрыть таблицу' : 'Показать сделки'}
                        </button>
                    </div>
                </header>

                {tradesExpanded && (
                    <div className="mt-4 overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60">
                        {tradesLoading ? (
                            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
                                Загрузка сделок Bybit…
                            </div>
                        ) : tradeRecords.length ? (
                            <table className="min-w-full divide-y divide-slate-800 text-sm">
                                <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
                                    <tr>
                                        <th className="px-4 py-3 text-left">Время</th>
                                        <th className="px-4 py-3 text-left">Инструмент</th>
                                        <th className="px-4 py-3 text-left">Сторона</th>
                                        <th className="px-4 py-3 text-left">Цена</th>
                                        <th className="px-4 py-3 text-left">Количество</th>
                                        <th className="px-4 py-3 text-left">PnL</th>
                                        <th className="px-4 py-3 text-left">Комиссия</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800">
                                    {tradeRecords.map((trade) => (
                                        <tr key={trade.exec_id} className="hover:bg-slate-800/30">
                                            <td className="px-4 py-3 text-slate-300">
                                                {trade.trade_time ? new Date(trade.trade_time).toLocaleString('ru-RU') : '—'}
                                            </td>
                                            <td className="px-4 py-3 text-white">
                                                <div className="font-semibold">{trade.symbol}</div>
                                                <div className="text-xs text-slate-500">{trade.exec_id.slice(-8)}</div>
                                            </td>
                                            <td className="px-4 py-3 capitalize text-slate-300">{trade.side?.toLowerCase() ?? '—'}</td>
                                            <td className="px-4 py-3 text-slate-300">{formatNumber(trade.price)}</td>
                                            <td className="px-4 py-3 text-slate-300">{formatNumber(trade.quantity, 4)}</td>
                                            <td
                                                className={`px-4 py-3 font-semibold ${trade.realized_pnl
                                                    ? trade.realized_pnl > 0
                                                        ? 'text-emerald-300'
                                                        : trade.realized_pnl < 0
                                                            ? 'text-rose-300'
                                                            : 'text-slate-300'
                                                    : 'text-slate-300'
                                                    }`}
                                            >
                                                {formatNumber(trade.realized_pnl)} USDT
                                            </td>
                                            <td className="px-4 py-3 text-slate-300">
                                                {formatNumber(trade.fee)} {trade.fee_currency ?? ''}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
                                Нет сделок в выбранном диапазоне.
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
                <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Дата начала
                            <input
                                type="datetime-local"
                                value={formatDateInput(transactionFilters.start)}
                                onChange={(event) =>
                                    updateTransactionFilters({
                                        start: event.target.value ? new Date(event.target.value).toISOString() : null,
                                    })
                                }
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Дата окончания
                            <input
                                type="datetime-local"
                                value={formatDateInput(transactionFilters.end)}
                                onChange={(event) =>
                                    updateTransactionFilters({
                                        end: event.target.value ? new Date(event.target.value).toISOString() : null,
                                    })
                                }
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Тип операции
                            <input
                                type="text"
                                value={transactionFilters.txType}
                                onChange={(event) => updateTransactionFilters({ txType: event.target.value.toUpperCase() })}
                                placeholder="FUNDING"
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <div className="flex items-end gap-2 text-xs text-slate-400">
                            <button
                                type="button"
                                onClick={resetTransactionFilters}
                                className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                            >
                                Сбросить
                            </button>
                            <span>Транзакций: {transactionTotal}</span>
                        </div>
                    </div>
                    <div className="flex flex-col gap-3">
                        <div className="flex flex-wrap gap-2">
                            {transactionSummaryMetrics.map((metric) => (
                                <SummaryBadge key={metric.label} {...metric} />
                            ))}
                        </div>
                        <p className="text-xs text-slate-400">Сводка рассчитывается по данным Bybit transaction log.</p>
                        <button
                            type="button"
                            onClick={() => setTransactionsExpanded((value) => !value)}
                            className="inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                        >
                            {transactionsExpanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                            {transactionsExpanded ? 'Скрыть таблицу' : 'Показать транзакции'}
                        </button>
                    </div>
                </header>
                {transactionsExpanded && (
                    <div className="mt-6 overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60">
                        {transactionsLoading ? (
                            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
                                Загрузка транзакций Bybit…
                            </div>
                        ) : transactionRecords.length ? (
                            <table className="min-w-full divide-y divide-slate-800 text-sm">
                                <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
                                    <tr>
                                        <th className="px-4 py-3 text-left">Время</th>
                                        <th className="px-4 py-3 text-left">Тип</th>
                                        <th className="px-4 py-3 text-left">Сумма</th>
                                        <th className="px-4 py-3 text-left">Комиссия</th>
                                        <th className="px-4 py-3 text-left">Привязка</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800">
                                    {transactionRecords.map((item) => (
                                        <tr key={item.transaction_id} className="hover:bg-slate-800/30">
                                            <td className="px-4 py-3 text-slate-300">
                                                {item.created_time ? new Date(item.created_time).toLocaleString('ru-RU') : '—'}
                                            </td>
                                            <td className="px-4 py-3 text-white">
                                                <div className="font-semibold">{item.type}</div>
                                                {item.sub_type && <div className="text-xs text-slate-500">{item.sub_type}</div>}
                                            </td>
                                            <td
                                                className={`px-4 py-3 font-semibold ${item.amount
                                                    ? item.amount > 0
                                                        ? 'text-emerald-300'
                                                        : item.amount < 0
                                                            ? 'text-rose-300'
                                                            : 'text-slate-300'
                                                    : 'text-slate-300'
                                                    }`}
                                            >
                                                {formatNumber(item.amount)} {item.currency ?? ''}
                                            </td>
                                            <td className="px-4 py-3 text-slate-300">{formatNumber(item.fee)} {item.currency ?? ''}</td>
                                            <td className="px-4 py-3 text-xs text-slate-300">{item.reference_id ?? '—'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
                                Нет транзакций в выбранном диапазоне.
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
                <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-[repeat(4,minmax(0,1fr))]">
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Дата начала
                            <input
                                type="datetime-local"
                                value={formatDateInput(equityFilters.start)}
                                onChange={(event) =>
                                    updateEquityFilters({
                                        start: event.target.value ? new Date(event.target.value).toISOString() : null,
                                    })
                                }
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Дата окончания
                            <input
                                type="datetime-local"
                                value={formatDateInput(equityFilters.end)}
                                onChange={(event) =>
                                    updateEquityFilters({
                                        end: event.target.value ? new Date(event.target.value).toISOString() : null,
                                    })
                                }
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <label className="flex flex-col gap-2 text-xs text-slate-400">
                            Срезов
                            <input
                                type="number"
                                min={20}
                                max={500}
                                value={equityFilters.limit}
                                onChange={(event) =>
                                    updateEquityFilters({
                                        limit: Math.max(20, Math.min(500, Number(event.target.value) || DEFAULT_EQUITY_LIMIT)),
                                    })
                                }
                                className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                            />
                        </label>
                        <div className="flex items-end gap-2 text-xs text-slate-400">
                            <button
                                type="button"
                                onClick={resetEquityFilters}
                                className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                            >
                                Сбросить
                            </button>
                            <span>Срезов: {snapshots.length}</span>
                        </div>
                    </div>
                    <div className="flex flex-col gap-3">
                        <div className="flex flex-wrap gap-2">
                            {equitySummaryMetrics.map((metric) => (
                                <SummaryBadge key={metric.label} {...metric} />
                            ))}
                        </div>
                        <p className="text-xs text-slate-400">
                            Последний снимок: {latest?.captured_at ? new Date(latest.captured_at).toLocaleString('ru-RU') : '—'}
                        </p>
                        <button
                            type="button"
                            onClick={() => setEquityExpanded((value) => !value)}
                            className="inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                        >
                            {equityExpanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                            {equityExpanded ? 'Скрыть таблицу' : 'Показать equity-срезы'}
                        </button>
                    </div>
                </header>

                {equityExpanded && (
                    <div className="mt-6 overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60">
                        {equityLoading ? (
                            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
                                Загрузка equity Bybit…
                            </div>
                        ) : snapshots.length ? (
                            <table className="min-w-full divide-y divide-slate-800 text-sm">
                                <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
                                    <tr>
                                        <th className="px-4 py-3 text-left">Время</th>
                                        <th className="px-4 py-3 text-left">Equity</th>
                                        <th className="px-4 py-3 text-left">Wallet</th>
                                        <th className="px-4 py-3 text-left">Available</th>
                                        <th className="px-4 py-3 text-left">Валюта</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800">
                                    {snapshots.map((snapshot, index) => (
                                        <tr key={snapshot.captured_at ?? `equity-${index}`} className="hover:bg-slate-800/30">
                                            <td className="px-4 py-3 text-slate-300">
                                                {snapshot.captured_at ? new Date(snapshot.captured_at).toLocaleString('ru-RU') : '—'}
                                            </td>
                                            <td className="px-4 py-3 text-white">{formatNumber(snapshot.total_equity)}</td>
                                            <td className="px-4 py-3 text-slate-300">{formatNumber(snapshot.wallet_balance)}</td>
                                            <td className="px-4 py-3 text-slate-300">{formatNumber(snapshot.available_balance)}</td>
                                            <td className="px-4 py-3 text-slate-300">{snapshot.currency ?? 'USDT'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
                                Нет equity-срезов в выбранном диапазоне.
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
                <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                        <h3 className="text-xl font-semibold text-white">PnL по гипотезам</h3>
                        <p className="text-sm text-slate-400">
                            Суммируем все закрытые сделки, связанные с каждой гипотезой. Видно, на чём идея зарабатывает или теряет.
                        </p>
                    </div>
                    <div className="flex flex-col gap-3">
                        <div className="flex flex-wrap gap-2">
                            {hypothesisSummaryMetrics.map((metric) => (
                                <SummaryBadge key={metric.label} {...metric} />
                            ))}
                        </div>
                        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                            <label className="flex items-center gap-2">
                                Показывать
                                <input
                                    type="number"
                                    min={5}
                                    max={500}
                                    value={hypothesisFilters.limit}
                                    onChange={(event) => updateHypothesisFilters({ limit: Math.max(5, Math.min(500, Number(event.target.value) || hypothesisFilters.limit)) })}
                                    className="w-20 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                                />
                            </label>
                            <button
                                type="button"
                                onClick={resetHypothesisFilters}
                                className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                            >
                                Сбросить
                            </button>
                            <button
                                type="button"
                                onClick={refreshHypothesis}
                                className="inline-flex items-center gap-2 rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                            >
                                <FiRefreshCcw className="text-base" /> Обновить
                            </button>
                            <button
                                type="button"
                                onClick={() => setHypothesisExpanded((value) => !value)}
                                className="inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                            >
                                {hypothesisExpanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                                {hypothesisExpanded ? 'Скрыть таблицу' : 'Показать список'}
                            </button>
                        </div>
                    </div>
                </header>

                {hypothesisExpanded && (
                    <div className="mt-6 overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60">
                        {hypothesisLoading ? (
                            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
                                Считаем PnL по гипотезам…
                            </div>
                        ) : hypothesisPnlEntries.length ? (
                            <table className="min-w-full divide-y divide-slate-800 text-sm">
                                <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
                                    <tr>
                                        <th className="px-4 py-3 text-left">Гипотеза</th>
                                        <th className="px-4 py-3 text-left">Инструмент</th>
                                        <th className="px-4 py-3 text-left">Направление</th>
                                        <th className="px-4 py-3 text-left">Сделок</th>
                                        <th className="px-4 py-3 text-left">Итого PnL</th>
                                        <th className="px-4 py-3 text-left">Средний %</th>
                                        <th className="px-4 py-3 text-left">Последнее закрытие</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800">
                                    {hypothesisPnlEntries.map((entry: HypothesisPnlEntry) => (
                                        <tr key={entry.hypothesis_id} className="hover:bg-slate-800/30">
                                            <td className="px-4 py-3 text-white">
                                                <div className="font-semibold">{entry.hypothesis_id}</div>
                                                <div className="text-xs text-slate-500">{entry.last_closed_at ? 'Закрыто' : 'Ещё открыта'}</div>
                                            </td>
                                            <td className="px-4 py-3 text-slate-300">{entry.symbol ?? '—'}</td>
                                            <td className="px-4 py-3 text-slate-300">{entry.direction ?? '—'}</td>
                                            <td className="px-4 py-3 text-slate-300">{entry.trades}</td>
                                            <td
                                                className={`px-4 py-3 font-semibold ${entry.total_pnl_usdt
                                                    ? entry.total_pnl_usdt > 0
                                                        ? 'text-emerald-300'
                                                        : entry.total_pnl_usdt < 0
                                                            ? 'text-rose-300'
                                                            : 'text-slate-300'
                                                    : 'text-slate-300'
                                                    }`}
                                            >
                                                {formatNumber(entry.total_pnl_usdt)} USDT
                                            </td>
                                            <td className="px-4 py-3 text-slate-300">{formatNumber(entry.avg_pnl_pct)} %</td>
                                            <td className="px-4 py-3 text-slate-300">
                                                {entry.last_closed_at ? new Date(entry.last_closed_at).toLocaleString('ru-RU') : '—'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
                                Пока нет закрытых сделок по гипотезам.
                            </div>
                        )}
                    </div>
                )}
            </div>
        </section>
    );
}
