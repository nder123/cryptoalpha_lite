import type { TradingMode } from '../types';
type Props = {
    mode: TradingMode;
    onChange: (mode: TradingMode) => Promise<void>;
};
export declare function ModeSwitch({ mode, onChange }: Props): import("react/jsx-runtime").JSX.Element;
export {};
