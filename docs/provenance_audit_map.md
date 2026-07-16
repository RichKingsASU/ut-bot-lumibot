# Data Provenance Audit Map

This document maps every location in the backtesting suite that generates synthetic data, operates as a fallback data source, or acts as a result/report sink.

| File | Lines | Type | Current Behavior |
| :--- | :--- | :--- | :--- |
| `backtests/data.py` | 143–178 | `generator` | `_synthetic(cfg)` generates reproducible GBM minute bars over RTH (looks like IWM). |
| `backtests/data.py` | 253–260 | `fallback` | `load_underlying` falls back to `_synthetic(cfg)` when QuestDB, local Parquet, and Alpaca all return empty. |
| `scripts/backtest_hmm_switching.py` | 29–76 | `generator` | `generate_synthetic_data` generates synthetic daily returns, OHLCV, and volume with regime shifts. |
| `scripts/backtest_hmm_switching.py` | 89–91, 101–102 | `fallback` | `load_data` falls back to `generate_synthetic_data` if local Parquet files are missing or unreadable. |
| `scripts/simulate_decay_recovery.py` | 33–58 | `generator` | `generate_trade_stream` generates a 100% synthetic trade sequence (Healthy $\rightarrow$ Decayed $\rightarrow$ Recovered). |
| `scripts/backtest_questdb_spot.py` | 315–328 | `result-sink` | Saves trade metrics and log details to `questdb_spot_{symbol}.json`. |
| `scripts/backtest_hmm_switching.py` | 392–427 | `result-sink` | Prints evaluation metrics to stdout and saves JSON to `hmm_switching_comparison.json`. |
| `scripts/simulate_decay_recovery.py` | 159–209 | `result-sink` | Prints evaluation metrics to stdout and saves JSON to `decay_recovery_simulation.json`. |
| `backtests/report.py` | 37–80 | `result-sink` | `assumptions_block` prints details of the underlying data source and quote provider source. |
| `backtests/runner.py` | 50–57 | `result-sink` | `run_single` prints Single assumptions, metrics, and data source labels. |
| `backtests/runner.py` | 98–103 | `result-sink` | `run_sweep` prints Sweep assumptions and comparative ranking list. |
| `.harness/pipeline.yaml` | 50 | `ci-entrypoint` | CI executes unit and reliability tests via `pytest tests/ -v`. |
| `.github/workflows/ci.yml` | 28 | `ci-entrypoint` | CI executes compilation syntax check on `config.py`, `main.py`, and `strategies/ut_bot.py`. |
