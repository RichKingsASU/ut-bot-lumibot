# IWM Options Habitat Test — Track 2 Findings

**Date:** 2026-07-16
**Branch:** `research/iwm-options-habitat`
**Verdict:** **NO-GO** — No cell clears the gate after spread costs.

## Context

The UT Bot ATR signal was proven edgeless on daily SPY equity (gross -28.6%,
net -37.3%, corr -0.0385 — see `docs/hmm_signal_diagnosis.md`). This test asks
whether expressing the same signal as IWM options (leverage, defined risk,
theta) changes the picture.

---

## Step 1: Harness Audit

### a) IWM Underlying Data

| Property | Value |
|----------|-------|
| Source | Local parquet (`/mnt/tick-storage/historical/equities/IWM/`) |
| Provenance | `REAL_PARQUET` |
| 1-minute bars | 1,159,919 rows, 77 monthly files (2020-01 to 2026-05) |
| Daily bars | 2,612 rows (2016-01-04 to 2026-05-22) |
| Backtest window | 2024-01-02 to 2026-05-22 (resampled to 5m/15m) |
| 15m bars used | 16,196 |
| 5m bars used | 47,367 |

### b) Option Pricing

**Provenance class: `real_underlying_modeled_options`**

The harness uses **Black-Scholes modeled pricing** for option premiums:
- `bs_price()` with closed-form Black-Scholes
- IV estimated via `iv_estimate()`: base IV = 0.20 with moneyness skew
  (`1 + 1.5 * |log(S/K)|`) and short-dated term bump
- Bid/ask constructed as: `half_spread = max($0.01, 0.0075 * mid)`

An Alpaca-backed reference run (86% real option bars, 14% BS fallback) was also
conducted for the 15m/DTE4/ATM cell. It produced the same NO-GO verdict
(expectancy = -$2.94/trade vs -$5.22 with pure BS).

**Every result in this document reflects modeled option prices unless
explicitly labeled otherwise.**

### c) Spread Cost Assumption

| Parameter | Value |
|-----------|-------|
| Half-spread | `max($0.01, 0.75% of mid)` |
| Full spread (ATM ~$3 mid) | ~$0.045 |
| Slippage | 1 tick ($0.01) per side |
| Round-trip cost/contract | ~$6.50 |
| Commission | $0.00 |

**Verdict: Realistic.** IWM front-month ATM options trade $0.02-$0.05 wide.
The $0.045 assumption is in the middle of the observed range. ITM spreads are
slightly wider in practice, which the model captures (0.75% of higher mid).

### d) Signal Source

`backtests/signal.py:compute_ut_signal()` — **confirmed** as the 4-branch
SMA-ATR trailing stop, verbatim from `strategies/ut_bot.py` (lines 116-154).
Same function the live bot uses. ATR_PERIOD=10, SENSITIVITY=1.0.

---

## Step 2: Sweep Results

**Grid:** DTE {3, 4, 5} x Strike {ATM, ITM1, ITM2} x Timeframe {5m, 15m}
= 18 cells

**Sizing:** Flat (1 contract per trade, no HMM)

**Data provenance on ALL rows: `real_underlying_modeled_options`**

### Full Results Table

| Rank | TF | DTE | Strike | Trades | Win% | Gross $ | Net $ | Exp/Trade $ | Exp/Trade % | MaxDD $ | Sharpe |
|------|----|-----|--------|--------|------|---------|-------|-------------|-------------|---------|--------|
| 1 | 15m | 3 | ATM | 1,902 | 37.1% | $333 | -$9,392 | -$4.94 | -2.22% | -$9,490 | -4.29 |
| 2 | 15m | 4 | ATM | 1,902 | 36.5% | $460 | -$9,920 | -$5.22 | -2.13% | -$10,011 | -4.46 |
| 3 | 15m | 5 | ATM | 1,902 | 36.5% | $526 | -$10,369 | -$5.45 | -2.07% | -$10,459 | -4.73 |
| 4 | 15m | 3 | ITM1 | 1,902 | 37.9% | -$598 | -$11,873 | -$6.24 | -2.25% | -$11,970 | -5.05 |
| 5 | 15m | 4 | ITM1 | 1,902 | 37.9% | -$504 | -$12,437 | -$6.54 | -2.19% | -$12,527 | -5.26 |
| 6 | 15m | 5 | ITM1 | 1,902 | 37.1% | -$428 | -$12,911 | -$6.79 | -2.14% | -$13,001 | -5.55 |
| 7 | 15m | 3 | ITM2 | 1,902 | 37.6% | -$1,149 | -$14,158 | -$7.44 | -2.20% | -$14,259 | -5.69 |
| 8 | 15m | 4 | ITM2 | 1,902 | 37.4% | -$1,034 | -$14,673 | -$7.71 | -2.15% | -$14,769 | -5.91 |
| 9 | 15m | 5 | ITM2 | 1,902 | 37.1% | -$960 | -$15,119 | -$7.95 | -2.11% | -$15,215 | -6.19 |
| 10 | 5m | 3 | ATM | 5,007 | 35.9% | -$232 | -$25,702 | -$5.13 | -2.45% | -$25,709 | -14.78 |
| 11 | 5m | 4 | ATM | 5,007 | 35.4% | $185 | -$26,977 | -$5.39 | -2.31% | -$26,983 | -15.29 |
| 12 | 5m | 5 | ATM | 5,007 | 34.8% | $179 | -$28,422 | -$5.68 | -2.25% | -$28,423 | -16.25 |
| 13 | 5m | 3 | ITM1 | 5,007 | 36.5% | -$1,498 | -$31,035 | -$6.20 | -2.33% | -$31,031 | -15.15 |
| 14 | 5m | 4 | ITM1 | 5,007 | 36.0% | -$1,304 | -$32,551 | -$6.50 | -2.25% | -$32,546 | -16.02 |
| 15 | 5m | 5 | ITM1 | 5,007 | 35.5% | -$1,285 | -$33,959 | -$6.78 | -2.21% | -$33,949 | -16.90 |
| 16 | 5m | 3 | ITM2 | 5,007 | 36.6% | -$1,848 | -$36,057 | -$7.20 | -2.19% | -$36,049 | -15.71 |
| 17 | 5m | 4 | ITM2 | 5,007 | 35.9% | -$1,718 | -$37,586 | -$7.51 | -2.14% | -$37,574 | -16.66 |
| 18 | 5m | 5 | ITM2 | 5,007 | 35.3% | -$1,588 | -$38,826 | -$7.75 | -2.10% | -$38,814 | -17.43 |

### Alpaca-Backed Reference (86% Real Option Data)

| TF | DTE | Strike | Trades | Win% | Gross $ | Net $ | Exp/Trade $ | BS% |
|----|-----|--------|--------|------|---------|-------|-------------|-----|
| 15m | 4 | ATM | 1,904 | 39.5% | $4,695 | -$5,605 | **-$2.94** | 14% |

Even with real Alpaca option bars capturing actual IV dynamics, net expectancy
is still firmly negative.

---

## Step 3: Go/No-Go Gate

**Gate:** Net expectancy per trade after spread > $0

| Rank | Cell | Exp/Trade $ | Trades | Verdict |
|------|------|-------------|--------|---------|
| 1 | 15m/DTE3/ATM | -$4.94 | 1,902 | **NO-GO** |
| 2 | 15m/DTE4/ATM | -$5.22 | 1,902 | **NO-GO** |
| 3 | 15m/DTE5/ATM | -$5.45 | 1,902 | **NO-GO** |
| 4 | 15m/DTE3/ITM1 | -$6.24 | 1,902 | **NO-GO** |
| ... | (all remaining) | -$6.50 to -$7.95 | 1,902-5,007 | **NO-GO** |

**Every cell fails the gate.** Not a single configuration produces positive
net expectancy.

### Overfit Guard

**Best cell:** 15m/DTE3/ATM (exp = -$4.94, 1,902 trades)
**Median cell:** 15m/DTE5/ITM1 (exp = -$6.79, rank 6 of 18)

**Neighbor check for best cell (15m/DTE3/ATM):**
- DTE neighbor: 15m/DTE4/ATM: exp = -$5.22 (same direction, NO-GO)
- Strike neighbor: 15m/DTE3/ITM1: exp = -$6.24 (same direction, NO-GO)
- Timeframe neighbor: 5m/DTE3/ATM: exp = -$5.13 (same direction, NO-GO)

**Best cell is SUPPORTED** — all neighbors agree. The surface is uniformly
negative; there are no isolated pockets of apparent edge.

---

## Step 4: Verdict

### **NO-GO**

No cell clears the gate after spread costs. The UT Bot ATR signal expressed as
IWM options is **edgeless** across all tested configurations.

### Key Findings

1. **The signal has no gross edge on intraday IWM bars.** Gross P&L ranges from
   -$1,848 to +$526 across 18 cells (1,902-5,007 trades each). The best gross
   result ($526) represents $0.28/trade — statistical noise.

2. **Spread costs annihilate any residual edge.** Average spread cost per trade
   is $5-$7. Where gross P&L is slightly positive, spread costs are 20-160x
   larger.

3. **The options structure does NOT rescue an edgeless signal.** Leverage
   amplifies losses proportionally. Defined risk (premium stop) caps downside
   per trade but doesn't improve the base edge. Theta works against long-premium
   positions (another cost layer, not a benefit).

4. **More trades does not equal more edge.** 5m timeframe generates 2.6x more trades than
   15m but with worse per-trade expectancy (more noise, same zero edge, more
   spread paid).

5. **Going ITM makes it worse.** Higher premiums lead to larger absolute spread costs.
   ITM2 cells are the worst performers across the board.

6. **Win rates are uniformly poor** (34.8%-37.9%). A profitable options scalp
   strategy typically requires 45%+ win rate at these payoff ratios, or much
   larger avg_win/avg_loss skew.

### What Would Change the Verdict

- **A signal with actual gross edge:** The fundamental problem is not spread
  cost — it's that the UT Bot signal produces zero gross edge on intraday IWM
  bars. A signal with consistent $10+/trade gross edge could overcome the $5-7
  spread friction.

- **Dramatically tighter spreads:** If spread costs were cut by 80%+ (e.g.,
  maker rebates, sub-penny pricing), the best cell's -$4.94 expectancy might
  approach breakeven. But this isn't realistic for retail options flow.

- **Different underlying/timeframe:** The signal might have edge on a different
  asset or timeframe not tested here. But the daily SPY test (Track 1) and this
  intraday IWM test together cover the live trading range.

- **Real option pricing with wider coverage:** The BS model may understate
  IV-regime effects. However, the Alpaca-backed reference run (86% real data)
  still showed -$2.94/trade — better than BS but still firmly NO-GO.

---

## Data Files

| File | Description |
|------|-------------|
| `backtests/results/iwm_options_habitat.json` | Complete sweep results (18 cells + Alpaca reference) |
| `backtests/results/trades_IWM_*.csv` | Per-trade detail for each cell (gitignored, local only) |
| `backtests/results/equity_IWM_*.png` | Equity curve charts per cell (gitignored, local only) |

## Supabase Persistence

Supabase credentials not available in this environment. Insert SQL provided
below for manual execution:

```sql
-- IWM Options Habitat Test — Track 2
-- Run date: 2026-07-16
-- Option pricing: modeled_BS (+ Alpaca reference)

INSERT INTO backtest_results (symbol, strategy, timeframe, start_date, end_date,
  trades, win_rate, gross_pnl, net_pnl, expectancy_dollar, max_drawdown, sharpe,
  params, created_at)
VALUES
  -- Best cell (BS)
  ('IWM', 'ut_bot_options', '15m', '2024-01-01', '2026-06-01',
   1902, 0.3707, 333.0, -9392.0, -4.94, -9490.0, -4.285,
   '{"dte": 3, "strike_mode": "ATM", "timeframe": "15m", "option_pricing": "modeled", "spread_assumption": "$0.045", "verdict": "NO-GO"}'::jsonb,
   NOW()),
  -- Median cell (BS)
  ('IWM', 'ut_bot_options', '15m', '2024-01-01', '2026-06-01',
   1902, 0.3712, -428.0, -12911.0, -6.79, -13001.0, -5.549,
   '{"dte": 5, "strike_mode": "ITM1", "timeframe": "15m", "option_pricing": "modeled", "spread_assumption": "$0.045", "verdict": "NO-GO"}'::jsonb,
   NOW()),
  -- Worst cell (BS)
  ('IWM', 'ut_bot_options', '5m', '2024-01-01', '2026-06-01',
   5007, 0.3531, -1588.0, -38826.0, -7.75, -38814.0, -17.429,
   '{"dte": 5, "strike_mode": "ITM2", "timeframe": "5m", "option_pricing": "modeled", "spread_assumption": "$0.045", "verdict": "NO-GO"}'::jsonb,
   NOW()),
  -- Alpaca reference (86% real option data)
  ('IWM', 'ut_bot_options', '15m', '2024-01-01', '2026-06-01',
   1904, 0.395, 4695.0, -5605.0, -2.94, -5696.0, -3.64,
   '{"dte": 4, "strike_mode": "ATM", "timeframe": "15m", "option_pricing": "mixed_86pct_real", "spread_assumption": "$0.045", "verdict": "NO-GO"}'::jsonb,
   NOW());
```
