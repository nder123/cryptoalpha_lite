import { useMemo } from 'react';

import type { MarketBuckets } from '../types';

const BUCKET_ORDER: Array<keyof MarketBuckets> = ['ignored', 'watch', 'candidate', 'active'];

const BUCKET_META: Record<keyof MarketBuckets, { title: string; accent: string; description: string }> = {
    ignored: {
        title: 'Игнорируемые',
        accent: 'from-slate-800 to-slate-900',
        description: 'Символы вне зоны интереса CTO-AI',
    },
    watch: {
        title: 'Наблюдение',
        accent: 'from-sky-900 to-indigo-900',
        description: 'Символы под пассивным контролем',
    },
    candidate: {
        title: 'Кандидаты',
        accent: 'from-amber-900 to-amber-700',
        description: 'Подготовленные гипотезы к торгам',
    },
    active: {
        title: 'Активные',
        accent: 'from-emerald-900 to-emerald-700',
        description: 'Текущие позиции и сопровождаемые сделки',
    },
};

type Props = {
    market: MarketBuckets;
};

function formatScore(score: number | undefined) {
    if (typeof score !== 'number') return '—';
    return `${Math.round(score)}`;
}

export function MarketOverview({ market }: Props) {
    const data = useMemo(() => {
        return BUCKET_ORDER.map((key) => {
            const entries = Object.entries(market[key]);
            const sorted = entries.sort(([, a], [, b]) => b.score - a.score);
            const top = sorted.slice(0, 3);
            return {
                key,
                count: entries.length,
                top,
            };
        });
    }, [market]);

    return (
        <div className="grid gap-4 xl:grid-cols-4">
            {data.map(({ key, count, top }) => {
                const meta = BUCKET_META[key];
                return (
                    <div
                        key={key}
                        className="relative overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-card"
                    >
                        <div className={`absolute inset-0 opacity-40`}>
                            <div className={`absolute inset-0 bg-gradient-to-br ${meta.accent}`} />
                        </div>
                        <div className="relative space-y-4">
                            <div className="flex items-baseline justify-between">
                                <h3 className="text-lg font-semibold text-white">{meta.title}</h3>
                                <span className="text-3xl font-bold text-slate-100">{count}</span>
                            </div>
                            <p className="text-sm text-slate-300">{meta.description}</p>
                            <div className="space-y-3">
                                {top.length ? (
                                    top.map(([symbol, entry]) => (
                                        <div key={symbol} className="flex items-center justify-between rounded-xl bg-slate-900/70 px-3 py-2">
                                            <div>
                                                <div className="text-sm font-semibold text-slate-100">{symbol}</div>
                                                {entry.rationale.length > 0 && (
                                                    <p className="text-xs text-slate-400">{entry.rationale[0]}</p>
                                                )}
                                            </div>
                                            <span className="text-sm font-semibold text-indigo-200">{formatScore(entry.score)}</span>
                                        </div>
                                    ))
                                ) : (
                                    <p className="text-sm text-slate-400">Нет записей</p>
                                )}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
