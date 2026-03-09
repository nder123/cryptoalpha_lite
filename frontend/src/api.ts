import type {
    AccountTransactionListResponse,
    AccountTransactionSummary,
    AuditEvent,
    CTOAISnapshot,
    DashboardApiBundle,
    DashboardState,
    DecisionStreamEntry,
    EquitySnapshotEntry,
    ExchangeTradeListResponse,
    ExchangeTradeSummary,
    ExecutionStreamEntry,
    HypothesisStreamEntry,
    HypothesisPnlEntry,
    ManualDirectivePayload,
    MarketBuckets,
    PositionEntry,
    PositionStreamEntry,
    RejectionEntry,
    RiskBudget,
    RiskStreamEntry,
    RLStatusResponse,
    RuntimeConfig,
    RuntimeConfigUpdatePayload,
    ServiceHealthMap,
    TradeDirective,
    TradeSessionRecord,
    TradeStatsListResponse,
    TradeStatsSummaryBundle,
    TradingMode,
    TradeStatsOverview,
} from './types';

const API_BASE = '/api';

async function get<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, init);
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.json() as Promise<T>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, init);
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | number | undefined | null>) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            query.set(key, String(value));
        }
    });
    const result = query.toString();
    return result ? `?${result}` : '';
}

export function fetchDashboardSnapshot() {
    return Promise.all([
        get<MarketBuckets>('/market/overview'),
        get<CTOAISnapshot>('/ctoai/state'),
        get<TradeDirective[]>('/ctoai/directives'),
        get<RejectionEntry[]>('/ctoai/rejections'),
        get<PositionEntry[]>('/exchange/positions'),
        get<AuditEvent[]>('/audit/events?limit=100'),
        get<RuntimeConfig>('/config/runtime'),
        get<ServiceHealthMap>('/services/health'),
        get<RiskBudget>('/config/risk-budget'),
        get<TradeStatsOverview>('/stats/trades/dashboard'),
    ]).then(([market, ctoai, directives, rejections, positions, events, config, services, riskBudget, tradeStats]) => ({
        market,
        ctoai,
        directives,
        rejections,
        positions,
        events,
        config,
        services,
        riskBudget,
        tradeStats,
    }));
}

export function fetchHypothesisPnl({ limit = 50 }: { limit?: number } = {}) {
    const query = buildQuery({ limit });
    return get<HypothesisPnlEntry[]>(`/stats/hypotheses/pnl${query}`);
}

export function createDashboardSocket(onMessage: (state: DashboardState) => void) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.port === '5173' ? `${window.location.hostname}:8000` : window.location.host;
    const ws = new WebSocket(`${protocol}//${wsHost}/ws/dashboard`);

    let pingTimer: number | null = null;
    ws.onopen = () => {
        // Backend keeps the connection alive by awaiting receive_text(), so we periodically send a ping.
        pingTimer = window.setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 15000);
    };
    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data) as DashboardState;
            onMessage(payload);
        } catch (error) {
            console.error('Failed to parse dashboard update', error);
        }
    };

    ws.onerror = () => {
        // In dev (React.StrictMode) the socket may be opened/closed quickly; avoid noisy errors.
    };
    ws.onclose = () => {
        if (pingTimer) {
            window.clearInterval(pingTimer);
            pingTimer = null;
        }
    };
    return ws;
}

export async function updateMode(mode: TradingMode) {
    return request('/ctoai/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
    });
}

export async function triggerEmergencyStop() {
    return request('/ctoai/emergency-stop', {
        method: 'POST',
    });
}

export async function clearRejections() {
    return request<{ cleared: number }>('/ctoai/rejections/clear', {
        method: 'POST',
    });
}

export function fetchRuntimeConfig() {
    return get<RuntimeConfig>('/config/runtime');
}

export function fetchServiceHealth() {
    return get<ServiceHealthMap>('/services/health');
}

export async function patchRuntimeConfig(payload: RuntimeConfigUpdatePayload) {
    return request<RuntimeConfig>('/config/runtime', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export async function submitManualDirective(payload: ManualDirectivePayload) {
    return request<TradeDirective>('/ctoai/manual-directive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export function fetchRLStatus() {
    return get<RLStatusResponse>('/rl/status');
}

export function fetchTradeStats({
    start,
    end,
    symbol,
    limit = 50,
    offset = 0,
}: {
    start?: string | null;
    end?: string | null;
    symbol?: string | null;
    limit?: number;
    offset?: number;
}) {
    const query = buildQuery({ start, end, symbol, limit, offset });
    return get<TradeStatsListResponse>(`/stats/trades${query}`);
}

export function fetchTradeStatsSummary({
    start,
    end,
}: {
    start?: string | null;
    end?: string | null;
}) {
    const query = buildQuery({ start, end });
    return get<TradeStatsSummaryBundle>(`/stats/trades/summary${query}`);
}

export async function exportTradeStats({
    start,
    end,
    symbol,
}: {
    start?: string | null;
    end?: string | null;
    symbol?: string | null;
}) {
    const query = buildQuery({ start, end, symbol });
    const response = await fetch(`${API_BASE}/stats/trades/export${query}`);
    if (!response.ok) {
        throw new Error(`Export failed: ${response.status}`);
    }
    return response.blob();
}

export function fetchExchangeTrades({
    start,
    end,
    symbol,
    limit = 100,
    offset = 0,
}: {
    start?: string | null;
    end?: string | null;
    symbol?: string | null;
    limit?: number;
    offset?: number;
}) {
    const query = buildQuery({ start, end, symbol, limit, offset });
    return get<ExchangeTradeListResponse>(`/exchange/trades${query}`);
}

export function fetchExchangeTradeSummary({
    start,
    end,
    symbol,
}: {
    start?: string | null;
    end?: string | null;
    symbol?: string | null;
}) {
    const query = buildQuery({ start, end, symbol });
    return get<ExchangeTradeSummary>(`/exchange/trades/summary${query}`);
}

export function fetchAccountTransactions({
    start,
    end,
    txType,
    limit = 100,
    offset = 0,
}: {
    start?: string | null;
    end?: string | null;
    txType?: string | null;
    limit?: number;
    offset?: number;
}) {
    const query = buildQuery({ start, end, tx_type: txType, limit, offset });
    return get<AccountTransactionListResponse>(`/exchange/transactions${query}`);
}

export function fetchAccountTransactionSummary({
    start,
    end,
    txType,
}: {
    start?: string | null;
    end?: string | null;
    txType?: string | null;
}) {
    const query = buildQuery({ start, end, tx_type: txType });
    return get<AccountTransactionSummary>(`/exchange/transactions/summary${query}`);
}

export function fetchEquitySnapshots({
    start,
    end,
    limit = 200,
}: {
    start?: string | null;
    end?: string | null;
    limit?: number;
}) {
    const query = buildQuery({ start, end, limit });
    return get<EquitySnapshotEntry[]>(`/exchange/equity${query}`);
}

export function fetchLatestEquitySnapshot() {
    return get<EquitySnapshotEntry | null>('/exchange/equity/latest');
}

export function fetchExecutionStream({
    limit = 40,
    afterId,
}: {
    limit?: number;
    afterId?: string;
} = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get<ExecutionStreamEntry[]>(`/streams/execution${query}`);
}

export function fetchDecisionStream({
    limit = 40,
    afterId,
}: {
    limit?: number;
    afterId?: string;
} = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get<DecisionStreamEntry[]>(`/streams/decisions${query}`);
}

export function fetchRiskStream({
    limit = 40,
    afterId,
}: {
    limit?: number;
    afterId?: string;
} = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get<RiskStreamEntry[]>(`/streams/risk${query}`);
}

export function fetchHypothesisStream({
    limit = 40,
    afterId,
}: {
    limit?: number;
    afterId?: string;
} = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get<HypothesisStreamEntry[]>(`/streams/hypotheses${query}`);
}

export function fetchPositionStream({
    limit = 40,
    afterId,
}: {
    limit?: number;
    afterId?: string;
} = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get<PositionStreamEntry[]>(`/streams/positions${query}`);
}
