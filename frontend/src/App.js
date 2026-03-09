import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FiAlertTriangle, FiPlay, FiStopCircle } from 'react-icons/fi';
import { patchRuntimeConfig, triggerEmergencyStop, updateMode } from './api';
import { RLStatusPanel } from './components/RLStatusPanel';
import { AuditLog } from './components/AuditLog';
import { DirectivesTable } from './components/DirectivesTable';
import { MarketOverview } from './components/MarketOverview';
import { ModeSwitch } from './components/ModeSwitch';
import { ManualTradePanel } from './components/ManualTradePanel';
import { RuntimeConfigPanel } from './components/RuntimeConfigPanel';
import { RejectionsList } from './components/RejectionsList';
import { StatusCard } from './components/StatusCard';
import { TopCandidatesChart } from './components/TopCandidatesChart';
import { ExchangePositionsTable } from './components/ExchangePositionsTable';
import { ServiceHealthStatus } from './components/ServiceHealthStatus';
import { RiskBudgetPanel } from './components/RiskBudgetPanel';
import { AutoResearchIndicator } from './components/AutoResearchIndicator';
import { useDashboard } from './hooks/useDashboard';
import { useRLStatus } from './hooks/useRLStatus';
import { TelemetryStreamsPanel } from './components/TelemetryStreamsPanel';
import { ExchangeReconciliationPanel } from './components/ExchangeReconciliationPanel';
import { TradeStatsSection } from './components/TradeStatsSection';
import { TradeOverviewSummary } from './components/TradeOverviewSummary';
export default function App() {
    const { market, ctoai, directives, rejections, positions, events, config, services, riskBudget, tradeStats, loading, error, setCtoaiSnapshot, setRuntimeConfig, } = useDashboard();
    const { status: rlStatus, loading: rlLoading, error: rlError, refresh: refreshRL } = useRLStatus();
    const [message, setMessage] = useState(null);
    const [configSaving, setConfigSaving] = useState(false);
    const messageTimeoutRef = useRef();
    const serviceAlerts = useMemo(() => {
        const entries = Object.entries(services ?? {});
        return entries.filter(([, payload]) => {
            const status = (payload.status ?? '').toString().toLowerCase();
            return ['error', 'degraded', 'insufficient_balance', 'stopped', 'unknown'].includes(status);
        });
    }, [services]);
    const pushMessage = useCallback((text) => {
        if (!text) {
            setMessage(null);
            if (messageTimeoutRef.current) {
                window.clearTimeout(messageTimeoutRef.current);
                messageTimeoutRef.current = undefined;
            }
            return;
        }
        setMessage(text);
        if (messageTimeoutRef.current) {
            window.clearTimeout(messageTimeoutRef.current);
        }
        messageTimeoutRef.current = window.setTimeout(() => {
            setMessage(null);
            messageTimeoutRef.current = undefined;
        }, 3000);
    }, []);
    useEffect(() => {
        return () => {
            if (messageTimeoutRef.current) {
                window.clearTimeout(messageTimeoutRef.current);
            }
        };
    }, []);
    const handleModeChange = useCallback(async (mode) => {
        try {
            const snapshot = await updateMode(mode);
            setCtoaiSnapshot(snapshot);
            pushMessage(`Режим обновлён: ${mode}`);
        }
        catch (err) {
            pushMessage(err instanceof Error ? err.message : 'Не удалось сменить режим');
        }
    }, [pushMessage, setCtoaiSnapshot]);
    const handleEmergencyStop = useCallback(async () => {
        if (!confirm('Подтвердите аварийную остановку CTO-AI. Все активные действия будут остановлены.')) {
            return;
        }
        try {
            await triggerEmergencyStop();
            pushMessage('Аварийная остановка активирована');
        }
        catch (err) {
            pushMessage(err instanceof Error ? err.message : 'Не удалось выполнить аварийный стоп');
        }
    }, [pushMessage]);
    const handleConfigSubmit = useCallback(async (payload) => {
        if (!Object.keys(payload).length) {
            return;
        }
        setConfigSaving(true);
        try {
            const nextConfig = await patchRuntimeConfig(payload);
            setRuntimeConfig(nextConfig);
            pushMessage('Параметры обновлены');
        }
        catch (err) {
            pushMessage(err instanceof Error ? err.message : 'Не удалось сохранить настройки');
        }
        finally {
            setConfigSaving(false);
        }
    }, [pushMessage, setRuntimeConfig]);
    const handleManualNotify = useCallback((text) => {
        pushMessage(text);
    }, [pushMessage]);
    const activeDirectives = useMemo(() => directives.filter((directive) => directive.action === 'open'), [directives]);
    const manualModeActive = ctoai.mode === 'manual';
    if (loading) {
        return (_jsx("div", { className: "flex min-h-screen items-center justify-center bg-slate-950 text-slate-200", children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430 \u0434\u0430\u043D\u043D\u044B\u0445 CTO-AI\u2026" }));
    }
    if (error) {
        return (_jsx("div", { className: "flex min-h-screen items-center justify-center bg-slate-950 p-6 text-center text-rose-300", children: _jsxs("div", { children: [_jsx("p", { className: "text-xl font-semibold", children: "\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u043F\u0430\u043D\u0435\u043B\u044C" }), _jsx("p", { className: "mt-2 text-sm text-rose-200/70", children: error })] }) }));
    }
    return (_jsx("div", { className: "min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200", children: _jsxs("div", { className: "mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10", children: [_jsxs("header", { className: "flex flex-col gap-4 rounded-3xl border border-slate-800 bg-slate-950/80 p-6 shadow-card md:flex-row md:items-center md:justify-between", children: [_jsxs("div", { children: [_jsx("h1", { className: "text-3xl font-bold text-white", children: "CTO-AI Control Center" }), _jsx("p", { className: "mt-2 max-w-2xl text-sm text-slate-400", children: "\u0426\u0435\u043D\u0442\u0440\u0430\u043B\u044C\u043D\u0430\u044F \u043F\u0430\u043D\u0435\u043B\u044C \u0443\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u044F \u0430\u0432\u0442\u043E\u043D\u043E\u043C\u043D\u044B\u043C \u0442\u0440\u0435\u0439\u0434\u0438\u043D\u0433\u043E\u043C Bybit USDT-M. \u0412\u0441\u0435 \u0440\u0435\u0448\u0435\u043D\u0438\u044F \u043F\u0440\u043E\u0445\u043E\u0434\u044F\u0442 \u0447\u0435\u0440\u0435\u0437 CTO-AI, telemetry \u0432 \u0440\u0435\u0430\u043B\u044C\u043D\u043E\u043C \u0432\u0440\u0435\u043C\u0435\u043D\u0438, \u043F\u043E\u043B\u043D\u044B\u0439 \u0430\u0443\u0434\u0438\u0442 \u0438 \u0440\u0443\u0447\u043D\u044B\u0435 overrides." })] }), _jsxs("div", { className: "flex flex-wrap items-center gap-3 text-sm", children: [_jsxs("div", { className: "flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1 text-emerald-300", children: [_jsx(FiPlay, { className: "text-lg" }), _jsx("span", { children: "\u041F\u043E\u0442\u043E\u043A \u0434\u0430\u043D\u043D\u044B\u0445 \u0430\u043A\u0442\u0438\u0432\u0435\u043D" })] }), _jsxs("button", { type: "button", onClick: handleEmergencyStop, className: "flex items-center gap-2 rounded-full border border-rose-500/60 bg-rose-500/10 px-3 py-1 text-rose-300 transition hover:bg-rose-500/20", children: [_jsx(FiStopCircle, { className: "text-lg" }), "\u0410\u0432\u0430\u0440\u0438\u0439\u043D\u044B\u0439 \u0441\u0442\u043E\u043F"] })] })] }), message && (_jsx("div", { className: "rounded-2xl border border-indigo-500/40 bg-indigo-500/10 p-4 text-sm text-indigo-200", children: message })), serviceAlerts.length > 0 && (_jsxs("div", { className: "flex flex-col gap-2 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100", children: [_jsxs("div", { className: "flex items-center gap-2 text-amber-200", children: [_jsx(FiAlertTriangle, { className: "text-lg" }), _jsxs("span", { children: ["\u041E\u0431\u043D\u0430\u0440\u0443\u0436\u0435\u043D\u044B \u043F\u0440\u043E\u0431\u043B\u0435\u043C\u044B \u0441 \u0441\u0435\u0440\u0432\u0438\u0441\u0430\u043C\u0438: ", serviceAlerts.map(([name]) => name).join(', ')] })] }), _jsx("p", { className: "text-xs text-amber-100/80", children: "\u041F\u0440\u043E\u0432\u0435\u0440\u044C\u0442\u0435 \u0441\u0435\u0440\u0432\u0438\u0441\u044B \u043D\u0438\u0436\u0435 \u2014 \u0441\u0442\u0430\u0442\u0443\u0441\u044B \u043E\u0431\u043D\u043E\u0432\u043B\u044F\u044E\u0442\u0441\u044F \u0430\u0432\u0442\u043E\u043C\u0430\u0442\u0438\u0447\u0435\u0441\u043A\u0438 \u0447\u0435\u0440\u0435\u0437 ServiceSupervisor." })] })), rlError && (_jsxs("div", { className: "rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200", children: ["\u041D\u0435 \u0443\u0434\u0430\u043B\u043E\u0441\u044C \u043F\u043E\u043B\u0443\u0447\u0438\u0442\u044C \u0441\u0442\u0430\u0442\u0443\u0441 RL: ", rlError] })), _jsxs("section", { className: "grid gap-6", children: [_jsx(TradeOverviewSummary, { tradeStats: tradeStats, positions: positions }), _jsx(StatusCard, { snapshot: ctoai }), _jsx(ModeSwitch, { mode: ctoai.mode, onChange: handleModeChange }), _jsx(RiskBudgetPanel, { budget: riskBudget }), _jsx(RuntimeConfigPanel, { config: config, saving: configSaving, onSubmit: handleConfigSubmit }), _jsx(ManualTradePanel, { disabled: !manualModeActive, modeLabel: ctoai.mode, onNotify: handleManualNotify }), _jsx(RLStatusPanel, { status: rlStatus, loading: rlLoading, onRefresh: refreshRL }), _jsx(ExchangePositionsTable, { positions: positions }), _jsx(ServiceHealthStatus, { services: services }), _jsx(AutoResearchIndicator, { entry: services?.['auto-research-manager'] })] }), _jsxs("section", { className: "grid gap-6 xl:grid-cols-[2fr,1fr]", children: [_jsxs("div", { className: "space-y-6", children: [_jsx(MarketOverview, { market: market }), _jsxs("div", { className: "grid gap-6 lg:grid-cols-[1.2fr,1fr]", children: [_jsx(TopCandidatesChart, { data: market.candidate }), _jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card", children: [_jsxs("h3", { className: "flex items-center gap-2 text-lg font-semibold text-white", children: [_jsx(FiAlertTriangle, { className: "text-amber-400" }), "\u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0435 \u0434\u0438\u0440\u0435\u043A\u0442\u0438\u0432\u044B"] }), _jsxs("p", { className: "mt-2 text-sm text-slate-400", children: ["\u041A\u043E\u043B\u0438\u0447\u0435\u0441\u0442\u0432\u043E \u0434\u0438\u0440\u0435\u043A\u0442\u0438\u0432 \u0432 \u0440\u0430\u0431\u043E\u0442\u0435: ", _jsx("span", { className: "font-semibold text-white", children: activeDirectives.length })] })] }), _jsx(RejectionsList, { rejections: rejections })] })] }), _jsx(DirectivesTable, { directives: directives })] }), _jsx(AuditLog, { events: events })] }), _jsx(TelemetryStreamsPanel, {}), _jsx(TradeStatsSection, {}), _jsx(ExchangeReconciliationPanel, {})] }) }));
}
