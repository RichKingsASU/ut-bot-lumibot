import sys
from pathlib import Path
import pytest

# Make repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from scripts.simulate_decay_recovery import (
    generate_trade_stream,
    calculate_ic_scalar,
    run_simulation
)


def test_generate_trade_stream():
    trades = generate_trade_stream(n_healthy=10, n_decay=10, n_recovery=10)
    assert len(trades) == 30
    for t in trades:
        assert "sig" in t
        assert "pnl" in t
        assert t["sig"] in [1, -1]
        assert isinstance(t["pnl"], float)


def test_calculate_ic_scalar():
    assert calculate_ic_scalar(0.05) == 1.0   # Healthy (>= 0.02)
    assert calculate_ic_scalar(0.01) == 0.75  # Degrading (>= 0.005)
    assert calculate_ic_scalar(0.002) == 0.50 # Weak (>= 0.0)
    assert calculate_ic_scalar(-0.01) == 0.0  # Dead (< 0.0)
    assert calculate_ic_scalar(None) == 1.0   # Fallback


def test_run_simulation_output():
    # Make a tiny stream of 60 trades
    trades = generate_trade_stream(n_healthy=20, n_decay=20, n_recovery=20)
    res = run_simulation(trades, lookback=10)
    
    assert res is not None
    assert "ic_scores" in res
    assert "ic_scalars" in res
    assert len(res["ic_scores"]) == len(trades)
    assert len(res["eq_static"]) == len(trades) + 1
    assert len(res["eq_adaptive"]) == len(trades) + 1
    assert "capital_saved" in res
    assert isinstance(res["capital_saved"], float)
