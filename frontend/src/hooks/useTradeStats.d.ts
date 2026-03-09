import type { TradeSessionRecord, TradeStatsSummary } from '../types';
type TradeStatsFilters = {
    start: string | null;
    end: string | null;
    symbol: string;
};
export declare function useTradeStats(limit?: number): {
    filters: TradeStatsFilters;
    records: TradeSessionRecord[];
    total: number;
    summary: TradeStatsSummary;
    daily: import("../types").TradeStatsPeriodEntry[];
    weekly: import("../types").TradeStatsPeriodEntry[];
    loading: boolean;
    error: string;
    updateFilters: (patch: Partial<TradeStatsFilters>) => void;
    resetFilters: () => void;
    refresh: () => void;
    exportCsv: () => Promise<void>;
    exporting: boolean;
};
export {};
