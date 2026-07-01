# UT Bot Options Backtest Harness

Answers ONE question: **does the UT Bot ATR signal have a tradeable edge when
expressed as long IWM options (3–5 DTE, held intraday) — AFTER paying the
bid-ask spread and theta?**

Unlike `scripts/backtest_utbot.py` (which tests the signal on the *underlying*
on daily bars and models none of the option economics), this harness models the
option lifecycle: real fills at ask/bid, the full spread, slippage, and theta.

## Quick start

```bash
# Primary run — the goal configuration
python scripts/run_options_backtest.py \
    --symbol IWM --timeframe 15m --dte 4 --strike ATM \
    --start 2024-06-01 --end 2026-06-01 \
    --time-stop-min 20 --profit-target 0.5 --premium-stop 0.4

# Grid: DTE {3,4,5} x strike {ATM,ITM1,ITM2} x timeframe {5m,15m}
python scripts/run_options_backtest.py --sweep
```

Outputs land in `backtests/results/`: per-trade CSV, equity-curve PNG, and
`sweep_comparison.csv` (git-ignored — regenerate any time).

## What it reuses (faithfully, no reinvention)

| Concern | Source of truth | How |
|---|---|---|
| Signal (ATR trailing stop + crossover) | `strategies/ut_bot.py` (OFF-LIMITS) | replicated **verbatim** in `signal.py::compute_ut_signal`; parity unit-tested |
| Production exits (RSI step-back, underlying %-stop, EOD flatten 15:55 ET) | `strategies/ut_bot.py` | reproduced in `engine.py` |
| Contract selection (target expiry, strike offset, nearest-strike) | `strategies/options_executor.py` | `contracts.py` (parameterized by DTE for the sweep) |
| OCC symbol format | `options_executor.sync_state_with_broker` | `contracts.build_occ_symbol` (SYMBOL+YYMMDD+C/P+strike×1000, 8-pad) |
| bid/ask/mid convention | `options_executor.get_option_quote` | `quotes.Quote.mid = round((bid+ask)/2, 2)` |
| Risk limits | `config.py` | `MAX_TRADES_PER_DAY`, `MAX_POSITION_SIZE`, `OPTION_STRIKE_STEP` |

The live `/v2/options/contracts` chain endpoint is **not** called for historical
dates (it only returns currently-active contracts). Instead the selection rules
compute the target strike + expiry and the OCC symbol is constructed directly,
then handed to the quote provider for historical pricing.

## Data precedence

1. **Local parquet** — `/mnt/tick-storage/historical/equities/<SYM>/` (same store
   the existing backtest reads).
2. **Alpaca** — `StockHistoricalDataClient` minute bars (cached to parquet);
   options premium from `OptionHistoricalDataClient` (real theta/IV). Requires
   `ALPACA_API_KEY` / `ALPACA_API_SECRET` + network egress.
3. **Synthetic** (last resort) — deterministic GBM bars + Black-Scholes pricing
   so the harness and tests run in a data-less/offline sandbox. **Loudly labeled**
   in every run's Assumptions block; numbers are illustrative of mechanics, not a
   real edge estimate. Disable with `--no-synthetic`.

Every trade is tagged `priced_via = real | bs`.

## Modules

- `config.py` — `BacktestConfig` (pulls production risk/option settings).
- `data.py` — underlying load/resample/cache (local → Alpaca → synthetic).
- `signal.py` — verbatim UT Bot signal + RSI; reference `calculate_ut_signals`.
- `contracts.py` — selection rules + OCC symbol construction.
- `pricing.py` — Black-Scholes fallback + RVX-proxy IV.
- `quotes.py` — quote providers (Alpaca real / BS fallback).
- `costs.py` — enter@ask / exit@bid + slippage; gross(mid) vs net; spread paid.
- `engine.py` — event loop, exit priority, risk enforcement.
- `metrics.py` — summary stats, equity curve, drawdown, Sharpe.
- `report.py` — CSV, printed summary, equity PNG, Assumptions block.
- `runner.py` — single-run + sweep orchestration.
- `tests/` — signal parity, cost model, golden trade.

## Tests

```bash
python -m pytest backtests/tests/ -q
```
