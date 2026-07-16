# HMM Switching Backtest — Phase 1 Diagnosis (read-only)

`DATA PROVENANCE: real_parquet | rows=6671 | symbol=SPY`

Window: 2000-01-01 → 2026-07-14 | bars analysed: 6651 (2000-01-31 → 2026-07-13)

## (a) Is the P&L engine correct?

| Test | Total return |
|---|---|
| Raw buy & hold (`close[-1]/close[0]-1`) | 436.8% |
| Buy & hold **through `simulate_portfolio`**, fee=0.001 | 435.7% |
| Buy & hold **through `simulate_portfolio`**, fee=0 | 436.8% |

## (b) Is the raw signal inverted or mis-shifted?

- Exposure: **long 63.5%**, flat 36.5%, short 0.0% of 6651 bars
- **corr(pos[t], ret[t→t+1]) = -0.0385**  ← inversion test
- corr(pos[t], ret[t-1→t]) = +0.4264 (look-ahead alignment)
- corr(pos[t], ret[t+1→t+2]) = -0.0229 (lagged alignment)
- Trades: **645** (one per 10.3 bars, avg hold 6.5 bars)
- Win rate 35.5% | avg win 2.4% | avg loss -1.4% | **expectancy/trade -0.0%**
- Sum of gross (fee-free) trade returns: -13.3%

### Alignment proof (vectorised rebuild vs zero-fee engine)

Zero-fee engine total return: **-28.6%**

| Alignment | Vectorised return | Matches engine? |
|---|---|---|
| t -> t+1 (correct, no look-ahead) | -28.6% | **YES** |
| t-1 -> t (LOOK-AHEAD) | 4941373877.1% | no |
| t+1 -> t+2 (lagged) | 30.0% | no |

### Cost decomposition (same signal, `fee_pct` varied)

| fee_pct (per side) | Total return | Sharpe | Max DD |
|---|---|---|---|
| 0.001 | -80.4% | -0.41 | -84.8% |
| 0.0005 | -62.6% | -0.22 | -76.7% |
| 0.0001 | -37.3% | -0.07 | -70.8% |
| 0.0 | -28.6% | -0.03 | -69.1% |

### Repo signal vs published UT Bot reference (comparison only — nothing changed)

The repo's `calculate_ut_signals` has 2 branches; the published UT Bot has 4 — it is
missing the RESET branch, so on a stop cross the stop is clamped to the stale prior
stop (`max(prev_stop, ...)`) instead of resetting a full ATR from price.

| Metric | Repo `calculate_ut_signals` | Reference UT Bot (4-branch) |
|---|---|---|
| Trades | 645 | 519 |
| Avg hold (bars) | 6.5 | 8.0 |
| Win rate | 35.5% | 39.9% |
| Expectancy/trade | -0.0% | -0.1% |
| corr(pos[t], ret[t→t+1]) | -0.0385 | -0.0460 |
| Return @ fee=0 | -28.6% | -48.5% |
| Return @ fee=0.001 | -80.4% | -81.8% |

#### KNOWN DEVIATION — accepted, will NOT be fixed

`calculate_ut_signals` is **not** a faithful UT Bot: it implements 2 of the
published indicator's 4 trailing-stop branches, omitting the RESET branch. On a
stop cross it clamps to the stale prior stop via `max(prev_stop, close - nLoss)`
instead of resetting a full ATR from price, so the stop sits just under price and
whipsaws out — hence the 6.5-bar average hold.

**This is a fidelity bug, not the cause of the loss.** Measured above: the correct
4-branch reference is *worse* on this data — **-48.5% gross vs -28.6% gross** for the repo version. Repairing it
would reduce returns, not rescue them. Documented as a known deviation and left
in place deliberately (decision: 2026-07-15); `calculate_ut_signals` is unchanged.

## (c) How broken is the HMM fit?

- Refits: **6399** (lookback 252, n_components=4, diag, n_iter=100)
- Failed fits (exception → carry previous regime): 6 (0.1%)
- **Hit the n_iter=100 cap (did NOT converge to tol): 25 (0.4%)**
- Final EM step *lowered* log-likelihood: 5 (0.1%)
- **Refits whose FINAL model has ≥1 phantom state (zero-sum transmat row): 0 (0.0%)**
- Total phantom rows across all refits: 0
- States actually populated in the final model: mean 4.00 of 4 requested (min 4, max 4)
  - exactly 1 populated: 0.0%
  - exactly 2 populated: 0.0%
  - exactly 3 populated: 0.0%
  - exactly 4 populated: 100.0%
- EM iterations: mean 30.8, max 100 (cap 100)
- **BULL state index permuted between consecutive refits: 69.7% of refits**
- Full regime→index map changed between consecutive refits: 90.0% of refits

hmmlearn log lines actually emitted (the warning spam in the run logs):

- `Some rows of transmat_ have zero sum...`: **167** lines
- `Model is not converging...`: **5** lines

> Both messages are misleading. The zero-sum check (`hmmlearn/base.py:497`) sits
> *after* the `break` on convergence at `:494`, so it can only ever fire on a
> **non-final** EM iteration — a state that is transiently empty mid-fit and
> repopulated before `fit()` returns. And `ConvergenceMonitor.converged` returns
> True when `iter == n_iter`, while its delta test omits `abs()`, so a *falling*
> log-likelihood logs "not converging" yet still reports converged. Neither log
> line describes the model that actually produces the regime labels.

### Do the SEMANTIC regime labels mean anything?

`map_regimes` re-derives BULL/BEAR by sorting emission means on **every** refit,
so it is invariant to hmmlearn's arbitrary state ordering — the raw-index
permutation above is expected and already handled. These are the metrics that
actually bear on the regime→size map:

- Label churn: regime changes on **41.9%** of bars

| Regime | Bars | Mean fwd return (bp/day) | Annualised return | Annualised vol |
|---|---|---|---|---|
| BULL | 1294 | -1.10 | -2.8% | 20.7% |
| QUIET | 2754 | +3.08 | 7.8% | 13.6% |
| VOLATILE | 1539 | +7.79 | 19.6% | 19.0% |
| BEAR | 812 | +3.12 | 7.9% | 29.8% |

### Control: does the regime map beat a constant size at the same exposure?

Regime sizing averages **0.744** exposure. If the regime
signal is real it must beat a flat line at that same average exposure; if it merely
holds less of a losing strategy, the two will match.

- Regime distribution: {'QUIET': 3006, 'VOLATILE': 1539, 'BULL': 1294, 'BEAR': 812}

| Variant | Total return | Sharpe | Max DD |
|---|---|---|---|
| regime | -61.5% | -0.34 | -67.3% |
| constant_matched | -69.0% | -0.41 | -74.6% |

## Verdict

1. **P&L engine: CORRECT.** Buy & hold through `simulate_portfolio` returns 435.7% vs 436.8% raw. No sign, compounding or shift error.
2. **Signal: NOT inverted, NOT mis-shifted.** Positions are long/flat only (`{0.0, 1.0}`) — a short is structurally impossible. corr(pos[t], ret[t→t+1]) = -0.0385 ≈ 0: no edge, not an inversion. The vectorised t→t+1 rebuild reproduces the engine exactly, so alignment is correct.
3. **Root cause: transaction-cost drag on an edgeless signal.** 645 round trips × 2 sides × `fee_pct=0.001` = 129% of notional paid in fees. (1-0.286) × (1-0.001)^1290 = -80.4% vs -80.4% actual — the loss is fully accounted for.
4. **HMM is not fabricating phantom states** (0% of final models degenerate; 100% have all 4 states populated; 0.4% hit the iteration cap). **But labels permute on 69.7% of refits**, which is real and unfixed.

