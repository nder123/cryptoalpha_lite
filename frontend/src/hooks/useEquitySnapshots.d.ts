import type { EquitySnapshotEntry } from '../types';
type EquityFilters = {
    start: string | null;
    end: string | null;
    limit: number;
};
export declare function useEquitySnapshots(): {
    readonly filters: EquityFilters;
    readonly snapshots: EquitySnapshotEntry[];
    readonly latest: EquitySnapshotEntry;
    readonly latestEquity: number;
    readonly latestAvailable: number;
    readonly averageEquity: number;
    readonly loading: boolean;
    readonly error: string;
    readonly updateFilters: (patch: Partial<EquityFilters>) => void;
    readonly resetFilters: () => void;
    readonly refresh: () => void;
};
export {};
