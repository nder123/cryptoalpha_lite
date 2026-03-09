import { useMemo, useState } from 'react';
import { FiRefreshCcw, FiDownload, FiChevronDown, FiChevronUp } from 'react-icons/fi';

import { useTradeStats } from '../hooks/useTradeStats';
import { TradeStatsSummaryCards } from './TradeStatsSummaryCards';
import { TradeStatsTable } from './TradeStatsTable';

type SummaryMetric = {
    label: string;
    value: number | null;
    unit?: string;
    fractionDigits?: number;
    trend?: 'goodIfPositive' | 'goodIfNegative';
};

function formatMetricValue(value: number | null, fractionDigits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return '—';
    }
    return value.toLocaleString('ru-RU', {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    });
}

function SummaryBadge({ label, value, unit, fractionDigits = 2, trend }: SummaryMetric) {
    const formatted = formatMetricValue(value, fractionDigits);
    const display = formatted === '—' ? formatted : unit ? `${formatted} ${unit}` : formatted;
    let toneClass = 'text-white';
    if (value === null || value === undefined || Number.isNaN(value)) {
        toneClass = 'text-slate-300';
    } else if (trend === 'goodIfPositive') {
        toneClass = value >= 0 ? 'text-emerald-200' : 'text-rose-300';
    } else if (trend === 'goodIfNegative') {
        toneClass = value <= 0 ? 'text-emerald-200' : 'text-rose-300';
    }
    return (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
            <div className={`text-sm font-semibold ${toneClass}`}>{display}</div>
        </div>
    );
}

function formatDateInput(value: string | null) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    const iso = date.toISOString();
    return iso.slice(0, 16);
}

export function TradeStatsSection() {
    const {
        filters,
        records,
        total,
        summary,
        daily,
        weekly,
        loading,
        error,
        updateFilters,
        resetFilters,
        refresh,
        exportCsv,
        exporting,
    } = useTradeStats();

    const [expanded, setExpanded] = useState(false);

    const summaryMetrics = useMemo<SummaryMetric[]>(() => {
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

    return (
        <section className="space-y-6">
            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h2 className="text-2xl font-semibold text-white">Статистика сделок</h2>
                        <p className="mt-1 text-sm text-slate-400">
                            Автоматический журнал завершённых сделок с PnL, R/R и попаданиями по TP/SL. Формируется из
                            отчётов Execution Engine.
                        </p>
                    </div>
                    <div className="flex flex-col items-start gap-3 md:items-end">
                        <div className="flex flex-wrap gap-2">
                            {summaryMetrics.map((metric) => (
                                <SummaryBadge key={metric.label} {...metric} />
                            ))}
                        </div>
                        <div className="flex flex-wrap gap-2 text-sm">
                            <button
                                type="button"
                                onClick={refresh}
                                className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                            >
                                <FiRefreshCcw className="text-base" />
                                Обновить
                            </button>
                            <button
                                type="button"
                                disabled={exporting}
                                onClick={exportCsv}
                                className={`inline-flex items-center gap-2 rounded-full px-4 py-2 transition ${exporting
                                    ? 'cursor-not-allowed border border-slate-700 bg-slate-800 text-slate-500'
                                    : 'border border-emerald-400/60 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20'
                                    }`}
                            >
                                <FiDownload className="text-base" />
                                Экспорт CSV
                            </button>
                            <button
                                type="button"
                                onClick={() => setExpanded((value) => !value)}
                                className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                            >
                                {expanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                                {expanded ? 'Скрыть журнал' : 'Показать журнал'}
                            </button>
                        </div>
                    </div>
                </div>

                <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                    <label className="flex flex-col gap-2 text-xs text-slate-400">
                        Дата начала
                        <input
                            type="datetime-local"
                            value={formatDateInput(filters.start)}
                            onChange={(event) =>
                                updateFilters({ start: event.target.value ? new Date(event.target.value).toISOString() : null })
                            }
                            className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        />
                    </label>
                    <label className="flex flex-col gap-2 text-xs text-slate-400">
                        Дата окончания
                        <input
                            type="datetime-local"
                            value={formatDateInput(filters.end)}
                            onChange={(event) =>
                                updateFilters({ end: event.target.value ? new Date(event.target.value).toISOString() : null })
                            }
                            className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        />
                    </label>
                    <label className="flex flex-col gap-2 text-xs text-slate-400">
                        Символ
                        <input
                            type="text"
                            value={filters.symbol}
                            onChange={(event) => updateFilters({ symbol: event.target.value.toUpperCase() })}
                            placeholder="Например, BTCUSDT"
                            className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        />
                    </label>
                    <div className="flex items-end gap-2">
                        <button
                            type="button"
                            onClick={resetFilters}
                            className="rounded-xl border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                        >
                            Сбросить фильтры
                        </button>
                        <div className="text-xs text-slate-500">Сделок: {total}</div>
                    </div>
                </div>

                {error && <div className="mt-4 rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>}
            </div>

            {expanded ? (
                <div className="max-h-[520px] overflow-auto rounded-2xl border border-slate-800 bg-slate-950/50 shadow-card">
                    <TradeStatsTable records={records} loading={loading} />
                </div>
            ) : null}

            <TradeStatsSummaryCards summary={summary} loading={loading} />

            <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <h3 className="text-sm font-semibold text-white">PnL по дням</h3>
                    <ul className="mt-3 space-y-2 text-sm text-slate-300">
                        {daily.length ? (
                            daily.map((entry, index) => {
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
                                return (
                                    <li key={entry.period_start ?? `daily-${index}`} className="flex items-center justify-between">
                                        <span className="text-xs text-slate-500">{dateLabel}</span>
                                        <span className={`font-medium ${pnlClass}`}>
                                            {pnlValue !== null ? pnlValue.toFixed(2) : '—'} USDT
                                        </span>
                                    </li>
                                );
                            })
                        ) : (
                            <li className="text-xs text-slate-500">Нет данных для выбранного периода.</li>
                        )}
                    </ul>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <h3 className="text-sm font-semibold text-white">PnL по неделям</h3>
                    <ul className="mt-3 space-y-2 text-sm text-slate-300">
                        {weekly.length ? (
                            weekly.map((entry, index) => {
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
                                return (
                                    <li key={entry.period_start ?? `weekly-${index}`} className="flex items-center justify-between">
                                        <span className="text-xs text-slate-500">{dateLabel}</span>
                                        <span className={`font-medium ${pnlClass}`}>
                                            {pnlValue !== null ? pnlValue.toFixed(2) : '—'} USDT
                                        </span>
                                    </li>
                                );
                            })
                        ) : (
                            <li className="text-xs text-slate-500">Нет данных для выбранного периода.</li>
                        )}
                    </ul>
                </div>
            </div>
        </section>
    );
}
