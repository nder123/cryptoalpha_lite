import { useMemo, useState } from 'react';

import type { PositionEntry, TradeStatsOverview } from '../types';

interface Props {
    tradeStats: TradeStatsOverview | null;
    positions: PositionEntry[];
}

function formatSigned(value: number | null | undefined, fractionDigits = 2): string {
    if (value === null || value === undefined) {
        return '—';
    }
    const fixed = value.toFixed(fractionDigits);
    return value > 0 ? `+${fixed}` : fixed;
}

function formatTimestamp(value: string | null | undefined): string {
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

function valueTone(value: number | null | undefined): string {
    if (value === null || value === undefined) return 'text-slate-200';
    if (value > 0) return 'text-emerald-300';
    if (value < 0) return 'text-rose-300';
    return 'text-slate-200';
}

function sumUnrealized(positions: PositionEntry[]): number {
    return positions.reduce((total, position) => total + (position.unrealized_pnl ?? 0), 0);
}

function computeDailyPnl(tradeStats: TradeStatsOverview | null): number | null {
    if (!tradeStats) return null;
    const today = new Date();
    const dayKey = today.toISOString().slice(0, 10);
    const total = tradeStats.recent.reduce((acc, entry) => {
        if (!entry.closed_at) return acc;
        const entryDay = entry.closed_at.slice(0, 10);
        if (entryDay !== dayKey) return acc;
        return acc + (entry.pnl_usdt ?? 0);
    }, 0);
    return total;
}

export function TradeOverviewSummary({ tradeStats, positions }: Props) {
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

    return (
        <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
            <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-xl font-semibold text-white">Итоги торговли</h2>
                    <p className="text-sm text-slate-400">Сводка dry-run за последние операции.</p>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                    <span>Обновлено: {formatTimestamp(tradeStats?.updated_at)}</span>
                    <button
                        type="button"
                        onClick={() => setExpanded((value) => !value)}
                        className="rounded-full border border-slate-700 px-3 py-1 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                    >
                        {expanded ? 'Свернуть детали' : 'Раскрыть детали'}
                    </button>
                </div>
            </header>

            <div className="mt-5 grid gap-4 md:grid-cols-3">
                <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <h3 className="text-xs uppercase tracking-wide text-slate-400">Общий PnL</h3>
                    <p className={`mt-3 text-3xl font-semibold ${valueTone(overallPnl)}`}>
                        {formatSigned(overallPnl)} <span className="text-base text-slate-400">USDT</span>
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Учтены закрытые сделки + текущая нереализованная прибыль.</p>
                </article>
                <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <h3 className="text-xs uppercase tracking-wide text-slate-400">Последний PnL</h3>
                    <p className={`mt-3 text-3xl font-semibold ${valueTone(lastTradePnl)}`}>
                        {formatSigned(lastTradePnl)} <span className="text-base text-slate-400">USDT</span>
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Результат последней закрытой сделки.</p>
                </article>
                <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                    <h3 className="text-xs uppercase tracking-wide text-slate-400">Открытые позиции</h3>
                    <p className="mt-3 text-3xl font-semibold text-sky-300">{openPositions.length}</p>
                    <p className="mt-1 text-xs text-slate-500">Совпадает с таблицей «Позиции».</p>
                </article>
            </div>

            {expanded && (
                <div className="mt-6 space-y-6">
                    <div className="grid gap-4 md:grid-cols-2">
                        <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                            <h3 className="text-xs uppercase tracking-wide text-slate-400">PnL (день)</h3>
                            <p className={`mt-3 text-2xl font-semibold ${valueTone(dailyPnl)}`}>
                                {formatSigned(dailyPnl)} <span className="text-base text-slate-400">USDT</span>
                            </p>
                            <p className="mt-1 text-xs text-slate-500">Сумма завершённых сделок за сегодня.</p>
                        </article>
                        <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                            <h3 className="text-xs uppercase tracking-wide text-slate-400">PnL (всего)</h3>
                            <p className={`mt-3 text-2xl font-semibold ${valueTone(realizedPnl)}`}>
                                {formatSigned(realizedPnl)} <span className="text-base text-slate-400">USDT</span>
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                                Реализованный результат всех закрытых сделок (после комиссий, если доступны).
                            </p>
                        </article>
                    </div>

                    {realizedPnlNet !== null || realizedFees !== null ? (
                        <div className="grid gap-4 md:grid-cols-2">
                            <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                                <h3 className="text-xs uppercase tracking-wide text-slate-400">PnL (брутто)</h3>
                                <p className={`mt-3 text-2xl font-semibold ${valueTone(realizedPnlGross)}`}>
                                    {formatSigned(realizedPnlGross)} <span className="text-base text-slate-400">USDT</span>
                                </p>
                                <p className="mt-1 text-xs text-slate-500">Без вычета комиссий.</p>
                            </article>
                            <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                                <h3 className="text-xs uppercase tracking-wide text-slate-400">Комиссии</h3>
                                <p className="mt-3 text-2xl font-semibold text-slate-200">
                                    {formatSigned(realizedFees)} <span className="text-base text-slate-400">USDT</span>
                                </p>
                                <p className="mt-1 text-xs text-slate-500">Сумма комиссий по закрытым сделкам.</p>
                            </article>
                        </div>
                    ) : null}

                    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                        <h3 className="text-sm font-semibold text-white">Последняя сделка</h3>
                        {lastTrade ? (
                            <dl className="mt-3 grid gap-3 text-sm text-slate-300 sm:grid-cols-2 lg:grid-cols-4">
                                <div>
                                    <dt className="text-xs uppercase tracking-wide text-slate-400">Инструмент</dt>
                                    <dd className="mt-1 font-semibold text-white">
                                        {lastTrade.symbol}{' '}
                                        <span className="text-slate-400">({lastTrade.direction})</span>
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-xs uppercase tracking-wide text-slate-400">PnL</dt>
                                    <dd className={`mt-1 font-semibold ${valueTone(lastTradePnl)}`}>
                                        {formatSigned(lastTradePnl)} USDT
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-xs uppercase tracking-wide text-slate-400">Длительность</dt>
                                    <dd className="mt-1 text-white">
                                        {lastTrade.duration_seconds !== null && lastTrade.duration_seconds !== undefined
                                            ? `${Math.round(lastTrade.duration_seconds / 60)} мин`
                                            : '—'}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-xs uppercase tracking-wide text-slate-400">Закрыта</dt>
                                    <dd className="mt-1 text-white">{formatTimestamp(lastTrade.closed_at)}</dd>
                                </div>
                            </dl>
                        ) : (
                            <p className="mt-3 text-sm text-slate-400">Пока нет завершённых сделок.</p>
                        )}
                    </div>
                </div>
            )}
        </section>
    );
}
