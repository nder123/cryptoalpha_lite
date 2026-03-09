import type { TradeStatsSummary } from '../types';

interface Props {
    summary: TradeStatsSummary | null;
    loading: boolean;
}

const cards = [
    {
        key: 'total_pnl_usdt' as const,
        label: 'Суммарный PnL (USDT)',
        accent: 'text-emerald-300',
    },
    {
        key: 'total_pnl_usdt_net' as const,
        label: 'PnL после комиссий (USDT)',
        accent: 'text-emerald-200',
    },
    {
        key: 'total_fees_usdt' as const,
        label: 'Комиссии (USDT)',
        accent: 'text-slate-300',
    },
    {
        key: 'avg_pnl_pct' as const,
        label: 'Средний PnL %',
        accent: 'text-indigo-300',
    },
    {
        key: 'win_rate' as const,
        label: 'Win Rate',
        accent: 'text-amber-300',
    },
    {
        key: 'avg_rr' as const,
        label: 'Средний R/R',
        accent: 'text-sky-300',
    },
    {
        key: 'total_trades' as const,
        label: 'Всего сделок',
        accent: 'text-rose-300',
    },
];

function formatValue(key: keyof TradeStatsSummary, summary: TradeStatsSummary | null): string {
    if (!summary) return '—';
    const value = summary[key];
    if (value === null || value === undefined) return '—';
    switch (key) {
        case 'total_pnl_usdt':
            return `${value.toFixed(2)} USDT`;
        case 'total_pnl_usdt_net':
            return `${value.toFixed(2)} USDT`;
        case 'total_fees_usdt':
            return `${value.toFixed(2)} USDT`;
        case 'avg_pnl_pct':
            return `${value.toFixed(2)} %`;
        case 'win_rate':
            return `${(value * 100).toFixed(1)} %`;
        case 'avg_rr':
            return value.toFixed(2);
        case 'total_trades':
        case 'winning_trades':
            return String(value);
        default:
            return String(value);
    }
}

export function TradeStatsSummaryCards({ summary, loading }: Props) {
    return (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {cards.map((card) => (
                <div
                    key={card.key}
                    className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-card"
                >
                    <div className="text-xs uppercase tracking-wide text-slate-400">{card.label}</div>
                    <div className={`mt-3 text-2xl font-semibold ${card.accent}`}>
                        {loading ? '…' : formatValue(card.key, summary)}
                    </div>
                </div>
            ))}
        </div>
    );
}
