import { useMemo, useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';

import type { TradeDirective } from '../types';

type Props = {
    directives: TradeDirective[];
};

export function DirectivesTable({ directives }: Props) {
    if (!directives.length) {
        return (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-300">
                Активных директив нет. CTO-AI находится в режиме наблюдения.
            </div>
        );
    }

    const [expanded, setExpanded] = useState(false);

    const summary = useMemo(() => {
        const total = directives.length;
        const openCount = directives.filter((item) => item.action === 'open').length;
        const closeCount = directives.filter((item) => item.action === 'close').length;
        const avgConfidence = directives.reduce((acc, item) => acc + item.confidence, 0) / total;
        const avgLeverage = directives.reduce((acc, item) => acc + (item.leverage ?? 0), 0) / total;
        const totalNotional = directives.reduce((acc, item) => acc + (item.notional_usdt ?? 0), 0);
        return {
            total,
            openCount,
            closeCount,
            avgConfidence: Number.isFinite(avgConfidence) ? avgConfidence : null,
            avgLeverage: Number.isFinite(avgLeverage) ? avgLeverage : null,
            totalNotional,
        };
    }, [directives]);

    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card">
            <header className="flex flex-col gap-3 border-b border-slate-800 px-6 py-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-white">Активные директивы</h2>
                    <p className="text-sm text-slate-400">Заявки, отправленные CTO-AI на исполнение.</p>
                </div>
                <div className="flex flex-col items-start gap-3 md:items-end">
                    <div className="flex flex-wrap gap-2">
                        <SummaryBadge label="Всего" value={summary.total} fractionDigits={0} />
                        <SummaryBadge label="Открыть" value={summary.openCount} fractionDigits={0} />
                        <SummaryBadge label="Закрыть" value={summary.closeCount} fractionDigits={0} />
                        <SummaryBadge label="Средн. уверенность" value={summary.avgConfidence !== null ? summary.avgConfidence * 100 : null} unit="%" fractionDigits={1} />
                        <SummaryBadge label="Средн. плечо" value={summary.avgLeverage} fractionDigits={1} />
                        <SummaryBadge label="Номинал" value={summary.totalNotional} unit="USDT" />
                    </div>
                    <button
                        type="button"
                        onClick={() => setExpanded((value) => !value)}
                        className="inline-flex items-center gap-2 self-start rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-900"
                    >
                        {expanded ? <FiChevronUp className="text-base" /> : <FiChevronDown className="text-base" />}
                        {expanded ? 'Скрыть директивы' : 'Показать директивы'}
                    </button>
                </div>
            </header>

            {expanded ? (
                <div className="max-h-[520px] overflow-auto">
                    <table className="min-w-full divide-y divide-slate-800">
                        <thead className="bg-slate-900/80">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">Инструмент</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">Действие</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">Тип</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">Объём</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">Цена</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">TP / SL</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">Увер.</th>
                                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">Время</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                            {directives.map((directive) => {
                                const takeProfit = directive.take_profit_price ? directive.take_profit_price.toFixed(2) : '—';
                                const stopLoss = directive.stop_loss_price ? directive.stop_loss_price.toFixed(2) : '—';
                                const basePrice = directive.price ? directive.price.toFixed(2) : '—';
                                return (
                                    <tr key={directive.directive_id} className="align-top hover:bg-slate-800/40">
                                        <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-100">
                                            <div className="font-semibold text-white">{directive.symbol}</div>
                                            <div className="text-xs text-slate-500">ID: {directive.directive_id}</div>
                                        </td>
                                        <td className="px-4 py-3 text-sm text-slate-200">
                                            <div className="capitalize">{directive.action}</div>
                                            <div className="mt-1 text-xs text-slate-400 capitalize">{directive.direction}</div>
                                        </td>
                                        <td className="px-4 py-3 text-sm uppercase text-slate-200">
                                            {directive.order_type}
                                            <div className="mt-1 text-xs text-slate-400">TIF: {directive.time_in_force}</div>
                                        </td>
                                        <td className="px-4 py-3 text-sm text-slate-200">
                                            {directive.quantity.toFixed(3)}
                                            <div className="mt-1 text-xs text-slate-400">x{(directive.leverage ?? 0).toFixed(1)}</div>
                                        </td>
                                        <td className="px-4 py-3 text-sm text-slate-200">{basePrice}</td>
                                        <td className="px-4 py-3 text-sm text-indigo-300">
                                            <div>TP: {takeProfit}</div>
                                            <div>SL: {stopLoss}</div>
                                        </td>
                                        <td className="px-4 py-3 text-sm text-emerald-300">{(directive.confidence * 100).toFixed(1)}%</td>
                                        <td className="px-4 py-3 text-xs text-slate-400">
                                            {new Date(directive.issued_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            ) : null}
        </section>
    );
}

type SummaryBadgeProps = {
    label: string;
    value: number | null;
    unit?: string;
    fractionDigits?: number;
};

function SummaryBadge({ label, value, unit, fractionDigits = 2 }: SummaryBadgeProps) {
    const formatted = value === null || Number.isNaN(value) ? '—' : value.toLocaleString('ru-RU', {
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
    });
    const display = formatted === '—' ? formatted : unit ? `${formatted} ${unit}` : formatted;
    return (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
            <div className="text-sm font-semibold text-white">{display}</div>
        </div>
    );
}
