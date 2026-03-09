import { FiActivity, FiPause, FiPlay, FiRefreshCcw } from 'react-icons/fi';

import { useTelemetryStreams } from '../hooks/useTelemetryStreams';
import type {
    DecisionStreamEntry,
    ExecutionStreamEntry,
    HypothesisStreamEntry,
    PositionStreamEntry,
    RiskStreamEntry,
} from '../types';

function formatTimestamp(value: string | null | undefined) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatNumber(value: number | null | undefined, fractionDigits = 2) {
    if (value === null || value === undefined) {
        return '—';
    }
    return value.toFixed(fractionDigits);
}

type StreamCardProps<T> = {
    title: string;
    description: string;
    accentClass: string;
    items: T[];
    renderItem: (item: T) => JSX.Element;
};

function StreamCard<T>({ title, description, accentClass, items, renderItem }: StreamCardProps<T>) {
    return (
        <div className="flex h-full flex-col rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card">
            <div className="border-b border-slate-800 px-5 py-4">
                <h3 className="text-base font-semibold text-white">{title}</h3>
                <p className="mt-1 text-xs text-slate-400">{description}</p>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">
                {items.length === 0 ? (
                    <p className="text-sm text-slate-500">Нет событий в выбранном окне.</p>
                ) : (
                    <ul className="space-y-3 text-sm text-slate-200">
                        {items
                            .slice()
                            .reverse()
                            .map((item, index) => (
                                <li
                                    /* eslint-disable-next-line react/no-array-index-key */
                                    key={index}
                                    className="space-y-1 rounded-xl bg-slate-900/70 p-3"
                                >
                                    <div className="flex items-center justify-between text-xs text-slate-400">
                                        <span className={accentClass}>{title}</span>
                                        <span>{formatTimestamp((item as any).timestamp ?? (item as any).data?.reported_at)}</span>
                                    </div>
                                    {renderItem(item)}
                                </li>
                            ))}
                    </ul>
                )}
            </div>
        </div>
    );
}

function renderExecution(entry: ExecutionStreamEntry) {
    const data = entry.data;
    const status = data.status?.toUpperCase() ?? 'UNKNOWN';
    const statusColor =
        data.status === 'filled'
            ? 'text-emerald-300'
            : data.status === 'failed' || data.status === 'rejected'
                ? 'text-rose-300'
                : 'text-indigo-300';

    return (
        <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{data.symbol}</span>
                <span className={`text-xs font-semibold ${statusColor}`}>{status}</span>
            </div>
            <div className="text-xs text-slate-400">
                Кол-во: {formatNumber(data.quantity, 3)} • Цена: {formatNumber(data.avg_price)} • Комиссии: {formatNumber(data.fees_paid)}
            </div>
            {data.notes?.length ? (
                <ul className="list-disc space-y-1 pl-5 text-xs text-slate-400">
                    {data.notes.map((note, idx) => (
                        <li key={idx}>{note}</li>
                    ))}
                </ul>
            ) : null}
        </div>
    );
}

function renderDecision(entry: DecisionStreamEntry) {
    const data = entry.data;
    const actionLabel = data.action?.toUpperCase() ?? '—';
    const actionClass = data.action === 'open' ? 'text-emerald-300' : data.action === 'close' ? 'text-amber-300' : 'text-indigo-300';
    return (
        <div className="space-y-1 text-sm">
            <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{data.symbol}</span>
                <span className={`text-xs font-semibold ${actionClass}`}>{actionLabel}</span>
            </div>
            <div className="text-xs text-slate-400">
                Размер: {formatNumber(data.size, 3)} • Нотионал: {formatNumber(data.notional_usdt)} USDT • Источник: {data.source}
            </div>
            {data.directive?.rationale?.length ? (
                <ul className="list-disc space-y-1 pl-5 text-xs text-slate-400">
                    {data.directive.rationale.map((reason, idx) => (
                        <li key={idx}>{reason}</li>
                    ))}
                </ul>
            ) : null}
        </div>
    );
}

function renderRisk(entry: RiskStreamEntry) {
    const data = entry.data;
    const approved = data.decision === 'approved';
    return (
        <div className="space-y-1 text-sm">
            <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{data.symbol}</span>
                <span className={`text-xs font-semibold ${approved ? 'text-emerald-300' : 'text-rose-300'}`}>
                    {approved ? 'APPROVED' : 'BLOCKED'}
                </span>
            </div>
            <div className="text-xs text-slate-400">
                Confidence: {formatNumber(data.risk_metrics?.confidence, 2)} • Exposure: {formatNumber(data.risk_metrics?.projected_exposure)} USDT
            </div>
            {!approved && data.blockers?.length ? (
                <ul className="list-disc space-y-1 pl-5 text-xs text-slate-400">
                    {data.blockers.map((reason, idx) => (
                        <li key={idx}>{reason}</li>
                    ))}
                </ul>
            ) : null}
        </div>
    );
}

function renderHypothesis(entry: HypothesisStreamEntry) {
    const data = entry.data;
    return (
        <div className="space-y-1 text-sm">
            <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{data.symbol}</span>
                <span className="text-xs font-semibold text-indigo-300">{(data.confidence * 100).toFixed(1)}%</span>
            </div>
            <div className="text-xs text-slate-400">
                Тип: {data.hypothesis_type} • Направление: {data.direction.toUpperCase()} • Леверидж: {formatNumber(data.leverage, 1)}x
            </div>
            <div className="text-xs text-slate-500">
                Вход: {formatNumber(data.entry_price)} • Target: {formatNumber(data.target_price)} • Stop: {formatNumber(data.stop_price)}
            </div>
        </div>
    );
}

function renderPosition(entry: PositionStreamEntry) {
    const { data } = entry;
    const eventLabel = data.event?.toUpperCase() ?? entry.event_type.toUpperCase();
    const eventColorMap: Record<string, string> = {
        OPEN_TRACKED: 'text-emerald-300',
        OPEN_UPDATED: 'text-emerald-200',
        CLOSE_REQUESTED: 'text-amber-300',
        FORCE_CLOSE_TIMEOUT: 'text-rose-300',
        CLOSE_CONFIRMED: 'text-emerald-400',
        CLOSE_PARTIAL: 'text-sky-300',
        PRICE_FETCH_FAILED: 'text-amber-200',
        ERROR: 'text-rose-400',
    };
    const eventColor = eventColorMap[eventLabel] ?? 'text-slate-200';

    return (
        <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{data.symbol}</span>
                <span className={`text-xs font-semibold ${eventColor}`}>{eventLabel}</span>
            </div>
            <div className="text-xs text-slate-400">
                Направление: {data.direction?.toUpperCase()} • Кол-во: {formatNumber(data.quantity ?? null, 3)} • Цена: {formatNumber(data.price ?? null)}
            </div>
            {(data.reason || data.status) && (
                <div className="text-xs text-slate-500">
                    {data.reason ? `Причина: ${data.reason}` : null}
                    {data.reason && data.status ? ' • ' : null}
                    {data.status ? `Статус: ${data.status}` : null}
                </div>
            )}
            {data.origin_directive_id ? (
                <div className="text-xs text-slate-500">Исходная директива: {data.origin_directive_id}</div>
            ) : null}
            {data.notes?.length ? (
                <ul className="list-disc space-y-1 pl-5 text-xs text-slate-400">
                    {data.notes.map((note, idx) => (
                        <li key={idx}>{note}</li>
                    ))}
                </ul>
            ) : null}
        </div>
    );
}

export function TelemetryStreamsPanel() {
    const { execution, decisions, risk, hypotheses, positions, loading, error, lastUpdated, autoRefresh, setAutoRefresh, refresh } =
        useTelemetryStreams();

    return (
        <section className="space-y-6">
            <header className="flex flex-col gap-4 rounded-3xl border border-slate-800 bg-slate-950/80 p-5 shadow-card md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-3 text-slate-200">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-300">
                        <FiActivity className="text-xl" />
                    </div>
                    <div>
                        <h2 className="text-xl font-semibold text-white">Потоки телеметрии</h2>
                        <p className="text-sm text-slate-400">
                            Живые данные по гипотезам, решениям, риску, исполнению и управлению позициями. Автообновление каждые 5 секунд.
                        </p>
                    </div>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-sm">
                    <button
                        type="button"
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 transition ${autoRefresh
                            ? 'border-emerald-400/70 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20'
                            : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500'
                            }`}
                    >
                        {autoRefresh ? <FiPause className="text-base" /> : <FiPlay className="text-base" />}
                        {autoRefresh ? 'Пауза' : 'Автообновление'}
                    </button>
                    <button
                        type="button"
                        onClick={() => {
                            refresh().catch((err) => {
                                console.error('Manual telemetry refresh failed', err);
                            });
                        }}
                        className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                        disabled={loading}
                    >
                        <FiRefreshCcw className="text-base" />
                        Обновить
                    </button>
                    <div className="text-xs text-slate-500">
                        {loading ? 'Загрузка…' : lastUpdated ? `Обновлено: ${formatTimestamp(lastUpdated.toISOString())}` : '—'}
                    </div>
                </div>
            </header>

            {error ? (
                <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
                    {error}
                </div>
            ) : null}

            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-5">
                <StreamCard
                    title="Execution"
                    description="Отчёты Execution Engine о каждом ордере"
                    accentClass="text-emerald-300"
                    items={execution}
                    renderItem={renderExecution}
                />
                <StreamCard
                    title="Decisions"
                    description="Решения CTO-AI, отправленные на исполнение"
                    accentClass="text-indigo-300"
                    items={decisions}
                    renderItem={renderDecision}
                />
                <StreamCard
                    title="Risk"
                    description="Оценки Risk Engine для гипотез"
                    accentClass="text-amber-300"
                    items={risk}
                    renderItem={renderRisk}
                />
                <StreamCard
                    title="Hypotheses"
                    description="Сырые торговые гипотезы из Research"
                    accentClass="text-sky-300"
                    items={hypotheses}
                    renderItem={renderHypothesis}
                />
                <StreamCard
                    title="Positions"
                    description="Каждый чих Position Manager: события открытия/закрытия"
                    accentClass="text-amber-300"
                    items={positions}
                    renderItem={renderPosition}
                />
            </div>
        </section>
    );
}
