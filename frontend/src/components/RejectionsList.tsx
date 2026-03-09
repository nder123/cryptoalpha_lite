import { useMemo, useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';

import { clearRejections } from '../api';
import type { RejectionEntry } from '../types';

type Props = {
    rejections: RejectionEntry[];
};

export function RejectionsList({ rejections }: Props) {
    const summary = useMemo(() => {
        const total = rejections.length;
        const uniqueHypotheses = new Set(rejections.map((item) => item.hypothesis_id)).size;
        const uniqueSymbols = new Set(rejections.map((item) => item.symbol)).size;
        const lastTimestamp = rejections[rejections.length - 1]?.created_at ?? null;
        return { total, uniqueHypotheses, uniqueSymbols, lastTimestamp };
    }, [rejections]);

    const [expanded, setExpanded] = useState(false);
    const [clearing, setClearing] = useState(false);

    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card">
            <header className="flex flex-col gap-3 border-b border-slate-800 px-6 py-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-white">Последние отклонения</h2>
                    <p className="text-sm text-slate-400">Обоснования решений Risk/CTO-AI</p>
                </div>
                <div className="flex flex-col items-start gap-3 md:items-end">
                    <div className="flex flex-wrap gap-2">
                        <SummaryBadge label="Всего" value={summary.total} fractionDigits={0} />
                        <SummaryBadge label="Гипотез" value={summary.uniqueHypotheses} fractionDigits={0} />
                        <SummaryBadge label="Инструментов" value={summary.uniqueSymbols} fractionDigits={0} />
                        <SummaryBadge
                            label="Последнее"
                            value={summary.lastTimestamp ? Date.parse(summary.lastTimestamp) : null}
                            render={(val) =>
                                typeof val === 'number'
                                    ? new Date(val).toLocaleTimeString('ru-RU', {
                                        hour: '2-digit',
                                        minute: '2-digit',
                                        second: '2-digit',
                                    })
                                    : '—'
                            }
                        />
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            type="button"
                            disabled={clearing || rejections.length === 0}
                            onClick={async () => {
                                if (rejections.length === 0) {
                                    return;
                                }
                                if (!confirm('Очистить список отклонений?')) {
                                    return;
                                }
                                setClearing(true);
                                try {
                                    await clearRejections();
                                } catch (error) {
                                    console.error('Failed to clear rejections', error);
                                } finally {
                                    setClearing(false);
                                }
                            }}
                            className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Очистить
                        </button>
                        <button
                            type="button"
                            onClick={() => setExpanded((value) => !value)}
                            className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                        >
                            {expanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                            {expanded ? 'Скрыть список' : 'Показать детали'}
                        </button>
                    </div>
                </div>
            </header>

            {expanded && (
                <div className="max-h-80 overflow-y-auto px-6 py-4">
                    {rejections.length === 0 ? (
                        <p className="text-sm text-slate-400">Пока всё чисто. Риски не заблокировали сделки.</p>
                    ) : (
                        <ul className="space-y-4">
                            {rejections
                                .slice(-20)
                                .reverse()
                                .map((item) => (
                                    <li key={`${item.hypothesis_id}-${item.created_at}`} className="space-y-2 rounded-xl bg-slate-900/80 p-3">
                                        <div className="flex items-center justify_between text-sm text-indigo-200">
                                            <span className="font-semibold text-slate-100">{item.symbol}</span>
                                            <span className="text-xs text-slate-400">
                                                {new Date(item.created_at).toLocaleTimeString('ru-RU', {
                                                    hour: '2-digit',
                                                    minute: '2-digit',
                                                    second: '2-digit',
                                                })}
                                            </span>
                                        </div>
                                        <ul className="list-disc space-y-1 pl-4 text-xs text-slate-300">
                                            {item.reasons.map((reason, index) => (
                                                <li key={index}>{reason}</li>
                                            ))}
                                        </ul>
                                    </li>
                                ))}
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
    fractionDigits?: number;
    render?: (value: number | null) => string;
};

function SummaryBadge({ label, value, fractionDigits = 0, render }: SummaryBadgeProps) {
    const content = render
        ? render(value)
        : value === null || Number.isNaN(value)
            ? '—'
            : value.toLocaleString('ru-RU', {
                minimumFractionDigits: fractionDigits,
                maximumFractionDigits: fractionDigits,
            });
    return (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
            <div className="text-sm font-semibold text-white">{content}</div>
        </div>
    );
}
