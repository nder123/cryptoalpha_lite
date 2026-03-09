import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { FiAlertTriangle, FiCheckCircle, FiLoader } from 'react-icons/fi';
const STATUS_COLORS = {
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
const STATUS_ICONS = {
    healthy: () => _jsx(FiCheckCircle, { className: "text-lg" }),
    running: () => _jsx(FiCheckCircle, { className: "text-lg" }),
    active: () => _jsx(FiCheckCircle, { className: "text-lg" }),
    starting: () => _jsx(FiLoader, { className: "text-lg animate-spin" }),
    stopping: () => _jsx(FiLoader, { className: "text-lg animate-spin" }),
    degraded: () => _jsx(FiAlertTriangle, { className: "text-lg" }),
    insufficient_balance: () => _jsx(FiAlertTriangle, { className: "text-lg" }),
    idle: () => _jsx(FiLoader, { className: "text-lg" }),
    paused: () => _jsx(FiAlertTriangle, { className: "text-lg" }),
    error: () => _jsx(FiAlertTriangle, { className: "text-lg" }),
    stopped: () => _jsx(FiAlertTriangle, { className: "text-lg" }),
    unknown: () => _jsx(FiAlertTriangle, { className: "text-lg" }),
};
function formatTimestamp(value) {
    if (!value) {
        return '—';
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return parsed.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
function classifyStatus(raw) {
    if (!raw) {
        return 'unknown';
    }
    const lowered = raw.trim().toLowerCase();
    if (STATUS_COLORS[lowered]) {
        return lowered;
    }
    return 'unknown';
}
export function ServiceHealthStatus({ services }) {
    const entries = Object.entries(services);
    const sorted = entries.sort(([a], [b]) => a.localeCompare(b));
    return (_jsxs("section", { className: "rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-card", children: [_jsx("header", { className: "mb-4 flex items-center justify-between", children: _jsxs("div", { children: [_jsx("h2", { className: "text-lg font-semibold text-white", children: "\u0421\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u0435 \u0441\u0435\u0440\u0432\u0438\u0441\u043E\u0432" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u041A\u0430\u0436\u0434\u044B\u0439 \u0431\u044D\u043A\u0433\u0440\u0430\u0443\u043D\u0434\u043D\u044B\u0439 \u043F\u0440\u043E\u0446\u0435\u0441\u0441 \u043E\u0442\u0447\u0451\u0442\u043B\u0438\u0432\u043E \u0441\u0438\u0433\u043D\u0430\u043B\u0438\u0442 \u043E \u0441\u0432\u043E\u0451\u043C \u0441\u0442\u0430\u0442\u0443\u0441\u0435." })] }) }), sorted.length === 0 ? (_jsx("p", { className: "text-sm text-slate-500", children: "\u041D\u0435\u0442 \u0434\u0430\u043D\u043D\u044B\u0445 \u043E \u0441\u0435\u0440\u0432\u0438\u0441\u0430\u0445." })) : (_jsx("ul", { className: "grid gap-3 md:grid-cols-2 xl:grid-cols-3", children: sorted.map(([name, payload]) => {
                    const status = classifyStatus(payload.status);
                    const color = STATUS_COLORS[status] ?? 'text-slate-400';
                    const Icon = STATUS_ICONS[status] ?? STATUS_ICONS.unknown;
                    return (_jsxs("li", { className: "flex items-start gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4", children: [_jsx("span", { className: color, children: _jsx(Icon, {}) }), _jsxs("div", { className: "space-y-1 text-sm text-slate-200", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: "font-semibold text-white", children: name }), _jsx("span", { className: `rounded-full bg-slate-800 px-2 py-0.5 text-xs uppercase ${color}`, children: status })] }), payload.message ? _jsx("div", { className: "text-xs text-slate-400", children: payload.message }) : null, payload.error ? (_jsx("div", { className: "rounded-md border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-200", children: payload.error })) : null, _jsxs("div", { className: "text-xs text-slate-500", children: ["\u041E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u043E: ", formatTimestamp(payload.updated_at)] })] })] }, name));
                }) }))] }));
}
