import { FiAlertTriangle, FiCheckCircle, FiLoader } from 'react-icons/fi';

import type { ServiceHealthMap } from '../types';

const STATUS_COLORS: Record<string, string> = {
    healthy: 'text-emerald-300',
    running: 'text-emerald-300',
    active: 'text-emerald-300',
    starting: 'text-indigo-300',
    stopping: 'text-amber-300',
    degraded: 'text-amber-300',
    insufficient_balance: 'text-amber-300',
    idle: 'text-sky-300',
    paused: 'text-slate-300',
    error: 'text-rose-300',
    stopped: 'text-slate-400',
    unknown: 'text-slate-400',
};

const STATUS_ICONS: Record<string, () => JSX.Element> = {
    healthy: () => <FiCheckCircle className="text-lg" />,
    running: () => <FiCheckCircle className="text-lg" />,
    active: () => <FiCheckCircle className="text-lg" />,
    starting: () => <FiLoader className="text-lg animate-spin" />,
    stopping: () => <FiLoader className="text-lg animate-spin" />,
    degraded: () => <FiAlertTriangle className="text-lg" />,
    insufficient_balance: () => <FiAlertTriangle className="text-lg" />,
    idle: () => <FiLoader className="text-lg" />,
    paused: () => <FiAlertTriangle className="text-lg" />,
    error: () => <FiAlertTriangle className="text-lg" />,
    stopped: () => <FiAlertTriangle className="text-lg" />,
    unknown: () => <FiAlertTriangle className="text-lg" />,
};

function formatTimestamp(value?: string | null) {
    if (!value) {
        return '—';
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return parsed.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function classifyStatus(raw: string | undefined) {
    if (!raw) {
        return 'unknown';
    }
    const lowered = raw.trim().toLowerCase();
    if (STATUS_COLORS[lowered]) {
        return lowered;
    }
    return 'unknown';
}

type Props = {
    services: ServiceHealthMap;
};

export function ServiceHealthStatus({ services }: Props) {
    const entries = Object.entries(services);
    const sorted = entries.sort(([a], [b]) => a.localeCompare(b));

    return (
        <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
            <header className="mb-4 flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-white">Состояние сервисов</h2>
                    <p className="text-sm text-slate-400">Каждый бэкграундный процесс отчётливо сигналит о своём статусе.</p>
                </div>
            </header>

            {sorted.length === 0 ? (
                <p className="text-sm text-slate-500">Нет данных о сервисах.</p>
            ) : (
                <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {sorted.map(([name, payload]) => {
                        const status = classifyStatus(payload.status as string | undefined);
                        const color = STATUS_COLORS[status] ?? 'text-slate-400';
                        const Icon = STATUS_ICONS[status] ?? STATUS_ICONS.unknown;
                        return (
                            <li key={name} className="flex items-start gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                                <span className={color}>
                                    <Icon />
                                </span>
                                <div className="space-y-1 text-sm text-slate-200">
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-white">{name}</span>
                                        <span className={`rounded-full bg-slate-800 px-2 py-0.5 text-xs uppercase ${color}`}>{status}</span>
                                    </div>
                                    {payload.message ? <div className="text-xs text-slate-400">{payload.message}</div> : null}
                                    {payload.error ? (
                                        <div className="rounded-md border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-200">
                                            {payload.error}
                                        </div>
                                    ) : null}
                                    <div className="text-xs text-slate-500">Обновлено: {formatTimestamp(payload.updated_at as string | undefined)}</div>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
        </section>
    );
}
