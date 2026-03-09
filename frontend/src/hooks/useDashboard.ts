import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type {
    DashboardState,
    MarketBuckets,
    TradeDirective,
    RejectionEntry,
    AuditEvent,
    CTOAISnapshot,
    RuntimeConfig,
    PositionEntry,
    ServiceHealthMap,
    RiskBudget,
    TradeStatsOverview,
} from '../types';
import { createDashboardSocket, fetchDashboardSnapshot } from '../api';

export function useDashboard() {
    const [market, setMarket] = useState<MarketBuckets>({ ignored: {}, watch: {}, candidate: {}, active: {} });
    const [ctoai, setCtoai] = useState<CTOAISnapshot>({ mode: 'manual', state: 'idle', confidence: 0, active_directives: [] });
    const [directives, setDirectives] = useState<TradeDirective[]>([]);
    const [rejections, setRejections] = useState<RejectionEntry[]>([]);
    const [positions, setPositions] = useState<PositionEntry[]>([]);
    const [events, setEvents] = useState<AuditEvent[]>([]);
    const [config, setConfig] = useState<RuntimeConfig | null>(null);
    const [services, setServices] = useState<ServiceHealthMap>({});
    const [riskBudget, setRiskBudget] = useState<RiskBudget | null>(null);
    const [tradeStats, setTradeStats] = useState<TradeStatsOverview | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        fetchDashboardSnapshot()
            .then(({ market, ctoai, directives, rejections, positions, events, config, services, riskBudget, tradeStats }) => {
                setMarket(market);
                setCtoai(ctoai);
                setDirectives(directives);
                setRejections(rejections);
                setPositions(positions ?? []);
                setEvents(events);
                setConfig(config);
                setServices(services ?? {});
                setRiskBudget(riskBudget ?? null);
                setTradeStats(tradeStats ?? null);
                setLoading(false);
            })
            .catch((err) => {
                setError(err instanceof Error ? err.message : String(err));
                setLoading(false);
            });

        const ws = createDashboardSocket((state: DashboardState) => {
            setMarket(state.market);
            setCtoai(state.ctoai);
            setDirectives(state.directives);
            setRejections(state.rejections);
            if (state.positions) {
                setPositions(state.positions);
            }
            setEvents((prev) => state.events ?? prev);
            if (state.config) {
                setConfig((prev) => {
                    if (!prev) {
                        return state.config ?? null;
                    }
                    if (!state.config.updated_at || !prev.updated_at) {
                        return state.config ?? prev;
                    }
                    return state.config.updated_at === prev.updated_at ? prev : state.config;
                });
            }
            if (state.services) {
                setServices(state.services);
            }
            if (state.risk_budget) {
                setRiskBudget(state.risk_budget);
            }
            if (state.trade_stats) {
                setTradeStats(state.trade_stats);
            }
        });
        wsRef.current = ws;

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, []);

    const setCtoaiSnapshot = useCallback((snapshot: CTOAISnapshot) => {
        setCtoai(snapshot);
    }, []);

    const setRuntimeConfig = useCallback((next: RuntimeConfig | null) => {
        setConfig(next);
    }, []);

    return useMemo(
        () => ({
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
        }),
        [
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
        ]
    );
}
