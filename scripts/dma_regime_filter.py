#!/usr/bin/env python3
"""
DMA Regime Filter Research — Fix choppy-market weakness.

Fix 1: Longer SMA pairs (10/50, 20/100, 20/200, 50/200)
Fix 2: ADX regime filter (thresholds 15, 20, 25, 30)
Fix 3: Combined best-of-both

Builds on dma_validation.py engine with 1-bar delay, 1bp fee, quarter-Kelly.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np
import pandas as pd

STORAGE_ROOT = Path("/mnt/tick-storage/historical/equities")
RESULTS_DIR = Path(_REPO_ROOT) / "backtests" / "results"

FEE_PER_SIDE = 0.0001
INITIAL_CAPITAL = 100_000.0
TRADING_DAYS = 252

SUBPERIODS = [
    ("2000-2006", "2000-01-01", "2006-12-31"),
    ("2007-2012", "2007-01-01", "2012-12-31"),
    ("2013-2019", "2013-01-01", "2019-12-31"),
    ("2020-2026", "2020-01-01", "2026-12-31"),
]


def load_daily(symbol: str) -> pd.DataFrame:
    sym_dir = STORAGE_ROOT / symbol
    files = sorted(sym_dir.glob(f"{symbol}_1D_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No daily data for {symbol} in {sym_dir}")
    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    if "ts" in df.columns and "timestamp" not in df.columns:
        df = df.rename(columns={"ts": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    df = df.dropna(subset=["close"])
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df[["timestamp", "open", "high", "low", "close", "volume"]].copy()


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr_s = pd.Series(tr.values, index=df.index).ewm(span=period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(span=period, adjust=False).mean() / atr_s
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(span=period, adjust=False).mean() / atr_s
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    adx = dx.ewm(span=period, adjust=False).mean()
    return adx


def backtest_dma(
    df: pd.DataFrame,
    fast: int = 5,
    slow: int = 20,
    fee_per_side: float = FEE_PER_SIDE,
    vol_threshold: float | None = None,
    adx_threshold: float | None = None,
) -> dict:
    sig = df.copy()
    sig["sma_fast"] = sig["close"].rolling(fast).mean()
    sig["sma_slow"] = sig["close"].rolling(slow).mean()
    sig["raw_signal"] = (sig["sma_fast"] > sig["sma_slow"]).astype(int)
    sig["signal"] = sig["raw_signal"]
    sig = sig.dropna(subset=["sma_fast", "sma_slow"]).reset_index(drop=True)

    if vol_threshold is not None:
        sig["realized_vol_20d"] = sig["close"].pct_change().rolling(20).std() * np.sqrt(TRADING_DAYS)
        sig.loc[sig["realized_vol_20d"] >= vol_threshold, "signal"] = 0

    if adx_threshold is not None:
        adx = compute_adx(sig, period=14)
        sig["adx"] = adx.values
        # Gate NEW entries only: if currently flat and ADX < threshold, suppress entry
        # Exits are NOT gated — once in a position, stay until crossover says exit
        sig["prev_signal"] = sig["signal"].shift(1).fillna(0).astype(int)
        for i in range(1, len(sig)):
            if sig.loc[sig.index[i], "signal"] == 1 and sig.loc[sig.index[i - 1], "signal"] == 0:
                # New entry attempt
                if sig.loc[sig.index[i], "adx"] < adx_threshold:
                    sig.loc[sig.index[i], "signal"] = 0
            elif sig.loc[sig.index[i], "signal"] == 1 and sig.loc[sig.index[i - 1], "signal"] == 1:
                # Continuing position — don't gate (but if prev was gated, this is also new)
                pass
        # Re-propagate: if entry was suppressed, position stays flat until next valid entry
        # Walk forward to handle cascading suppressions
        for i in range(1, len(sig)):
            prev_pos = sig.loc[sig.index[i - 1], "signal"]
            curr_raw = sig.loc[sig.index[i], "raw_signal"]
            curr_sig = sig.loc[sig.index[i], "signal"]
            if curr_raw == 1 and prev_pos == 0 and curr_sig == 1:
                if sig.loc[sig.index[i], "adx"] < adx_threshold:
                    sig.loc[sig.index[i], "signal"] = 0

    sig["daily_return"] = sig["close"].pct_change()
    sig["position"] = sig["signal"].shift(1).fillna(0).astype(int)
    sig["trade"] = sig["position"].diff().abs().fillna(0)
    sig["strat_return"] = sig["position"] * sig["daily_return"]
    sig.loc[sig["trade"] > 0, "strat_return"] -= fee_per_side
    sig = sig.dropna(subset=["strat_return"])

    sig["equity"] = INITIAL_CAPITAL * (1 + sig["strat_return"]).cumprod()

    entries = sig[sig["position"].diff() == 1]
    n_trades = len(entries)

    n_years = len(sig) / TRADING_DAYS
    returns = sig["strat_return"]
    compound_return = (sig["equity"].iloc[-1] / INITIAL_CAPITAL - 1) * 100
    ann_return = returns.mean() * TRADING_DAYS
    ann_vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

    peak = sig["equity"].cummax()
    drawdown = (sig["equity"] - peak) / peak
    max_dd = drawdown.min() * 100

    trades_per_year = n_trades / n_years if n_years > 0 else 0

    start_date = sig["timestamp"].iloc[0]
    end_date = sig["timestamp"].iloc[-1]

    return {
        "fast": fast,
        "slow": slow,
        "vol_threshold": vol_threshold,
        "adx_threshold": adx_threshold,
        "start_date": str(start_date.date()) if hasattr(start_date, "date") else str(start_date),
        "end_date": str(end_date.date()) if hasattr(end_date, "date") else str(end_date),
        "n_years": round(n_years, 1),
        "trades": n_trades,
        "trades_per_year": round(trades_per_year, 1),
        "net_sharpe": round(sharpe, 3),
        "compound_return": round(compound_return, 1),
        "max_drawdown": round(max_dd, 1),
        "final_equity": round(sig["equity"].iloc[-1], 2),
    }


def run_subperiods(df_full: pd.DataFrame, fast: int, slow: int,
                   vol_threshold=None, adx_threshold=None) -> dict:
    results = {}
    for label, start, end in SUBPERIODS:
        mask = (df_full["timestamp"] >= pd.Timestamp(start, tz="UTC")) & \
               (df_full["timestamp"] <= pd.Timestamp(end, tz="UTC"))
        df_sub = df_full[mask].reset_index(drop=True)
        if len(df_sub) < slow + 20:
            results[label] = {"net_sharpe": float("nan"), "trades": 0}
            continue
        r = backtest_dma(df_sub, fast, slow, vol_threshold=vol_threshold,
                         adx_threshold=adx_threshold)
        results[label] = r
    return results


# ═══════════════════════════════════════════════════════════════════
# FIX 1: Longer SMA pairs
# ═══════════════════════════════════════════════════════════════════
def fix1_longer_pairs(df_spy: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("FIX 1: Longer SMA Pairs")
    print("=" * 70)

    pairs = [(10, 50), (20, 100), (20, 200), (50, 200)]
    results = []

    for fast, slow in pairs:
        for vol_thresh in [None, 0.20]:
            label = f"{fast}/{slow}" + (" +vol" if vol_thresh else "")
            r = backtest_dma(df_spy, fast, slow, vol_threshold=vol_thresh)
            subs = run_subperiods(df_spy, fast, slow, vol_threshold=vol_thresh)

            cell = {
                "label": label,
                "fast": fast,
                "slow": slow,
                "vol_threshold": vol_thresh,
                "full": r,
                "subperiods": subs,
            }
            results.append(cell)

            sub_sharpes = {k: v["net_sharpe"] for k, v in subs.items()}
            worst_sub = min(sub_sharpes.values())
            print(f"  {label:16s} | Sharpe={r['net_sharpe']:+.3f} | "
                  f"compound={r['compound_return']:+.1f}% | trades={r['trades']:3d} | "
                  f"worst_sub={worst_sub:+.3f}")

    # Find pair with highest WORST sub-period Sharpe
    best = max(results, key=lambda c: min(
        v["net_sharpe"] for v in c["subperiods"].values()
        if not (isinstance(v["net_sharpe"], float) and np.isnan(v["net_sharpe"]))
    ))
    worst_of_best = min(v["net_sharpe"] for v in best["subperiods"].values()
                        if not (isinstance(v["net_sharpe"], float) and np.isnan(v["net_sharpe"])))
    print(f"\n  BEST (most stable): {best['label']} | worst subperiod={worst_of_best:+.3f}")

    return {"cells": results, "best": best}


# ═══════════════════════════════════════════════════════════════════
# FIX 2: ADX regime filter
# ═══════════════════════════════════════════════════════════════════
def fix2_adx_filter(df_spy: pd.DataFrame, best_pair: dict) -> dict:
    print("\n" + "=" * 70)
    print("FIX 2: ADX Regime Filter")
    print("=" * 70)

    best_fast = best_pair["fast"]
    best_slow = best_pair["slow"]
    best_vol = best_pair.get("vol_threshold")

    test_pairs = [
        (5, 20, "5/20 (original)"),
        (best_fast, best_slow, f"{best_fast}/{best_slow} (Fix1 best)"),
    ]
    adx_thresholds = [15, 20, 25, 30]
    results = []

    for fast, slow, pair_label in test_pairs:
        for adx_t in adx_thresholds:
            label = f"{pair_label} ADX>{adx_t}"
            r = backtest_dma(df_spy, fast, slow, vol_threshold=best_vol,
                             adx_threshold=adx_t)
            subs = run_subperiods(df_spy, fast, slow, vol_threshold=best_vol,
                                  adx_threshold=adx_t)

            cell = {
                "label": label,
                "fast": fast,
                "slow": slow,
                "vol_threshold": best_vol,
                "adx_threshold": adx_t,
                "full": r,
                "subperiods": subs,
            }
            results.append(cell)

            sub_sharpes = {k: v["net_sharpe"] for k, v in subs.items()}
            s2000 = sub_sharpes.get("2000-2006", float("nan"))
            print(f"  {label:35s} | Sharpe={r['net_sharpe']:+.3f} | "
                  f"compound={r['compound_return']:+.1f}% | trades={r['trades']:3d} | "
                  f"2000-2006={s2000:+.3f}")

    # Find threshold where 2000-2006 turns positive
    turn_positive = None
    for cell in results:
        s = cell["subperiods"].get("2000-2006", {}).get("net_sharpe", -1)
        if s > 0 and turn_positive is None:
            turn_positive = cell["adx_threshold"]

    print(f"\n  2000-2006 turns positive at: ADX>{turn_positive}" if turn_positive
          else "\n  2000-2006 NEVER turns positive with ADX filter alone")

    return {"cells": results, "turn_positive_threshold": turn_positive}


# ═══════════════════════════════════════════════════════════════════
# FIX 3: Combined approach
# ═══════════════════════════════════════════════════════════════════
def _evaluate_candidate(df_spy, fast, slow, vol_thresh, adx_thresh, label) -> dict:
    print(f"\n  Candidate: {label}")
    print(f"    Config: {fast}/{slow} + vol<{vol_thresh} + ADX>{adx_thresh}")

    spy_full = backtest_dma(df_spy, fast, slow, vol_threshold=vol_thresh,
                            adx_threshold=adx_thresh)
    spy_subs = run_subperiods(df_spy, fast, slow, vol_threshold=vol_thresh,
                              adx_threshold=adx_thresh)

    print(f"    SPY full: Sharpe={spy_full['net_sharpe']:+.3f} | "
          f"compound={spy_full['compound_return']:+.1f}% | trades={spy_full['trades']} | "
          f"tpy={spy_full['trades_per_year']:.1f}")
    for plabel, r in spy_subs.items():
        print(f"      {plabel}: Sharpe={r['net_sharpe']:+.3f}")

    realistic = backtest_dma(df_spy, fast, slow, fee_per_side=0.0006,
                             vol_threshold=vol_thresh, adx_threshold=adx_thresh)
    print(f"    Realistic (6bp): Sharpe={realistic['net_sharpe']:+.3f}")

    oos_results = {}
    for symbol in ["QQQ", "GLD", "IWM", "TLT"]:
        try:
            df = load_daily(symbol)
            r = backtest_dma(df, fast, slow, vol_threshold=vol_thresh,
                             adx_threshold=adx_thresh)
            oos_results[symbol] = r
            verdict = "PASS" if r["net_sharpe"] > 0.3 else (
                "MARGINAL" if r["net_sharpe"] >= 0 else "FAIL")
            print(f"    OOS {symbol}: Sharpe={r['net_sharpe']:+.3f} | {verdict}")
        except FileNotFoundError as e:
            print(f"    OOS {symbol}: NO_DATA — {e}")

    all_sub_positive = all(v["net_sharpe"] > 0 for v in spy_subs.values()
                          if not (isinstance(v["net_sharpe"], float) and np.isnan(v["net_sharpe"])))
    oos_passes = sum(1 for v in oos_results.values() if v["net_sharpe"] > 0.3)
    tpy = spy_full["trades_per_year"]

    criteria = {
        "full_sharpe_gt_040": spy_full["net_sharpe"] > 0.40,
        "all_subperiods_positive": all_sub_positive,
        "oos_3_of_4_pass": oos_passes >= 3,
        "realistic_sharpe_gt_030": realistic["net_sharpe"] > 0.30,
        "trades_per_year_gt_5": tpy > 5,
        "trades_per_year_lt_100": tpy < 100,
    }
    n_passed = sum(criteria.values())

    if n_passed == 6:
        verdict = "DEPLOY-READY"
    elif n_passed >= 4:
        verdict = "RESEARCH-FURTHER"
    else:
        verdict = "DO-NOT-DEPLOY"

    worst_sub = min(v["net_sharpe"] for v in spy_subs.values()
                    if not (isinstance(v["net_sharpe"], float) and np.isnan(v["net_sharpe"])))

    print(f"    CRITERIA: {n_passed}/6 | {verdict}")
    for k, v in criteria.items():
        status = "PASS" if v else "FAIL"
        print(f"      [{status}] {k}")

    return {
        "label": label,
        "config": {"fast": fast, "slow": slow, "vol_threshold": vol_thresh,
                   "adx_threshold": adx_thresh},
        "spy_full": spy_full,
        "spy_subperiods": spy_subs,
        "realistic": realistic,
        "oos": oos_results,
        "criteria": criteria,
        "n_passed": n_passed,
        "verdict": verdict,
        "worst_subperiod_sharpe": worst_sub,
    }


def fix3_combined(df_spy: pd.DataFrame, fix1_result: dict, fix2_result: dict) -> dict:
    print("\n" + "=" * 70)
    print("FIX 3: Combined Approach — Testing Multiple Candidates")
    print("=" * 70)

    best_pair = fix1_result["best"]

    # Find best ADX threshold from Fix 2 for the best pair
    fix2_cells_best = [c for c in fix2_result["cells"]
                       if c["fast"] == best_pair["fast"] and c["slow"] == best_pair["slow"]]
    if not fix2_cells_best:
        fix2_cells_best = fix2_result["cells"]
    best_adx_cell = max(fix2_cells_best, key=lambda c: c["full"]["net_sharpe"])
    best_adx = best_adx_cell["adx_threshold"]

    # Also find best ADX for 5/20
    fix2_cells_520 = [c for c in fix2_result["cells"] if c["fast"] == 5 and c["slow"] == 20]
    best_adx_520 = max(fix2_cells_520, key=lambda c: c["full"]["net_sharpe"])["adx_threshold"] if fix2_cells_520 else 20

    # Test multiple candidates to find the one that passes the most criteria
    candidates = [
        (best_pair["fast"], best_pair["slow"], best_pair.get("vol_threshold"), best_adx,
         f"A: {best_pair['fast']}/{best_pair['slow']}+ADX>{best_adx} (Fix1 best)"),
        (20, 200, None, best_adx,
         f"B: 20/200+ADX>{best_adx} (more trades)"),
        (20, 100, None, best_adx,
         f"C: 20/100+ADX>{best_adx} (even more trades)"),
        (10, 50, None, 20,
         "D: 10/50+ADX>20 (highest freq stable)"),
        (5, 20, 0.20, best_adx_520,
         f"E: 5/20+vol+ADX>{best_adx_520} (original enhanced)"),
    ]

    results = []
    for fast, slow, vol_thresh, adx_thresh, label in candidates:
        r = _evaluate_candidate(df_spy, fast, slow, vol_thresh, adx_thresh, label)
        results.append(r)

    # Pick winner: most criteria passed, then highest full Sharpe as tiebreaker
    winner = max(results, key=lambda r: (r["n_passed"], r["spy_full"]["net_sharpe"]))

    print(f"\n  {'=' * 60}")
    print(f"  WINNER: {winner['label']} — {winner['n_passed']}/6 criteria | "
          f"Sharpe={winner['spy_full']['net_sharpe']:+.3f} | {winner['verdict']}")

    # Return winner as the primary result, but include all candidates
    winner["all_candidates"] = results
    return winner


# ═══════════════════════════════════════════════════════════════════
# Report + persist
# ═══════════════════════════════════════════════════════════════════
def generate_report(fix1, fix2, fix3) -> str:
    lines = [
        "# DMA Regime Filter Research Report",
        "",
        f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "**Branch**: research/dma-regime-filter",
        "**Baseline**: DMA 5/20 Sharpe=0.336 (with vol filter: 0.396)",
        "**Problem**: negative Sharpe in 2000-2006 (-0.083) and 2007-2012 (-0.075)",
        "",
        "---",
        "",
        "## Fix 1: Longer SMA Pairs (SPY 2000-2026)",
        "",
        "| Pair | Vol Filter | Full Sharpe | Compound | Trades | "
        "2000-2006 | 2007-2012 | 2013-2019 | 2020-2026 |",
        "|------|-----------|-------------|----------|--------|"
        "-----------|-----------|-----------|-----------|",
    ]
    for cell in fix1["cells"]:
        vf = "0.20" if cell["vol_threshold"] else "none"
        f = cell["full"]
        s = cell["subperiods"]
        lines.append(
            f"| {cell['fast']}/{cell['slow']} | {vf} | "
            f"{f['net_sharpe']:+.3f} | {f['compound_return']:+.1f}% | {f['trades']} | "
            f"{s['2000-2006']['net_sharpe']:+.3f} | "
            f"{s['2007-2012']['net_sharpe']:+.3f} | "
            f"{s['2013-2019']['net_sharpe']:+.3f} | "
            f"{s['2020-2026']['net_sharpe']:+.3f} |"
        )

    best = fix1["best"]
    worst_of_best = min(v["net_sharpe"] for v in best["subperiods"].values()
                        if not (isinstance(v["net_sharpe"], float) and np.isnan(v["net_sharpe"])))
    lines += [
        "",
        f"**Most stable pair**: {best['label']} — worst sub-period Sharpe = {worst_of_best:+.3f}",
        "",
        "---",
        "",
        "## Fix 2: ADX Regime Filter",
        "",
        f"Applied to 5/20 (original) and {best['fast']}/{best['slow']} (Fix 1 best), "
        f"vol filter = {best.get('vol_threshold', 'none')}",
        "",
        "| Pair | ADX Threshold | Full Sharpe | Compound | Trades | "
        "2000-2006 | 2007-2012 | 2013-2019 | 2020-2026 |",
        "|------|--------------|-------------|----------|--------|"
        "-----------|-----------|-----------|-----------|",
    ]
    for cell in fix2["cells"]:
        f = cell["full"]
        s = cell["subperiods"]
        lines.append(
            f"| {cell['fast']}/{cell['slow']} | >{cell['adx_threshold']} | "
            f"{f['net_sharpe']:+.3f} | {f['compound_return']:+.1f}% | {f['trades']} | "
            f"{s['2000-2006']['net_sharpe']:+.3f} | "
            f"{s['2007-2012']['net_sharpe']:+.3f} | "
            f"{s['2013-2019']['net_sharpe']:+.3f} | "
            f"{s['2020-2026']['net_sharpe']:+.3f} |"
        )

    tp = fix2.get("turn_positive_threshold")
    lines += [
        "",
        f"**2000-2006 turns positive at**: ADX > {tp}" if tp
        else "**2000-2006**: never turns positive with ADX alone",
        "",
        "---",
        "",
        "## Fix 3: Combined Approach — Candidate Comparison",
        "",
        "Tested multiple configurations to find the best balance of stability and signal frequency.",
        "",
        "### Candidate Summary",
        "",
        "| Candidate | Sharpe | Compound | Trades/yr | Worst Sub | Criteria |",
        "|-----------|--------|----------|-----------|-----------|----------|",
    ]
    for cand in fix3.get("all_candidates", [fix3]):
        cfg = cand["config"]
        lbl = cand.get("label", f"{cfg['fast']}/{cfg['slow']}")
        lines.append(
            f"| {lbl} | {cand['spy_full']['net_sharpe']:+.3f} | "
            f"{cand['spy_full']['compound_return']:+.1f}% | "
            f"{cand['spy_full']['trades_per_year']:.1f} | "
            f"{cand['worst_subperiod_sharpe']:+.3f} | "
            f"{cand['n_passed']}/6 |"
        )

    cfg = fix3["config"]
    lines += [
        "",
        f"### Winner: {fix3.get('label', str(cfg['fast']) + '/' + str(cfg['slow']))}",
        "",
        f"**Configuration**: {cfg['fast']}/{cfg['slow']} + vol<{cfg['vol_threshold']} "
        f"+ ADX>{cfg['adx_threshold']}",
        "",
        "### SPY Results",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Full-period Sharpe | {fix3['spy_full']['net_sharpe']:+.3f} |",
        f"| Compound return | {fix3['spy_full']['compound_return']:+.1f}% |",
        f"| Total trades | {fix3['spy_full']['trades']} |",
        f"| Trades/year | {fix3['spy_full']['trades_per_year']:.1f} |",
        f"| Max drawdown | {fix3['spy_full']['max_drawdown']:.1f}% |",
        f"| Realistic Sharpe (6bp) | {fix3['realistic']['net_sharpe']:+.3f} |",
        "",
        "### Sub-Period Stability",
        "",
        "| Period | Net Sharpe |",
        "|--------|-----------|",
    ]
    for label, r in fix3["spy_subperiods"].items():
        lines.append(f"| {label} | {r['net_sharpe']:+.3f} |")

    lines += [
        "",
        "### OOS Assets",
        "",
        "| Asset | Net Sharpe | Compound | Verdict |",
        "|-------|-----------|----------|---------|",
    ]
    for sym, r in fix3["oos"].items():
        v = "PASS" if r["net_sharpe"] > 0.3 else ("MARGINAL" if r["net_sharpe"] >= 0 else "FAIL")
        lines.append(f"| {sym} | {r['net_sharpe']:+.3f} | {r['compound_return']:+.1f}% | {v} |")

    lines += [
        "",
        "### Deploy Criteria",
        "",
        "| Criterion | Result |",
        "|-----------|--------|",
    ]
    labels = {
        "full_sharpe_gt_040": f"Full-period net Sharpe > 0.40 ({fix3['spy_full']['net_sharpe']:.3f})",
        "all_subperiods_positive": f"All 4 sub-periods Sharpe > 0 (worst: {fix3['worst_subperiod_sharpe']:+.3f})",
        "oos_3_of_4_pass": f"OOS 3+ of 4 PASS (Sharpe > 0.30)",
        "realistic_sharpe_gt_030": f"Realistic (6bp) Sharpe > 0.30 ({fix3['realistic']['net_sharpe']:.3f})",
        "trades_per_year_gt_5": f"Trades/year > 5 ({fix3['spy_full']['trades_per_year']:.1f})",
        "trades_per_year_lt_100": f"Trades/year < 100 ({fix3['spy_full']['trades_per_year']:.1f})",
    }
    for k, v in fix3["criteria"].items():
        status = "PASS" if v else "FAIL"
        lines.append(f"| {labels[k]} | **{status}** |")

    lines += [
        "",
        f"## OVERALL VERDICT: **{fix3['verdict']}**",
        "",
        f"- {fix3['n_passed']}/6 criteria met",
        "",
    ]

    return "\n".join(lines)


def persist_to_supabase(fix1, fix2, fix3):
    try:
        import httpx
        from dotenv import load_dotenv
        load_dotenv(Path(_REPO_ROOT) / ".env")

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            print("  Supabase creds not found, skipping persist")
            return False

        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

        rows = []

        def _row(symbol, r, test_type, extra_params=None):
            params = {"test_type": test_type}
            params.update({"sma_fast": r.get("fast"), "sma_slow": r.get("slow"),
                          "vol_threshold": r.get("vol_threshold"),
                          "adx_threshold": r.get("adx_threshold")})
            if extra_params:
                params.update(extra_params)
            return {
                "strategy": "dma_regime_filter",
                "symbol": symbol,
                "timeframe": "1D",
                "data_source": "parquet",
                "date_start": r.get("start_date"),
                "date_end": r.get("end_date"),
                "initial_capital": INITIAL_CAPITAL,
                "final_value": r.get("final_equity", INITIAL_CAPITAL),
                "total_return_pct": r.get("compound_return", 0),
                "max_drawdown_pct": abs(r.get("max_drawdown", 0)),
                "sharpe_ratio": r.get("net_sharpe", 0),
                "total_trades": r.get("trades", 0),
                "win_rate_pct": 0,
                "params": json.dumps(params),
            }

        # Fix 1 cells
        for cell in fix1["cells"]:
            rows.append(_row("SPY", cell["full"], "fix1_longer_pairs"))

        # Fix 2 cells
        for cell in fix2["cells"]:
            rows.append(_row("SPY", cell["full"], "fix2_adx_filter"))

        # Fix 3
        rows.append(_row("SPY", fix3["spy_full"], "fix3_combined"))
        rows.append(_row("SPY", fix3["realistic"], "fix3_combined_realistic",
                         {"fee_per_side": 0.0006}))
        for sym, r in fix3["oos"].items():
            rows.append(_row(sym, r, "fix3_combined_oos"))

        if rows:
            resp = httpx.post(
                f"{url}/rest/v1/backtest_results",
                headers=headers,
                json=rows,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                print(f"  Persisted {len(rows)} rows to Supabase")
                return True
            else:
                print(f"  Supabase insert failed: {resp.status_code} {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"  Supabase persist error: {e}")
        return False


def main():
    print("=" * 70)
    print("DMA REGIME FILTER RESEARCH")
    print("=" * 70)

    df_spy = load_daily("SPY")

    # Fix 1
    fix1 = fix1_longer_pairs(df_spy)

    # Fix 2
    fix2 = fix2_adx_filter(df_spy, fix1["best"])

    # Fix 3
    fix3 = fix3_combined(df_spy, fix1, fix2)

    # Save JSON — strip all_candidates from fix3 to avoid circular ref
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / "dma_regime_filter.json"

    fix3_slim = {k: v for k, v in fix3.items() if k != "all_candidates"}
    candidates_slim = []
    for c in fix3.get("all_candidates", []):
        candidates_slim.append({k: v for k, v in c.items() if k != "all_candidates"})

    all_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fix1": {
            "cells": [{k: v for k, v in c.items()} for c in fix1["cells"]],
            "best_label": fix1["best"]["label"],
        },
        "fix2": {
            "cells": [{k: v for k, v in c.items()} for c in fix2["cells"]],
            "turn_positive_threshold": fix2["turn_positive_threshold"],
        },
        "fix3_winner": fix3_slim,
        "fix3_candidates": candidates_slim,
    }
    json_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\n  Results JSON: {json_path}")

    # Generate report
    report = generate_report(fix1, fix2, fix3)
    docs_dir = Path(_REPO_ROOT) / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / "dma_regime_filter_report.md"
    report_path.write_text(report)
    print(f"  Report: {report_path}")

    # Persist to Supabase
    print("\n  Persisting to Supabase...")
    persist_to_supabase(fix1, fix2, fix3_slim)

    # Final summary
    best_pair = fix1["best"]
    worst_fix1 = min(v["net_sharpe"] for v in best_pair["subperiods"].values()
                     if not (isinstance(v["net_sharpe"], float) and np.isnan(v["net_sharpe"])))

    # Best ADX from fix2 — pick the one with highest full Sharpe among those
    # where the best_pair is used
    fix2_best_pair_cells = [c for c in fix2["cells"]
                           if c["fast"] == best_pair["fast"] and c["slow"] == best_pair["slow"]]
    if fix2_best_pair_cells:
        best_adx_cell = max(fix2_best_pair_cells, key=lambda c: c["full"]["net_sharpe"])
    else:
        best_adx_cell = max(fix2["cells"], key=lambda c: c["full"]["net_sharpe"])
    s2000_adx = best_adx_cell["subperiods"]["2000-2006"]["net_sharpe"]

    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(f"  FIX1_BEST_PAIR:          {best_pair['fast']}/{best_pair['slow']} | "
          f"full Sharpe={best_pair['full']['net_sharpe']:+.3f} | "
          f"worst subperiod={worst_fix1:+.3f}")
    print(f"  FIX1_WORST_SUBPERIOD_FIXED: "
          f"{'yes — worst now ' + f'{worst_fix1:+.3f}' if worst_fix1 > 0 else 'no — still negative'}")
    print(f"  FIX2_BEST_THRESHOLD:     ADX {best_adx_cell['adx_threshold']} | "
          f"2000-2006 Sharpe={s2000_adx:+.3f}")
    s2007_adx = best_adx_cell["subperiods"]["2007-2012"]["net_sharpe"]
    both_pos = s2000_adx > 0 and s2007_adx > 0
    print(f"  FIX2_2000_2012_FIXED:    "
          f"{'yes — both positive' if both_pos else 'partial' if s2000_adx > 0 or s2007_adx > 0 else 'no'}")
    cfg = fix3["config"]
    fix3_label = fix3.get('label', str(cfg['fast']) + '/' + str(cfg['slow']))
    print(f"  FIX3_COMBINED:           {fix3_label} | "
          f"Sharpe={fix3['spy_full']['net_sharpe']:+.3f} | "
          f"compound={fix3['spy_full']['compound_return']:+.1f}% | "
          f"worst subperiod={fix3['worst_subperiod_sharpe']:+.3f}")
    failed = [k for k, v in fix3["criteria"].items() if not v]
    print(f"  DEPLOY_CRITERIA:         {fix3['n_passed']}/6 passed"
          + (f" — failed: {', '.join(failed)}" if failed else ""))
    print(f"  OVERALL_VERDICT:         {fix3['verdict']}")

    return all_results


if __name__ == "__main__":
    main()
