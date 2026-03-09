import { useState } from 'react';
import { motion } from 'framer-motion';

import type { TradingMode } from '../types';

const MODES: { value: TradingMode; label: string; description: string }[] = [
    { value: 'manual', label: 'Manual', description: 'CTO-AI рекомендует, решения принимает оператор.' },
    { value: 'semi_auto', label: 'Semi-auto', description: 'CTO-AI готовит сделки, оператор подтверждает.' },
    { value: 'full_auto', label: 'Full auto', description: 'CTO-AI полностью автономен в рамках лимитов.' },
];

type Props = {
    mode: TradingMode;
    onChange: (mode: TradingMode) => Promise<void>;
};

export function ModeSwitch({ mode, onChange }: Props) {
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleClick = async (next: TradingMode) => {
        if (next === mode || pending) return;
        try {
            setPending(true);
            setError(null);
            await onChange(next);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Не удалось сменить режим');
        } finally {
            setPending(false);
        }
    };

    return (
        <div className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card">
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">Режим CTO-AI</h2>
                {pending && <span className="text-xs text-slate-400">Обновление…</span>}
            </div>
            <div className="grid gap-3 md:grid-cols-3">
                {MODES.map((item) => {
                    const isActive = item.value === mode;
                    return (
                        <button
                            key={item.value}
                            type="button"
                            onClick={() => handleClick(item.value)}
                            className={`relative overflow-hidden rounded-xl border transition-all ${isActive
                                    ? 'border-indigo-400 bg-indigo-500/10 text-white'
                                    : 'border-slate-800 bg-slate-900/60 text-slate-200 hover:border-slate-700'
                                } px-4 py-3 text-left`}
                            disabled={pending}
                        >
                            {isActive && (
                                <motion.div
                                    layoutId="mode-active"
                                    className="absolute inset-0 bg-indigo-500/10"
                                    transition={{ type: 'spring', stiffness: 250, damping: 24 }}
                                />
                            )}
                            <div className="relative z-10 space-y-1">
                                <div className="text-sm font-semibold uppercase tracking-wide text-indigo-300">
                                    {item.label}
                                </div>
                                <p className="text-xs text-slate-300">{item.description}</p>
                            </div>
                        </button>
                    );
                })}
            </div>
            {error && <p className="text-sm text-rose-400">{error}</p>}
        </div>
    );
}
