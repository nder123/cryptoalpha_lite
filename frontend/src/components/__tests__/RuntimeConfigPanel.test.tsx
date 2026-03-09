import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockedFunction } from 'vitest';

import type { RuntimeConfig, RuntimeConfigUpdatePayload } from '../../types';
import { RuntimeConfigPanel } from '../RuntimeConfigPanel';

const baseConfig: RuntimeConfig = {
    market_scan_interval_seconds: 10,
    research_refresh_interval_seconds: 30,
    research_max_hypotheses_per_minute: 60,
    funding_threshold: 0.005,
    volatility_threshold: 0.02,
    max_candidate_symbols: 25,
    max_portfolio_exposure_usdt: 1000,
    max_symbol_allocation_pct: 0.1,
    max_leverage: 3,
    min_confidence_threshold: 0.5,
    default_stop_loss_pct: 0.1,
    default_take_profit_pct: 0.2,
    execution_retry_attempts: 3,
    execution_retry_backoff_seconds: 1,
    execution_degraded_threshold: 5,
    execution_degraded_cooldown_seconds: 120,
    position_manager_poll_interval_seconds: 5,
    position_manager_force_close_minutes: 180,
    position_manager_use_market_exit: true,
    position_manager_limit_exit_timeout_seconds: 20,
    symbol_denylist: [],
    auto_exposure_enabled: false,
    auto_exposure_portfolio_pct: 0.1,
    auto_symbol_allocation_pct: 0.1,
    auto_research_enabled: true,
    auto_research_interval_minutes: 5,
    auto_research_batch_size: 5,
    dry_run: false,
    rl_enabled: true,
    rl_policy_min_confidence: 0.65,
    rl_retrain_interval_hours: 6,
    rl_experience_window_days: 30,
    max_trades_per_day: 50,
    max_daily_loss_usdt: 50,
    max_consecutive_losses: 10,
    updated_at: new Date('2024-01-01T12:00:00Z').toISOString(),
};

describe('RuntimeConfigPanel', () => {
    let onSubmit: MockedFunction<(payload: RuntimeConfigUpdatePayload) => Promise<void>>;

    beforeEach(() => {
        onSubmit = vi.fn(async (_payload: RuntimeConfigUpdatePayload) => undefined) as MockedFunction<
            (payload: RuntimeConfigUpdatePayload) => Promise<void>
        >;
    });

    it('renders loading state without config', () => {
        render(<RuntimeConfigPanel config={null} saving={false} onSubmit={onSubmit} />);
        expect(screen.getByText('Загрузка текущих настроек…')).toBeInTheDocument();
    });

    it('disables submit when nothing changed', () => {
        render(<RuntimeConfigPanel config={baseConfig} saving={false} onSubmit={onSubmit} />);
        const submit = screen.getByRole('button', { name: 'Сохранить' });
        expect(submit).toBeDisabled();
    });

    it('toggles auto research and submits payload', async () => {
        render(<RuntimeConfigPanel config={baseConfig} saving={false} onSubmit={onSubmit} />);

        const toggle = screen.getByRole('button', { name: 'Переключить auto-research' }) as HTMLButtonElement;
        fireEvent.click(toggle);

        const submit = screen.getByRole('button', { name: 'Сохранить' });
        expect(submit).not.toBeDisabled();

        fireEvent.submit(submit.closest('form') as HTMLFormElement);

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalledWith({ auto_research_enabled: false });
        });
    });

    it('updates numeric field and sends diff', async () => {
        render(<RuntimeConfigPanel config={baseConfig} saving={false} onSubmit={onSubmit} />);

        const intervalInput = screen.getByLabelText(/Auto-research: интервал/i);
        fireEvent.change(intervalInput, { target: { value: '8' } });

        const batchInput = screen.getByLabelText(/Auto-research: размер батча/i);
        fireEvent.change(batchInput, { target: { value: '7' } });

        const submit = screen.getByRole('button', { name: 'Сохранить' });
        expect(submit).not.toBeDisabled();
        fireEvent.submit(submit.closest('form') as HTMLFormElement);

        await waitFor(() => {
            expect(onSubmit).toHaveBeenCalled();
        });

        const calls = onSubmit.mock.calls;
        const payload = calls.length ? calls[calls.length - 1][0] : undefined;
        expect(payload).toMatchObject({
            auto_research_interval_minutes: 8,
            auto_research_batch_size: 7,
        });
    });

    it('resets form to original values', async () => {
        render(<RuntimeConfigPanel config={baseConfig} saving={false} onSubmit={onSubmit} />);

        const toggle = screen.getByRole('button', { name: 'Переключить auto-research' }) as HTMLButtonElement;
        fireEvent.click(toggle);

        const reset = screen.getByRole('button', { name: 'Сбросить' });
        fireEvent.click(reset);

        const submit = screen.getByRole('button', { name: 'Сохранить' });
        expect(submit).toBeDisabled();
    });
});
