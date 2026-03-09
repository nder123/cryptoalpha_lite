import { useMemo, useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';

import type { AuditEvent } from '../types';

type Props = {
    events: AuditEvent[];
};

function formatTimestamp(value: string | null) {
    if (!value) return '—';
    const date = new Date(value);
    return date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}

function formatNumber(value: unknown, fractionDigits = 2) {
    const num = typeof value === 'number' ? value : value === null || value === undefined ? null : Number(value);
    if (num === null || Number.isNaN(num)) return '—';
    return num.toFixed(fractionDigits);
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function snapshotSummary(payload: Record<string, unknown>) {
    const symbol = typeof payload.symbol === 'string' ? payload.symbol : null;
    const score = payload.market_score ?? payload.score;
    const status = typeof payload.status === 'string' ? payload.status : null;
    const timestamp = typeof payload.timestamp === 'string' ? payload.timestamp : null;
    const metrics = isRecord(payload.metrics) ? payload.metrics : null;
    if (!symbol && !metrics) return null;

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

export function AuditLog({ events }: Props) {
    const summary = useMemo(() => {
        const total = events.length;
        const uniqueStreams = new Set(events.map((event) => event.stream)).size;
        const latest = events[0]?.created_at ?? null;
        return { total, uniqueStreams, latest };
    }, [events]);

    const [expanded, setExpanded] = useState(false);

    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card">
            <header className="flex flex-col gap-3 border-b border-slate-800 px-6 py-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-white">Аудит событий</h2>
                    <p className="text-sm text-slate-400">Хронология сигналов и действий системы</p>
                </div>
                <div className="flex flex-col items-start gap-3 md:items-end">
                    <div className="flex flex-wrap gap-2">
                        <SummaryBadge label="Записей" value={summary.total} />
                        <SummaryBadge label="Потоков" value={summary.uniqueStreams} />
                        <SummaryBadge
                            label="Последнее"
                            value={summary.latest ? Date.parse(summary.latest) : null}
                            render={(val) =>
                                typeof val === 'number'
                                    ? formatTimestamp(new Date(val).toISOString())
                                    : '—'
                            }
                        />
                    </div>
                    <button
                        type="button"
                        onClick={() => setExpanded((value) => !value)}
                        className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                    >
                        {expanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                        {expanded ? 'Скрыть журнал' : 'Показать журнал'}
                    </button>
                </div>
            </header>

            {expanded && (
                <div className="max-h-[28rem] overflow-y-auto">
                    {events.length === 0 ? (
                        <p className="px-6 py-4 text-sm text-slate-400">Журнал пуст.</p>
                    ) : (
                        <ul className="divide-y divide-slate-800">
                            {events.slice(0, 50).map((event) => {
                                const summary = snapshotSummary(event.payload);
                                const headerSymbol = summary?.symbol;
                                const headerTime = summary?.timestamp ?? event.created_at;

                                return (
                                    <li key={event.id} className="px-6 py-4">
                                        <details className="group rounded-2xl bg-slate-950/30 p-3">
                                            <summary className="flex cursor-pointer list-none flex-col gap-2">
                                                <div className="flex items-center justify-between text-xs text-slate-400">
                                                    <span className="rounded-full bg-slate-800 px-2 py-1 font-mono text-[11px] uppercase tracking-wide text-indigo-300">
                                                        {event.stream}
                                                    </span>
                                                    <span>{formatTimestamp(headerTime)}</span>
                                                </div>

                                                <div className="flex flex-wrap items-center justify-between gap-2">
                                                    <div className="text-sm font-semibold text-white">
                                                        {headerSymbol ? `${headerSymbol} • ${event.event_type}` : event.event_type}
                                                    </div>
                                                    <div className="flex items-center gap-2 text-xs text-slate-400">
                                                        <span className="hidden group-open:inline-flex">
                                                            <FiChevronUp className="text-base" />
                                                        </span>
                                                        <span className="inline-flex group-open:hidden">
                                                            <FiChevronDown className="text-base" />
                                                        </span>
                                                    </div>
                                                </div>

                                                {summary ? (
                                                    <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2 lg:grid-cols-4">
                                                        <div>
                                                            <span className="text-slate-500">Score:</span>{' '}
                                                            <span className="text-slate-200">{formatNumber(summary.score, 2)}</span>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Статус:</span>{' '}
                                                            <span className="text-slate-200">{summary.status ?? '—'}</span>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Цена:</span>{' '}
                                                            <span className="text-slate-200">{formatNumber(summary.lastPrice, 4)}</span>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Funding:</span>{' '}
                                                            <span className="text-slate-200">{formatNumber(summary.funding, 6)}</span>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">Volume 24h:</span>{' '}
                                                            <span className="text-slate-200">{formatNumber(summary.volume, 2)}</span>
                                                        </div>
                                                        <div>
                                                            <span className="text-slate-500">OI:</span>{' '}
                                                            <span className="text-slate-200">{formatNumber(summary.openInterest, 2)}</span>
                                                        </div>
                                                    </div>
                                                ) : null}
                                            </summary>

                                            <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950/60 p-3 text-xs text-slate-300">
                                                {JSON.stringify(event.payload, null, 2)}
                                            </pre>
                                        </details>
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>
            )}
        </section>
    );
}

type SummaryBadgeProps = {
    label: string;
    value: number | null;
    render?: (value: number | null) => string;
};

function SummaryBadge({ label, value, render }: SummaryBadgeProps) {
    const content = render
        ? render(value)
        : value === null || Number.isNaN(value)
            ? '—'
            : value.toLocaleString('ru-RU', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
            });
    return (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
            <div className="text-sm font-semibold text-white">{content}</div>
        </div>
    );
}
