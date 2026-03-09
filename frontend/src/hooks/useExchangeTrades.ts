import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { fetchExchangeTradeSummary, fetchExchangeTrades } from '../api';
import type { ExchangeTradeEntry, ExchangeTradeSummary } from '../types';

type ExchangeTradeFilters = {
    start: string | null;
    end: string | null;
    symbol: string;
};

const DEFAULT_FILTERS: ExchangeTradeFilters = {
    start: null,
    end: null,
    symbol: '',
};

export function useExchangeTrades(limit: number = 100, initialFilters?: Partial<ExchangeTradeFilters>) {
    const mergedInitial = useMemo(
        () => ({
            ...DEFAULT_FILTERS,
            ...initialFilters,
        }),
        [initialFilters]
    );
    const initialRef = useRef<ExchangeTradeFilters>(mergedInitial);

    const [filters, setFilters] = useState<ExchangeTradeFilters>(initialRef.current);
    const [records, setRecords] = useState<ExchangeTradeEntry[]>([]);
    const [total, setTotal] = useState(0);
    const [summary, setSummary] = useState<ExchangeTradeSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshCounter, setRefreshCounter] = useState(0);

    const normalizedFilters = useMemo(() => {
        const trimmedSymbol = filters.symbol.trim().toUpperCase();
        return {
            start: filters.start ?? undefined,
            end: filters.end ?? undefined,
            symbol: trimmedSymbol.length ? trimmedSymbol : undefined,
        } as const;
    }, [filters]);

    useEffect(() => {
        let cancelled = false;

        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const [listResponse, summaryResponse] = await Promise.all([
                    fetchExchangeTrades({
                        start: normalizedFilters.start,
                        end: normalizedFilters.end,
                        symbol: normalizedFilters.symbol,
                        limit,
                        offset: 0,
                    }),
                    fetchExchangeTradeSummary({
                        start: normalizedFilters.start,
                        end: normalizedFilters.end,
                        symbol: normalizedFilters.symbol,
                    }),
                ]);
                if (cancelled) return;
                setRecords(listResponse.items);
                setTotal(listResponse.total);
                setSummary(summaryResponse);
            } catch (err) {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : 'Не удалось загрузить сделки биржи');
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        load();
        return () => {
            cancelled = true;
        };
    }, [limit, normalizedFilters, refreshCounter]);

    const updateFilters = useCallback((patch: Partial<ExchangeTradeFilters>) => {
        setFilters((prev) => ({ ...prev, ...patch }));
    }, []);

    const resetFilters = useCallback(() => {
        setFilters(initialRef.current);
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
    } as const;
}
