import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
    fetchDecisionStream,
    fetchExecutionStream,
    fetchHypothesisStream,
    fetchPositionStream,
    fetchRiskStream,
} from '../api';
import type {
    DecisionStreamEntry,
    ExecutionStreamEntry,
    HypothesisStreamEntry,
    PositionStreamEntry,
    RiskStreamEntry,
} from '../types';

type Options = {
    pollIntervalMs?: number;
    initialLimit?: number;
    incrementalLimit?: number;
    maxEntries?: number;
};

type LastIdRegistry = {
    execution: string | null;
    decisions: string | null;
    risk: string | null;
    hypotheses: string | null;
    positions: string | null;
};

type TelemetrySnapshot = {
    execution: ExecutionStreamEntry[];
    decisions: DecisionStreamEntry[];
    risk: RiskStreamEntry[];
    hypotheses: HypothesisStreamEntry[];
    positions: PositionStreamEntry[];
};

type RefreshMode = 'full' | 'incremental';

const DEFAULT_OPTIONS: Required<Options> = {
    pollIntervalMs: 5000,
    initialLimit: 80,
    incrementalLimit: 40,
    maxEntries: 200,
};

function mergeEntries<T extends { id: string }>(prev: T[], incoming: T[], maxEntries: number): T[] {
    if (!incoming.length) {
        return prev;
    }
    const existingIds = new Set(prev.map((entry) => entry.id));
    const filtered = incoming.filter((entry) => !existingIds.has(entry.id));
    if (!filtered.length) {
        return prev;
    }
    const merged = [...prev, ...filtered];
    return merged.length > maxEntries ? merged.slice(-maxEntries) : merged;
}

export function useTelemetryStreams(options: Options = {}) {
    const { pollIntervalMs, initialLimit, incrementalLimit, maxEntries } = useMemo(
        () => ({ ...DEFAULT_OPTIONS, ...options }),
        [options],
    );

    const [execution, setExecution] = useState<ExecutionStreamEntry[]>([]);
    const [decisions, setDecisions] = useState<DecisionStreamEntry[]>([]);
    const [risk, setRisk] = useState<RiskStreamEntry[]>([]);
    const [hypotheses, setHypotheses] = useState<HypothesisStreamEntry[]>([]);
    const [positions, setPositions] = useState<PositionStreamEntry[]>([]);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [autoRefresh, setAuto] = useState(true);

    const lastIdsRef = useRef<LastIdRegistry>({ execution: null, decisions: null, risk: null, hypotheses: null, positions: null });
    const isMountedRef = useRef(true);

    useEffect(
        () => () => {
            isMountedRef.current = false;
        },
        [],
    );

    const runFetch = useCallback(
        async (mode: RefreshMode) => {
            const full = mode === 'full';
            if (full && isMountedRef.current) {
                setLoading(true);
            }
            try {
                const [executionResp, decisionsResp, riskResp, hypothesesResp, positionsResp] = await Promise.all([
                    fetchExecutionStream(
                        full
                            ? { limit: initialLimit }
                            : {
                                limit: incrementalLimit,
                                afterId: lastIdsRef.current.execution ?? undefined,
                            },
                    ),
                    fetchDecisionStream(
                        full
                            ? { limit: initialLimit }
                            : {
                                limit: incrementalLimit,
                                afterId: lastIdsRef.current.decisions ?? undefined,
                            },
                    ),
                    fetchRiskStream(
                        full
                            ? { limit: initialLimit }
                            : {
                                limit: incrementalLimit,
                                afterId: lastIdsRef.current.risk ?? undefined,
                            },
                    ),
                    fetchHypothesisStream(
                        full
                            ? { limit: initialLimit }
                            : {
                                limit: incrementalLimit,
                                afterId: lastIdsRef.current.hypotheses ?? undefined,
                            },
                    ),
                    fetchPositionStream(
                        full
                            ? { limit: initialLimit }
                            : {
                                limit: incrementalLimit,
                                afterId: lastIdsRef.current.positions ?? undefined,
                            },
                    ),
                ]);

                if (!isMountedRef.current) {
                    return;
                }

                if (full) {
                    const execTrimmed = executionResp.slice(-maxEntries);
                    const decisionsTrimmed = decisionsResp.slice(-maxEntries);
                    const riskTrimmed = riskResp.slice(-maxEntries);
                    const hypothesesTrimmed = hypothesesResp.slice(-maxEntries);
                    const positionsTrimmed = positionsResp.slice(-maxEntries);

                    setExecution(execTrimmed);
                    setDecisions(decisionsTrimmed);
                    setRisk(riskTrimmed);
                    setHypotheses(hypothesesTrimmed);
                    setPositions(positionsTrimmed);

                    lastIdsRef.current.execution = execTrimmed.length ? execTrimmed[execTrimmed.length - 1].id : null;
                    lastIdsRef.current.decisions = decisionsTrimmed.length ? decisionsTrimmed[decisionsTrimmed.length - 1].id : null;
                    lastIdsRef.current.risk = riskTrimmed.length ? riskTrimmed[riskTrimmed.length - 1].id : null;
                    lastIdsRef.current.hypotheses = hypothesesTrimmed.length ? hypothesesTrimmed[hypothesesTrimmed.length - 1].id : null;
                    lastIdsRef.current.positions = positionsTrimmed.length ? positionsTrimmed[positionsTrimmed.length - 1].id : null;
                } else {
                    if (executionResp.length) {
                        setExecution((prev) => mergeEntries(prev, executionResp, maxEntries));
                        lastIdsRef.current.execution = executionResp[executionResp.length - 1].id;
                    }
                    if (decisionsResp.length) {
                        setDecisions((prev) => mergeEntries(prev, decisionsResp, maxEntries));
                        lastIdsRef.current.decisions = decisionsResp[decisionsResp.length - 1].id;
                    }
                    if (riskResp.length) {
                        setRisk((prev) => mergeEntries(prev, riskResp, maxEntries));
                        lastIdsRef.current.risk = riskResp[riskResp.length - 1].id;
                    }
                    if (hypothesesResp.length) {
                        setHypotheses((prev) => mergeEntries(prev, hypothesesResp, maxEntries));
                        lastIdsRef.current.hypotheses = hypothesesResp[hypothesesResp.length - 1].id;
                    }
                    if (positionsResp.length) {
                        setPositions((prev) => mergeEntries(prev, positionsResp, maxEntries));
                        lastIdsRef.current.positions = positionsResp[positionsResp.length - 1].id;
                    }
                }

                setError(null);
                setLastUpdated(new Date());
            } catch (err) {
                if (!isMountedRef.current) {
                    return;
                }
                const message = err instanceof Error ? err.message : 'Не удалось загрузить телеметрию';
                setError(message);
                throw err;
            } finally {
                if (full && isMountedRef.current) {
                    setLoading(false);
                }
            }
        },
        [incrementalLimit, initialLimit, maxEntries],
    );

    const refresh = useCallback(async () => runFetch('full'), [runFetch]);

    const refreshIncremental = useCallback(async () => runFetch('incremental'), [runFetch]);

    useEffect(() => {
        refresh().catch((err) => {
            console.error('Initial telemetry load failed', err);
        });
    }, [refresh]);

    useEffect(() => {
        if (!autoRefresh) {
            return;
        }
        const handle = window.setInterval(() => {
            refreshIncremental().catch((err) => {
                console.error('Telemetry poll failed', err);
            });
        }, pollIntervalMs);
        return () => {
            window.clearInterval(handle);
        };
    }, [autoRefresh, pollIntervalMs, refreshIncremental]);

    const setAutoRefresh = useCallback((next: boolean) => {
        setAuto(next);
    }, []);

    const snapshot: TelemetrySnapshot = useMemo(
        () => ({ execution, decisions, risk, hypotheses, positions }),
        [execution, decisions, risk, hypotheses, positions],
    );

    return {
        ...snapshot,
        loading,
        error,
        lastUpdated,
        autoRefresh,
        setAutoRefresh,
        refresh,
    };
}
