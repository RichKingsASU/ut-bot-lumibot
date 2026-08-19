import numpy as np
import pandas as pd

from strategies.ut_bot_logic import calculate_ut_bot_signals


def test_signal_generation_matches_production_calculation():
    dates = pd.date_range(start="2026-01-01", periods=20, freq="D")
    closes = [100.0 + i for i in range(15)] + [80.0, 79.0, 78.0, 77.0, 76.0]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": [close + 2 for close in closes],
            "low": [close - 2 for close in closes],
            "close": closes,
            "volume": np.ones(20) * 1000,
        },
        index=dates,
    )

    result = calculate_ut_bot_signals(df, atr_period=10, sensitivity=1.0)

    assert result is df
    assert result["atr"].iloc[:9].isna().all()
    assert result["trail_stop"].iloc[9] == 105.0
    assert result["signal"].tolist() == ([0] * 15) + [-1] + ([0] * 4)
