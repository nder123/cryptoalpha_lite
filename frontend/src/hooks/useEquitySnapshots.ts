import { useCallback, useEffect, useMemo, useState } from 'react';

import { fetchEquitySnapshots, fetchLatestEquitySnapshot } from '../api';
import type { EquitySnapshotEntry } from '../types';

type EquityFilters = {
    start: string | null;
    end: string | null;
    limit: number;
};

const DEFAULT_FILTERS: EquityFilters = {
    start: null,
    end: null,
    limit: 200,
};

export function useEquitySnapshots() {
    const [filters, setFilters] = useState<EquityFilters>(DEFAULT_FILTERS);
    const [snapshots, setSnapshots] = useState<EquitySnapshotEntry[]>([]);
    const [latest, setLatest] = useState<EquitySnapshotEntry | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshCounter, setRefreshCounter] = useState(0);

    const normalizedFilters = useMemo(() => ({
        start: filters.start ?? undefined,
        end: filters.end ?? undefined,
        limit: filters.limit,
    }), [filters]);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const [history, current] = await Promise.all([
                    fetchEquitySnapshots(normalizedFilters),
                    fetchLatestEquitySnapshot(),
                ]);
                if (cancelled) return;
                setSnapshots(history);
                setLatest(current ?? null);
            } catch (err) {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : 'Не удалось загрузить equity Bybit');
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        load();
        return () => {
            cancelled = true;
        };
    }, [normalizedFilters, refreshCounter]);

    const updateFilters = useCallback((patch: Partial<EquityFilters>) => {
        setFilters((prev) => ({ ...prev, ...patch }));
    }, []);

    const resetFilters = useCallback(() => {
        setFilters(DEFAULT_FILTERS);
    }, []);

    const refresh = useCallback(() => {
        setRefreshCounter((value) => value + 1);
    }, []);

    const latestEquity = latest?.total_equity ?? null;
    const latestAvailable = latest?.available_balance ?? null;

    const averageEquity = useMemo(() => {
        if (!snapshots.length) return null;
        const sum = snapshots.reduce((acc, entry) => acc + (entry.total_equity ?? 0), 0);
        return sum / snapshots.length;
    }, [snapshots]);

    return {
        filters,
        snapshots,
        latest,
        latestEquity,
        latestAvailable,
        averageEquity,
        loading,
        error,
        updateFilters,
        resetFilters,
        refresh,
    } as const;
}
