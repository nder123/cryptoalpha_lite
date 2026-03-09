const API_BASE = '/api';
async function get(path, init) {
    const response = await fetch(`${API_BASE}${path}`, init);
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
}
async function request(path, init) {
    const response = await fetch(`${API_BASE}${path}`, init);
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
}
function buildQuery(params) {
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
        get('/market/overview'),
        get('/ctoai/state'),
        get('/ctoai/directives'),
        get('/ctoai/rejections'),
        get('/exchange/positions'),
        get('/audit/events?limit=100'),
        get('/config/runtime'),
        get('/services/health'),
        get('/config/risk-budget'),
        get('/stats/trades/dashboard'),
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
export function fetchHypothesisPnl({ limit = 50 } = {}) {
    const query = buildQuery({ limit });
    return get(`/stats/hypotheses/pnl${query}`);
}
export function createDashboardSocket(onMessage) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.port === '5173' ? `${window.location.hostname}:8000` : window.location.host;
    const ws = new WebSocket(`${protocol}//${wsHost}/ws/dashboard`);

    let pingTimer = null;
    ws.onopen = () => {
        pingTimer = window.setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 15000);
    };
    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            onMessage(payload);
        }
        catch (error) {
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
export async function updateMode(mode) {
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
    return request('/ctoai/rejections/clear', {
        method: 'POST',
    });
}
export function fetchRuntimeConfig() {
    return get('/config/runtime');
}
export function fetchServiceHealth() {
    return get('/services/health');
}
export async function patchRuntimeConfig(payload) {
    return request('/config/runtime', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}
export async function submitManualDirective(payload) {
    return request('/ctoai/manual-directive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}
export function fetchRLStatus() {
    return get('/rl/status');
}
export function fetchTradeStats({ start, end, symbol, limit = 50, offset = 0, }) {
    const query = buildQuery({ start, end, symbol, limit, offset });
    return get(`/stats/trades${query}`);
}
export function fetchTradeStatsSummary({ start, end, }) {
    const query = buildQuery({ start, end });
    return get(`/stats/trades/summary${query}`);
}
export async function exportTradeStats({ start, end, symbol, }) {
    const query = buildQuery({ start, end, symbol });
    const response = await fetch(`${API_BASE}/stats/trades/export${query}`);
    if (!response.ok) {
        throw new Error(`Export failed: ${response.status}`);
    }
    return response.blob();
}
export function fetchExchangeTrades({ start, end, symbol, limit = 100, offset = 0, }) {
    const query = buildQuery({ start, end, symbol, limit, offset });
    return get(`/exchange/trades${query}`);
}
export function fetchExchangeTradeSummary({ start, end, symbol, }) {
    const query = buildQuery({ start, end, symbol });
    return get(`/exchange/trades/summary${query}`);
}
export function fetchAccountTransactions({ start, end, txType, limit = 100, offset = 0, }) {
    const query = buildQuery({ start, end, tx_type: txType, limit, offset });
    return get(`/exchange/transactions${query}`);
}
export function fetchAccountTransactionSummary({ start, end, txType, }) {
    const query = buildQuery({ start, end, tx_type: txType });
    return get(`/exchange/transactions/summary${query}`);
}
export function fetchEquitySnapshots({ start, end, limit = 200, }) {
    const query = buildQuery({ start, end, limit });
    return get(`/exchange/equity${query}`);
}
export function fetchLatestEquitySnapshot() {
    return get('/exchange/equity/latest');
}
export function fetchExecutionStream({ limit = 40, afterId, } = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get(`/streams/execution${query}`);
}
export function fetchDecisionStream({ limit = 40, afterId, } = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get(`/streams/decisions${query}`);
}
export function fetchRiskStream({ limit = 40, afterId, } = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get(`/streams/risk${query}`);
}
export function fetchHypothesisStream({ limit = 40, afterId, } = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get(`/streams/hypotheses${query}`);
}
export function fetchPositionStream({ limit = 40, afterId, } = {}) {
    const query = buildQuery({ limit, after_id: afterId });
    return get(`/streams/positions${query}`);
}
