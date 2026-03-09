import type { HypothesisPnlEntry } from '../types';
type HypothesisPnlFilters = {
    limit: number;
};
export declare function useHypothesisPnl(initialLimit?: number): {
    readonly filters: {
        limit: number;
    };
    readonly entries: HypothesisPnlEntry[];
    readonly loading: boolean;
    readonly error: string;
    readonly updateFilters: (patch: Partial<HypothesisPnlFilters>) => void;
    readonly resetFilters: () => void;
    readonly refresh: () => void;
};
export {};
