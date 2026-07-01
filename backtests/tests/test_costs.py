"""
Cost-model tests: enter@ask+slip, exit@bid-slip, gross=mid-to-mid, spread paid.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtests.config import BacktestConfig
from backtests.costs import compute_costs, entry_fill, exit_fill
from backtests.quotes import Quote


def _cfg(**kw):
    defaults = dict(slippage_ticks=1.0, tick_size=0.01, commission_per_contract=0.0)
    defaults.update(kw)
    return BacktestConfig(**defaults)


def test_enter_ask_exit_bid_with_slippage():
    cfg = _cfg()
    entry_q = Quote(bid=1.00, ask=1.10, priced_via="bs")  # mid 1.05
    exit_q = Quote(bid=1.50, ask=1.60, priced_via="bs")   # mid 1.55

    ef = entry_fill(entry_q, cfg)
    xf = exit_fill(exit_q, cfg)

    # enter at ask + 1 tick; exit at bid - 1 tick
    assert ef.price == 1.11
    assert xf.price == 1.49
    assert ef.mid == 1.05
    assert xf.mid == 1.55


def test_gross_vs_net_and_spread_paid():
    cfg = _cfg()
    entry_q = Quote(bid=1.00, ask=1.10, priced_via="bs")  # mid 1.05
    exit_q = Quote(bid=1.50, ask=1.60, priced_via="bs")   # mid 1.55
    ef = entry_fill(entry_q, cfg)   # 1.11
    xf = exit_fill(exit_q, cfg)     # 1.49

    costs = compute_costs(ef, xf, qty=1, cfg=cfg)

    # gross = (1.55 - 1.05) * 100 = 50
    assert costs.gross_pnl == 50.0
    # net = (1.49 - 1.11) * 100 = 38
    assert costs.net_pnl == 38.0
    # spread+slippage cost = gross - net (no commission) = 12
    assert costs.spread_paid == 12.0


def test_commission_reduces_net():
    cfg = _cfg(commission_per_contract=0.65)
    entry_q = Quote(bid=1.00, ask=1.10, priced_via="bs")
    exit_q = Quote(bid=1.50, ask=1.60, priced_via="bs")
    ef = entry_fill(entry_q, cfg)
    xf = exit_fill(exit_q, cfg)
    costs = compute_costs(ef, xf, qty=2, cfg=cfg)

    # commission = 2 sides * 0.65 * 2 contracts = 2.60
    assert costs.commission == 2.60
    # net = (1.49-1.11)*100*2 - 2.60 = 76 - 2.60 = 73.40
    assert costs.net_pnl == 73.40
