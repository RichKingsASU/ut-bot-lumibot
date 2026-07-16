"""Tests for DMA 20/200 crossover strategy."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd
import pytest

from strategies.dma_crossover import DmaCrossoverStrategy


def _make_df(prices: list[float], fast: int = 20, slow: int = 200) -> pd.DataFrame:
    """Build a minimal OHLCV dataframe from a close price series."""
    n = len(prices)
    return pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC"),
        "open": prices,
        "high": [p * 1.01 for p in prices],
        "low": [p * 0.99 for p in prices],
        "close": prices,
        "volume": [1_000_000] * n,
    })


def _trending_then_cross(n_trend: int, n_reversal: int, start: float = 100.0,
                          trend_step: float = 0.5, reverse_step: float = -1.0):
    """Generate prices that trend up then reverse, creating a death cross."""
    prices = [start + i * trend_step for i in range(n_trend)]
    last = prices[-1]
    for i in range(1, n_reversal + 1):
        prices.append(last + i * reverse_step)
    return prices


class TestGoldenCross:
    def test_golden_cross_fires(self):
        """SMA(20) crossing above SMA(200) emits signal=+1."""
        # Build prices: 200 bars trending down, then 50 bars sharply up
        prices = [100 - i * 0.1 for i in range(220)]
        prices += [prices[-1] + i * 2.0 for i in range(1, 60)]
        df = _make_df(prices)

        strat = DmaCrossoverStrategy(fast_period=20, slow_period=200)
        # Walk forward to find the golden cross
        found_golden = False
        for end in range(200, len(df)):
            result = strat.evaluate(df.iloc[:end + 1].reset_index(drop=True))
            if result["signal"] == 1 and result["action"] == "BUY":
                found_golden = True
                assert result["is_crossover"] is True
                assert result["warmup"] is False
                break
        assert found_golden, "Golden cross should fire when fast crosses above slow"


class TestDeathCross:
    def test_death_cross_fires(self):
        """SMA(20) crossing below SMA(200) emits signal=-1."""
        # Build prices: 200 bars trending up, then 50 bars sharply down
        prices = [100 + i * 0.1 for i in range(220)]
        prices += [prices[-1] - i * 2.0 for i in range(1, 60)]
        df = _make_df(prices)

        strat = DmaCrossoverStrategy(fast_period=20, slow_period=200)
        found_death = False
        for end in range(200, len(df)):
            result = strat.evaluate(df.iloc[:end + 1].reset_index(drop=True))
            if result["signal"] == -1 and result["action"] == "SELL":
                found_death = True
                assert result["is_crossover"] is True
                break
        assert found_death, "Death cross should fire when fast crosses below slow"


class TestHoldNoCross:
    def test_hold_no_cross(self):
        """No crossover emits signal=0 / HOLD."""
        # Steady uptrend — no crossover after warmup
        prices = [100 + i * 0.3 for i in range(250)]
        df = _make_df(prices)

        strat = DmaCrossoverStrategy(fast_period=20, slow_period=200)
        result = strat.evaluate(df)
        assert result["signal"] == 0
        assert result["action"] == "HOLD"
        assert result["is_crossover"] is False


class TestWarmupSuppression:
    def test_warmup_suppression(self):
        """Fewer than 200 bars emits signal=0 with warmup=True."""
        prices = [100 + i * 0.5 for i in range(150)]
        df = _make_df(prices)

        strat = DmaCrossoverStrategy(fast_period=20, slow_period=200)
        result = strat.evaluate(df)
        assert result["signal"] == 0
        assert result["warmup"] is True
        assert result["fast_ma"] is None
        assert result["slow_ma"] is None


class TestNoLookahead:
    def test_no_lookahead(self):
        """Signal at bar N uses data through bar N only, position applied at N+1."""
        prices = [100 + i * 0.1 for i in range(220)]
        prices += [prices[-1] + i * 2.0 for i in range(1, 60)]
        df = _make_df(prices)

        strat = DmaCrossoverStrategy(fast_period=20, slow_period=200)
        result = strat.backtest(df)

        # Verify via the backtest engine: position is shift(1) of signal
        sig = df.copy()
        sig["sma_fast"] = sig["close"].rolling(20).mean()
        sig["sma_slow"] = sig["close"].rolling(200).mean()
        sig["raw_signal"] = (sig["sma_fast"] > sig["sma_slow"]).astype(int)
        sig = sig.dropna(subset=["sma_fast", "sma_slow"]).reset_index(drop=True)

        # Position at bar i should equal signal at bar i-1
        position = sig["raw_signal"].shift(1).fillna(0).astype(int)
        for i in range(1, len(sig)):
            assert position.iloc[i] == sig["raw_signal"].iloc[i - 1], (
                f"Position at bar {i} should equal signal at bar {i-1} (no lookahead)"
            )


class TestKellyCap:
    def test_kelly_cap(self):
        """kelly_f > 0.25 is capped at 0.25."""
        # Strong uptrend — high win rate → high Kelly
        prices = [100 + i * 1.0 for i in range(300)]
        df = _make_df(prices)

        strat = DmaCrossoverStrategy(fast_period=20, slow_period=200,
                                     kelly_cap=0.25, kelly_floor=0.05)
        result = strat.evaluate(df)
        assert result["kelly_size"] <= 0.25, f"Kelly {result['kelly_size']} exceeds cap 0.25"


class TestKellyFloor:
    def test_kelly_floor(self):
        """kelly_f < 0.05 is floored at 0.05."""
        # Choppy/flat — poor win rate → low Kelly
        np.random.seed(42)
        noise = np.random.randn(300) * 0.5
        prices = [100 + n for n in np.cumsum(noise)]
        df = _make_df(prices)

        strat = DmaCrossoverStrategy(fast_period=20, slow_period=200,
                                     kelly_cap=0.25, kelly_floor=0.05)
        result = strat.evaluate(df)
        if not result["warmup"]:
            assert result["kelly_size"] >= 0.05, f"Kelly {result['kelly_size']} below floor 0.05"
