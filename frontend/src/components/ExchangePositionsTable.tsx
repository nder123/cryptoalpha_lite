import { useMemo, useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';

import type { PositionEntry } from '../types';

function formatNumber(value: number | null | undefined, fractionDigits = 2): string {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return '—';
    }
    return value.toLocaleString('ru-RU', {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    });
}

type SummaryMetric = {
    label: string;
    value: number | null;
    unit?: string;
    fractionDigits?: number;
    trend?: 'goodIfPositive' | 'goodIfNegative';
};

function SummaryBadge({ label, value, unit, fractionDigits = 2, trend }: SummaryMetric) {
    const formatted = value === null ? '—' : formatNumber(value, fractionDigits);
    const display = formatted === '—' ? formatted : unit ? `${formatted} ${unit}` : formatted;
    let toneClass = 'text-white';
    if (value === null) {
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

type Props = {
    positions: PositionEntry[];
};

export function ExchangePositionsTable({ positions }: Props) {
    if (!positions.length) {
        return (
            <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card">
                <h3 className="text-lg font-semibold text-white">Открытые позиции (биржа)</h3>
                <p className="mt-3 text-sm text-slate-400">На бирже нет активных позиций. Портфель в нуле.</p>
            </section>
        );
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

    const metrics = useMemo<SummaryMetric[]>(
        () => [
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
        ],
        [positions.length, summary.avgLeverage, summary.netExposure, summary.totalNotional, summary.totalUnrealized]
    );

    const [expanded, setExpanded] = useState(false);

    return (
        <section className="rounded-2xl border border-emerald-700/60 bg-emerald-950/20 shadow-card">
            <div className="flex flex-col gap-4 border-b border-emerald-800/40 bg-emerald-900/20 px-6 py-5 md:flex-row md:items-center md:justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-white">Открытые позиции (биржа)</h3>
                    <p className="mt-1 text-sm text-emerald-200/80">Синхронизация выполняется каждые 5 секунд.</p>
                </div>
                <div className="flex flex-col items-start gap-3 md:items-end">
                    <div className="flex flex-wrap gap-2">
                        {metrics.map((metric) => (
                            <SummaryBadge key={metric.label} {...metric} />
                        ))}
                    </div>
                    <button
                        type="button"
                        onClick={() => setExpanded((value) => !value)}
                        className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 transition hover:bg-emerald-500/20"
                    >
                        {expanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                        {expanded ? 'Скрыть позиции' : 'Показать список'}
                    </button>
                </div>
            </div>
            {expanded && (
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-emerald-800/60">
                        <thead className="bg-emerald-900/40">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-emerald-200">Инструмент</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-emerald-200">Сторона</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200">Размер</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200">Цена входа</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200">Маркет</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200">Номинал</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200">PnL / %</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200">Ликв. цена</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200">Плечо</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-emerald-200">Обновлено</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-emerald-800/40">
                            {positions.map((position) => {
                                const sideBadgeClass =
                                    position.side === 'short'
                                        ? 'bg-rose-500/20 text-rose-200 border border-rose-500/40'
                                        : 'bg-emerald-500/20 text-emerald-100 border border-emerald-500/40';
                                return (
                                    <tr key={`${position.symbol}-${position.side}`} className="hover:bg-emerald-900/20">
                                        <td className="whitespace-nowrap px-4 py-3 text-sm text-white">
                                            <div className="font-semibold text-white">{position.symbol}</div>
                                            <div className="text-xs text-emerald-300/70">
                                                {position.take_profit ? `TP ${formatNumber(position.take_profit)}` : 'TP —'} •{' '}
                                                {position.stop_loss ? `SL ${formatNumber(position.stop_loss)}` : 'SL —'}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-sm">
                                            <span className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${sideBadgeClass}`}>
                                                {position.side === 'short' ? 'Шорт' : 'Лонг'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right text-sm text-emerald-100">{formatNumber(position.size, 3)}</td>
                                        <td className="px-4 py-3 text-right text-sm text-emerald-100">{formatNumber(position.entry_price)}</td>
                                        <td className="px-4 py-3 text-right text-sm text-emerald-100">{formatNumber(position.mark_price)}</td>
                                        <td className="px-4 py-3 text-right text-sm text-emerald-100">{formatNumber(position.notional_usdt)}</td>
                                        <td className="px-4 py-3 text-right text-sm">
                                            <div className={position.unrealized_pnl && position.unrealized_pnl < 0 ? 'text-rose-300' : 'text-emerald-200'}>
                                                {formatNumber(position.unrealized_pnl)}
                                            </div>
                                            <div className="text-xs text-emerald-200/70">{formatNumber(position.unrealized_pnl_pct)}%</div>
                                        </td>
                                        <td className="px-4 py-3 text-right text-sm text-emerald-100">{formatNumber(position.liquidation_price)}</td>
                                        <td className="px-4 py-3 text-right text-sm text-emerald-100">{formatNumber(position.leverage, 1)}</td>
                                        <td className="px-4 py-3 text-right text-sm text-emerald-200/80">
                                            {position.updated_at
                                                ? new Date(position.updated_at).toLocaleTimeString('ru-RU', {
                                                    hour: '2-digit',
                                                    minute: '2-digit',
                                                })
                                                : '—'}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </section>
    );
}
