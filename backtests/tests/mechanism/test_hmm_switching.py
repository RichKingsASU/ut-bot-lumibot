import sys
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from hmmlearn import hmm

# Make repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from scripts.backtest_hmm_switching import (
    generate_synthetic_data,
    extract_features,
    calculate_ut_signals,
    map_regimes,
    simulate_portfolio,
    evaluate_metrics
)


def test_generate_synthetic_data():
    df = generate_synthetic_data(date(2025, 1, 1), date(2025, 6, 1))
    assert df is not None
    assert len(df) > 100
    for col in ["open", "high", "low", "close", "volume"]:
        assert col in df.columns
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df["close"]).all()


def test_extract_features():
    df = generate_synthetic_data(date(2025, 1, 1), date(2025, 3, 1))
    feats = extract_features(df)
    assert feats is not None
    assert len(feats) > 0
    for col in ["returns", "volatility", "volume_ratio", "range_ratio"]:
        assert col in feats.columns
    # check that NaN rows are dropped
    assert not feats.isna().any().any()


def test_calculate_ut_signals():
    df = generate_synthetic_data(date(2025, 1, 1), date(2025, 3, 1))
    pos = calculate_ut_signals(df, atr_period=10, sensitivity=1.0)
    assert pos is not None
    assert len(pos) == len(df)
    # Positions should only contain 0.0 or 1.0 (long-only strategy simulator)
    assert set(pos.unique()).issubset({0.0, 1.0})


def test_map_regimes():
    # Construct mock model with distinct state means
    model = hmm.GaussianHMM(n_components=4)
    # Feature 0: return, Feature 1: vol
    model.means_ = np.array([
        [0.01, 0.005],   # highest return -> BULL
        [-0.01, 0.02],   # lowest return -> BEAR
        [0.0, 0.04],     # highest volatility of rest -> VOLATILE
        [0.0001, 0.002]  # lowest volatility of rest -> QUIET
    ])
    
    # map_regimes only reads means from model
    state_map = map_regimes(model, None)
    assert state_map[0] == "BULL"
    assert state_map[1] == "BEAR"
    assert state_map[2] == "VOLATILE"
    assert state_map[3] == "QUIET"


def test_simulate_portfolio_and_metrics():
    df = generate_synthetic_data(date(2025, 1, 1), date(2025, 3, 1))
    positions = pd.Series(1.0, index=df.index)  # Always fully long
    sizes = pd.Series(0.8, index=df.index)      # Constant 80% sizing scale
    
    init_cash = 10000.0
    eq_curve = simulate_portfolio(df, positions, sizes, init_cash=init_cash, fee_pct=0.001)
    
    assert eq_curve is not None
    assert len(eq_curve) == len(df)
    assert eq_curve.iloc[0] == init_cash
    
    metrics = evaluate_metrics(eq_curve, init_cash)
    assert "total_return" in metrics
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert isinstance(metrics["total_return"], float)
