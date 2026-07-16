"""
DMA Crossover with Volatility Filter — signal research backtest.

Sweeps fast/slow MA periods and vol-filter thresholds on real daily SPY
2000-2026 with Kelly-optimal sizing, 1bp/side fee, and strict overfit guards.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from itertools import product
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[2]
DATA_FILE = Path("/mnt/tick-storage/historical/equities/SPY/SPY_1D_2000-01-03_2026-07-14.parquet")
RESULTS_DIR = REPO / "backtests" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Sweep grid ─────────────────────────────────────────────────────────────
FAST_PERIODS = [5, 10, 20, 50]
SLOW_PERIODS = [20, 50, 100, 200]
VOL_THRESHOLDS = [0.20, 0.25, 0.30, None]  # None = no filter

FEE_PER_SIDE = 0.0001  # 1bp equity ETF rate
KELLY_CAP = 0.25       # quarter-Kelly
KELLY_FLOOR = 0.05     # 5% floor
KELLY_LOOKBACK = 252   # rolling window for kelly estimation
INITIAL_CAPITAL = 100_000.0


@dataclass
class CellResult:
    fast: int
    slow: int
    vol_threshold: float | None
    trades: int
    gross_return: float
    net_return: float
    sharpe: float
    max_drawdown: float
    fee_drag_pct: float
    expectancy_per_trade: float
    avg_hold_days: float
    kelly_avg_size: float
    vol_filter_pct: float
    compound_return: float


def load_data() -> pd.DataFrame:
    if not DATA_FILE.exists():
        print(f"FATAL: real parquet not found at {DATA_FILE}", file=sys.stderr)
        sys.exit(1)
    df = pd.read_parquet(DATA_FILE)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")
    df = df.sort_index()
    df["close"] = df["close"].ffill()
    df = df.dropna(subset=["close"])
    print(f"Loaded {len(df)} daily bars: {df.index[0].date()} → {df.index[-1].date()}")
    return df


def compute_signal(close: pd.Series, fast: int, slow: int) -> pd.Series:
    """DMA crossover: +1 on golden cross, -1 on death cross, 0 hold."""
    fast_ma = close.rolling(fast).mean()
    slow_ma = close.rolling(slow).mean()

    cross_up = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
    cross_down = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

    signal = pd.Series(0, index=close.index)
    signal[cross_up] = 1
    signal[cross_down] = -1
    return signal


def compute_vol_filter(close: pd.Series, threshold: float | None) -> pd.Series:
    """True = allowed to enter. Exits are never filtered."""
    if threshold is None:
        return pd.Series(True, index=close.index)
    realized_vol = close.pct_change().rolling(20).std() * sqrt(252)
    return realized_vol < threshold


def run_cell(df: pd.DataFrame, fast: int, slow: int,
             vol_threshold: float | None) -> CellResult:
    close = df["close"].astype(float)
    signal = compute_signal(close, fast, slow)
    vol_ok = compute_vol_filter(close, vol_threshold)

    daily_ret = close.pct_change().fillna(0.0)

    # Rolling Kelly estimation
    rolling_mean = daily_ret.rolling(KELLY_LOOKBACK).mean()
    rolling_var = daily_ret.rolling(KELLY_LOOKBACK).var()

    position = pd.Series(0.0, index=close.index)
    cur_pos = 0.0  # +1 long, -1 short, 0 flat
    cur_size = 0.0

    entry_prices = []
    exit_prices = []
    hold_days_list = []
    kelly_sizes = []
    signals_total = 0
    signals_filtered = 0
    entry_day = 0

    trades = 0
    gross_pnl = 0.0
    net_pnl = 0.0
    entry_price = 0.0

    equity = np.ones(len(close)) * INITIAL_CAPITAL

    for i in range(1, len(close)):
        sig = signal.iloc[i]
        price = close.iloc[i]
        prev_price = close.iloc[i - 1]

        if sig != 0:
            signals_total += 1

        # Exit on reversal signal (regardless of vol filter)
        if cur_pos != 0 and sig != 0 and sig != cur_pos:
            trade_ret = (price / entry_price - 1) * cur_pos
            fee = FEE_PER_SIDE * 2  # entry + exit
            gross_pnl += trade_ret * cur_size
            net_pnl += (trade_ret - fee) * cur_size
            trades += 1
            hold_days_list.append(i - entry_day)
            cur_pos = 0.0
            cur_size = 0.0

        # Entry on signal (respects vol filter for NEW entries only)
        if sig != 0 and cur_pos == 0:
            if vol_ok.iloc[i]:
                # Kelly sizing from rolling estimates
                mu = rolling_mean.iloc[i] if not np.isnan(rolling_mean.iloc[i]) else 0.0
                var = rolling_var.iloc[i] if not np.isnan(rolling_var.iloc[i]) else 1.0
                if var > 0:
                    kelly_raw = mu / var
                else:
                    kelly_raw = 0.0
                kelly_f = max(KELLY_FLOOR, min(KELLY_CAP, abs(kelly_raw)))
                cur_pos = float(sig)
                cur_size = kelly_f
                entry_price = price
                entry_day = i
                kelly_sizes.append(kelly_f)
            else:
                signals_filtered += 1

        # Mark position for equity tracking
        if cur_pos != 0:
            day_ret = (price / prev_price - 1) * cur_pos * cur_size
        else:
            day_ret = 0.0

        equity[i] = equity[i - 1] * (1 + day_ret)

    # Close any open position at the end
    if cur_pos != 0:
        price = close.iloc[-1]
        trade_ret = (price / entry_price - 1) * cur_pos
        fee = FEE_PER_SIDE * 2
        gross_pnl += trade_ret * cur_size
        net_pnl += (trade_ret - fee) * cur_size
        trades += 1
        hold_days_list.append(len(close) - 1 - entry_day)

    # Metrics
    equity_series = pd.Series(equity, index=close.index)
    daily_equity_ret = equity_series.pct_change().dropna()

    if len(daily_equity_ret) > 1 and daily_equity_ret.std() > 0:
        sharpe = float(daily_equity_ret.mean() / daily_equity_ret.std() * sqrt(252))
    else:
        sharpe = 0.0

    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max
    max_dd = float(drawdown.min())

    compound_ret = (equity[-1] / INITIAL_CAPITAL) - 1.0
    gross_ret = gross_pnl
    net_ret = net_pnl
    fee_drag = (gross_pnl - net_pnl) / abs(gross_pnl) * 100 if gross_pnl != 0 else 0.0
    avg_hold = float(np.mean(hold_days_list)) if hold_days_list else 0.0
    avg_kelly = float(np.mean(kelly_sizes)) if kelly_sizes else 0.0
    vol_filt_pct = (signals_filtered / signals_total * 100) if signals_total > 0 else 0.0
    exp_per_trade = net_pnl / trades if trades > 0 else 0.0

    return CellResult(
        fast=fast,
        slow=slow,
        vol_threshold=vol_threshold,
        trades=trades,
        gross_return=round(gross_ret, 6),
        net_return=round(net_ret, 6),
        sharpe=round(sharpe, 4),
        max_drawdown=round(max_dd, 4),
        fee_drag_pct=round(fee_drag, 2),
        expectancy_per_trade=round(exp_per_trade, 6),
        avg_hold_days=round(avg_hold, 1),
        kelly_avg_size=round(avg_kelly, 4),
        vol_filter_pct=round(vol_filt_pct, 1),
        compound_return=round(compound_ret, 4),
    )


def neighbor_check(results: list[CellResult], top_n: int = 3) -> list[dict]:
    """Check whether the best N cells have similar-performing neighbors."""
    sorted_r = sorted(results, key=lambda r: r.sharpe, reverse=True)
    checks = []
    for cell in sorted_r[:top_n]:
        neighbors = []
        for r in results:
            if r is cell:
                continue
            fast_close = abs(r.fast - cell.fast) <= max(cell.fast, 5)
            slow_close = abs(r.slow - cell.slow) <= max(cell.slow // 4, 10)
            vol_close = (r.vol_threshold == cell.vol_threshold) or \
                        (r.vol_threshold is not None and cell.vol_threshold is not None and
                         abs(r.vol_threshold - cell.vol_threshold) <= 0.05)
            if fast_close and slow_close and vol_close:
                neighbors.append(r)

        neighbor_sharpes = [n.sharpe for n in neighbors]
        avg_neighbor = float(np.mean(neighbor_sharpes)) if neighbor_sharpes else 0.0
        checks.append({
            "cell": f"{cell.fast}/{cell.slow}/{'none' if cell.vol_threshold is None else cell.vol_threshold}",
            "sharpe": cell.sharpe,
            "neighbor_count": len(neighbors),
            "avg_neighbor_sharpe": round(avg_neighbor, 4),
            "isolated": len(neighbors) == 0 or avg_neighbor < cell.sharpe * 0.3,
        })
    return checks


def persist_to_supabase(results: list[CellResult]) -> int:
    """Write results to Supabase backtest_results table."""
    from dotenv import load_dotenv
    import httpx

    load_dotenv(REPO / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("WARNING: Supabase credentials not found, skipping persistence")
        return 0

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    rows = []
    for r in results:
        rows.append({
            "strategy": "dma_crossover_vol_filter",
            "symbol": "SPY",
            "timeframe": "1D",
            "total_return_pct": round(r.compound_return * 100, 4),
            "max_drawdown_pct": round(r.max_drawdown * 100, 4),
            "sharpe_ratio": r.sharpe,
            "total_trades": r.trades,
            "params": json.dumps({
                "fast": r.fast,
                "slow": r.slow,
                "vol_threshold": r.vol_threshold,
                "kelly_cap": KELLY_CAP,
                "kelly_floor": KELLY_FLOOR,
                "fee_per_side": FEE_PER_SIDE,
                "gross_return": r.gross_return,
                "net_return": r.net_return,
                "fee_drag_pct": r.fee_drag_pct,
                "expectancy_per_trade": r.expectancy_per_trade,
                "avg_hold_days": r.avg_hold_days,
                "kelly_avg_size": r.kelly_avg_size,
                "vol_filter_pct": r.vol_filter_pct,
                "data_provenance": "real_parquet",
            }),
        })

    def sanitize(obj):
        if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
            return None
        return obj

    for row in rows:
        for k, v in row.items():
            row[k] = sanitize(v)

    resp = httpx.post(
        f"{url}/rest/v1/backtest_results",
        headers=headers,
        json=rows,
        timeout=30,
    )
    if resp.status_code in (200, 201):
        print(f"Persisted {len(rows)} rows to Supabase backtest_results")
        return len(rows)
    else:
        print(f"Supabase write failed: {resp.status_code} {resp.text[:200]}")
        return 0


def main():
    df = load_data()

    # Build valid cells (fast < slow)
    grid = []
    for fast, slow, vol_t in product(FAST_PERIODS, SLOW_PERIODS, VOL_THRESHOLDS):
        if fast >= slow:
            continue
        grid.append((fast, slow, vol_t))

    print(f"Sweeping {len(grid)} cells...")
    results: list[CellResult] = []
    for i, (fast, slow, vol_t) in enumerate(grid):
        vol_label = "none" if vol_t is None else f"{vol_t:.0%}"
        print(f"  [{i+1}/{len(grid)}] fast={fast} slow={slow} vol={vol_label}", end="")
        r = run_cell(df, fast, slow, vol_t)
        results.append(r)
        print(f"  → trades={r.trades} sharpe={r.sharpe:.3f} compound={r.compound_return:.1%}")

    # Sort by Sharpe
    results.sort(key=lambda r: r.sharpe, reverse=True)

    # Best and median
    best = results[0]
    median_idx = len(results) // 2
    median = results[median_idx]

    # Neighbor check
    neighbors = neighbor_check(results)

    # Save JSON
    out_json = RESULTS_DIR / "dma_crossover_sweep.json"
    out_data = {
        "strategy": "dma_crossover_vol_filter",
        "data_source": "real_parquet",
        "data_file": str(DATA_FILE),
        "bars": len(df),
        "date_range": f"{df.index[0].date()} → {df.index[-1].date()}",
        "cells_swept": len(results),
        "fee_per_side": FEE_PER_SIDE,
        "kelly_cap": KELLY_CAP,
        "kelly_floor": KELLY_FLOOR,
        "initial_capital": INITIAL_CAPITAL,
        "best": asdict(best),
        "median": asdict(median),
        "neighbor_check": neighbors,
        "all_results": [asdict(r) for r in results],
    }
    out_json.write_text(json.dumps(out_data, indent=2, default=str))
    print(f"\nResults saved to {out_json}")

    # Print summary
    print("\n" + "=" * 80)
    print("DMA CROSSOVER VOL-FILTER SWEEP — REAL SPY 2000-2026")
    print("=" * 80)

    print(f"\n{'Rank':<5} {'Fast':<6} {'Slow':<6} {'Vol':<8} {'Trades':<8} "
          f"{'Sharpe':<9} {'Compound':<12} {'NetRet':<12} {'MaxDD':<10} "
          f"{'Exp/Trade':<12} {'AvgHold':<9} {'Kelly':<8} {'VolFilt%':<9}")
    print("-" * 120)
    for i, r in enumerate(results[:20]):
        vol_label = "none" if r.vol_threshold is None else f"{r.vol_threshold:.0%}"
        print(f"{i+1:<5} {r.fast:<6} {r.slow:<6} {vol_label:<8} {r.trades:<8} "
              f"{r.sharpe:<9.4f} {r.compound_return:<12.4f} {r.net_return:<12.6f} "
              f"{r.max_drawdown:<10.4f} {r.expectancy_per_trade:<12.6f} "
              f"{r.avg_hold_days:<9.1f} {r.kelly_avg_size:<8.4f} {r.vol_filter_pct:<9.1f}")

    print(f"\n── BEST CELL ──")
    print(f"  {best.fast}/{best.slow}/{'none' if best.vol_threshold is None else best.vol_threshold}")
    print(f"  Sharpe: {best.sharpe:.4f}  Compound: {best.compound_return:.4f}  "
          f"Trades: {best.trades}  MaxDD: {best.max_drawdown:.4f}")

    print(f"\n── MEDIAN CELL ──")
    print(f"  {median.fast}/{median.slow}/{'none' if median.vol_threshold is None else median.vol_threshold}")
    print(f"  Sharpe: {median.sharpe:.4f}  Compound: {median.compound_return:.4f}  "
          f"Trades: {median.trades}")

    print(f"\n── NEIGHBOR CHECK ──")
    for n in neighbors:
        status = "ISOLATED ⚠" if n["isolated"] else "SUPPORTED ✓"
        print(f"  {n['cell']}: sharpe={n['sharpe']:.4f} neighbors={n['neighbor_count']} "
              f"avg_neighbor={n['avg_neighbor_sharpe']:.4f} → {status}")

    # UT Bot baseline comparison
    utbot_sharpe = 0.060
    utbot_compound = -0.17
    print(f"\n── VS UT BOT BASELINE ──")
    print(f"  UT Bot best (10/2.5): net Sharpe={utbot_sharpe:.3f}  compound={utbot_compound:.0%}")
    print(f"  DMA best ({best.fast}/{best.slow}): net Sharpe={best.sharpe:.4f}  "
          f"compound={best.compound_return:.1%}")
    if best.sharpe > utbot_sharpe and best.compound_return > 0:
        verdict = "YES — positive net expectancy AND positive compound return"
        comparison = "BETTER"
    elif best.sharpe > utbot_sharpe:
        verdict = "PARTIAL — better Sharpe but compound return still negative"
        comparison = "MIXED"
    elif best.compound_return > 0:
        verdict = "PARTIAL — positive compound but worse Sharpe"
        comparison = "MIXED"
    else:
        verdict = "NO — edgeless, no improvement over UT Bot"
        comparison = "WORSE" if best.sharpe < utbot_sharpe else "SAME"

    print(f"\n══ HONEST VERDICT: {verdict}")
    print(f"══ DMA vs UT Bot: {comparison} on net Sharpe")

    # Persist to Supabase
    print("\n── SUPABASE PERSISTENCE ──")
    rows_written = persist_to_supabase(results)
    print(f"  Rows written: {rows_written}")

    return results, best, median, neighbors, verdict, comparison, rows_written


if __name__ == "__main__":
    main()
