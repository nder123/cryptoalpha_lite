import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { FiActivity, FiAlertTriangle, FiChevronDown, FiChevronRight, FiClock, FiDatabase } from 'react-icons/fi';
const STATUS_STYLES = {
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
export function AutoResearchIndicator({ entry }) {
    const [expanded, setExpanded] = useState(false);
    if (!entry) {
        return null;
    }
    const status = (entry.status ?? 'unknown').toString().trim().toLowerCase();
    const style = STATUS_STYLES[status] ?? FALLBACK_STYLE;
    const backlogSize = useMemo(() => {
        const raw = entry.backlog;
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
        const raw = entry.dispatched;
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
        const raw = entry.updated_at;
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
            icon: _jsx(FiDatabase, { className: "text-base" }),
            title: 'Размер бэклога',
            value: backlogSize,
        },
        {
            icon: _jsx(FiActivity, { className: "text-base" }),
            title: 'Отправлено в этом цикле',
            value: dispatchedCount,
        },
        {
            icon: _jsx(FiClock, { className: "text-base" }),
            title: 'Последнее обновление',
            value: updatedAtLabel,
        },
    ];
    const shouldStartExpanded = status === 'error';
    return (_jsxs("section", { className: `rounded-3xl border bg-slate-950/80 ${style.border} ${style.glow} transition-all`, children: [_jsxs("button", { type: "button", onClick: () => setExpanded((prev) => !prev), className: "flex w-full items-center justify-between gap-4 px-6 py-5 text-left", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("div", { className: `flex h-9 w-9 items-center justify-center rounded-2xl ${style.pill}`, children: _jsx(FiActivity, { className: "text-base" }) }), _jsxs("div", { children: [_jsx("h3", { className: "text-lg font-semibold text-white", children: "Auto-Research" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u0424\u043E\u043D\u043E\u0432\u044B\u0439 \u0446\u0438\u043A\u043B, \u0433\u043E\u043D\u044F\u044E\u0449\u0438\u0439 \u043A\u0430\u043D\u0434\u0438\u0434\u0430\u0442\u043E\u0432 \u0447\u0435\u0440\u0435\u0437 ResearchEngine." })] })] }), _jsxs("div", { className: "flex items-center gap-3", children: [_jsx("span", { className: `inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs uppercase tracking-wide ${style.badge}`, children: status }), expanded || shouldStartExpanded ? _jsx(FiChevronDown, { className: "text-lg text-slate-300" }) : _jsx(FiChevronRight, { className: "text-lg text-slate-300" })] })] }), (expanded || shouldStartExpanded) && (_jsxs("div", { className: "space-y-4 border-t border-slate-800/60 px-6 py-5", children: [_jsx("ul", { className: "grid gap-3 md:grid-cols-3", children: indicators.map(({ icon, title, value }) => (_jsxs("li", { className: "flex flex-col gap-1 rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4", children: [_jsxs("div", { className: "flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400", children: [icon, title] }), _jsx("div", { className: "text-2xl font-semibold text-white", children: value })] }, title))) }), helperText ? (_jsx("div", { className: "rounded-2xl border border-sky-500/40 bg-sky-500/5 p-4 text-sm text-sky-100", children: helperText })) : null, errorText ? (_jsxs("div", { className: "flex items-start gap-2 rounded-2xl border border-rose-500/50 bg-rose-500/10 p-4 text-sm text-rose-100", children: [_jsx(FiAlertTriangle, { className: "mt-0.5 text-lg" }), _jsx("span", { children: errorText })] })) : null, _jsx("div", { className: "text-xs text-slate-500", children: "\u041F\u043E\u0434\u0441\u043A\u0430\u0437\u043A\u0430: \u0441\u0435\u0440\u0432\u0438\u0441 \u043F\u0443\u0431\u043B\u0438\u043A\u0443\u0435\u0442 \u0441\u0442\u0430\u0442\u0443\u0441 \u043A\u0430\u0436\u0434\u044B\u0435 30 \u0441\u0435\u043A\u0443\u043D\u0434. \u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043D\u0430\u0445\u043E\u0434\u044F\u0442\u0441\u044F \u0432 RuntimeConfig \u2192 auto_research_*." })] }))] }));
}
