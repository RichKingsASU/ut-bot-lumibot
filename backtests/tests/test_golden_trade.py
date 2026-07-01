"""
Golden-trade tests.

  * OCC symbol construction matches the format parsed by
    ``options_executor.sync_state_with_broker``.
  * A full engine run over a crafted V-shaped price path produces a trade whose
    fills and P&L accounting are exactly as the cost model dictates (constant
    quotes → known numbers, time-stop exit).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtests.config import BacktestConfig
from backtests.contracts import build_occ_symbol, select_contract
from backtests.engine import run_backtest, trades_to_frame
from backtests.quotes import Quote


def test_occ_symbol_roundtrip():
    """OCC symbol == SYMBOL+YYMMDD+C/P+strike*1000 (8-pad), re-parseable."""
    sym = build_occ_symbol("IWM", date(2024, 7, 5), "call", 200.0)
    assert sym == "IWM240705C00200000"

    # Re-parse exactly like sync_state_with_broker (options_executor.py:90-101).
    suffix = sym[len("IWM"):]              # 240705C00200000
    exp = f"20{suffix[0:2]}-{suffix[2:4]}-{suffix[4:6]}"
    otype = "call" if suffix[6].upper() == "C" else "put"
    strike = float(suffix[7:]) / 1000.0
    assert exp == "2024-07-05"
    assert otype == "call"
    assert strike == 200.0

    put = build_occ_symbol("IWM", date(2025, 12, 19), "put", 187.5)
    assert put == "IWM251219P00187500"


class _ConstStub:
    """Quote provider returning a fixed bid/ask regardless of time/underlying."""

    def get_quote(self, contract, underlying_price, ts):
        return Quote(bid=1.00, ask=1.10, priced_via="bs")


def _v_shaped_df(n_side: int = 40) -> pd.DataFrame:
    """Down-then-up path guaranteed to produce a UT crossover (a signal)."""
    down = np.linspace(200, 188, n_side)
    up = np.linspace(188, 205, n_side)
    close = np.concatenate([down, up])
    idx = pd.date_range("2024-06-03 09:30", periods=len(close), freq="15min",
                        tz="America/New_York")
    return pd.DataFrame(
        {"open": close, "high": close + 0.2, "low": close - 0.2, "close": close},
        index=idx,
    )


def test_golden_engine_trade():
    df = _v_shaped_df()
    cfg = BacktestConfig(
        symbol="IWM", timeframe="15m", dte=4, strike_mode="ATM",
        slippage_ticks=1.0, tick_size=0.01, commission_per_contract=0.0,
        time_stop_min=0,            # force a deterministic time-stop exit
        profit_target=99.0, premium_stop=99.0, stop_pct=99.0,
        rsi_step_thresh=999.0,      # disable other exits
    )
    trades = run_backtest(df, cfg, _ConstStub())
    assert len(trades) >= 1

    t = trades[0]
    # constant quotes: enter@ask+slip, exit@bid-slip
    assert t.entry_fill == 1.11
    assert t.exit_fill == 0.99
    assert t.entry_mid == 1.05 and t.exit_mid == 1.05
    # gross mid-to-mid = 0; net = -(spread+slippage) = -12
    assert t.gross_pnl == 0.0
    assert t.net_pnl == -12.0
    assert t.spread_paid == 12.0
    assert t.exit_reason == "time_stop"
    # long premium: LONG->call, SHORT->put; symbol well-formed
    assert t.option_type in ("call", "put")
    assert t.contract_symbol.startswith("IWM")
    assert len(t.contract_symbol) == len("IWM240705C00200000")


def test_frame_has_all_columns():
    df = _v_shaped_df()
    cfg = BacktestConfig(time_stop_min=0, profit_target=99, premium_stop=99,
                         stop_pct=99, rsi_step_thresh=999)
    tdf = trades_to_frame(run_backtest(df, cfg, _ConstStub()))
    for col in ["gross_pnl", "net_pnl", "spread_paid", "exit_reason", "priced_via"]:
        assert col in tdf.columns
