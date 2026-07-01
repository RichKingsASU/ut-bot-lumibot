#!/usr/bin/env python3
"""
UT Bot options backtest — CLI entry point.

Answers: does the UT Bot ATR signal have a tradeable edge as long IWM options
(3-5 DTE, intraday scalps) AFTER paying the bid-ask spread and theta?

Examples
--------
  python scripts/run_options_backtest.py \
      --symbol IWM --timeframe 15m --dte 4 --strike ATM \
      --start 2024-06-01 --end 2026-06-01 \
      --time-stop-min 20 --profit-target 0.5 --premium-stop 0.4

  python scripts/run_options_backtest.py --sweep

All new code lives under backtests/; this script is a thin wrapper.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# Make the repo root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtests.config import BacktestConfig
from backtests.runner import run_single, run_sweep


def _date(s: str) -> date:
    return date.fromisoformat(s)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="UT Bot IWM options backtest harness")
    p.add_argument("--symbol", default="IWM")
    p.add_argument("--timeframe", default="15m", choices=["5m", "15m"])
    p.add_argument("--dte", type=int, default=4)
    p.add_argument("--strike", default="ATM",
                   choices=["ITM3", "ITM2", "ITM1", "ATM", "OTM1", "OTM2", "OTM3"])
    p.add_argument("--start", type=_date, default=date(2024, 6, 1))
    p.add_argument("--end", type=_date, default=date(2026, 6, 1))
    # scalp exits
    p.add_argument("--time-stop-min", type=int, default=20, dest="time_stop_min")
    p.add_argument("--profit-target", type=float, default=0.5, dest="profit_target")
    p.add_argument("--premium-stop", type=float, default=0.4, dest="premium_stop")
    # cost model
    p.add_argument("--slippage-ticks", type=float, default=1.0, dest="slippage_ticks")
    p.add_argument("--tick-size", type=float, default=0.01, dest="tick_size")
    p.add_argument("--spread-frac", type=float, default=0.0075, dest="spread_frac")
    p.add_argument("--commission", type=float, default=0.0, dest="commission_per_contract")
    p.add_argument("--contracts", type=int, default=1)
    # pricing
    p.add_argument("--base-iv", type=float, default=0.20, dest="base_iv")
    p.add_argument("--risk-free-rate", type=float, default=0.04, dest="risk_free_rate")
    # data
    p.add_argument("--no-synthetic", action="store_true",
                   help="fail instead of falling back to synthetic underlying data")
    p.add_argument("--sweep", action="store_true",
                   help="grid over DTE{3,4,5} x strike{ATM,ITM1,ITM2} x tf{5m,15m}")
    return p


def config_from_args(args) -> BacktestConfig:
    return BacktestConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=args.start,
        end=args.end,
        dte=args.dte,
        strike_mode=args.strike,
        time_stop_min=args.time_stop_min,
        profit_target=args.profit_target,
        premium_stop=args.premium_stop,
        slippage_ticks=args.slippage_ticks,
        tick_size=args.tick_size,
        spread_frac=args.spread_frac,
        commission_per_contract=args.commission_per_contract,
        contracts=args.contracts,
        base_iv=args.base_iv,
        risk_free_rate=args.risk_free_rate,
        allow_synthetic=not args.no_synthetic,
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = config_from_args(args)
    if args.sweep:
        run_sweep(cfg)
    else:
        run_single(cfg, verbose=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
