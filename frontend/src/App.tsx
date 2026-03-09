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
import type { RuntimeConfigUpdatePayload, TradingMode, CTOAISnapshot } from './types';
import { TelemetryStreamsPanel } from './components/TelemetryStreamsPanel';
import { ExchangeReconciliationPanel } from './components/ExchangeReconciliationPanel';
import { TradeStatsSection } from './components/TradeStatsSection';
import { TradeOverviewSummary } from './components/TradeOverviewSummary';

export default function App() {
    const {
        market,
        ctoai,
        directives,
        rejections,
        positions,
        events,
        config,
        services,
        riskBudget,
        tradeStats,
        loading,
        error,
        setCtoaiSnapshot,
        setRuntimeConfig,
    } = useDashboard();
    const { status: rlStatus, loading: rlLoading, error: rlError, refresh: refreshRL } = useRLStatus();
    const [message, setMessage] = useState<string | null>(null);
    const [configSaving, setConfigSaving] = useState(false);
    const messageTimeoutRef = useRef<number | undefined>();
    const serviceAlerts = useMemo(() => {
        const entries = Object.entries(services ?? {});
        return entries.filter(([, payload]) => {
            const status = (payload.status ?? '').toString().toLowerCase();
            return ['error', 'degraded', 'insufficient_balance', 'stopped', 'unknown'].includes(status);
        });
    }, [services]);

    const pushMessage = useCallback((text: string | null) => {
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

    const handleModeChange = useCallback(async (mode: TradingMode) => {
        try {
            const snapshot = await updateMode(mode);
            setCtoaiSnapshot(snapshot as CTOAISnapshot);
            pushMessage(`Режим обновлён: ${mode}`);
        } catch (err) {
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
        } catch (err) {
            pushMessage(err instanceof Error ? err.message : 'Не удалось выполнить аварийный стоп');
        }
    }, [pushMessage]);

    const handleConfigSubmit = useCallback(
        async (payload: RuntimeConfigUpdatePayload) => {
            if (!Object.keys(payload).length) {
                return;
            }
            setConfigSaving(true);
            try {
                const nextConfig = await patchRuntimeConfig(payload);
                setRuntimeConfig(nextConfig);
                pushMessage('Параметры обновлены');
            } catch (err) {
                pushMessage(err instanceof Error ? err.message : 'Не удалось сохранить настройки');
            } finally {
                setConfigSaving(false);
            }
        },
        [pushMessage, setRuntimeConfig]
    );

    const handleManualNotify = useCallback(
        (text: string) => {
            pushMessage(text);
        },
        [pushMessage]
    );

    const activeDirectives = useMemo(
        () => directives.filter((directive) => directive.action === 'open'),
        [directives]
    );

    const manualModeActive = ctoai.mode === 'manual';

    if (loading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-200">
                Загрузка данных CTO-AI…
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-center text-rose-300">
                <div>
                    <p className="text-xl font-semibold">Не удалось загрузить панель</p>
                    <p className="mt-2 text-sm text-rose-200/70">{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200">
            <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10">
                <header className="flex flex-col gap-4 rounded-3xl border border-slate-800 bg-slate-950/80 p-6 shadow-card md:flex-row md:items-center md:justify-between">
                    <div>
                        <h1 className="text-3xl font-bold text-white">CTO-AI Control Center</h1>
                        <p className="mt-2 max-w-2xl text-sm text-slate-400">
                            Центральная панель управления автономным трейдингом Bybit USDT-M. Все решения проходят через CTO-AI,
                            telemetry в реальном времени, полный аудит и ручные overrides.
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-sm">
                        <div className="flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1 text-emerald-300">
                            <FiPlay className="text-lg" />
                            <span>Поток данных активен</span>
                        </div>
                        <button
                            type="button"
                            onClick={handleEmergencyStop}
                            className="flex items-center gap-2 rounded-full border border-rose-500/60 bg-rose-500/10 px-3 py-1 text-rose-300 transition hover:bg-rose-500/20"
                        >
                            <FiStopCircle className="text-lg" />
                            Аварийный стоп
                        </button>
                    </div>
                </header>

                {message && (
                    <div className="rounded-2xl border border-indigo-500/40 bg-indigo-500/10 p-4 text-sm text-indigo-200">
                        {message}
                    </div>
                )}
                {serviceAlerts.length > 0 && (
                    <div className="flex flex-col gap-2 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100">
                        <div className="flex items-center gap-2 text-amber-200">
                            <FiAlertTriangle className="text-lg" />
                            <span>Обнаружены проблемы с сервисами: {serviceAlerts.map(([name]) => name).join(', ')}</span>
                        </div>
                        <p className="text-xs text-amber-100/80">
                            Проверьте сервисы ниже — статусы обновляются автоматически через ServiceSupervisor.
                        </p>
                    </div>
                )}
                {rlError && (
                    <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
                        Не удалось получить статус RL: {rlError}
                    </div>
                )}

                <section className="grid gap-6">
                    <TradeOverviewSummary tradeStats={tradeStats} positions={positions} />
                    <StatusCard snapshot={ctoai} />
                    <ModeSwitch mode={ctoai.mode} onChange={handleModeChange} />
                    <RiskBudgetPanel budget={riskBudget} />
                    <RuntimeConfigPanel config={config} saving={configSaving} onSubmit={handleConfigSubmit} />
                    <ManualTradePanel
                        disabled={!manualModeActive}
                        modeLabel={ctoai.mode}
                        onNotify={handleManualNotify}
                    />
                    <RLStatusPanel status={rlStatus} loading={rlLoading} onRefresh={refreshRL} />
                    <ExchangePositionsTable positions={positions} />
                    <ServiceHealthStatus services={services} />
                    <AutoResearchIndicator entry={services?.['auto-research-manager']} />
                </section>

                <section className="grid gap-6 xl:grid-cols-[2fr,1fr]">
                    <div className="space-y-6">
                        <MarketOverview market={market} />
                        <div className="grid gap-6 lg:grid-cols-[1.2fr,1fr]">
                            <TopCandidatesChart data={market.candidate} />
                            <div className="space-y-6">
                                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-card">
                                    <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
                                        <FiAlertTriangle className="text-amber-400" />
                                        Активные директивы
                                    </h3>
                                    <p className="mt-2 text-sm text-slate-400">
                                        Количество директив в работе: <span className="font-semibold text-white">{activeDirectives.length}</span>
                                    </p>
                                </div>
                                <RejectionsList rejections={rejections} />
                            </div>
                        </div>
                        <DirectivesTable directives={directives} />
                    </div>
                    <AuditLog events={events} />
                </section>

                <TelemetryStreamsPanel />
                <TradeStatsSection />
                <ExchangeReconciliationPanel />
            </div>
        </div>
    );
}
