# Disrupting Alpha Version 2 Phase 5.5 — Unified Handoff Documentation

Welcome to the unified handoff documentation for **Disrupting Alpha Version 2 Phase 5.5**. This documentation outlines the institutional-grade features implemented across **Runs 1, 2, and 3** to establish an autonomous, risk-aware, and performant multi-agent system.

---

## 1. Executive Summary

Phase 5.5 has elevated the Disrupting Alpha multi-agent architecture into a complete, institutional-grade intelligence stack. We have combined **Advanced Mathematical Modeling (HMM)**, **Optimal Capital Allocation (Kelly Criterion)**, and **Statistical Edge Quality Tracking (Information Coefficient Decay)** to protect portfolio equity and dynamically scale resources.

```
┌────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│  HMM REGIME DETECTOR   │ ───> │  KELLY POSITION SIZER  │ <─── │  SIGNAL DECAY MONITOR  │
│ (BULL/BEAR/VOL/QUIET)  │      │ (Regime + Greeks + IC) │      │ (Spearman Rank Corr)   │
└────────────────────────┘      └────────────────────────┘      └────────────────────────┘
```

---

## 2. Core Components Built

### Component A: Hidden Markov Model (HMM) Regime Detector
- **Agent**: `agents/regime_detector.py`
- **Objective**: Dynamically classify asset price behavior into 4 hidden states: `BULL`, `BEAR`, `VOLATILE`, and `QUIET`.
- **Mechanics**:
  - Loads historical 1D Parquet bars from tick storage.
  - Extracts 4 mathematical features: log returns, rolling volatility (10-bar), volume ratio (20-bar rolling mean), and daily range-to-close ratio.
  - Standardizes features and fits a `GaussianHMM` on a 252-day lookback window.
  - Dynamically labels states by analyzing returns/volatility means (highest returns = BULL, lowest returns = BEAR, highest remaining volatility = VOLATILE, lowest remaining volatility = QUIET).
  - Persists states to the `regime_states` table and publishes state events to NATS (`regime.{asset_class}.{symbol}`).

### Component B: Kelly Criterion Position Sizer
- **Agent**: `agents/kelly_sizer.py`
- **Objective**: Replace static position sizing with conservative, data-driven fractional Kelly capital allocation.
- **Mechanics**:
  - Computes trade stats from `trade_performance` (win rate, payout ratio).
  - Computes the raw optimal Kelly fraction using a conservative **25% fractional Kelly** betting formula.
  - Imposes strict risk floors and caps (`2%` minimum, `20%` maximum portfolio size per trade).
  - **Multi-Factor Sizing Scalers**:
    1. **Regime Scaling**: Adjusts size based on overall market state (BULL = `100%`, QUIET = `80%`, VOLATILE = `60%`, BEAR = `40%`).
    2. **Greeks Risk Scalar**: Integrates risk metrics from options risk analysis.
    3. **Information Coefficient (IC) Sizing**: Scales allocation based on predictive edge quality.

### Component C: Signal Decay Monitor
- **Agent**: `agents/signal_decay_monitor.py`
- **Objective**: Prevent trading decaying strategies by measuring the Spearman rank correlation (Information Coefficient) between historical signal predictions and subsequent trade returns.
- **Mechanics**:
  - Matches signals (`signal_log`) to trade outcomes (`trade_performance`) by temporal proximity (within a 5-day window).
  - Calculates Spearman rank correlation using `scipy.stats.spearmanr` over a rolling 30-day lookback.
  - Classifies quality into 4 distinct performance brackets:
    - **HEALTHY** (`IC >= 0.02`): Edge confirmed. No capital adjustment (`ic_scalar = 1.0`).
    - **DEGRADING** (`IC >= 0.005`): Warning state. Reduce trade size by `25%` (`ic_scalar = 0.75`).
    - **WEAK** (`IC >= 0.0`): Critical degradation. Reduce trade size by `50%` (`ic_scalar = 0.50`).
    - **DEAD** (`IC < 0.0`): Edge lost. Immediately disable strategy and block capital allocation (`ic_scalar = 0.0`). Sends instant high-priority Telegram alerts.

---

## 3. Daily Schedules & Lifecycle

The agent orchestrator `run_agents.py` is configured with a dual-cadence scheduling loop:

### 1. Cycle Pipeline (Every 15 Minutes)
Runs the LangGraph AgentStateGraph in parallel for Crypto and Equities universes:
- Calls `RegimeDetector` to assess current asset states.
- Triggers `MarketAnalystAgent` for sentiment-rich data scraping.
- Generates tactical trade proposals via `SignalAgent`.
- Applies Kelly position sizing incorporating active regime and database-cached IC scores.
- Runs exposure checks via `RiskAgent` / `GreeksRiskEngine` to block/approve orders.
- Delivers a unified status summary to the Telegram channel.

### 2. Signal Health Decay Audit (Daily at 8:00 PM ET)
Runs immediately after market close to evaluate capital allocation metrics:
- Instantiates `SignalDecayMonitor` to calculate rolling Spearman correlation coefficients.
- Writes historical results to the `signal_performance` database.
- Delivers a comprehensive **Signal Health Report** summarizing healthy, degrading, dead, and insufficient data strategies.
- Triggers instant warning alerts on system performance degradation.

---

## 4. Phase 6 Preview: Institutional-Scale Backtesting

With Phase 5.5 complete, the portfolio possesses a self-adjusting, risk-mitigating tactical layer. We are fully prepared for **Phase 6: Backtesting on 10.7M rows**, which will include:
1. **High-Frequency Backtester Integration**: Executing backtests on raw tick databases stored in QuestDB.
2. **HMM State Conditioned Strategies**: Backtesting how our portfolio performs by switching strategy modes under past BULL/BEAR/VOLATILE regimes.
3. **Simulated Decay Recovery**: Testing the speed at which the Kelly Sizer reacts to synthetic edge decay and recovery.
