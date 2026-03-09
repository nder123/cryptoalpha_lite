import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchAccountTransactionSummary, fetchAccountTransactions } from '../api';
const DEFAULT_FILTERS = {
    start: null,
    end: null,
    txType: '',
};
export function useExchangeTransactions(limit = 100) {
    const [filters, setFilters] = useState(DEFAULT_FILTERS);
    const [records, setRecords] = useState([]);
    const [total, setTotal] = useState(0);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [refreshCounter, setRefreshCounter] = useState(0);
    const normalizedFilters = useMemo(() => {
        const cleanedType = filters.txType.trim().toUpperCase();
        return {
            start: filters.start ?? undefined,
            end: filters.end ?? undefined,
            txType: cleanedType.length ? cleanedType : undefined,
        };
    }, [filters]);
    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const [listResponse, summaryResponse] = await Promise.all([
                    fetchAccountTransactions({
                        start: normalizedFilters.start,
                        end: normalizedFilters.end,
                        txType: normalizedFilters.txType,
                        limit,
                        offset: 0,
                    }),
                    fetchAccountTransactionSummary({
                        start: normalizedFilters.start,
                        end: normalizedFilters.end,
                        txType: normalizedFilters.txType,
                    }),
                ]);
                if (cancelled)
                    return;
                setRecords(listResponse.items);
                setTotal(listResponse.total);
                setSummary(summaryResponse);
            }
            catch (err) {
                if (cancelled)
                    return;
                setError(err instanceof Error ? err.message : 'Не удалось загрузить транзакции биржи');
            }
            finally {
                if (!cancelled)
                    setLoading(false);
            }
        };
        load();
        return () => {
            cancelled = true;
        };
    }, [limit, normalizedFilters, refreshCounter]);
    const updateFilters = useCallback((patch) => {
        setFilters((prev) => ({ ...prev, ...patch }));
    }, []);
    const resetFilters = useCallback(() => {
        setFilters(DEFAULT_FILTERS);
    }, []);
    const refresh = useCallback(() => {
        setRefreshCounter((value) => value + 1);
    }, []);
    return {
        filters,
        records,
        total,
        summary,
        loading,
        error,
        updateFilters,
        resetFilters,
        refresh,
    };
}
