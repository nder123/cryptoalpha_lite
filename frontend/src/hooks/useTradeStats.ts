import { useCallback, useEffect, useMemo, useState } from 'react';

import { exportTradeStats, fetchTradeStats, fetchTradeStatsSummary } from '../api';
import type {
    TradeSessionRecord,
    TradeStatsListResponse,
    TradeStatsSummary,
    TradeStatsSummaryBundle,
} from '../types';

type TradeStatsFilters = {
    start: string | null;
    end: string | null;
    symbol: string;
};

const DEFAULT_FILTERS: TradeStatsFilters = {
    start: null,
    end: null,
    symbol: '',
};

export function useTradeStats(limit: number = 50) {
    const [filters, setFilters] = useState<TradeStatsFilters>(DEFAULT_FILTERS);
    const [records, setRecords] = useState<TradeSessionRecord[]>([]);
    const [total, setTotal] = useState(0);
    const [summary, setSummary] = useState<TradeStatsSummary | null>(null);
    const [daily, setDaily] = useState<TradeStatsSummaryBundle['daily']>([]);
    const [weekly, setWeekly] = useState<TradeStatsSummaryBundle['weekly']>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshCounter, setRefreshCounter] = useState(0);
    const [exporting, setExporting] = useState(false);

    const normalizedFilters = useMemo(() => {
        const trimmedSymbol = filters.symbol.trim();
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
                    fetchTradeStats({
                        start: normalizedFilters.start,
                        end: normalizedFilters.end,
                        symbol: normalizedFilters.symbol,
                        limit,
                        offset: 0,
                    }),
                    fetchTradeStatsSummary({
                        start: normalizedFilters.start,
                        end: normalizedFilters.end,
                    }),
                ]);
                if (cancelled) return;
                updateFromList(listResponse);
                updateFromSummary(summaryResponse);
            } catch (err) {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : 'Не удалось загрузить статистику');
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        const updateFromList = (response: TradeStatsListResponse) => {
            setRecords(response.items);
            setTotal(response.total);
        };

        const updateFromSummary = (bundle: TradeStatsSummaryBundle) => {
            setSummary(bundle.summary);
            setDaily(bundle.daily);
            setWeekly(bundle.weekly);
        };

        load();
        return () => {
            cancelled = true;
        };
    }, [limit, normalizedFilters, refreshCounter]);

    const refresh = useCallback(() => {
        setRefreshCounter((value) => value + 1);
    }, []);

    const updateFilters = useCallback((patch: Partial<TradeStatsFilters>) => {
        setFilters((prev) => ({ ...prev, ...patch }));
    }, []);

    const resetFilters = useCallback(() => {
        setFilters(DEFAULT_FILTERS);
    }, []);

    const exportCsv = useCallback(async () => {
        setExporting(true);
        try {
            const blob = await exportTradeStats({
                start: normalizedFilters.start,
                end: normalizedFilters.end,
                symbol: normalizedFilters.symbol,
            });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            a.download = `trade-stats_${timestamp}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } finally {
            setExporting(false);
        }
    }, [normalizedFilters]);

    return {
        filters,
        records,
        total,
        summary,
        daily,
        weekly,
        loading,
        error,
        updateFilters,
        resetFilters,
        refresh,
        exportCsv,
        exporting,
    };
}
