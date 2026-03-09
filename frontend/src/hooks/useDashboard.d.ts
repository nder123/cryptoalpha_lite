import type { MarketBuckets, TradeDirective, RejectionEntry, AuditEvent, CTOAISnapshot, RuntimeConfig, PositionEntry, ServiceHealthMap, RiskBudget, TradeStatsOverview } from '../types';
export declare function useDashboard(): {
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
    loading: boolean;
    error: string;
    setCtoaiSnapshot: (snapshot: CTOAISnapshot) => void;
    setRuntimeConfig: (next: RuntimeConfig | null) => void;
};
