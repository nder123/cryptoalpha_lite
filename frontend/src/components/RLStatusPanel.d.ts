import type { RLStatusResponse } from '../types';
interface RLStatusPanelProps {
    status: RLStatusResponse | null;
    loading: boolean;
    onRefresh: () => void;
}
export declare function RLStatusPanel({ status, loading, onRefresh }: RLStatusPanelProps): import("react/jsx-runtime").JSX.Element;
export {};
