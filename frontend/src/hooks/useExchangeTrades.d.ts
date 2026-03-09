import type { ExchangeTradeEntry, ExchangeTradeSummary } from '../types';
type ExchangeTradeFilters = {
    start: string | null;
    end: string | null;
    symbol: string;
};
export declare function useExchangeTrades(limit?: number, initialFilters?: Partial<ExchangeTradeFilters>): {
    readonly filters: ExchangeTradeFilters;
    readonly records: ExchangeTradeEntry[];
    readonly total: number;
    readonly summary: ExchangeTradeSummary;
    readonly loading: boolean;
    readonly error: string;
    readonly updateFilters: (patch: Partial<ExchangeTradeFilters>) => void;
    readonly resetFilters: () => void;
    readonly refresh: () => void;
};
export {};
