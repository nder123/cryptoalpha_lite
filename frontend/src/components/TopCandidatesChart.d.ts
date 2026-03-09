import type { MarketBucketEntry } from '../types';
type Props = {
    data: Record<string, MarketBucketEntry>;
};
declare function TopCandidatesChartComponent({ data }: Props): import("react/jsx-runtime").JSX.Element;
export declare const TopCandidatesChart: import("react").MemoExoticComponent<typeof TopCandidatesChartComponent>;
export {};
