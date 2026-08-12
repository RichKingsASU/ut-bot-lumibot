# OPERATIONAL HARDENING CHANGELOG (OAT TIER 1)
**Date**: 2026-05-15
**Audit ID**: OAT-2026-05-15-BETA
**Status**: IMPLEMENTED

## 1. Risk Management & Safety (Backend)
- **File**: `config.py`
  - **Change**: Introduced `ABSOLUTE_DAILY_LOSS_LIMIT` constant (Default: $5,000).
  - **Rationale**: Provides a hard-coded fallback that cannot be overridden by UI/Database configuration errors. Ensures a "Fail-Closed" posture.
- **File**: `strategies/ut_bot.py`
  - **Change**: Updated `on_trading_iteration` to calculate `effective_limit` as the minimum of the dynamic config and the absolute safeguard.
  - **Rationale**: Prevents the bot from trading without a safety net if the database connection fails or returns corrupted values.

## 2. Dashboard Integrity (Frontend)
- **File**: `RiskRulesView.tsx`
  - **Change 1 (Sanitization)**: Added numeric-only validation to all configuration inputs.
  - **Change 2 (Synchronization)**: Implemented a `useEffect` fetch to synchronize the UI state with the Supabase `risk_config` table on load.
  - **Change 3 (UX)**: Added a "Loading..." state to prevent users from interacting with stale/default data during initialization.
  - **Rationale**: Eliminates the risk of "Dirty Data" crashes and prevents silent overwrites caused by editing a non-synchronized state.
- **File**: `DataView.tsx`
  - **Change**: Restored the `SEEDING` tab and integrated the `SeedStatus` component.
  - **Rationale**: Restores visibility into the Alpaca SIP/OPRA data ingestion pipeline, which was previously a "blind spot" for operators.

## 3. Operational Documentation
- **File**: `README.md`
  - **Change**: Added "Emergency Procedures" and "Manual Kill Switch" instructions.
  - **Rationale**: Standardizes the human-in-the-loop recovery process, fulfilling enterprise SOP requirements for high-stakes algorithmic trading.

---
---
## 4. Crypto Operational Readiness
- **File**: `main_crypto.py`
  - **Change**: Created dedicated entry point for ETH/USD Adaptive strategy.
  - **Rationale**: Isolates 24/7 crypto operations from equities trading. Includes independent health checks on port 8001.
- **File**: `SOP_LIBRARY.md`
  - **Change**: Added **SOP-004: Crypto Paper Trading**.
  - **Rationale**: Standardizes the setup and monitoring of ADX-based regime switching for ETH.

*Verified by Operational Readiness Task Force*
