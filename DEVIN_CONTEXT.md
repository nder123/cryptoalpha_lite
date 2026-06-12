# CryptoAlpha Lite — Dev Continuation Context

## Current state
System is partially refactored trading/execution engine.

## Architecture overview
- backend/app → core application layer
- backend/runtime → control/monitoring layer
- backend/services → execution + trading logic
- backend/infrastructure → event bus + persistence

## Important subsystems
- execution engine: backend/app/services/execution_engine.py
- risk engine: backend/app/services/risk_engine.py
- trading gate: backend/app/services/trading_gate.py
- watchdog: backend/runtime/watchdog/
- freeze guard: backend/runtime/freeze_guard/

## Known historical layers (Windsurf archive)
Older runtime control system existed:
- watchdog
- timeline
- retention
- chaos
These were partially refactored into current architecture.

Archive:
cryptoalpha_windsurf_history.tgz

## Current focus areas
- stabilize execution engine
- ensure risk controls are enforced
- validate watchdog + freeze_guard integration
- improve system observability

## Entry point for Devin
Start from:
backend/app/main.py
