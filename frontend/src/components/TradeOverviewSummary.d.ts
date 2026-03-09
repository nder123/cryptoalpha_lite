import type { PositionEntry, TradeStatsOverview } from '../types';
interface Props {
    tradeStats: TradeStatsOverview | null;
    positions: PositionEntry[];
}
export declare function TradeOverviewSummary({ tradeStats, positions }: Props): import("react/jsx-runtime").JSX.Element;
export {};
