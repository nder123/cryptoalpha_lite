import { useState } from 'react';

import { FiActivity, FiAlertTriangle, FiClock, FiCpu, FiDatabase, FiRefreshCcw, FiChevronDown, FiChevronUp } from 'react-icons/fi';

import type { ClosedTradeEntry, RLStatusResponse } from '../types';

interface RLStatusPanelProps {
    status: RLStatusResponse | null;
    loading: boolean;
    onRefresh: () => void;
}

function formatCountdown(target: string | null | undefined) {
    if (!target) {
        return { label: '—', diffMs: null };
    }
    const date = new Date(target);
    if (Number.isNaN(date.getTime())) {
        return { label: '—', diffMs: null };
    }
    const diffMs = date.getTime() - Date.now();
    if (diffMs <= 0) {
        return { label: 'готово', diffMs };
    }

    const totalSeconds = Math.floor(diffMs / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
        return { label: `${hours}ч ${minutes}м`, diffMs };
    }
    if (minutes > 0) {
        return { label: `${minutes}м ${seconds}с`, diffMs };
    }
    return { label: `${seconds}с`, diffMs };
}

function formatNumber(value: number | null | undefined, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return '—';
    }
    return value.toFixed(digits);
}

function formatDate(value: string | null | undefined) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString('ru-RU');
}

function formatDuration(value: number | null | undefined) {
    if (value === null || value === undefined) {
        return '—';
    }
    if (value < 60) {
        return `${value}s`;
    }
    const minutes = Math.floor(value / 60);
    const seconds = value % 60;
    if (minutes < 60) {
        return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
    }
    const hours = Math.floor(minutes / 60);
    const remMinutes = minutes % 60;
    return remMinutes ? `${hours}h ${remMinutes}m` : `${hours}h`;
}

function ClosedTradesTable({ trades }: { trades: ClosedTradeEntry[] }) {
    if (!trades.length) {
        return (
            <div className="rounded-2xl border border-violet-700/40 bg-violet-900/20 p-4 text-sm text-violet-100/70">
                Недавние закрытые сделки отсутствуют.
            </div>
        );
    }

    return (
        <div className="max-h-80 overflow-auto rounded-2xl border border-violet-700/40">
            <table className="min-w-full divide-y divide-violet-800/60 bg-violet-950/20 text-sm text-violet-100/80">
                <thead className="bg-violet-900/40 text-xs uppercase tracking-wide text-violet-200/80">
                    <tr>
                        <th className="px-4 py-3 text-left">Сессия</th>
                        <th className="px-4 py-3 text-left">Инструмент</th>
                        <th className="px-4 py-3 text-left">PnL, USDT</th>
                        <th className="px-4 py-3 text-left">PnL, %</th>
                        <th className="px-4 py-3 text-left">Открыта</th>
                        <th className="px-4 py-3 text-left">Закрыта</th>
                        <th className="px-4 py-3 text-left">Длительность</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-violet-800/40">
                    {trades.map((trade) => (
                        <tr key={trade.session_id} className="hover:bg-violet-900/30">
                            <td className="px-4 py-3 font-mono text-xs text-violet-200/90">
                                {trade.session_id.slice(0, 8)}…
                            </td>
                            <td className="px-4 py-3">
                                <div className="font-semibold text-violet-100">{trade.symbol}</div>
                                <div className="text-xs text-violet-300/70">{trade.direction}</div>
                            </td>
                            <td className="px-4 py-3 text-violet-100">
                                {formatNumber(trade.pnl_usdt, 2)}
                            </td>
                            <td className={`px-4 py-3 ${trade.pnl_pct && trade.pnl_pct > 0 ? 'text-emerald-300' : trade.pnl_pct && trade.pnl_pct < 0 ? 'text-rose-300' : 'text-violet-100'}`}>
                                {formatNumber(trade.pnl_pct, 2)}
                            </td>
                            <td className="px-4 py-3 text-xs text-violet-300/80">{formatDate(trade.opened_at)}</td>
                            <td className="px-4 py-3 text-xs text-violet-300/80">{formatDate(trade.closed_at)}</td>
                            <td className="px-4 py-3 text-xs text-violet-200/80">{formatDuration(trade.duration_seconds)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export function RLStatusPanel({ status, loading, onRefresh }: RLStatusPanelProps) {
    const [recentExpanded, setRecentExpanded] = useState(false);

    if (!status) {
        return (
            <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card">
                <div className="flex items-center justify-between">
                    <h2 className="text-2xl font-semibold text-white">RL контроллер</h2>
                    <button
                        type="button"
                        onClick={onRefresh}
                        className="inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                    >
                        <FiRefreshCcw className="text-base" />
                        Обновить
                    </button>
                </div>
                <p className="mt-3 text-sm text-slate-400">
                    Информация о состоянии RL Trainer временно недоступна. Попробуйте обновить панель.
                </p>
            </section>
        );
    }

    const { experience_count, experience_latest, experience_oldest, latest_metrics, policy, closed_summary, recent_closed } = status;
    const bufferReady = status.buffer_ready;
    const minBatchRequired = status.min_batch_required;
    const experienceShortfall = Math.max(0, minBatchRequired - experience_count);
    const queueSize = status.force_queue_size;
    const { label: countdownLabelRaw, diffMs } = formatCountdown(status.next_eligible_at);
    const lastTrainedLabel = formatDate(status.last_trained_at);
    const nextEligibleLabel = formatDate(status.next_eligible_at);

    let countdownBadgeLabel = countdownLabelRaw;
    let countdownBadgeClass = 'inline-flex items-center gap-2 rounded-xl border border-violet-600/50 bg-violet-500/10 px-3 py-1 text-xs text-violet-100';

    if (countdownLabelRaw === '—') {
        countdownBadgeLabel = 'Окно не определено';
        countdownBadgeClass = 'inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-200';
    } else if (diffMs !== null && diffMs <= 0) {
        if (bufferReady) {
            countdownBadgeLabel = 'Готов к запуску';
            countdownBadgeClass = 'inline-flex items-center gap-2 rounded-xl border border-emerald-500/50 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-100';
        } else {
            countdownBadgeLabel = 'Ждём накопления опыта';
            countdownBadgeClass = 'inline-flex items-center gap-2 rounded-xl border border-amber-500/60 bg-amber-500/10 px-3 py-1 text-xs text-amber-100';
        }
    } else if (diffMs !== null && diffMs > 0) {
        countdownBadgeLabel = `через ${countdownLabelRaw}`;
    }

    return (
        <section className="space-y-6 rounded-3xl border border-violet-700/40 bg-violet-950/20 p-6 shadow-card">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-2xl font-semibold text-white">RL контроллер</h2>
                    <p className="mt-1 text-sm text-violet-200/80">
                        Статус обучения PPO и последней политики, выгружаемой из Redis.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={onRefresh}
                    disabled={loading}
                    className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition ${loading
                        ? 'cursor-wait border border-violet-500/40 bg-violet-900/50 text-violet-200/70'
                        : 'border border-violet-500/60 bg-violet-500/10 text-violet-200 hover:bg-violet-500/20'
                        }`}
                >
                    <FiRefreshCcw className="text-base" />
                    {loading ? 'Обновление…' : 'Обновить'}
                </button>
            </div>

            <div className="space-y-3">
                {!bufferReady && (
                    <div className="flex items-start gap-3 rounded-2xl border border-amber-500/50 bg-amber-500/10 p-4 text-sm text-amber-100">
                        <FiAlertTriangle className="mt-0.5 text-lg" />
                        <span>
                            Для следующего цикла обучения нужно минимум {minBatchRequired} событий. Сейчас {experience_count}
                            {experienceShortfall > 0 ? `, не хватает ещё ${experienceShortfall}.` : '.'}
                        </span>
                    </div>
                )}
                {queueSize > 0 && (
                    <div className="flex items-start gap-3 rounded-2xl border border-indigo-500/50 bg-indigo-500/10 p-4 text-sm text-indigo-100">
                        <FiRefreshCcw className="mt-0.5 text-lg" />
                        <span>
                            В очереди на принудительный запуск: {queueSize}. Тренер запустит обучение в ближайшем доступном окне.
                        </span>
                    </div>
                )}
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                <div className="rounded-2xl border border-violet-700/40 bg-violet-900/30 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-violet-200">
                        <FiDatabase /> Буфер опыта
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-white">{experience_count}</p>
                    <div
                        className={`mt-3 inline-flex items-center gap-2 rounded-xl px-3 py-1 text-xs font-semibold ${bufferReady
                            ? 'border border-emerald-500/40 bg-emerald-500/10 text-emerald-100'
                            : 'border border-amber-500/50 bg-amber-500/10 text-amber-100'
                            }`}
                    >
                        {bufferReady ? 'Готов к обучению' : `Не хватает ${experienceShortfall}`}
                    </div>
                    <dl className="mt-3 space-y-1 text-xs text-violet-100/70">
                        <div className="flex justify-between">
                            <dt>Первый:</dt>
                            <dd>{experience_oldest?.symbol ?? '—'}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Последний:</dt>
                            <dd>{experience_latest?.symbol ?? '—'}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Минимум для запуска:</dt>
                            <dd>{minBatchRequired}</dd>
                        </div>
                    </dl>
                </div>

                <div className="rounded-2xl border border-violet-700/40 bg-violet-900/30 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-violet-200">
                        <FiCpu /> Политика
                    </div>
                    <p className="mt-2 text-lg text-white">{policy?.architecture ?? '—'}</p>
                    <dl className="mt-3 space-y-1 text-xs text-violet-100/70">
                        <div className="flex justify-between">
                            <dt>Версия:</dt>
                            <dd>{policy?.version ?? '—'}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Порог:</dt>
                            <dd>{formatNumber(policy?.threshold)}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Размеры:</dt>
                            <dd>
                                in {policy?.input_size ?? '—'} → hid {policy?.hidden_size ?? '—'} → out {policy?.action_size ?? '—'}
                            </dd>
                        </div>
                    </dl>
                </div>

                <div className="rounded-2xl border border-violet-700/40 bg-violet-900/30 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-violet-200">
                        <FiActivity /> Последняя награда
                    </div>
                    <p className="mt-2 text-3xl font-semibold text-white">
                        {formatNumber(latest_metrics?.last_trade_reward, 3)}
                    </p>
                    <dl className="mt-3 space-y-1 text-xs text-violet-100/70">
                        <div className="flex justify-between">
                            <dt>Trade PnL %:</dt>
                            <dd>{formatNumber(latest_metrics?.last_trade_pnl_pct, 3)}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Обновлено:</dt>
                            <dd>{formatDate(latest_metrics?.timestamp)}</dd>
                        </div>
                    </dl>
                </div>

                <div className="rounded-2xl border border-violet-700/40 bg-violet-900/30 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-violet-200">
                        <FiActivity /> Производительность
                    </div>
                    <dl className="mt-3 space-y-2 text-xs text-violet-100/70">
                        <div className="flex justify-between">
                            <dt>Сделок всего:</dt>
                            <dd>{latest_metrics?.total_trades ?? '—'}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Win rate:</dt>
                            <dd>{formatNumber(latest_metrics?.win_rate, 3)}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Sharpe:</dt>
                            <dd>{formatNumber(latest_metrics?.sharpe_ratio, 3)}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Макс. просадка:</dt>
                            <dd>{formatNumber(latest_metrics?.max_drawdown, 2)}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Убыточных за окно:</dt>
                            <dd>{latest_metrics?.losses_last_window ?? '—'}</dd>
                        </div>
                    </dl>
                </div>

                <div className="rounded-2xl border border-violet-700/40 bg-violet-900/30 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-violet-200">
                        <FiClock /> Расписание обучения
                    </div>
                    <dl className="mt-3 space-y-1 text-xs text-violet-100/70">
                        <div className="flex justify-between">
                            <dt>Последний запуск:</dt>
                            <dd>{lastTrainedLabel}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Следующее окно:</dt>
                            <dd>{nextEligibleLabel}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Очередь принудительных:</dt>
                            <dd>{queueSize}</dd>
                        </div>
                    </dl>
                    <div className={`${countdownBadgeClass} mt-3`}>{countdownBadgeLabel}</div>
                </div>
            </div>

            {closed_summary && (
                <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-2xl border border-violet-700/40 bg-violet-900/20 p-4">
                        <h3 className="text-sm font-semibold text-violet-200">Сводка закрытых сделок</h3>
                        <dl className="mt-3 space-y-2 text-xs text-violet-100/70">
                            <div className="flex justify-between">
                                <dt>Всего сделок:</dt>
                                <dd>{closed_summary.total_trades}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Победных:</dt>
                                <dd>{closed_summary.winning_trades}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Total PnL, USDT:</dt>
                                <dd>{formatNumber(closed_summary.total_pnl_usdt, 2)}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Средний PnL, %:</dt>
                                <dd>{formatNumber(closed_summary.avg_pnl_pct, 2)}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Win rate:</dt>
                                <dd>{formatNumber(closed_summary.win_rate, 3)}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Средний R/R:</dt>
                                <dd>{formatNumber(closed_summary.avg_rr, 2)}</dd>
                            </div>
                        </dl>
                    </div>
                    <div className="rounded-2xl border border-violet-700/40 bg-violet-900/20 p-4">
                        <h3 className="text-sm font-semibold text-violet-200">Последний опыт</h3>
                        <dl className="mt-3 space-y-1 text-xs text-violet-100/70">
                            <div className="flex justify-between">
                                <dt>Директива:</dt>
                                <dd>{experience_latest?.directive_id ?? '—'}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Символ:</dt>
                                <dd>{experience_latest?.symbol ?? '—'}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Действие:</dt>
                                <dd>{experience_latest?.action ?? '—'}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Создан:</dt>
                                <dd>{formatDate(experience_latest?.timestamp ?? null)}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt>Награда:</dt>
                                <dd>{formatNumber(experience_latest?.reward, 3)}</dd>
                            </div>
                        </dl>
                    </div>
                </div>
            )}

            {!closed_summary && (
                <div className="rounded-2xl border border-violet-700/40 bg-violet-900/20 p-4">
                    <h3 className="text-sm font-semibold text-violet-200">Последний опыт</h3>
                    <dl className="mt-3 space-y-1 text-xs text-violet-100/70">
                        <div className="flex justify-between">
                            <dt>Директива:</dt>
                            <dd>{experience_latest?.directive_id ?? '—'}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Символ:</dt>
                            <dd>{experience_latest?.symbol ?? '—'}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Действие:</dt>
                            <dd>{experience_latest?.action ?? '—'}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Создан:</dt>
                            <dd>{formatDate(experience_latest?.timestamp ?? null)}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt>Награда:</dt>
                            <dd>{formatNumber(experience_latest?.reward, 3)}</dd>
                        </div>
                    </dl>
                </div>
            )}

            <div className="rounded-2xl border border-violet-700/40 bg-violet-900/20 p-4">
                <h3 className="text-sm font-semibold text-violet-200">Первый опыт (в буфере)</h3>
                <dl className="mt-3 space-y-1 text-xs text-violet-100/70">
                    <div className="flex justify-between">
                        <dt>Директива:</dt>
                        <dd>{experience_oldest?.directive_id ?? '—'}</dd>
                    </div>
                    <div className="flex justify-between">
                        <dt>Символ:</dt>
                        <dd>{experience_oldest?.symbol ?? '—'}</dd>
                    </div>
                    <div className="flex justify-between">
                        <dt>Действие:</dt>
                        <dd>{experience_oldest?.action ?? '—'}</dd>
                    </div>
                    <div className="flex justify-between">
                        <dt>Создан:</dt>
                        <dd>{formatDate(experience_oldest?.timestamp ?? null)}</dd>
                    </div>
                    <div className="flex justify-between">
                        <dt>Награда:</dt>
                        <dd>{formatNumber(experience_oldest?.reward, 3)}</dd>
                    </div>
                </dl>
            </div>

            <div className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <h3 className="text-sm font-semibold text-violet-200">Недавние закрытые сделки</h3>
                    <button
                        type="button"
                        onClick={() => setRecentExpanded((value) => !value)}
                        className="inline-flex items-center gap-2 self-start rounded-full border border-violet-500/60 px-4 py-2 text-xs text-violet-100 transition hover:bg-violet-500/10 sm:self-auto"
                    >
                        {recentExpanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                        {recentExpanded ? 'Скрыть' : 'Показать'}
                    </button>
                </div>
                {recentExpanded ? <ClosedTradesTable trades={recent_closed} /> : null}
            </div>
        </section>
    );
}
