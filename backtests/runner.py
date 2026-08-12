"""
Orchestration: wire data → signal → engine → metrics → report for one run,
and the ``--sweep`` grid over DTE × strike × timeframe.
"""

from __future__ import annotations

import os
from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from .config import BacktestConfig
from .data import load_underlying
from .engine import run_backtest, trades_to_frame
from .metrics import Summary, summarize
from .quotes import build_quote_provider
from .report import (
    assumptions_block,
    format_summary,
    save_equity_png,
    save_trades_csv,
)


def _credentials() -> Tuple[Optional[str], Optional[str]]:
    return os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_API_SECRET")


def run_single(cfg: BacktestConfig, verbose: bool = True) -> Tuple[Summary, pd.DataFrame, str, str]:
    """Run one configuration end-to-end. Returns (summary, trades_df, u_src, q_src)."""
    key, secret = _credentials()
    sd = load_underlying(cfg, key, secret)
    df = sd.data
    u_src = sd.provenance.value
    provider, q_src = build_quote_provider(cfg, key, secret)

    trades = run_backtest(df, cfg, provider)
    tdf = trades_to_frame(trades)
    summ = summarize(tdf)
    summ.data_provenance = u_src
    summ.data_rows = sd.rows

    results = Path(cfg.results_dir)
    tag = f"{cfg.symbol}_{cfg.timeframe}_dte{cfg.dte}_{cfg.strike_mode}"
    csv_path = results / f"trades_{tag}.csv"
    png_path = results / f"equity_{tag}.png"
    save_trades_csv(trades, csv_path)
    png = save_equity_png(trades, png_path, f"UT Bot options — {tag}")

    if verbose:
        print(assumptions_block(cfg, u_src, q_src, summ.bs_priced_pct, rows=sd.rows))
        print(format_summary(summ, cfg))
        
        # OOS Splits (50/50 Time Split)
        if len(tdf) > 4:
            mid_idx = len(tdf) // 2
            summ_is = summarize(tdf.iloc[:mid_idx])
            summ_oos = summarize(tdf.iloc[mid_idx:])
            print("\n  [ IN-SAMPLE (First 50%) ]")
            print(f"    Trades: {summ_is.trades} | Net P&L: ${summ_is.net_total:,.2f} | Win Rate: {summ_is.win_rate:.1%} | PF: {summ_is.profit_factor:.2f} | Sharpe: {summ_is.sharpe:.2f}")
            print("  [ OUT-OF-SAMPLE (Last 50%) ]")
            print(f"    Trades: {summ_oos.trades} | Net P&L: ${summ_oos.net_total:,.2f} | Win Rate: {summ_oos.win_rate:.1%} | PF: {summ_oos.profit_factor:.2f} | Sharpe: {summ_oos.sharpe:.2f}")
            
        print(f"\n  Per-trade CSV : {csv_path}")
        if png:
            print(f"  Equity PNG    : {png}")
        print(f"  Bars analyzed : {len(df)}  ({df.index.min()} → {df.index.max()})"
              if len(df) else "  Bars analyzed : 0")
    return summ, tdf, u_src, q_src


SWEEP_DTE = [3, 4, 5]
SWEEP_STRIKE = ["ATM", "ITM1", "ITM2"]
SWEEP_TF = ["5m", "15m"]


def run_sweep(base: BacktestConfig) -> pd.DataFrame:
    """Grid over DTE {3,4,5} × strike {ATM,ITM1,ITM2} × timeframe {5m,15m}."""
    rows = []
    u_src = q_src = ""
    for dte, strike, tf in product(SWEEP_DTE, SWEEP_STRIKE, SWEEP_TF):
        cfg = replace(base, dte=dte, strike_mode=strike, timeframe=tf)
        summ, _tdf, u_src, q_src = run_single(cfg, verbose=False)
        rows.append({
            "timeframe": tf,
            "dte": dte,
            "strike": strike,
            "trades": summ.trades,
            "win_rate": summ.win_rate,
            "expectancy_$": summ.expectancy_dollar,
            "expectancy_%": summ.expectancy_pct,
            "profit_factor": summ.profit_factor,
            "net_total": summ.net_total,
            "gross_total": summ.gross_total,
            "spread_cost": summ.total_spread_cost,
            "pct_edge_lost": summ.pct_edge_lost_to_spread,
            "sharpe": summ.sharpe,
            "max_dd": summ.max_drawdown,
        })
    grid = pd.DataFrame(rows)
    # Rank by net_total desc (primary edge), then expectancy%.
    grid = grid.sort_values(["net_total", "expectancy_%"], ascending=False).reset_index(drop=True)
    grid.insert(0, "rank", grid.index + 1)

    out = Path(base.results_dir) / "sweep_comparison.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(out, index=False)

    print(assumptions_block(base, u_src, q_src))
    print("\n════════════════════ SWEEP: ranked by NET total P&L ════════════════════\n")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(grid.to_string(index=False))
    print(f"\n  Comparison CSV : {out}")
    return grid
