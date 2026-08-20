# Paper-Trading Soak Plan

Follow this phased plan to validate execution before activating live mode.

## Stage 1: Offline Fake-Broker Soak
- **Goal:** Verify config parsing and bot startup without network calls.
- **Criteria:** Bot starts, validates config, connects to Supabase, but broker adapters are stubbed out.

## Stage 2: Broker Read-Only Connectivity
- **Goal:** Connect to Alpaca in paper mode, fetch account info, pull market data.
- **Criteria:** Logs show successful sync_state_with_broker(). No orders sent.

## Stage 3: Paper-Account Observation
- **Goal:** Watch signals without execution.
- **Criteria:** Bot runs through a full day, prints intended orders to logs, but order sizing is forced to 0.

## Stage 4: Minimal Paper Orders
- **Goal:** Test order submission and lifecycle.
- **Criteria:** Explicitly authorize 1-contract sizing in paper mode. Verify partial fills, cancellations, and EOD flattening occur cleanly.

## Stage 5: Multi-Session Paper Soak
- **Goal:** Let the bot run across multiple days.
- **Criteria:** Runs unattended for 1 full week in paper mode. Handle weekend transition, missing bars, and daily resets cleanly.

## Stage 6: Human Go-Live Review
- **Goal:** Operator verifies all logs and metrics.
- **Criteria:** All paper trades matched expected strategy logic. OPERATIONS_RUNBOOK.md go-live checklist completed.

## Stage 7: Limited Live Rollout
- **Goal:** Switch TRADING_MODE=live with tight limits.
- **Criteria:** MAX_DAILY_LOSS minimized, MAX_POSITION_SIZE=1. Monitor heavily for 3 days.
