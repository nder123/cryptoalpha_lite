import { jsx as _jsx } from "react/jsx-runtime";
import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AutoResearchIndicator } from '../AutoResearchIndicator';
const baseEntry = {
    status: 'active',
    updated_at: new Date('2024-01-01T12:00:00Z').toISOString(),
    backlog: 12,
    dispatched: 4,
};
afterEach(() => {
    vi.useRealTimers();
});
describe('AutoResearchIndicator', () => {
    it('renders nothing when entry is undefined', () => {
        const { container } = render(_jsx(AutoResearchIndicator, { entry: undefined }));
        expect(container).toBeEmptyDOMElement();
    });
    it('renders collapsed summary with status badge', () => {
        render(_jsx(AutoResearchIndicator, { entry: baseEntry }));
        expect(screen.getByText('Auto-Research')).toBeInTheDocument();
        expect(screen.getByText('active')).toBeInTheDocument();
        const helperText = screen.queryByText(/Переиздаёт кандидатов/);
        expect(helperText).not.toBeInTheDocument();
    });
    it('expands to show metrics when clicked', () => {
        render(_jsx(AutoResearchIndicator, { entry: baseEntry }));
        const toggle = screen.getByRole('button', { name: /Auto-Research/i });
        fireEvent.click(toggle);
        expect(screen.getByText('Размер бэклога')).toBeInTheDocument();
        expect(screen.getByText('12')).toBeInTheDocument();
        expect(screen.getByText('Отправлено в этом цикле')).toBeInTheDocument();
    });
    it('shows helper and error messages when provided', () => {
        render(_jsx(AutoResearchIndicator, { entry: {
                ...baseEntry,
                status: 'paused',
                message: 'disabled via runtime config',
                error: 'redis timeout',
            } }));
        const toggle = screen.getByRole('button', { name: /Auto-Research/i });
        fireEvent.click(toggle);
        expect(screen.getByText('disabled via runtime config')).toBeInTheDocument();
        expect(screen.getByText('redis timeout')).toBeInTheDocument();
    });
    it('auto expands errors without user interaction', () => {
        render(_jsx(AutoResearchIndicator, { entry: {
                ...baseEntry,
                status: 'error',
                error: 'bus failure',
            } }));
        expect(screen.getByText('bus failure')).toBeInTheDocument();
    });
});
