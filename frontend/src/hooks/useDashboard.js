import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createDashboardSocket, fetchDashboardSnapshot } from '../api';
export function useDashboard() {
    const [market, setMarket] = useState({ ignored: {}, watch: {}, candidate: {}, active: {} });
    const [ctoai, setCtoai] = useState({ mode: 'manual', state: 'idle', confidence: 0, active_directives: [] });
    const [directives, setDirectives] = useState([]);
    const [rejections, setRejections] = useState([]);
    const [positions, setPositions] = useState([]);
    const [events, setEvents] = useState([]);
    const [config, setConfig] = useState(null);
    const [services, setServices] = useState({});
    const [riskBudget, setRiskBudget] = useState(null);
    const [tradeStats, setTradeStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const wsRef = useRef(null);
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
        const ws = createDashboardSocket((state) => {
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
    const setCtoaiSnapshot = useCallback((snapshot) => {
        setCtoai(snapshot);
    }, []);
    const setRuntimeConfig = useCallback((next) => {
        setConfig(next);
    }, []);
    return useMemo(() => ({
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
    }), [
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
    ]);
}
