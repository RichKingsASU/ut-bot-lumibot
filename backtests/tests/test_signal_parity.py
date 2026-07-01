"""
Signal parity tests.

1. Our reproduced ``calculate_ut_signals`` matches the reference implementation
   in ``scripts/backtest_utbot.py`` byte-for-byte (the function the task names).
2. Our canonical ``compute_ut_signal`` matches a verbatim bar-by-bar re-run of
   the production loop from ``strategies/ut_bot.py`` (the live source of truth).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtests.signal import calculate_ut_signals, compute_ut_signal


def _sample_df(n: int = 300, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 200 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + np.abs(rng.normal(0, 0.3, n))
    low = close - np.abs(rng.normal(0, 0.3, n))
    idx = pd.date_range("2024-06-03 09:30", periods=n, freq="15min", tz="America/New_York")
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)


def test_calculate_ut_signals_matches_reference():
    """Parity vs scripts/backtest_utbot.py::calculate_ut_signals."""
    # Import the real reference function. It imports vectorbt at module load;
    # skip cleanly if that heavy dependency is unavailable.
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ref_backtest_utbot", ROOT / "scripts" / "backtest_utbot.py"
        )
        ref = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ref)
    except Exception as e:  # pragma: no cover
        import pytest

        pytest.skip(f"reference script unavailable: {e}")

    df = _sample_df()
    b1, s1, t1 = ref.calculate_ut_signals(df, atr_period=14, sensitivity=1.0)
    b2, s2, t2 = calculate_ut_signals(df, atr_period=14, sensitivity=1.0)

    pd.testing.assert_series_equal(t1, t2, check_names=False)
    pd.testing.assert_series_equal(b1, b2, check_names=False)
    pd.testing.assert_series_equal(s1, s2, check_names=False)


def _production_loop(df: pd.DataFrame, atr_period=10, sensitivity=1.0) -> pd.DataFrame:
    """Verbatim copy of strategies/ut_bot.py:116-154 for parity checking."""
    df = df.copy()
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = abs(df["high"] - df["close"].shift())
    df["low_close"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)
    df["atr"] = df["tr"].rolling(window=atr_period).mean()
    df["loss"] = sensitivity * df["atr"]
    df["trail_stop"] = 0.0
    for i in range(1, len(df)):
        close = df.iloc[i]["close"]
        prev_close = df.iloc[i - 1]["close"]
        prev_trail_stop = df.iloc[i - 1]["trail_stop"]
        loss = df.iloc[i]["loss"]
        if close > prev_trail_stop and prev_close > prev_trail_stop:
            df.at[df.index[i], "trail_stop"] = max(prev_trail_stop, close - loss)
        elif close < prev_trail_stop and prev_close < prev_trail_stop:
            df.at[df.index[i], "trail_stop"] = min(prev_trail_stop, close + loss)
        elif close > prev_trail_stop:
            df.at[df.index[i], "trail_stop"] = close - loss
        else:
            df.at[df.index[i], "trail_stop"] = close + loss
    df["prev_trail_stop"] = df["trail_stop"].shift()
    df["signal"] = 0
    df.loc[(df["close"] > df["trail_stop"]) & (df["close"].shift() <= df["prev_trail_stop"]), "signal"] = 1
    df.loc[(df["close"] < df["trail_stop"]) & (df["close"].shift() >= df["prev_trail_stop"]), "signal"] = -1
    return df


def test_compute_ut_signal_matches_production_loop():
    """Canonical vectorized signal == verbatim production loop."""
    df = _sample_df()
    prod = _production_loop(df, atr_period=10, sensitivity=1.0)
    ours = compute_ut_signal(df, atr_period=10, sensitivity=1.0)

    np.testing.assert_allclose(
        ours["trail_stop"].to_numpy(), prod["trail_stop"].to_numpy(), rtol=0, atol=1e-9
    )
    np.testing.assert_array_equal(ours["signal"].to_numpy(), prod["signal"].to_numpy())
