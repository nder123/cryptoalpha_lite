import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { motion } from 'framer-motion';
const MODES = [
    { value: 'manual', label: 'Manual', description: 'CTO-AI рекомендует, решения принимает оператор.' },
    { value: 'semi_auto', label: 'Semi-auto', description: 'CTO-AI готовит сделки, оператор подтверждает.' },
    { value: 'full_auto', label: 'Full auto', description: 'CTO-AI полностью автономен в рамках лимитов.' },
];
export function ModeSwitch({ mode, onChange }) {
    const [pending, setPending] = useState(false);
    const [error, setError] = useState(null);
    const handleClick = async (next) => {
        if (next === mode || pending)
            return;
        try {
            setPending(true);
            setError(null);
            await onChange(next);
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Не удалось сменить режим');
        }
        finally {
            setPending(false);
        }
    };
    return (_jsxs("div", { className: "space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h2", { className: "text-lg font-semibold text-white", children: "\u0420\u0435\u0436\u0438\u043C CTO-AI" }), pending && _jsx("span", { className: "text-xs text-slate-400", children: "\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435\u2026" })] }), _jsx("div", { className: "grid gap-3 md:grid-cols-3", children: MODES.map((item) => {
                    const isActive = item.value === mode;
                    return (_jsxs("button", { type: "button", onClick: () => handleClick(item.value), className: `relative overflow-hidden rounded-xl border transition-all ${isActive
                            ? 'border-indigo-400 bg-indigo-500/10 text-white'
                            : 'border-slate-800 bg-slate-900/60 text-slate-200 hover:border-slate-700'} px-4 py-3 text-left`, disabled: pending, children: [isActive && (_jsx(motion.div, { layoutId: "mode-active", className: "absolute inset-0 bg-indigo-500/10", transition: { type: 'spring', stiffness: 250, damping: 24 } })), _jsxs("div", { className: "relative z-10 space-y-1", children: [_jsx("div", { className: "text-sm font-semibold uppercase tracking-wide text-indigo-300", children: item.label }), _jsx("p", { className: "text-xs text-slate-300", children: item.description })] })] }, item.value));
                }) }), error && _jsx("p", { className: "text-sm text-rose-400", children: error })] }));
}
