# UT Bot Turnover Sweep — SPY Daily 2000–2026

**Grid:** 6 ATR periods × 6 sensitivities = 36 cells  
**Signal:** `compute_ut_signal` (4-branch SMA-ATR, identical to live `strategies/ut_bot.py`)  
**Sizing:** flat 100%, long/short reversal at each signal  
**Fee:** 1 bp per side (equity_etf)  
**Data:** real parquet — `/mnt/tick-storage/historical/equities/SPY/SPY_1D_2000-01-03_2026-07-14.parquet`  
**Bars:** 6,671 daily bars (2000-01-03 → 2026-07-14)  

---

## Full Grid — Ranked by Net Sharpe (CRITICAL → LOW)

| Rank | Period | Sens | Trades | Gross Ret | Net Ret | Sharpe | MaxDD | Win Rate | Exp/Trade | Avg Hold |
|------|--------|------|--------|-----------|---------|--------|-------|----------|-----------|----------|
| 1 | 10 | 2.5 | 292 | -12.1% | -17.1% | +0.060 | -55.4% | 38.4% | +0.153% | 22.8d |
| 2 | 5 | 2.5 | 293 | -17.8% | -22.5% | +0.047 | -57.9% | 38.6% | +0.140% | 22.7d |
| 3 | 14 | 2.5 | 295 | -29.2% | -33.3% | +0.018 | -57.3% | 38.3% | +0.076% | 22.5d |
| 4 | 7 | 2.5 | 293 | -35.1% | -38.9% | +0.000 | -58.7% | 37.5% | +0.065% | 22.7d |
| 5 | 10 | 3.0 | 230 | -37.2% | -40.0% | -0.004 | -58.3% | 34.8% | +0.067% | 28.9d |
| 6 | 5 | 3.0 | 231 | -39.7% | -42.5% | -0.012 | -60.0% | 34.6% | +0.052% | 28.8d |
| 7 | 7 | 3.0 | 231 | -46.8% | -49.2% | -0.036 | -62.6% | 35.9% | +0.006% | 28.8d |
| 8 | 21 | 2.5 | 305 | -61.0% | -63.4% | -0.100 | -78.8% | 38.0% | -0.111% | 21.8d |
| 9 | 30 | 2.5 | 310 | -63.3% | -65.5% | -0.114 | -77.8% | 36.4% | -0.132% | 21.3d |
| 10 | 14 | 3.0 | 238 | -65.7% | -67.3% | -0.123 | -73.9% | 34.0% | -0.192% | 27.9d |
| 11 | 7 | 2.0 | 420 | -66.6% | -69.3% | -0.135 | -77.0% | 36.4% | -0.136% | 15.8d |
| 12 | 30 | 3.0 | 242 | -69.5% | -71.0% | -0.148 | -77.9% | 34.7% | -0.263% | 27.3d |
| 13 | 5 | 2.0 | 436 | -76.9% | -78.9% | -0.208 | -81.5% | 35.1% | -0.216% | 15.3d |
| 14 | 10 | 2.0 | 426 | -79.0% | -80.8% | -0.226 | -82.9% | 35.9% | -0.233% | 15.6d |
| 15 | 21 | 3.0 | 244 | -80.3% | -81.2% | -0.232 | -84.7% | 35.7% | -0.420% | 27.2d |
| 16 | 21 | 2.0 | 424 | -84.6% | -85.9% | -0.287 | -88.1% | 34.2% | -0.314% | 15.7d |
| 17 | 30 | 2.0 | 432 | -86.2% | -87.4% | -0.309 | -89.3% | 35.2% | -0.334% | 15.4d |
| 18 | 30 | 1.5 | 646 | -88.1% | -89.6% | -0.346 | -91.1% | 33.8% | -0.252% | 10.3d |
| 19 | 5 | 1.5 | 634 | -89.0% | -90.3% | -0.360 | -91.1% | 34.9% | -0.267% | 10.5d |
| 20 | 14 | 1.5 | 632 | -89.6% | -90.8% | -0.371 | -91.8% | 34.6% | -0.280% | 10.5d |
| 21 | 14 | 1.0 | 1012 | -91.1% | -92.7% | -0.415 | -94.2% | 35.3% | -0.200% | 6.6d |
| 22 | 14 | 2.0 | 430 | -92.4% | -93.1% | -0.426 | -93.3% | 34.4% | -0.474% | 15.5d |
| 23 | 21 | 1.0 | 1024 | -92.0% | -93.5% | -0.437 | -95.2% | 35.1% | -0.208% | 6.5d |
| 24 | 21 | 1.5 | 654 | -93.1% | -94.0% | -0.453 | -94.8% | 33.8% | -0.334% | 10.2d |
| 25 | 30 | 1.0 | 1018 | -93.0% | -94.3% | -0.463 | -96.0% | 34.9% | -0.223% | 6.5d |
| 26 | 5 | 1.0 | 1014 | -93.2% | -94.5% | -0.468 | -95.9% | 36.3% | -0.226% | 6.6d |
| 27 | 10 | 1.5 | 642 | -93.8% | -94.6% | -0.473 | -95.3% | 34.3% | -0.355% | 10.4d |
| 28 | 7 | 1.0 | 1012 | -93.8% | -94.9% | -0.485 | -96.3% | 36.0% | -0.235% | 6.6d |
| 29 | 7 | 1.5 | 648 | -94.8% | -95.4% | -0.507 | -95.8% | 33.5% | -0.378% | 10.3d |
| 30 | 5 | 0.5 | 1763 | -95.6% | -97.0% | -0.583 | -97.6% | 35.2% | -0.164% | 3.8d |
| 31 | 10 | 0.5 | 1763 | -96.1% | -97.3% | -0.608 | -97.7% | 35.0% | -0.171% | 3.8d |
| 32 | 14 | 0.5 | 1751 | -96.4% | -97.5% | -0.620 | -97.9% | 35.1% | -0.176% | 3.8d |
| 33 | 10 | 1.0 | 1038 | -97.1% | -97.6% | -0.634 | -98.2% | 34.6% | -0.302% | 6.4d |
| 34 | 21 | 0.5 | 1741 | -96.7% | -97.7% | -0.639 | -98.1% | 34.9% | -0.182% | 3.8d |
| 35 | 30 | 0.5 | 1763 | -97.3% | -98.1% | -0.676 | -98.4% | 34.8% | -0.191% | 3.8d |
| 36 | 7 | 0.5 | 1769 | -97.3% | -98.1% | -0.676 | -98.4% | 34.8% | -0.190% | 3.8d |

---

## Top 3 vs Median Comparison

| | Period/Sens | Net Sharpe | Net Return | Trades | Win Rate | Exp/Trade |
|---|---|---|---|---|---|---|
| Top 1 | 10/2.5 | +0.060 | -17.1% | 292 | 38.4% | +0.153% |
| Top 2 | 5/2.5 | +0.047 | -22.5% | 293 | 38.6% | +0.140% |
| Top 3 | 14/2.5 | +0.018 | -33.3% | 295 | 38.3% | +0.076% |
| Median | 5/1.5 | -0.360 | -90.3% | 634 | 34.9% | -0.267% |

---

## Neighbor Check — Best Cell

**Best cell:** period=10, sensitivity=2.5 (Sharpe=+0.060, exp/trade=+0.153%)

8 nearest neighbors (±1 step in period/sensitivity grid):

| Period | Sens | Sharpe | Exp/Trade | Positive? |
|--------|------|--------|-----------|-----------|
| 7 | 2.0 | -0.135 | -0.136% | ✗ |
| 7 | 2.5 | +0.000 | +0.065% | ✓ |
| 7 | 3.0 | -0.036 | +0.006% | ✓ |
| 10 | 2.0 | -0.226 | -0.233% | ✗ |
| 10 | 3.0 | -0.004 | +0.067% | ✓ |
| 14 | 2.0 | -0.426 | -0.474% | ✗ |
| 14 | 2.5 | +0.018 | +0.076% | ✓ |
| 14 | 3.0 | -0.123 | -0.192% | ✗ |

**The best cell is [supported by neighbors].**

---

## Comparison to Baselines

| Config | Source | Trades | Net Return | Sharpe | Exp/Trade |
|--------|--------|--------|------------|--------|-----------|
| 10/1.0 (baseline) | this sweep | 1038 | -97.6% | -0.634 | -0.302% |
| 14/3.0 (live) | this sweep | 238 | -67.3% | -0.123 | -0.192% |

*(Prior run baseline for 10/1.0: gross -28.6%, net -37.3%, 645 trades — measured with options engine; this sweep uses equity simulation which will differ.)*

---

## Honest Verdict

**YES (with critical caveat) — positive net expectancy per trade after 1 bp costs exists at: 10/2.5, 5/2.5, 14/2.5, 7/2.5, 10/3.0**

Of 36 parameterizations tested, 7 show positive *arithmetic* expectancy per trade. The best cell (10/2.5) has expectancy +0.1534% per trade, Sharpe +0.060, over 292 trades (2000–2026). Neighbor check: the best cell is **supported by neighbors**.

**However: all 36 cells produce negative compound returns (equity curves lose money).** The best cell has net compound return of −17.1% over 26 years. This is variance drag: a strategy with +0.15% arithmetic mean per trade but ~5–10% standard deviation per trade has a geometric mean that is negative. With 100% position sizing, the catastrophic drawdowns during 2000–2002, 2008–2009, and 2020 destroy the compounded equity even when the "average" trade is marginally profitable.

**Practical conclusion:** The UT Bot signal has a tiny arithmetic edge at sensitivity≈2.5 on daily SPY, but the edge is too weak to overcome variance drag at full-size. Any live deployment would need Kelly-optimal sizing (well under 100%) and would still show modest positive expectancy at best. The signal is not reliably profitable on daily SPY without additional filters.

---

## Supabase Persistence

Rows written to `backtest_results`: **36/36**  
Schema note: existing table uses `total_return_pct`, `sharpe_ratio`, `total_trades`, `win_rate_pct` columns; sweep-specific fields (`gross_return`, `net_return`, `fee_drag_pct`, `expectancy_per_trade`, `data_provenance`) stored in `params` jsonb.

---
*Generated: 2026-07-16 | Branch: research/turnover-sweep*