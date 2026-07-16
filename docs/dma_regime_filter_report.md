# DMA Regime Filter Research Report

**Date**: 2026-07-16 19:26 UTC
**Branch**: research/dma-regime-filter
**Baseline**: DMA 5/20 Sharpe=0.336 (with vol filter: 0.396)
**Problem**: negative Sharpe in 2000-2006 (-0.083) and 2007-2012 (-0.075)

---

## Fix 1: Longer SMA Pairs (SPY 2000-2026)

| Pair | Vol Filter | Full Sharpe | Compound | Trades | 2000-2006 | 2007-2012 | 2013-2019 | 2020-2026 |
|------|-----------|-------------|----------|--------|-----------|-----------|-----------|-----------|
| 10/50 | none | +0.377 | +156.1% | 87 | +0.010 | +0.236 | +0.405 | +0.890 |
| 10/50 | 0.20 | +0.308 | +91.4% | 98 | -0.133 | +0.210 | +0.390 | +0.737 |
| 20/100 | none | +0.437 | +211.4% | 37 | +0.105 | +0.187 | +0.556 | +0.830 |
| 20/100 | 0.20 | +0.375 | +135.7% | 61 | +0.143 | -0.085 | +0.490 | +0.772 |
| 20/200 | none | +0.609 | +436.2% | 19 | +0.475 | +0.327 | +0.795 | +1.155 |
| 20/200 | 0.20 | +0.634 | +367.8% | 39 | +0.461 | +0.321 | +0.653 | +1.072 |
| 50/200 | none | +0.590 | +462.3% | 12 | +0.645 | +0.332 | +0.679 | +0.888 |
| 50/200 | 0.20 | +0.630 | +362.2% | 36 | +0.645 | +0.224 | +0.540 | +0.960 |

**Most stable pair**: 50/200 — worst sub-period Sharpe = +0.332

---

## Fix 2: ADX Regime Filter

Applied to 5/20 (original) and 50/200 (Fix 1 best), vol filter = None

| Pair | ADX Threshold | Full Sharpe | Compound | Trades | 2000-2006 | 2007-2012 | 2013-2019 | 2020-2026 |
|------|--------------|-------------|----------|--------|-----------|-----------|-----------|-----------|
| 5/20 | >15 | +0.348 | +136.4% | 197 | -0.083 | -0.026 | +0.454 | +1.037 |
| 5/20 | >20 | +0.357 | +141.1% | 185 | -0.096 | +0.030 | +0.481 | +0.994 |
| 5/20 | >25 | +0.210 | +54.2% | 162 | -0.152 | -0.021 | +0.090 | +0.809 |
| 5/20 | >30 | +0.368 | +112.3% | 116 | -0.087 | +0.304 | +0.244 | +0.774 |
| 50/200 | >15 | +0.590 | +462.3% | 12 | +0.645 | +0.332 | +0.679 | +0.888 |
| 50/200 | >20 | +0.580 | +443.4% | 12 | +0.645 | +0.328 | +0.679 | +0.888 |
| 50/200 | >25 | +0.568 | +423.4% | 12 | +0.645 | +0.278 | +0.676 | +0.888 |
| 50/200 | >30 | +0.559 | +405.5% | 12 | +0.645 | +0.281 | +0.667 | +0.888 |

**2000-2006 turns positive at**: ADX > 15

---

## Fix 3: Combined Approach — Candidate Comparison

Tested multiple configurations to find the best balance of stability and signal frequency.

### Candidate Summary

| Candidate | Sharpe | Compound | Trades/yr | Worst Sub | Criteria |
|-----------|--------|----------|-----------|-----------|----------|
| A: 50/200+ADX>15 (Fix1 best) | +0.590 | +462.3% | 0.5 | +0.332 | 4/6 |
| B: 20/200+ADX>15 (more trades) | +0.602 | +423.7% | 0.7 | +0.327 | 5/6 |
| C: 20/100+ADX>15 (even more trades) | +0.437 | +211.4% | 1.4 | +0.105 | 4/6 |
| D: 10/50+ADX>20 (highest freq stable) | +0.340 | +128.0% | 3.2 | -0.042 | 3/6 |
| E: 5/20+vol+ADX>30 (original enhanced) | +0.341 | +72.1% | 3.8 | -0.100 | 1/6 |

### Winner: B: 20/200+ADX>15 (more trades)

**Configuration**: 20/200 + vol<None + ADX>15

### SPY Results

| Metric | Value |
|--------|-------|
| Full-period Sharpe | +0.602 |
| Compound return | +423.7% |
| Total trades | 19 |
| Trades/year | 0.7 |
| Max drawdown | -33.7% |
| Realistic Sharpe (6bp) | +0.595 |

### Sub-Period Stability

| Period | Net Sharpe |
|--------|-----------|
| 2000-2006 | +0.475 |
| 2007-2012 | +0.327 |
| 2013-2019 | +0.795 |
| 2020-2026 | +1.155 |

### OOS Assets

| Asset | Net Sharpe | Compound | Verdict |
|-------|-----------|----------|---------|
| QQQ | +0.620 | +792.9% | PASS |
| GLD | +0.632 | +479.7% | PASS |
| IWM | +0.311 | +151.3% | PASS |
| TLT | +0.210 | +43.7% | MARGINAL |

### Deploy Criteria

| Criterion | Result |
|-----------|--------|
| Full-period net Sharpe > 0.40 (0.602) | **PASS** |
| All 4 sub-periods Sharpe > 0 (worst: +0.327) | **PASS** |
| OOS 3+ of 4 PASS (Sharpe > 0.30) | **PASS** |
| Realistic (6bp) Sharpe > 0.30 (0.595) | **PASS** |
| Trades/year > 5 (0.7) | **FAIL** |
| Trades/year < 100 (0.7) | **PASS** |

## OVERALL VERDICT: **RESEARCH-FURTHER**

- 5/6 criteria met
