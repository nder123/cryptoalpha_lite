import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
const STATE_LABELS = {
    idle: 'В ожидании',
    scanning: 'Сканирует рынок',
    evaluating: 'Оценивает гипотезы',
    awaiting_risk: 'Ждёт риск-отчёт',
    awaiting_execution: 'Ждёт исполнение',
    managing_position: 'Сопровождает позицию',
    emergency_stop: 'Аварийная остановка',
};
export function StatusCard({ snapshot }) {
    const stateLabel = STATE_LABELS[snapshot.state] ?? snapshot.state;
    const confidencePct = Math.round(snapshot.confidence * 100);
    return (_jsxs("div", { className: "grid gap-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card md:grid-cols-3", children: [_jsxs("div", { children: [_jsx("h3", { className: "text-sm font-semibold uppercase tracking-wide text-indigo-300", children: "\u0422\u0435\u043A\u0443\u0449\u0438\u0439 \u0440\u0435\u0436\u0438\u043C" }), _jsx("p", { className: "mt-1 text-2xl font-semibold text-white", children: snapshot.mode })] }), _jsxs("div", { children: [_jsx("h3", { className: "text-sm font-semibold uppercase tracking-wide text-indigo-300", children: "\u0421\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u0435" }), _jsx("p", { className: "mt-1 text-xl text-slate-200", children: stateLabel })] }), _jsxs("div", { children: [_jsx("h3", { className: "text-sm font-semibold uppercase tracking-wide text-indigo-300", children: "\u0423\u0432\u0435\u0440\u0435\u043D\u043D\u043E\u0441\u0442\u044C" }), _jsx("div", { className: "mt-2 h-2 rounded-full bg-slate-800", children: _jsx("div", { className: "h-full rounded-full bg-emerald-400", style: { width: `${confidencePct}%`, transition: 'width 0.3s ease-in-out' } }) }), _jsxs("p", { className: "mt-1 text-sm text-slate-300", children: [confidencePct, "%"] })] })] }));
}
