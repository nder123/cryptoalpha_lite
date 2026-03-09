import type { RLStatusResponse } from '../types';
export declare function useRLStatus(): {
    status: RLStatusResponse;
    loading: boolean;
    error: string;
    refresh: () => void;
};
