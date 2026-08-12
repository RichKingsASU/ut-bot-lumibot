# Strategy Validation Report

## Execution Parity
The core engine has been refactored to align exactly with the backtest timing mechanism. The live engine now evaluates the daily bar exactly at the 15:45 ET cutoff.

## Signal Generation
The daily and 5m bars are continuously evaluated. A SignalSnapshot dataclass wraps these calculations and forces validation checks against `MAX_5M_BAR_AGE_SECONDS`. If any of the constraints are violated (e.g. data older than 300 seconds), the signal is marked invalid, forcing the execution engine to fail closed.

## Risk Management Limits
- **Max Daily Loss:** Checked independently before any trade entry using the account realized P&L directly from Alpaca.
- **Max Trades Per Day:** Rejects new entries after 10 filled opening trades are executed in the current session.

## Backtest Reporting Additions
The `backtests/` suite now supports extensive reporting mechanisms:
1. **Out of Sample (OOS) Splits:** The `runner.py` now splits the output automatically to evaluate robustness over the first 50% vs last 50% of trades.
2. **Monte Carlo DD:** The summary provides a 95th percentile Max DD via trade bootstrap resampling.
3. **Annualized CAGR:** Equity curve output now computes a standardized CAGR over the simulated timeframe.

These metrics offer enhanced scrutiny over whether the UT Bot ATR Edge is viable long term.
