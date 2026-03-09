import type { AccountTransactionListResponse, AccountTransactionSummary, AuditEvent, CTOAISnapshot, DashboardState, DecisionStreamEntry, EquitySnapshotEntry, ExchangeTradeListResponse, ExchangeTradeSummary, ExecutionStreamEntry, HypothesisStreamEntry, HypothesisPnlEntry, ManualDirectivePayload, MarketBuckets, PositionEntry, PositionStreamEntry, RejectionEntry, RiskBudget, RiskStreamEntry, RLStatusResponse, RuntimeConfig, RuntimeConfigUpdatePayload, ServiceHealthMap, TradeDirective, TradeStatsListResponse, TradeStatsSummaryBundle, TradingMode, TradeStatsOverview } from './types';
export declare function fetchDashboardSnapshot(): Promise<{
    market: MarketBuckets;
    ctoai: CTOAISnapshot;
    directives: TradeDirective[];
    rejections: RejectionEntry[];
    positions: PositionEntry[];
    events: AuditEvent[];
    config: RuntimeConfig;
    services: ServiceHealthMap;
    riskBudget: RiskBudget;
    tradeStats: TradeStatsOverview;
}>;
export declare function fetchHypothesisPnl({ limit }?: {
    limit?: number;
}): Promise<HypothesisPnlEntry[]>;
export declare function createDashboardSocket(onMessage: (state: DashboardState) => void): WebSocket;
export declare function updateMode(mode: TradingMode): Promise<unknown>;
export declare function triggerEmergencyStop(): Promise<unknown>;
export declare function fetchRuntimeConfig(): Promise<RuntimeConfig>;
export declare function fetchServiceHealth(): Promise<ServiceHealthMap>;
export declare function patchRuntimeConfig(payload: RuntimeConfigUpdatePayload): Promise<RuntimeConfig>;
export declare function submitManualDirective(payload: ManualDirectivePayload): Promise<TradeDirective>;
export declare function fetchRLStatus(): Promise<RLStatusResponse>;
export declare function fetchTradeStats({ start, end, symbol, limit, offset, }: {
    start?: string | null;
    end?: string | null;
    symbol?: string | null;
    limit?: number;
    offset?: number;
}): Promise<TradeStatsListResponse>;
export declare function fetchTradeStatsSummary({ start, end, }: {
    start?: string | null;
    end?: string | null;
}): Promise<TradeStatsSummaryBundle>;
export declare function exportTradeStats({ start, end, symbol, }: {
    start?: string | null;
    end?: string | null;
    symbol?: string | null;
}): Promise<Blob>;
export declare function fetchExchangeTrades({ start, end, symbol, limit, offset, }: {
    start?: string | null;
    end?: string | null;
    symbol?: string | null;
    limit?: number;
    offset?: number;
}): Promise<ExchangeTradeListResponse>;
export declare function fetchExchangeTradeSummary({ start, end, symbol, }: {
    start?: string | null;
    end?: string | null;
    symbol?: string | null;
}): Promise<ExchangeTradeSummary>;
export declare function fetchAccountTransactions({ start, end, txType, limit, offset, }: {
    start?: string | null;
    end?: string | null;
    txType?: string | null;
    limit?: number;
    offset?: number;
}): Promise<AccountTransactionListResponse>;
export declare function fetchAccountTransactionSummary({ start, end, txType, }: {
    start?: string | null;
    end?: string | null;
    txType?: string | null;
}): Promise<AccountTransactionSummary>;
export declare function fetchEquitySnapshots({ start, end, limit, }: {
    start?: string | null;
    end?: string | null;
    limit?: number;
}): Promise<EquitySnapshotEntry[]>;
export declare function fetchLatestEquitySnapshot(): Promise<EquitySnapshotEntry>;
export declare function fetchExecutionStream({ limit, afterId, }?: {
    limit?: number;
    afterId?: string;
}): Promise<ExecutionStreamEntry[]>;
export declare function fetchDecisionStream({ limit, afterId, }?: {
    limit?: number;
    afterId?: string;
}): Promise<DecisionStreamEntry[]>;
export declare function fetchRiskStream({ limit, afterId, }?: {
    limit?: number;
    afterId?: string;
}): Promise<RiskStreamEntry[]>;
export declare function fetchHypothesisStream({ limit, afterId, }?: {
    limit?: number;
    afterId?: string;
}): Promise<HypothesisStreamEntry[]>;
export declare function fetchPositionStream({ limit, afterId, }?: {
    limit?: number;
    afterId?: string;
}): Promise<PositionStreamEntry[]>;
