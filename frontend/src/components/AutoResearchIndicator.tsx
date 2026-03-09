import { useMemo, useState } from 'react';
import { FiActivity, FiAlertTriangle, FiChevronDown, FiChevronRight, FiClock, FiDatabase } from 'react-icons/fi';

import type { ServiceHealthEntry } from '../types';

const STATUS_STYLES: Record<
    string,
    {
        badge: string;
        pill: string;
        border: string;
        glow: string;
    }
> = {
    active: {
        badge: 'border-emerald-400/60 bg-emerald-500/10 text-emerald-200',
        pill: 'bg-emerald-500/10 text-emerald-200',
        border: 'border-emerald-500/40',
        glow: 'shadow-[0_0_25px_rgba(16,185,129,0.25)]',
    },
    running: {
        badge: 'border-emerald-400/60 bg-emerald-500/10 text-emerald-200',
        pill: 'bg-emerald-500/10 text-emerald-200',
        border: 'border-emerald-500/40',
        glow: 'shadow-[0_0_25px_rgba(16,185,129,0.2)]',
    },
    starting: {
        badge: 'border-indigo-400/60 bg-indigo-500/10 text-indigo-200',
        pill: 'bg-indigo-500/10 text-indigo-200',
        border: 'border-indigo-500/40',
        glow: 'shadow-[0_0_20px_rgba(99,102,241,0.25)]',
    },
    idle: {
        badge: 'border-sky-400/60 bg-sky-500/10 text-sky-200',
        pill: 'bg-sky-500/10 text-sky-200',
        border: 'border-sky-500/40',
        glow: 'shadow-[0_0_20px_rgba(56,189,248,0.15)]',
    },
    degraded: {
        badge: 'border-amber-400/60 bg-amber-500/10 text-amber-200',
        pill: 'bg-amber-500/10 text-amber-200',
        border: 'border-amber-500/40',
        glow: 'shadow-[0_0_20px_rgba(251,191,36,0.2)]',
    },
    paused: {
        badge: 'border-slate-500/60 bg-slate-800 text-slate-300',
        pill: 'bg-slate-800 text-slate-300',
        border: 'border-slate-600/50',
        glow: 'shadow-none',
    },
    stopping: {
        badge: 'border-amber-400/60 bg-amber-500/10 text-amber-200',
        pill: 'bg-amber-500/10 text-amber-200',
        border: 'border-amber-500/40',
        glow: 'shadow-[0_0_20px_rgba(251,191,36,0.15)]',
    },
    stopped: {
        badge: 'border-slate-600 bg-slate-900 text-slate-300',
        pill: 'bg-slate-900 text-slate-300',
        border: 'border-slate-700/70',
        glow: 'shadow-none',
    },
    error: {
        badge: 'border-rose-500/60 bg-rose-500/10 text-rose-200',
        pill: 'bg-rose-500/10 text-rose-200',
        border: 'border-rose-500/50',
        glow: 'shadow-[0_0_28px_rgba(244,63,94,0.25)]',
    },
    unknown: {
        badge: 'border-slate-600 bg-slate-900 text-slate-200',
        pill: 'bg-slate-900 text-slate-200',
        border: 'border-slate-700/70',
        glow: 'shadow-none',
    },
};

const FALLBACK_STYLE = STATUS_STYLES.unknown;

type Props = {
    entry: ServiceHealthEntry | undefined;
};

export function AutoResearchIndicator({ entry }: Props) {
    const [expanded, setExpanded] = useState(false);

    if (!entry) {
        return null;
    }

    const status = (entry.status ?? 'unknown').toString().trim().toLowerCase();
    const style = STATUS_STYLES[status] ?? FALLBACK_STYLE;

    const backlogSize = useMemo(() => {
        const raw = entry.backlog as number | string | undefined;
        if (typeof raw === 'number') {
            return raw;
        }
        if (typeof raw === 'string') {
            const parsed = Number(raw);
            return Number.isFinite(parsed) ? parsed : 0;
        }
        return 0;
    }, [entry.backlog]);

    const dispatchedCount = useMemo(() => {
        const raw = entry.dispatched as number | string | undefined;
        if (typeof raw === 'number') {
            return raw;
        }
        if (typeof raw === 'string') {
            const parsed = Number(raw);
            return Number.isFinite(parsed) ? parsed : 0;
        }
        return 0;
    }, [entry.dispatched]);

    const updatedAtLabel = useMemo(() => {
        const raw = entry.updated_at as string | undefined;
        if (!raw) {
            return '—';
        }
        const date = new Date(raw);
        if (Number.isNaN(date.getTime())) {
            return raw;
        }
        return date.toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    }, [entry.updated_at]);

    const helperText = entry.message || (status === 'paused' ? 'Auto-research отключён настройками RuntimeConfig.' : null);
    const errorText = entry.error ? String(entry.error) : null;

    const indicators = [
        {
            icon: <FiDatabase className="text-base" />,
            title: 'Размер бэклога',
            value: backlogSize,
        },
        {
            icon: <FiActivity className="text-base" />,
            title: 'Отправлено в этом цикле',
            value: dispatchedCount,
        },
        {
            icon: <FiClock className="text-base" />,
            title: 'Последнее обновление',
            value: updatedAtLabel,
        },
    ];

    const shouldStartExpanded = status === 'error';

    return (
        <section className={`rounded-3xl border bg-slate-950/80 ${style.border} ${style.glow} transition-all`}>
            <button
                type="button"
                onClick={() => setExpanded((prev) => !prev)}
                className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
            >
                <div className="flex items-center gap-3">
                    <div className={`flex h-9 w-9 items-center justify-center rounded-2xl ${style.pill}`}>
                        <FiActivity className="text-base" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-white">Auto-Research</h3>
                        <p className="text-sm text-slate-400">Фоновый цикл, гоняющий кандидатов через ResearchEngine.</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs uppercase tracking-wide ${style.badge}`}>
                        {status}
                    </span>
                    {expanded || shouldStartExpanded ? <FiChevronDown className="text-lg text-slate-300" /> : <FiChevronRight className="text-lg text-slate-300" />}
                </div>
            </button>

            {(expanded || shouldStartExpanded) && (
                <div className="space-y-4 border-t border-slate-800/60 px-6 py-5">
                    <ul className="grid gap-3 md:grid-cols-3">
                        {indicators.map(({ icon, title, value }) => (
                            <li key={title} className="flex flex-col gap-1 rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4">
                                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                                    {icon}
                                    {title}
                                </div>
                                <div className="text-2xl font-semibold text-white">{value}</div>
                            </li>
                        ))}
                    </ul>

                    {helperText ? (
                        <div className="rounded-2xl border border-sky-500/40 bg-sky-500/5 p-4 text-sm text-sky-100">{helperText}</div>
                    ) : null}
                    {errorText ? (
                        <div className="flex items-start gap-2 rounded-2xl border border-rose-500/50 bg-rose-500/10 p-4 text-sm text-rose-100">
                            <FiAlertTriangle className="mt-0.5 text-lg" />
                            <span>{errorText}</span>
                        </div>
                    ) : null}

                    <div className="text-xs text-slate-500">
                        Подсказка: сервис публикует статус каждые 30 секунд. Настройки находятся в RuntimeConfig → auto_research_*.
                    </div>
                </div>
            )}
        </section>
    );
}
