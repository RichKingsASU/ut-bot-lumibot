# Disrupting Alpha Version 2 Phase 6 — Institutional-Scale Backtesting

Welcome to the handoff documentation for **Disrupting Alpha Version 2 Phase 6**. This phase establishes a high-frequency backtesting pipeline, integrates rolling HMM regime detection overlays, and validates the responsiveness of capital protection rules (Kelly sizing under signal decay/recovery transitions).

---

## 1. Core Architecture & Components

```
                     ┌──────────────────────────────┐
                     │     Historical Tick Data     │
                     │          (QuestDB)           │
                     └──────────────────────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │    QuestDB Data Connector    │
                     │  (Aggregated SQL SAMPLE BY)  │
                     └──────────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │             Institutional Backtest Harness             │
       ├────────────────────────────────────────────────────────┤
       │  1. HMM Rolling Classifier (Lookback: 252 Days)        │
       │     └─ BULL / BEAR / VOLATILE / QUIET                  │
       │  2. Dynamic Kelly Position Sizing Multipliers          │
       │  3. Adaptive Stop Loss / Parameter Selection           │
       │  4. Signal Spearman Correlation Audit (IC Monitor)      │
       └────────────────────────────────────────────────────────┘
```

---

## 2. Completed Milestones

### Milestone A: High-Frequency QuestDB Backtester Integration
- **Harness Integration**: [data.py](file:///home/k2/ut-bot-lumibot/backtests/data.py) & [config.py](file:///home/k2/ut-bot-lumibot/backtests/config.py)
- **Spot HF Engine**: [backtest_questdb_spot.py](file:///home/k2/ut-bot-lumibot/scripts/backtest_questdb_spot.py)
- **Objective**: Execute tick-level backtests using QuestDB's time-series database REST API, avoiding local file sandbox constraints.
- **Mechanics**:
  - Dynamically builds aggregated SQL queries using QuestDB's `SAMPLE BY 1m ALIGN TO CALENDAR` syntax.
  - Queries raw trades from the `ticks` table, resamples to OHLCV bars, and maps timestamps to tz-aware `America/New_York` timezone.
  - Runs simulated order execution tick-by-tick (applying transaction commissions and slippage adjustments).
- **Unit Tests**: [test_questdb_loader.py](file:///home/k2/ut-bot-lumibot/backtests/tests/test_questdb_loader.py) (All tests passed).

### Milestone B: HMM State-Conditioned Sizing & Parameter Adaptation
- **Harness Script**: [backtest_hmm_switching.py](file:///home/k2/ut-bot-lumibot/scripts/backtest_hmm_switching.py)
- **Objective**: Simulates trading strategies where position size and stop-loss sensitivity dynamically switch based on rolling Gaussian HMM models (eliminating look-ahead bias).
- **Mechanics**:
  - Fits a 4-state `GaussianHMM` on a rolling 252-day window at each step `t` using standardized return, volatility, volume ratio, and range ratio features.
  - Maps predicted hidden states to `BULL`, `BEAR`, `VOLATILE`, and `QUIET` using returns and volatility means.
  - Evaluates three configurations:
    1. *Baseline*: Fixed 100% position sizing and fixed ATR trailing-stop sensitivity (1.0).
    2. *Regime-Sized*: Dynamic scaling based on predicted regime (`BULL`=100%, `QUIET`=80%, `VOLATILE`=60%, `BEAR`=40%).
    3. *Regime-Adapted*: Sizing scaling + tighter stop-loss sensitivity (0.7 multiplier) in `BEAR` and `VOLATILE` regimes to exit failing trades faster.
- **Unit Tests**: [test_hmm_switching.py](file:///home/k2/ut-bot-lumibot/backtests/tests/test_hmm_switching.py) (All tests passed).

### Milestone C: Simulated Edge Decay & Recovery
- **Harness Script**: [simulate_decay_recovery.py](file:///home/k2/ut-bot-lumibot/scripts/simulate_decay_recovery.py)
- **Objective**: Verifies the responsiveness of the `SignalDecayMonitor` (IC Spearman rank correlation) and `KellySizer` scaling rules when an edge degrades and recovers.
- **Mechanics**:
  - Generates a 3-phase trade stream: Healthy (win rate = 56%), Decayed (win rate = 32%), and Recovered (win rate = 56%).
  - Tracks rolling 30-trade Spearman rank correlation between signals and outcomes.
  - Sizing scales down to `0%` (disabled) when IC is negative, and recovers back to `100%` when edge returns.
  - Measures reaction latencies and compares portfolio equity curves.
- **Unit Tests**: [test_decay_recovery.py](file:///home/k2/ut-bot-lumibot/backtests/tests/test_decay_recovery.py) (All tests passed).

---

## 3. Performance Summary Reports

### 1. Options QuestDB Underlying Backtest (ETHUSD 15m)
```
  Trades              : 16
  Win rate            : 50.0%  (8W / 8L)
  Avg win / avg loss  : $637.38 / $-424.75
  Profit factor       : 1.50
  Max drawdown        : $-1,671.00
  NET total (paid)    : $1,701.00
```

### 2. Rolling HMM State-Conditioned Backtest (SPY Daily)
- **Baseline**: Total Return: `-64.6%` | Max Drawdown: `-70.1%`
- **Regime-Sized**: Total Return: `-54.1%` | Max Drawdown: `-59.8%` *(Drawdown reduced by **10.3%**)*
- **Regime-Adapted**: Total Return: `-51.1%` | Max Drawdown: `-57.2%` *(Drawdown reduced by **12.9%**, returns improved by **13.5%**)*

### 3. Edge Decay & Recovery Sizing Simulation
- **Decay Warning Latency**: 8 trades (sizes scaled down to 75% -> 50%)
- **Decay Shutdown Latency**: 8 trades (allocation disabled to 0%)
- **Edge Recovery Latency**: 21 trades (allocation restored to 100%)
- **Static Sizer (Fixed 10%)**: Return: `1.0%` | Max Drawdown: `-5.6%`
- **Adaptive Sizer (Dynamic IC)**: Return: `4.7%` | Max Drawdown: `-1.2%` *(Drawdown reduced by **78.5%**, returns improved by **3.7%**)*
- **Capital Saved**: **$3,680.26** on a $100,000 portfolio.

---

## 4. Verification Commands

### Run Unit Tests
To run all newly added test suites:
```bash
python3 -m pytest backtests/tests/test_questdb_loader.py backtests/tests/test_hmm_switching.py backtests/tests/test_decay_recovery.py -v
```

### Run Backtests Manual Runs
```bash
# Options Backtest
python3 scripts/run_options_backtest.py --symbol ETHUSD --use-questdb --start 2026-06-01 --end 2026-06-05 --no-synthetic

# HF Spot Backtest
python3 scripts/backtest_questdb_spot.py --symbol BTCUSD --start 2026-06-01 --end 2026-06-05

# HMM State-Conditioned Sizing Backtest
python3 scripts/backtest_hmm_switching.py --symbol SPY --start 2020-01-01

# Edge Decay & Recovery Sizing Simulation
python3 scripts/simulate_decay_recovery.py
```
