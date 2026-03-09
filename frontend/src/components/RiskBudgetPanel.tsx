import type { RiskBudget } from '../types';

type Props = {
    budget: RiskBudget | null;
};

function formatNumber(value: number | null | undefined, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return '—';
    }
    return value.toLocaleString('ru-RU', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
}

export function RiskBudgetPanel({ budget }: Props) {
    const updatedAt = budget?.updated_at ? new Date(budget.updated_at) : null;
    const symbolLimits = Object.entries(budget?.symbol_limits ?? {})
        .sort(([, a], [, b]) => (b ?? 0) - (a ?? 0))
        .slice(0, 8);

    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-card">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h2 className="text-lg font-semibold text-white">Риск-бюджет портфеля</h2>
                    <p className="mt-1 text-xs text-slate-400">
                        Лимиты, рассчитанные AutoExposureManager на основе equity и волатильности.
                    </p>
                </div>
                {updatedAt && (
                    <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-200">
                        Обновлено {updatedAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                )}
            </div>

            <dl className="mt-4 grid gap-4 sm:grid-cols-3">
                <div className="space-y-1 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
                    <dt className="text-xs uppercase tracking-wide text-emerald-300/80">Лимит портфеля</dt>
                    <dd className="text-2xl font-semibold text-emerald-100">{formatNumber(budget?.portfolio_limit)}</dd>
                </div>
                <div className="space-y-1 rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-4">
                    <dt className="text-xs uppercase tracking-wide text-indigo-300/80">Доступный equity</dt>
                    <dd className="text-2xl font-semibold text-indigo-100">{formatNumber(budget?.available_equity)}</dd>
                </div>
                <div className="space-y-1 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
                    <dt className="text-xs uppercase tracking-wide text-amber-300/80">Волатильность</dt>
                    <dd className="text-2xl font-semibold text-amber-100">
                        {formatNumber(budget?.volatility_index ?? null, 3)}
                        <span className="ml-2 text-xs text-amber-200/70">фактор {formatNumber(budget?.volatility_factor ?? null, 2)}</span>
                    </dd>
                </div>
            </dl>

            <div className="mt-6">
                <h3 className="text-sm font-semibold text-white">Лимиты по символам</h3>
                {symbolLimits.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">Данные по символам пока не получены.</p>
                ) : (
                    <ul className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        {symbolLimits.map(([symbol, limit]) => (
                            <li key={symbol} className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm text-slate-200">
                                <div className="flex items-baseline justify-between">
                                    <span className="font-semibold text-white">{symbol}</span>
                                    <span className="text-xs text-slate-400">USDT</span>
                                </div>
                                <div className="mt-1 text-base font-semibold text-slate-100">{formatNumber(limit)}</div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
