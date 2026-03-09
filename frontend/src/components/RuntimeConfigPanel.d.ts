import type { RuntimeConfig, RuntimeConfigUpdatePayload } from '../types';
type Props = {
    config: RuntimeConfig | null;
    saving: boolean;
    onSubmit: (payload: RuntimeConfigUpdatePayload) => Promise<void>;
};
export declare function RuntimeConfigPanel({ config, saving, onSubmit }: Props): import("react/jsx-runtime").JSX.Element;
export {};
