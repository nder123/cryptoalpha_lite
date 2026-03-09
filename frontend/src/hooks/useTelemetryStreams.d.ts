import type { DecisionStreamEntry, ExecutionStreamEntry, HypothesisStreamEntry, PositionStreamEntry, RiskStreamEntry } from '../types';
type Options = {
    pollIntervalMs?: number;
    initialLimit?: number;
    incrementalLimit?: number;
    maxEntries?: number;
};
export declare function useTelemetryStreams(options?: Options): {
    loading: boolean;
    error: string;
    lastUpdated: Date;
    autoRefresh: boolean;
    setAutoRefresh: (next: boolean) => void;
    refresh: () => Promise<void>;
    execution: ExecutionStreamEntry[];
    decisions: DecisionStreamEntry[];
    risk: RiskStreamEntry[];
    hypotheses: HypothesisStreamEntry[];
    positions: PositionStreamEntry[];
};
export {};
