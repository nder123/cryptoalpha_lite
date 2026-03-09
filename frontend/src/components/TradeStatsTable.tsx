import { useState } from 'react';

import { FiChevronDown, FiChevronUp } from 'react-icons/fi';

import type { TradeSessionRecord } from '../types';

type Props = {
    records: TradeSessionRecord[];
    loading: boolean;
};

function formatDate(value: string | null) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit',
    });
}

function formatNumber(value: number | null, fractionDigits = 2) {
    if (value === null || value === undefined) return '—';
    return value.toFixed(fractionDigits);
}

function formatDuration(seconds: number | null) {
    if (!seconds && seconds !== 0) return '—';
    const mins = Math.floor(seconds / 60);
    if (mins < 60) {
        return `${mins} мин`;
    }
    const hours = Math.floor(mins / 60);
    const rem = mins % 60;
    return `${hours} ч ${rem} мин`;
}

function getPnlClass(value: number | null) {
    if (value === null || value === undefined) return 'text-slate-300';
    if (value > 0) return 'text-emerald-300';
    if (value < 0) return 'text-rose-300';
    return 'text-slate-300';
}

export function TradeStatsTable({ records, loading }: Props) {
    const [expanded, setExpanded] = useState<string | null>(null);

    if (loading) {
        return (
            <div className="flex h-48 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/60 text-sm text-slate-400">
                Загрузка статистики сделок…
            </div>
        );
    }

    if (!records.length) {
        return (
            <div className="flex h-48 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/60 text-sm text-slate-400">
                Пока нет завершённых сделок в выбранном диапазоне.
            </div>
        );
    }

    return (
        <div className="overflow-auto rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card">
            <table className="min-w-full divide-y divide-slate-800">
                <thead className="bg-slate-900/80 text-xs uppercase tracking-wide text-slate-400">
                    <tr>
                        <th className="px-4 py-3 text-left">Открытие</th>
                        <th className="px-4 py-3 text-left">Инструмент</th>
                        <th className="px-4 py-3 text-left">Режим</th>
                        <th className="px-4 py-3 text-left">Вход / Выход</th>
                        <th className="px-4 py-3 text-left">PnL</th>
                        <th className="px-4 py-3 text-left">TP / SL</th>
                        <th className="px-4 py-3 text-left">Длительность</th>
                        <th className="px-4 py-3 text-left">Комментарий</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-sm">
                    {records.map((record) => {
                        const isOpen = expanded === record.session_id;

                        return (
                            <>
                                <tr
                                    key={record.session_id}
                                    className="cursor-pointer hover:bg-slate-800/30"
                                    onClick={() => setExpanded((prev) => (prev === record.session_id ? null : record.session_id))}
                                >
                                    <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                                        <div className="flex items-center gap-2">
                                            <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800/60 text-slate-300">
                                                {isOpen ? <FiChevronUp /> : <FiChevronDown />}
                                            </span>
                                            <div>
                                                <div>{formatDate(record.opened_at)}</div>
                                                <div className="text-xs text-slate-500">Закрытие: {formatDate(record.closed_at)}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3 text-slate-100">
                                        <div className="font-semibold text-white">{record.symbol}</div>
                                        <div className="text-xs text-slate-500">
                                            {record.direction === 'long' ? 'Лонг' : 'Шорт'} • #{record.session_id.slice(-6)}
                                        </div>
                                    </td>
                                    <td className="px-4 py-3 text-slate-300 capitalize">{record.mode.replace('_', ' ')}</td>
                                    <td className="px-4 py-3 text-slate-300">
                                        <div>
                                            {formatNumber(record.entry_price)} @ {formatNumber(record.entry_qty, 3)}
                                        </div>
                                        <div className="text-xs text-slate-500">
                                            → {formatNumber(record.exit_price)} @ {formatNumber(record.exit_qty, 3)}
                                        </div>
                                    </td>
                                    <td className={`px-4 py-3 font-semibold ${getPnlClass(record.pnl_usdt)}`}>
                                        <div>{formatNumber(record.pnl_usdt)} USDT</div>
                                        <div className="text-xs">{formatNumber(record.pnl_pct)} %</div>
                                        <div className="text-xs text-slate-500">R/R: {formatNumber(record.risk_reward_ratio)}</div>
                                    </td>
                                    <td className="px-4 py-3 text-slate-300">
                                        <div>TP: {formatNumber(record.target_price)}</div>
                                        <div>SL: {formatNumber(record.stop_price)}</div>
                                        <div className="text-xs text-slate-500">
                                            TP hit: {record.tp_hit ? 'да' : 'нет'} • SL hit: {record.sl_hit ? 'да' : 'нет'}
                                        </div>
                                    </td>
                                    <td className="px-4 py-3 text-slate-300">{formatDuration(record.duration_seconds)}</td>
                                    <td className="px-4 py-3 text-slate-300">
                                        {record.comment ? (
                                            <span className="block max-h-10 overflow-hidden break-words text-xs text-slate-400">{record.comment}</span>
                                        ) : (
                                            <span className="text-xs text-slate-500">—</span>
                                        )}
                                    </td>
                                </tr>

                                {isOpen ? (
                                    <tr key={`${record.session_id}-details`} className="bg-slate-950/20">
                                        <td colSpan={8} className="px-4 py-4">
                                            <div className="grid gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-xs text-slate-300 md:grid-cols-2">
                                                <div className="space-y-1">
                                                    <div className="text-slate-500">TP / SL</div>
                                                    <div>
                                                        TP: <span className="text-slate-200">{formatNumber(record.target_price)}</span>{' '}
                                                        ({record.tp_hit ? 'hit' : 'нет'})
                                                    </div>
                                                    <div>
                                                        SL: <span className="text-slate-200">{formatNumber(record.stop_price)}</span>{' '}
                                                        ({record.sl_hit ? 'hit' : 'нет'})
                                                    </div>
                                                </div>
                                                <div className="space-y-1">
                                                    <div className="text-slate-500">Directive IDs</div>
                                                    <div className="font-mono text-[11px] text-slate-200">
                                                        entry: {record.entry_directive_id || '—'}
                                                    </div>
                                                    <div className="font-mono text-[11px] text-slate-200">
                                                        exit: {record.exit_directive_id || '—'}
                                                    </div>
                                                </div>
                                                <div className="space-y-1 md:col-span-2">
                                                    <div className="text-slate-500">Комментарий</div>
                                                    <div className="whitespace-pre-wrap text-slate-200">
                                                        {record.comment || '—'}
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                ) : null}
                            </>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
