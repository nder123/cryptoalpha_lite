
import { useCallback, useEffect, useMemo, useState } from 'react';

import { fetchHypothesisPnl } from '../api';
import type { HypothesisPnlEntry } from '../types';

type HypothesisPnlFilters = {
    limit: number;
};

const DEFAULT_FILTERS: HypothesisPnlFilters = {
    limit: 50,
};

export function useHypothesisPnl(initialLimit: number = DEFAULT_FILTERS.limit) {
    const [filters, setFilters] = useState<HypothesisPnlFilters>({ limit: initialLimit });
    const [entries, setEntries] = useState<HypothesisPnlEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshCounter, setRefreshCounter] = useState(0);

    const normalizedFilters = useMemo(() => ({
        limit: Math.max(1, Math.min(500, filters.limit)),
    }), [filters]);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const payload = await fetchHypothesisPnl(normalizedFilters);
                if (cancelled) return;
                setEntries(payload);
            } catch (err) {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : 'Не удалось загрузить PnL по гипотезам');
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };
        load();
        return () => {
            cancelled = true;
        };
    }, [normalizedFilters, refreshCounter]);

    const updateFilters = useCallback((patch: Partial<HypothesisPnlFilters>) => {
        setFilters((prev) => ({ ...prev, ...patch }));
    }, []);

    const resetFilters = useCallback(() => {
        setFilters(DEFAULT_FILTERS);
    }, []);

    const refresh = useCallback(() => {
        setRefreshCounter((value) => value + 1);
    }, []);

    return {
        filters: normalizedFilters,
        entries,
        loading,
        error,
        updateFilters,
        resetFilters,
        refresh,
    } as const;
}
