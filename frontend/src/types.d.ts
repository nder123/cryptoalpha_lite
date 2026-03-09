export interface MarketBucketEntry {
    score: number;
    rationale: string[];
    metrics: Record<string, number>;
    timestamp: string;
}
export interface TradeSessionRecord {
    session_id: string;
    symbol: string;
    direction: TradeDirection;
    mode: TradingMode;
    opened_at: string | null;
    closed_at: string | null;
    entry_price: number | null;
    entry_qty: number | null;
    exit_price: number | null;
    exit_qty: number | null;
    target_price: number | null;
    stop_price: number | null;
    pnl_usdt: number | null;
    pnl_pct: number | null;
    risk_reward_ratio: number | null;
    tp_hit: boolean;
    sl_hit: boolean;
    duration_seconds: number | null;
    entry_directive_id: string;
    exit_directive_id: string | null;
    comment: string | null;
}
export interface TradeStatsListResponse {
    items: TradeSessionRecord[];
    total: number;
}
export interface TradeStatsSummary {
    total_pnl_usdt: number | null;
    total_fees_usdt?: number | null;
    total_pnl_usdt_net?: number | null;
    avg_pnl_pct: number | null;
    total_trades: number;
    winning_trades: number;
    win_rate: number;
    avg_rr: number | null;
}
export interface TradeStatsPeriodEntry {
    period_start: string | null;
    pnl_usdt: number | null;
    fees_usdt?: number | null;
    pnl_usdt_net?: number | null;
    avg_pnl_pct: number | null;
    trades: number;
    avg_rr: number | null;
}
export interface TradeStatsSummaryBundle {
    summary: TradeStatsSummary;
    daily: TradeStatsPeriodEntry[];
    weekly: TradeStatsPeriodEntry[];
}
export interface ExchangeTradeEntry {
    exec_id: string;
    order_id: string | null;
    symbol: string;
    side: string | null;
    trade_type: string | null;
    price: number | null;
    quantity: number | null;
    fee: number | null;
    fee_currency: string | null;
    realized_pnl: number | null;
    trade_time: string | null;
}
export interface ExchangeTradeListResponse {
    total: number;
    items: ExchangeTradeEntry[];
}
export interface ExchangeTradeSummary {
    realized_pnl: number;
    fees: number;
    count: number;
}
export interface AccountTransactionEntry {
    transaction_id: string;
    reference_id: string | null;
    type: string;
    sub_type: string | null;
    amount: number | null;
    currency: string | null;
    fee: number | null;
    created_time: string | null;
}
export interface AccountTransactionListResponse {
    total: number;
    items: AccountTransactionEntry[];
}
export interface AccountTransactionSummary {
    amount: number;
    fees: number;
    count: number;
}
export interface EquitySnapshotEntry {
    captured_at: string | null;
    total_equity: number | null;
    wallet_balance: number | null;
    available_balance: number | null;
    currency: string | null;
}
export interface ReconciliationDelta {
    label: string;
    bybitValue: number | null;
    internalValue: number | null;
    delta: number | null;
    unit?: string;
}
export interface HypothesisPnlEntry {
    hypothesis_id: string;
    symbol: string | null;
    direction: TradeDirection | null;
    trades: number;
    total_pnl_usdt: number | null;
    avg_pnl_pct: number | null;
    last_closed_at: string | null;
}
export interface MarketBuckets {
    ignored: Record<string, MarketBucketEntry>;
    watch: Record<string, MarketBucketEntry>;
    candidate: Record<string, MarketBucketEntry>;
    active: Record<string, MarketBucketEntry>;
}
export interface StreamEventEntry<TData = Record<string, unknown>> {
    id: string;
    stream: string;
    event_type: string;
    timestamp: string | null;
    data: TData;
}
export type ExecutionStatus = 'submitted' | 'partially_filled' | 'filled' | 'cancelled' | 'failed' | 'rejected';
export interface ExecutionReportEventData {
    directive_id: string;
    symbol: string;
    status: ExecutionStatus;
    quantity: number;
    avg_price: number | null;
    fees_paid: number | null;
    reported_at: string;
    notes: string[];
}
export interface CTOAiDecisionEventData {
    decision_uid: string;
    directive_id: string;
    symbol: string;
    issued_at: string;
    action: TradeAction;
    size: number;
    notional_usdt: number;
    source: 'fsm' | 'operator' | 'position_manager';
    meta: Record<string, unknown>;
    directive: TradeDirective;
}
export interface RiskAssessmentEventData {
    assessment_id: string;
    hypothesis_id: string;
    symbol: string;
    evaluated_at: string;
    decision: 'approved' | 'blocked';
    blockers: string[];
    risk_metrics: Record<string, number>;
}
export interface TradeHypothesisEventData {
    hypothesis_id: string;
    symbol: string;
    created_at: string;
    hypothesis_type: string;
    confidence: number;
    direction: TradeDirection;
    entry_price: number;
    target_price: number;
    stop_price: number;
    position_size: number;
    leverage: number;
    notional_usdt: number;
    supporting_metrics: Record<string, number>;
    notes: string[];
}
export type PositionEventType = 'open_tracked' | 'open_updated' | 'close_requested' | 'close_confirmed' | 'close_partial' | 'price_fetch_failed' | 'force_close_timeout' | 'error';
export interface PositionEventData {
    event: PositionEventType;
    directive_id: string;
    symbol: string;
    direction: TradeDirection;
    created_at: string;
    quantity?: number | null;
    price?: number | null;
    reason?: string | null;
    status?: string | null;
    origin_directive_id?: string | null;
    notes: string[];
}
export type ExecutionStreamEntry = StreamEventEntry<ExecutionReportEventData>;
export type DecisionStreamEntry = StreamEventEntry<CTOAiDecisionEventData>;
export type RiskStreamEntry = StreamEventEntry<RiskAssessmentEventData>;
export type HypothesisStreamEntry = StreamEventEntry<TradeHypothesisEventData>;
export type PositionStreamEntry = StreamEventEntry<PositionEventData>;
export interface ServiceHealthEntry {
    status: string;
    updated_at?: string | null;
    message?: string | null;
    error?: string | null;
    [key: string]: unknown;
}
export type ServiceHealthMap = Record<string, ServiceHealthEntry>;
export type TradeDirection = 'long' | 'short';
export type TradeAction = 'open' | 'close' | 'hold' | 'reject' | 'no_trade';
export type TradingMode = 'manual' | 'semi_auto' | 'full_auto';
export type OrderType = 'market' | 'limit';
export type TimeInForce = 'GTC' | 'IOC' | 'FOK';
export interface TradeStatsOverviewSummary {
    total_pnl_usdt: number | null;
    total_fees_usdt?: number | null;
    total_pnl_usdt_net?: number | null;
    avg_pnl_pct: number | null;
    total_trades: number;
    winning_trades: number;
    win_rate: number;
    avg_rr: number | null;
}
export interface TradeStatsOverviewEntry {
    session_id: string;
    symbol: string;
    direction: TradeDirection;
    opened_at: string | null;
    closed_at: string | null;
    pnl_usdt: number | null;
    fees_usdt?: number | null;
    pnl_usdt_net?: number | null;
    pnl_pct: number | null;
    duration_seconds: number | null;
    entry_directive_id: string | null;
    exit_directive_id: string | null;
}
export interface TradeStatsOverview {
    summary: TradeStatsOverviewSummary | null;
    recent: TradeStatsOverviewEntry[];
    last_trade: TradeStatsOverviewEntry | null;
    updated_at: string | null;
}
export interface RuntimeConfig {
    market_scan_interval_seconds: number;
    research_refresh_interval_seconds: number;
    research_max_hypotheses_per_minute: number;
    funding_threshold: number;
    volatility_threshold: number;
    max_candidate_symbols: number;
    max_portfolio_exposure_usdt: number;
    max_symbol_allocation_pct: number;
    max_leverage: number;
    min_confidence_threshold: number;
    default_stop_loss_pct: number;
    default_take_profit_pct: number;
    execution_retry_attempts: number;
    execution_retry_backoff_seconds: number;
    execution_degraded_threshold: number;
    execution_degraded_cooldown_seconds: number;
    position_manager_poll_interval_seconds: number;
    position_manager_force_close_minutes: number;
    position_manager_use_market_exit: boolean;
    position_manager_limit_exit_timeout_seconds: number;
    symbol_denylist: string[];
    auto_exposure_enabled: boolean;
    auto_exposure_portfolio_pct: number;
    auto_symbol_allocation_pct: number;
    auto_research_enabled: boolean;
    auto_research_interval_minutes: number;
    auto_research_batch_size: number;
    dry_run: boolean;
    rl_enabled: boolean;
    rl_policy_min_confidence: number;
    rl_retrain_interval_hours: number;
    rl_experience_window_days: number;
    updated_at: string | null;
    max_trades_per_day: number;
    max_daily_loss_usdt: number;
    max_consecutive_losses: number;
}
export type RuntimeConfigUpdatePayload = Partial<Omit<RuntimeConfig, 'updated_at'>>;
export interface TradeDirective {
    directive_id: string;
    hypothesis_id: string | null;
    symbol: string;
    issued_at: string;
    action: TradeAction;
    rationale: string[];
    mode: TradingMode;
    confidence: number;
    direction: TradeDirection;
    order_type: OrderType;
    quantity: number;
    price: number | null;
    time_in_force: TimeInForce;
    leverage: number;
    reduce_only: boolean;
    notional_usdt: number;
    expires_at: string | null;
    take_profit_price: number | null;
    stop_loss_price: number | null;
}
export interface ManualDirectivePayload {
    symbol: string;
    direction: TradeDirection;
    action: 'open' | 'close';
    order_type: OrderType;
    quantity: number;
    price?: number | null;
    time_in_force: TimeInForce;
    take_profit_price?: number | null;
    stop_loss_price?: number | null;
    reduce_only?: boolean;
    leverage?: number;
    confidence?: number;
    expires_in_minutes?: number;
}
export interface PositionEntry {
    symbol: string;
    side: string;
    size: number;
    entry_price: number | null;
    mark_price: number | null;
    notional_usdt: number | null;
    leverage: number | null;
    unrealized_pnl: number | null;
    unrealized_pnl_pct: number | null;
    liquidation_price: number | null;
    take_profit: number | null;
    stop_loss: number | null;
    updated_at: string | null;
}
export interface RejectionEntry {
    hypothesis_id: string;
    symbol: string;
    created_at: string;
    reasons: string[];
}
export interface CTOAISnapshot {
    mode: TradingMode;
    state: string;
    confidence: number;
    active_directives: string[];
}
export interface RiskBudget {
    portfolio_limit: number | null;
    total_equity: number | null;
    available_equity: number | null;
    symbol_limits: Record<string, number>;
    volatility_index?: number | null;
    volatility_factor?: number | null;
    equity_guard_state?: 'normal' | 'caution' | 'halt';
    equity_drawdown_pct?: number | null;
    volatility_state?: 'calm' | 'choppy' | 'elevated' | 'turbulent';
    updated_at?: string | null;
}
export interface DashboardState {
    market: MarketBuckets;
    ctoai: CTOAISnapshot;
    directives: TradeDirective[];
    rejections: RejectionEntry[];
    positions?: PositionEntry[];
    config?: RuntimeConfig;
    events?: AuditEvent[];
    services?: ServiceHealthMap;
    risk_budget?: RiskBudget;
    trade_stats?: TradeStatsOverview;
}
export interface RLExperienceSample {
    directive_id: string;
    symbol: string;
    action: string;
    timestamp: string | null;
    reward: number | null;
    value: number | null;
}
export interface RLMetrics {
    timestamp: string | null;
    total_trades: number | null;
    win_rate: number | null;
    sharpe_ratio: number | null;
    max_drawdown: number | null;
    losses_last_window: number | null;
    last_trade_pnl_pct: number | null;
    last_trade_reward: number | null;
}
export interface RLPolicySummary {
    version: string | null;
    architecture: string | null;
    threshold: number | null;
    input_size: number | null;
    hidden_size: number | null;
    action_size: number | null;
}
export interface ClosedTradeSummary {
    total_pnl_usdt: number | null;
    avg_pnl_pct: number | null;
    total_trades: number;
    winning_trades: number;
    win_rate: number;
    avg_rr: number | null;
}
export interface ClosedTradeEntry {
    session_id: string;
    symbol: string;
    direction: string;
    opened_at: string | null;
    closed_at: string | null;
    pnl_usdt: number | null;
    pnl_pct: number | null;
    duration_seconds: number | null;
    entry_directive_id?: string | null;
    exit_directive_id?: string | null;
}
export interface RLStatusResponse {
    experience_count: number;
    experience_oldest: RLExperienceSample | null;
    experience_latest: RLExperienceSample | null;
    latest_metrics: RLMetrics | null;
    policy: RLPolicySummary | null;
    closed_summary: ClosedTradeSummary | null;
    recent_closed: ClosedTradeEntry[];
    force_queue_size: number;
    buffer_ready: boolean;
    min_batch_required: number;
    last_trained_at: string | null;
    next_eligible_at: string | null;
}
export interface AuditEvent {
    id: number;
    stream: string;
    event_type: string;
    payload: Record<string, unknown>;
    created_at: string | null;
}
export interface DashboardApiBundle {
    overview: MarketBuckets;
    ctoai: CTOAISnapshot;
    directives: TradeDirective[];
    rejections: RejectionEntry[];
    events: AuditEvent[];
    config: RuntimeConfig;
}
