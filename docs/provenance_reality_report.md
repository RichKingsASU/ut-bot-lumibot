# Data Provenance Reality Report

This report documents the results of executing the test and backtest suites with strict defaults (i.e. synthetic data disabled by default).

## Summary Table

| Test / Backtest | Status (Default Run) | Status (With `--allow-synthetic`) | Reality Analysis |
| :--- | :--- | :--- | :--- |
| `backtests/tests/test_costs.py` | `PASSED (real)` | N/A | Pure analytical trade cost and commission calculations. |
| `backtests/tests/test_golden_trade.py` | `PASSED (real)` | N/A | Validates parser/engine options pricing against actual OCC symbols. |
| `backtests/tests/test_questdb_loader.py` | `PASSED (real)` | N/A | Validates QuestDB loading queries and resampler processing via request mocks. |
| `backtests/tests/test_signal_parity.py` | `PASSED (real)` | N/A | Compares signal calculation parity against static data references. |
| `backtests/tests/mechanism/test_decay_recovery.py` | `PASSED (synthetic)` | N/A | Validates rolling Spearman IC calculation math against a mock decay curve. |
| `backtests/tests/mechanism/test_hmm_switching.py` | `PASSED (synthetic)` | N/A | Validates HMM regime mapping and rolling window fitting math against mock states. |
| `scripts/run_options_backtest.py` | `FAILED (real data unavailable)` | `PASSED (synthetic)` | Raised `SyntheticDataError` due to missing local Parquet files / Alpaca credentials in sandboxed run. |
| `scripts/backtest_hmm_switching.py` | `FAILED (real data unavailable)` | `PASSED (synthetic)` | Raised `SyntheticDataError` because the production `/mnt/tick-storage/` is restricted or empty. |
| `scripts/simulate_decay_recovery.py` | `FAILED (real data unavailable)` | `PASSED (synthetic)` | Raised `SyntheticDataError` because it uses a simulated trade stream by design. |

---

## Conclusion
*   **Green Checkmarks Audited:** Previously, running options backtests, HMM switching, and decay simulators silently generated synthetic results without alerting the developer.
*   **Safety Lock:** All backtests now strictly fail by default in validation environments (raising `SyntheticDataError`) unless they are explicitly passed `--allow-synthetic` (or `ALLOW_SYNTHETIC=1` / `TRADING_MODE=research`), forcing true data transparency.
