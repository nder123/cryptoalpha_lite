# CTO-AI Autonomous Futures Trading Platform

## 1. Mission Overview
CTO-AI is the single decision authority coordinating an intentionally conservative
Bybit USDT-M futures trading platform. The system continuously monitors the full
market, researches a narrow subset of symbols, performs multi-stage risk review,
and executes only trades explicitly approved by CTO-AI. All actions, rejections,
and inactions are fully observable through a real-time Web Dashboard that is the
sole control surface for operators.

## 2. Guiding Principles
- **Single Authority:** CTO-AI approves or rejects every state transition that
  may result in account exposure. No other component can issue trade commands.
- **Explainability:** Every report, hypothesis, decision, and execution produces
a structured log and is persisted for audit.
- **Intentional Trading:** The default posture is *NO TRADE*. Ignoring the
  market is a first-class outcome. Trade frequency is controlled by explicit
  confidence thresholds and operator-selectable modes.
- **Safety First:** Risk limits are enforced in layered defenses (symbol-level,
  portfolio-level, and operational) with an emergency stop wired into the
  infrastructure and UI.
- **Modularity:** The system is built as a set of asynchronous, event-driven
  services communicating via a typed, auditable message bus.

## 3. High-Level Architecture
```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Web Dashboard                               │
│ React + TypeScript SPA                                                   │
│ • Global market overview        • Symbol narratives                      │
│ • CTO-AI status & controls      • Trade lifecycle audit                  │
│ • Manual mode switch            • Emergency stop                         │
└──────────────▲──────────────────────────────────────────────────────────┘
               │ WebSocket/REST
┌──────────────┴──────────────────────────────────────────────────────────┐
│                             FastAPI Backend                             │
│                                                                          │
│ ┌──────────────┐   ┌────────────────┐   ┌────────────────┐              │
│ │ Global Market│   │ Pair Selection │   │ Risk Management│              │
│ │ Watcher      │   │ & Research     │   │ Engine          │              │
│ └──────┬───────┘   └──────┬────────┘   └──────┬─────────┘              │
│        │ Events          │ Reports        │ Risk Findings               │
│        ▼                 ▼                ▼                             │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │                     CTO-AI Orchestrator (FSM)                        │ │
│ │  • Maintains hypotheses, confidence, mode                            │ │
│ │  • Issues trade directives (OPEN/CLOSE/HOLD/NO TRADE/REJECT)         │ │
│ │  • Consumes metrics, research, risk verdicts                         │ │
│ └──────────────┬───────────────────────────────────────────────────────┘ │
│                │ Commands                                                  │
│      ┌─────────▼────────┐                                             │
│      │ Execution Engine │───Bybit REST/WebSocket───> Testnet/Mainnet   │
│      └─────────┬────────┘                                             │
│                │ Fills                                                 │
│      ┌─────────▼────────┐                                             │
│      │ Reporting & Audit│──Persist→ Postgres / Redis / Object storage  │
│      └──────────────────┘                                             │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## 4. Backend Services
All backend modules live in `backend/app/` and are orchestrated by a FastAPI
application. Services run as async tasks managed by a Service Supervisor. The
system uses a domain event bus implemented on top of Redis Streams for
horizontally scalable pub/sub with persistence guarantees.

### 4.1 Service Supervisor
- Launches supervised background workers (market polling, research pipeline,
  risk evaluation, etc.).
- Performs health checks and exposes readiness / liveness probes via FastAPI.
- Reacts to emergency stop by pausing or cancelling active tasks.

### 4.2 CTO-AI Orchestrator
- Finite State Machine with states: `Idle`, `Scanning`, `Evaluating`,
  `AwaitingRisk`, `AwaitingExecution`, `ManagingPosition`, `EmergencyStop`.
- Receives events: `MarketSnapshot`, `CandidateReport`, `RiskAssessment`,
  `ExecutionResult`, operator commands (`SetMode`, `EmergencyStop`, `ManualDecision`).
- Issues decisions encapsulated in `TradeDirective` objects referencing
  hypotheses, expected edge, risk rubric, and expiry TTL.
- Maintains global confidence score derived from market health, recent outcomes,
  and operator overrides.
- Modes:
  - `Manual`: UI must manually approve each directive.
  - `SemiAuto`: CTO-AI can recommend trades, operator must confirm.
  - `FullAuto`: CTO-AI auto-approves when risk checks pass and confidence ≥ threshold.

### 4.3 Global Market Watcher
- Consumes Bybit public REST endpoints (tickers, 24h stats, funding, open
  interest) and WebSocket streams for depth/liquidation events.
- Calculates normalized metrics and a composite `market_score` per symbol.
- Maintains watchlists categorized as `ignored`, `watch`, `candidate`. Roughly
  90–95% of symbols remain in `ignored` at any time.
- Emits `MarketSnapshot` events with rationale for symbol state transitions.

### 4.4 Pair Selection & Research Engine
- Triggered by `MarketSnapshot` updates that move symbols into `watch`.
- Fetches higher-fidelity data (klines, funding history, liquidation clusters).
- Runs pluggable setup detectors (trend-follow, mean reversion, funding bias,
  volatility squeeze, liquidation sweep) implemented as async strategy modules.
- Produces `TradeHypothesis` reports with supporting evidence and confidence.
- The default outcome is a rejection detailing exclusion reasons.

### 4.5 Risk Management Engine
- Stateless calculations per hypothesis combined with portfolio context.
- Validates: leverage (≤ 3x default), max position size, symbol correlation,
  margin impact, cumulative exposure, max drawdown window.
- Emits `RiskAssessment` events with `approved=false` and blocking reasons when
  limits are violated.

### 4.6 Execution Engine
- Implements an abstract `ExchangeAdapter` with Bybit-specific subclass.
- Stateless, receives `CTOAiDecision` events (directive envelope + `decision_uid`) via Redis stream `ctoai.decisions`.
- Uses Redis-backed `DecisionRegistry` for idempotency, retries failed orders with exponential backoff and quantized tick rules.
- Tracks consecutive failures, enters a timed `degraded` window after threshold breaches, and publishes health state to the dashboard.
- Emits `ExecutionReport` events consumed by CTO-AI and Reporting.
- Supports dry-run mode for testnet sandbox and toggled mainnet configs.

### 4.7 RL State Builder
- Subscribes to market, hypothesis, risk, directive, and execution streams.
- Enriches per-symbol context with rolling action/reward windows and portfolio KPIs from PostgreSQL.
- Produces normalized feature vectors (≈40 dims) cached under `rl_state_cache:{symbol}` in Redis.
- Refreshes metrics on configurable cadence and exposes feature metadata for training/inference parity.

### 4.8 RL Trainer (PPO + LSTM Actor-Critic)
- Collects experiential tuples by pairing directives with subsequent execution reports.
- Maintains normalized experience buffer respecting configurable window/interval thresholds.
- Trains recurrent actor-critic policy (PyTorch, PPO updates) and persists weights/normalization to `rl_policy:latest` key.
- Publishes recommended action priors and confidence scalers ingestible by CTO-AI.

### 4.9 Reporting & Audit Layer
- `structlog` + JSON logging fan-out to both disk and Redis Streams.
- PostgreSQL stores normalized tables: `events`, `decisions`, `executions`,
  `positions`, `metrics`.
- GlobalAppState aggregates market, risk, directives, positions, and live service health (`services.{name}`) for the dashboard.
- Object storage (MinIO / S3) retains raw research artifacts (e.g. enriched
  kline snapshots).
- Exposes an async repository API for the Web Dashboard and for offline
  analytics workloads.

## 5. Data Flow Summary
1. **Market Monitoring:** Market Watcher ingests Bybit feeds → publishes
   `MarketSnapshot` events.
2. **Research:** Eligible symbols trigger Research Engine → emits
   `TradeHypothesis` or `RejectedHypothesis` respecting rate limits.
3. **Decisioning:** CTO-AI ingests hypotheses, updates internal state, requests
   Risk evaluation.
4. **Risk Review:** Risk Engine scores candidate → emits `RiskAssessment`.
5. **Decision Contract:** CTO-AI emits both `TradeDirective` and `CTOAiDecision`
   with unique `decision_uid` onto the bus.
6. **Execution:** Execution Engine consumes decisions, attempts order placement
   with retries, enters `degraded` mode on repeated failures, emits `ExecutionReport`.
7. **Health Propagation:** Execution Engine updates GlobalAppState service status for UI feedback.
8. **RL State:** RL State Builder aggregates symbol features → caches vector snapshots in Redis.
9. **RL Training:** RL Trainer ingests cached vectors + execution rewards → updates `rl_policy:latest`.
10. **Audit & UI:** Reporting layer persists everything; Web Dashboard consumes
   REST/WebSocket endpoints serving portfolio metrics, decisions, and health.

## 6. State & Storage
- **Redis Streams:** Event bus (`market.snapshots`, `research.hypotheses`,
  `risk.assessments`, `ctoai.directives`, `execution.reports`). Supports replay
  for post-mortem analysis.
- **PostgreSQL:** Durable canonical store with referential integrity.
- **Redis Keyspace:** Ephemeral caches (latest market scores, CTO-AI state
  snapshot, active positions).
- **S3-Compatible Storage:** Optional retention for large research blobs.

## 7. Security & Safety
- API keys stored in PostgreSQL (encrypted at rest) and injected into Execution
  Engine via secrets manager at runtime. Never exposed to frontend.
- Strict role separation enforced at service layer.
- Operator authentication handled via OAuth/OpenID provider integration with
  RBAC; initial scaffold uses signed JWT with admin/operator roles.
- Emergency stop triggers immediate cancellation of directives and flushes all
  pending tasks through orchestrator state change to `EmergencyStop`.
- Rate limiting and circuit breakers around Bybit endpoints to prevent runaway
  loops when API degrades.

## 8. Deployment & Ops
- Docker Compose bundles `backend`, `frontend`, `redis`, `postgres`, `minio`,
  and `celery-beat`-like scheduler for periodic jobs.
- Production deployments target Kubernetes with Helm chart (future work).
- Observability via Prometheus metrics endpoint and OpenTelemetry traces.
- Structured logs shipped to ELK or Loki.

## 9. Extensibility Notes
- Strategy modules and risk rules register through plugin interface discovered
  via entry points.
- Exchange adapter layer allows additional derivatives venues without touching
  core logic.
- Web Dashboard provides narrative components fed by same event store; mobile
  layouts achieved through responsive design.

## 10. Outstanding Decisions
- Portfolio correlation calculations use Pearson correlation over 14-day window;
  can be upgraded to tail-risk copula analysis later.
- Market score weighting tuned via configuration served from PostgreSQL;
  defaults documented in README.
- Manual override queue retains operator decisions for 30 days; retention
  configurable via environment.

This document serves as the authoritative reference for the system structure and
will be updated alongside implementation milestones.
