import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchRLStatus } from '../api';
import type { RLStatusResponse } from '../types';

const REFRESH_INTERVAL_MS = 30_000;

export function useRLStatus() {
    const [status, setStatus] = useState<RLStatusResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const intervalRef = useRef<number | undefined>();

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetchRLStatus();
            setStatus(response);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Не удалось получить статус RL');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        intervalRef.current = window.setInterval(load, REFRESH_INTERVAL_MS);
        return () => {
            if (intervalRef.current) {
                window.clearInterval(intervalRef.current);
                intervalRef.current = undefined;
            }
        };
    }, [load]);

    const refresh = useCallback(() => {
        if (!loading) {
            void load();
        }
    }, [load, loading]);

    return { status, loading, error, refresh };
}
