import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { FiActivity, FiPause, FiPlay, FiRefreshCcw } from 'react-icons/fi';
import { useTelemetryStreams } from '../hooks/useTelemetryStreams';
function formatTimestamp(value) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
function formatNumber(value, fractionDigits = 2) {
    if (value === null || value === undefined) {
        return '—';
    }
    return value.toFixed(fractionDigits);
}
function StreamCard({ title, description, accentClass, items, renderItem }) {
    return (_jsxs("div", { className: "flex h-full flex-col rounded-2xl border border-slate-800 bg-slate-900/60 shadow-card", children: [_jsxs("div", { className: "border-b border-slate-800 px-5 py-4", children: [_jsx("h3", { className: "text-base font-semibold text-white", children: title }), _jsx("p", { className: "mt-1 text-xs text-slate-400", children: description })] }), _jsx("div", { className: "flex-1 overflow-y-auto px-5 py-4", children: items.length === 0 ? (_jsx("p", { className: "text-sm text-slate-500", children: "\u041D\u0435\u0442 \u0441\u043E\u0431\u044B\u0442\u0438\u0439 \u0432 \u0432\u044B\u0431\u0440\u0430\u043D\u043D\u043E\u043C \u043E\u043A\u043D\u0435." })) : (_jsx("ul", { className: "space-y-3 text-sm text-slate-200", children: items
                        .slice()
                        .reverse()
                        .map((item, index) => (_jsxs("li", { className: "space-y-1 rounded-xl bg-slate-900/70 p-3", children: [_jsxs("div", { className: "flex items-center justify-between text-xs text-slate-400", children: [_jsx("span", { className: accentClass, children: title }), _jsx("span", { children: formatTimestamp(item.timestamp ?? item.data?.reported_at) })] }), renderItem(item)] }, index))) })) })] }));
}
function renderExecution(entry) {
    const data = entry.data;
    const status = data.status?.toUpperCase() ?? 'UNKNOWN';
    const statusColor = data.status === 'filled'
        ? 'text-emerald-300'
        : data.status === 'failed' || data.status === 'rejected'
            ? 'text-rose-300'
            : 'text-indigo-300';
    return (_jsxs("div", { className: "space-y-2 text-sm", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("span", { className: "font-semibold text-white", children: data.symbol }), _jsx("span", { className: `text-xs font-semibold ${statusColor}`, children: status })] }), _jsxs("div", { className: "text-xs text-slate-400", children: ["\u041A\u043E\u043B-\u0432\u043E: ", formatNumber(data.quantity, 3), " \u2022 \u0426\u0435\u043D\u0430: ", formatNumber(data.avg_price), " \u2022 \u041A\u043E\u043C\u0438\u0441\u0441\u0438\u0438: ", formatNumber(data.fees_paid)] }), data.notes?.length ? (_jsx("ul", { className: "list-disc space-y-1 pl-5 text-xs text-slate-400", children: data.notes.map((note, idx) => (_jsx("li", { children: note }, idx))) })) : null] }));
}
function renderDecision(entry) {
    const data = entry.data;
    const actionLabel = data.action?.toUpperCase() ?? '—';
    const actionClass = data.action === 'open' ? 'text-emerald-300' : data.action === 'close' ? 'text-amber-300' : 'text-indigo-300';
    return (_jsxs("div", { className: "space-y-1 text-sm", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("span", { className: "font-semibold text-white", children: data.symbol }), _jsx("span", { className: `text-xs font-semibold ${actionClass}`, children: actionLabel })] }), _jsxs("div", { className: "text-xs text-slate-400", children: ["\u0420\u0430\u0437\u043C\u0435\u0440: ", formatNumber(data.size, 3), " \u2022 \u041D\u043E\u0442\u0438\u043E\u043D\u0430\u043B: ", formatNumber(data.notional_usdt), " USDT \u2022 \u0418\u0441\u0442\u043E\u0447\u043D\u0438\u043A: ", data.source] }), data.directive?.rationale?.length ? (_jsx("ul", { className: "list-disc space-y-1 pl-5 text-xs text-slate-400", children: data.directive.rationale.map((reason, idx) => (_jsx("li", { children: reason }, idx))) })) : null] }));
}
function renderRisk(entry) {
    const data = entry.data;
    const approved = data.decision === 'approved';
    return (_jsxs("div", { className: "space-y-1 text-sm", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("span", { className: "font-semibold text-white", children: data.symbol }), _jsx("span", { className: `text-xs font-semibold ${approved ? 'text-emerald-300' : 'text-rose-300'}`, children: approved ? 'APPROVED' : 'BLOCKED' })] }), _jsxs("div", { className: "text-xs text-slate-400", children: ["Confidence: ", formatNumber(data.risk_metrics?.confidence, 2), " \u2022 Exposure: ", formatNumber(data.risk_metrics?.projected_exposure), " USDT"] }), !approved && data.blockers?.length ? (_jsx("ul", { className: "list-disc space-y-1 pl-5 text-xs text-slate-400", children: data.blockers.map((reason, idx) => (_jsx("li", { children: reason }, idx))) })) : null] }));
}
function renderHypothesis(entry) {
    const data = entry.data;
    return (_jsxs("div", { className: "space-y-1 text-sm", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("span", { className: "font-semibold text-white", children: data.symbol }), _jsxs("span", { className: "text-xs font-semibold text-indigo-300", children: [(data.confidence * 100).toFixed(1), "%"] })] }), _jsxs("div", { className: "text-xs text-slate-400", children: ["\u0422\u0438\u043F: ", data.hypothesis_type, " \u2022 \u041D\u0430\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u0435: ", data.direction.toUpperCase(), " \u2022 \u041B\u0435\u0432\u0435\u0440\u0438\u0434\u0436: ", formatNumber(data.leverage, 1), "x"] }), _jsxs("div", { className: "text-xs text-slate-500", children: ["\u0412\u0445\u043E\u0434: ", formatNumber(data.entry_price), " \u2022 Target: ", formatNumber(data.target_price), " \u2022 Stop: ", formatNumber(data.stop_price)] })] }));
}
function renderPosition(entry) {
    const { data } = entry;
    const eventLabel = data.event?.toUpperCase() ?? entry.event_type.toUpperCase();
    const eventColorMap = {
        OPEN_TRACKED: 'text-emerald-300',
        OPEN_UPDATED: 'text-emerald-200',
        CLOSE_REQUESTED: 'text-amber-300',
        FORCE_CLOSE_TIMEOUT: 'text-rose-300',
        CLOSE_CONFIRMED: 'text-emerald-400',
        CLOSE_PARTIAL: 'text-sky-300',
        PRICE_FETCH_FAILED: 'text-amber-200',
        ERROR: 'text-rose-400',
    };
    const eventColor = eventColorMap[eventLabel] ?? 'text-slate-200';
    return (_jsxs("div", { className: "space-y-2 text-sm", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("span", { className: "font-semibold text-white", children: data.symbol }), _jsx("span", { className: `text-xs font-semibold ${eventColor}`, children: eventLabel })] }), _jsxs("div", { className: "text-xs text-slate-400", children: ["\u041D\u0430\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u0435: ", data.direction?.toUpperCase(), " \u2022 \u041A\u043E\u043B-\u0432\u043E: ", formatNumber(data.quantity ?? null, 3), " \u2022 \u0426\u0435\u043D\u0430: ", formatNumber(data.price ?? null)] }), (data.reason || data.status) && (_jsxs("div", { className: "text-xs text-slate-500", children: [data.reason ? `Причина: ${data.reason}` : null, data.reason && data.status ? ' • ' : null, data.status ? `Статус: ${data.status}` : null] })), data.origin_directive_id ? (_jsxs("div", { className: "text-xs text-slate-500", children: ["\u0418\u0441\u0445\u043E\u0434\u043D\u0430\u044F \u0434\u0438\u0440\u0435\u043A\u0442\u0438\u0432\u0430: ", data.origin_directive_id] })) : null, data.notes?.length ? (_jsx("ul", { className: "list-disc space-y-1 pl-5 text-xs text-slate-400", children: data.notes.map((note, idx) => (_jsx("li", { children: note }, idx))) })) : null] }));
}
export function TelemetryStreamsPanel() {
    const { execution, decisions, risk, hypotheses, positions, loading, error, lastUpdated, autoRefresh, setAutoRefresh, refresh } = useTelemetryStreams();
    return (_jsxs("section", { className: "space-y-6", children: [_jsxs("header", { className: "flex flex-col gap-4 rounded-3xl border border-slate-800 bg-slate-950/80 p-5 shadow-card md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { className: "flex items-center gap-3 text-slate-200", children: [_jsx("div", { className: "flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-300", children: _jsx(FiActivity, { className: "text-xl" }) }), _jsxs("div", { children: [_jsx("h2", { className: "text-xl font-semibold text-white", children: "\u041F\u043E\u0442\u043E\u043A\u0438 \u0442\u0435\u043B\u0435\u043C\u0435\u0442\u0440\u0438\u0438" }), _jsx("p", { className: "text-sm text-slate-400", children: "\u0416\u0438\u0432\u044B\u0435 \u0434\u0430\u043D\u043D\u044B\u0435 \u043F\u043E \u0433\u0438\u043F\u043E\u0442\u0435\u0437\u0430\u043C, \u0440\u0435\u0448\u0435\u043D\u0438\u044F\u043C, \u0440\u0438\u0441\u043A\u0443, \u0438\u0441\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u044E \u0438 \u0443\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u044E \u043F\u043E\u0437\u0438\u0446\u0438\u044F\u043C\u0438. \u0410\u0432\u0442\u043E\u043E\u0431\u043D\u043E\u0432\u043B\u0435\u043D\u0438\u0435 \u043A\u0430\u0436\u0434\u044B\u0435 5 \u0441\u0435\u043A\u0443\u043D\u0434." })] })] }), _jsxs("div", { className: "flex flex-wrap items-center gap-3 text-sm", children: [_jsxs("button", { type: "button", onClick: () => setAutoRefresh(!autoRefresh), className: `inline-flex items-center gap-2 rounded-full border px-4 py-2 transition ${autoRefresh
                                    ? 'border-emerald-400/70 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20'
                                    : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500'}`, children: [autoRefresh ? _jsx(FiPause, { className: "text-base" }) : _jsx(FiPlay, { className: "text-base" }), autoRefresh ? 'Пауза' : 'Автообновление'] }), _jsxs("button", { type: "button", onClick: () => {
                                    refresh().catch((err) => {
                                        console.error('Manual telemetry refresh failed', err);
                                    });
                                }, className: "inline-flex items-center gap-2 rounded-full border border-slate-700 px-4 py-2 text-slate-200 transition hover:border-slate-500 hover:bg-slate-900", disabled: loading, children: [_jsx(FiRefreshCcw, { className: "text-base" }), "\u041E\u0431\u043D\u043E\u0432\u0438\u0442\u044C"] }), _jsx("div", { className: "text-xs text-slate-500", children: loading ? 'Загрузка…' : lastUpdated ? `Обновлено: ${formatTimestamp(lastUpdated.toISOString())}` : '—' })] })] }), error ? (_jsx("div", { className: "rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200", children: error })) : null, _jsxs("div", { className: "grid gap-5 md:grid-cols-2 xl:grid-cols-5", children: [_jsx(StreamCard, { title: "Execution", description: "\u041E\u0442\u0447\u0451\u0442\u044B Execution Engine \u043E \u043A\u0430\u0436\u0434\u043E\u043C \u043E\u0440\u0434\u0435\u0440\u0435", accentClass: "text-emerald-300", items: execution, renderItem: renderExecution }), _jsx(StreamCard, { title: "Decisions", description: "\u0420\u0435\u0448\u0435\u043D\u0438\u044F CTO-AI, \u043E\u0442\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u043D\u044B\u0435 \u043D\u0430 \u0438\u0441\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435", accentClass: "text-indigo-300", items: decisions, renderItem: renderDecision }), _jsx(StreamCard, { title: "Risk", description: "\u041E\u0446\u0435\u043D\u043A\u0438 Risk Engine \u0434\u043B\u044F \u0433\u0438\u043F\u043E\u0442\u0435\u0437", accentClass: "text-amber-300", items: risk, renderItem: renderRisk }), _jsx(StreamCard, { title: "Hypotheses", description: "\u0421\u044B\u0440\u044B\u0435 \u0442\u043E\u0440\u0433\u043E\u0432\u044B\u0435 \u0433\u0438\u043F\u043E\u0442\u0435\u0437\u044B \u0438\u0437 Research", accentClass: "text-sky-300", items: hypotheses, renderItem: renderHypothesis }), _jsx(StreamCard, { title: "Positions", description: "\u041A\u0430\u0436\u0434\u044B\u0439 \u0447\u0438\u0445 Position Manager: \u0441\u043E\u0431\u044B\u0442\u0438\u044F \u043E\u0442\u043A\u0440\u044B\u0442\u0438\u044F/\u0437\u0430\u043A\u0440\u044B\u0442\u0438\u044F", accentClass: "text-amber-300", items: positions, renderItem: renderPosition })] })] }));
}
