import type { AccountTransactionEntry, AccountTransactionSummary } from '../types';
type ExchangeTransactionFilters = {
    start: string | null;
    end: string | null;
    txType: string;
};
export declare function useExchangeTransactions(limit?: number): {
    readonly filters: ExchangeTransactionFilters;
    readonly records: AccountTransactionEntry[];
    readonly total: number;
    readonly summary: AccountTransactionSummary;
    readonly loading: boolean;
    readonly error: string;
    readonly updateFilters: (patch: Partial<ExchangeTransactionFilters>) => void;
    readonly resetFilters: () => void;
    readonly refresh: () => void;
};
export {};
