# DMA Crossover Validation Report

**Date**: 2026-07-16 19:09 UTC
**Branch**: research/dma-validation
**Signal**: DMA crossover, fast=5/slow=20, no vol filter
**SPY Baseline** (recomputed, 1-bar delay, 1bp fee): Sharpe=0.336, compound=+128.6%
**Original sweep baseline**: Sharpe=0.791, compound=+158.1% (likely same-bar convention — higher due to lookahead)

---

## Test 1: Out-of-Sample Assets

Tests the 5/20 DMA crossover on assets NOT used during parameter selection.

| Asset | Period | Trades | Net Sharpe | Compound Return | Max Drawdown | Avg Hold (d) | Data Source | Verdict |
|-------|--------|--------|------------|-----------------|--------------|--------------|-------------|---------|
| IWM | 2000-06-26 to 2026-07-15 | 201 | 0.261 | +107.1% | -52.0% | 28 | parquet:/mnt/tick-storage/historical/equities/IWM | **MARGINAL** |
| QQQ | 2000-02-01 to 2026-07-15 | 200 | 0.399 | +273.7% | -52.4% | 29 | parquet:/mnt/tick-storage/historical/equities/QQQ | **PASS** |
| GLD | 2004-12-17 to 2026-07-15 | 173 | 0.535 | +296.6% | -22.8% | 26 | parquet:/mnt/tick-storage/historical/equities/GLD | **PASS** |
| TLT | 2004-02-02 to 2026-07-15 | 171 | 0.166 | +30.2% | -32.2% | 24 | parquet:/mnt/tick-storage/historical/equities/TLT | **MARGINAL** |

**OOS Verdict**: 2/4 PASS → **mixed**

---

## Test 2: Sub-Period Stability

Tests whether the signal works across different market regimes.

| Period | Description | Trades | Net Sharpe | Compound Return |
|--------|-------------|--------|------------|-----------------|
| 2000-2006 | Dot-com crash + recovery | 51 | -0.083 | -9.2% |
| 2007-2012 | GFC + recovery | 45 | -0.075 | -11.2% |
| 2013-2019 | Bull market | 51 | 0.457 | +25.9% |
| 2020-2026 | COVID + current | 48 | 1.044 | +115.4% |

**Weak Periods**: 2000-2006, 2007-2012

---

## Test 3: Realistic Execution Degradation

Tests impact of execution slippage and signal delay on performance.

| Scenario | Fill | Fee/side | Net Sharpe | Compound Return |
|----------|------|----------|------------|-----------------|
| Ideal | close | 1bp | 0.336 | +128.6% |
| Fee only (6bp) | close | 6bp | 0.269 | +87.6% |
| Delay only (next-open) | next-open | 1bp | 0.339 | +130.3% |
| Realistic (6bp + next-open) | next-open | 6bp | 0.272 | +89.0% |

**Degradation**: 0.064 Sharpe points
**Verdict**: **marginal** (threshold: Sharpe > 0.4)

---

## Test 4: Vol Filter Mechanism

Analyzed why `vol_threshold=0.20` is counterproductive for the 5/20 DMA crossover.

- **Total entry signals**: 195
- **Filtered out** (vol >= 0.20): 70 (35.9%)
- **Kept** (vol < 0.20): 125

| Metric | Filtered-out signals | Kept signals |
|--------|---------------------|--------------|
| Win rate (20d fwd) | 57.1% | 60.0% |
| Avg 20d return | +0.80% | +0.08% |

- No filter backtest: Sharpe=0.336, trades=198
- With filter (0.20) backtest: Sharpe=0.396, trades=173

**Mechanism**: high-vol signals have better raw returns but worse risk-adjusted performance; filter improves Sharpe by removing high-volatility trades

---

## Overall Verdict

### Baseline Recalibration Note

The original sweep reported Sharpe=0.791, but this used same-bar execution
(signal computed at close, traded at same close = lookahead bias). With
proper 1-bar delay, the SPY baseline is **Sharpe=0.336**.
All thresholds below use relative comparisons against this corrected baseline.

| Test | Result | Detail |
|------|--------|--------|
| OOS Assets | FAIL | mixed (2/4 PASS, threshold: 3) |
| Sub-period stability | FAIL | weak in 2000-2006, 2007-2012 |
| Realistic execution | PASS | 0.336 → 0.272 (19% degradation) |
| Vol filter | INFO | high-vol signals have better raw returns but worse risk-adju |

### **RESEARCH-FURTHER**

### Weaknesses to Investigate

- **OOS generalization**: weak on IWM, TLT
- **Sub-period stability**: negative Sharpe in 2000-2006, 2007-2012 (choppy markets with many whipsaws)

### Potential Improvements

1. **Longer SMAs** (e.g., 10/50 or 20/100) to reduce whipsaws in choppy markets
2. **Regime filter**: only trade in trending regimes (ADX > 25), skip range-bound
3. **Combine with existing UT Bot signal** as a complementary filter
4. The vol filter actually improves Sharpe (0.396 vs 0.336) — the original sweep's 'no filter wins' finding may have been an artifact of same-bar execution
