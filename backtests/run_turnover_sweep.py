"""
UT Bot turnover sweep — 6×6 grid (ATR period × sensitivity) on real SPY daily bars.

Methodology:
  - Signal:  compute_ut_signal (4-branch SMA-ATR, identical to live strategies/ut_bot.py)
  - Position: long on +1 crossover, short on -1 crossover (full reversal, no flat)
  - Sizing:  flat 100% of capital
  - Entry:   close of signal bar
  - Exit:    close of next opposing signal bar (or end of data)
  - Fee:     0.0001 per side (1 bp, equity_etf rate) — charged at every entry/exit
  - Window:  2000-01-01 to 2026-07-14 (6 671 trading days, real parquet)
  - Sharpe:  annualised (×√252) on daily net returns, risk-free = 0
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# ── repo root on path ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtests.signal import compute_ut_signal  # noqa: E402

# ── constants ─────────────────────────────────────────────────────────────────
PARQUET_PATH = Path("/mnt/tick-storage/historical/equities/SPY/SPY_1D_2000-01-03_2026-07-14.parquet")
FEE_PER_SIDE = 0.0001
PERIODS = [5, 7, 10, 14, 21, 30]
SENSITIVITIES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
RESULTS_DIR = ROOT / "backtests" / "results"
OUTPUT_JSON = RESULTS_DIR / "utbot_turnover_sweep.json"
OUTPUT_MD = ROOT / "docs" / "turnover_sweep_findings.md"


# ── data loading ──────────────────────────────────────────────────────────────
def load_spy() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET_PATH)
    if "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df = df.sort_values("date").reset_index(drop=True)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    # Drop any bars with NaN close (e.g. incomplete final bar)
    n_before = len(df)
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    if len(df) < n_before:
        print(f"  Dropped {n_before - len(df)} bar(s) with NaN close (last bar likely incomplete)")
    return df


# ── per-cell backtest ─────────────────────────────────────────────────────────
def run_cell(df: pd.DataFrame, period: int, sensitivity: float) -> dict:
    sig_df = compute_ut_signal(df, atr_period=period, sensitivity=sensitivity)

    closes = sig_df["close"].values.astype(float)
    signals = sig_df["signal"].values.astype(int)
    n = len(closes)

    # Build position series: enter at close of signal bar, hold until reversal
    pos = 0
    positions = np.zeros(n, dtype=float)
    for i, s in enumerate(signals):
        if s != 0:
            pos = float(s)
        positions[i] = pos

    # Fee events: |Δposition| * fee_per_side
    pos_diff = np.diff(positions, prepend=0.0)
    fee_drag_daily = np.abs(pos_diff) * FEE_PER_SIDE

    # Daily SPY return
    spy_ret = np.zeros(n)
    spy_ret[1:] = np.diff(closes) / closes[:-1]

    # Strategy daily gross return: position[t-1] * spy_ret[t]
    strat_gross = np.zeros(n)
    strat_gross[1:] = positions[:-1] * spy_ret[1:]

    # Net: subtract fees at each position change bar
    strat_net = strat_gross - fee_drag_daily

    # Equity curves
    gross_equity = np.cumprod(1.0 + strat_gross)
    net_equity = np.cumprod(1.0 + strat_net)

    gross_return = float(gross_equity[-1] - 1.0)
    net_return = float(net_equity[-1] - 1.0)
    fee_drag_pct = float(gross_return - net_return)

    # Sharpe on daily net returns (all 6671 days, incl. 0-return days)
    mean_net = float(np.mean(strat_net))
    std_net = float(np.std(strat_net, ddof=1))
    sharpe = float((mean_net / std_net) * np.sqrt(252)) if std_net > 0 else 0.0

    # Max drawdown from net equity curve
    running_max = np.maximum.accumulate(net_equity)
    drawdowns = (net_equity - running_max) / running_max
    max_drawdown = float(np.min(drawdowns))

    # Trade-level stats
    trades = []
    entry_idx = None
    entry_dir = 0
    cur_pos = 0.0

    for i in range(n):
        new_pos = positions[i]
        if new_pos != cur_pos:
            if cur_pos != 0.0 and entry_idx is not None:
                # close existing trade
                gross = cur_pos * (closes[i] - closes[entry_idx]) / closes[entry_idx]
                net = gross - 2.0 * FEE_PER_SIDE
                hold = i - entry_idx
                trades.append({"gross": gross, "net": net, "hold": hold, "dir": cur_pos})
            if new_pos != 0.0:
                entry_idx = i
            cur_pos = new_pos

    # Close open position at end
    if cur_pos != 0.0 and entry_idx is not None:
        gross = cur_pos * (closes[-1] - closes[entry_idx]) / closes[entry_idx]
        net = gross - 2.0 * FEE_PER_SIDE
        hold = n - 1 - entry_idx
        trades.append({"gross": gross, "net": net, "hold": hold, "dir": cur_pos})

    num_trades = len(trades)
    if num_trades > 0:
        nets = np.array([t["net"] for t in trades])
        win_rate = float(np.mean(nets > 0))
        expectancy = float(np.mean(nets))
        avg_hold = float(np.mean([t["hold"] for t in trades]))
    else:
        win_rate = 0.0
        expectancy = 0.0
        avg_hold = 0.0

    return {
        "period": period,
        "sensitivity": sensitivity,
        "trades": num_trades,
        "gross_return": round(gross_return, 6),
        "net_return": round(net_return, 6),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_drawdown, 6),
        "fee_drag_pct": round(fee_drag_pct, 6),
        "win_rate": round(win_rate, 4),
        "expectancy_per_trade": round(expectancy, 6),
        "avg_hold_days": round(avg_hold, 1),
        "data_provenance": "real_parquet",
    }


# ── Supabase insert ───────────────────────────────────────────────────────────
def push_to_supabase(rows: list[dict]) -> tuple[int, str]:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return 0, "NO_ENV"

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    written = 0
    for r in rows:
        payload = {
            "strategy": "ut_bot_sweep",
            "symbol": "SPY",
            "atr_period": r["period"],
            "sensitivity": r["sensitivity"],
            "total_return_pct": r["net_return"] * 100,
            "max_drawdown_pct": r["max_drawdown"] * 100,
            "sharpe_ratio": r["sharpe"],
            "total_trades": r["trades"],
            "win_rate_pct": r["win_rate"] * 100,
            "params": json.dumps({
                "period": r["period"],
                "sensitivity": r["sensitivity"],
                "gross_return": r["gross_return"],
                "net_return": r["net_return"],
                "fee_drag_pct": r["fee_drag_pct"],
                "expectancy_per_trade": r["expectancy_per_trade"],
                "avg_hold_days": r["avg_hold_days"],
                "data_provenance": r["data_provenance"],
            }),
        }
        resp = httpx.post(f"{url}/rest/v1/backtest_results", headers=headers, content=json.dumps(payload))
        if resp.status_code in (200, 201):
            written += 1
        else:
            print(f"  WARN insert failed {r['period']}/{r['sensitivity']}: {resp.status_code} {resp.text[:100]}")

    return written, "OK"


# ── neighbor check ────────────────────────────────────────────────────────────
def neighbor_check(results: list[dict], best: dict) -> tuple[bool, list[dict]]:
    p_idx = PERIODS.index(best["period"])
    s_idx = SENSITIVITIES.index(best["sensitivity"])
    neighbors = []
    for dp in [-1, 0, 1]:
        for ds in [-1, 0, 1]:
            if dp == 0 and ds == 0:
                continue
            np_ = p_idx + dp
            ns_ = s_idx + ds
            if 0 <= np_ < len(PERIODS) and 0 <= ns_ < len(SENSITIVITIES):
                p = PERIODS[np_]
                s = SENSITIVITIES[ns_]
                match = next((r for r in results if r["period"] == p and r["sensitivity"] == s), None)
                if match:
                    neighbors.append(match)
    positive_neighbors = [nb for nb in neighbors if nb["expectancy_per_trade"] > 0]
    supported = len(positive_neighbors) >= len(neighbors) // 2
    return supported, neighbors


# ── markdown report ───────────────────────────────────────────────────────────
def write_markdown(results: list[dict], top3: list[dict], median: dict, best: dict,
                   supported: bool, neighbors: list[dict], supabase_written: int) -> None:
    sorted_r = sorted(results, key=lambda x: x["sharpe"], reverse=True)
    positive_expectancy = [r for r in results if r["expectancy_per_trade"] > 0]
    verdict_yes = len(positive_expectancy) > 0

    lines = [
        "# UT Bot Turnover Sweep — SPY Daily 2000–2026",
        "",
        "**Grid:** 6 ATR periods × 6 sensitivities = 36 cells  ",
        "**Signal:** `compute_ut_signal` (4-branch SMA-ATR, identical to live `strategies/ut_bot.py`)  ",
        "**Sizing:** flat 100%, long/short reversal at each signal  ",
        "**Fee:** 1 bp per side (equity_etf)  ",
        "**Data:** real parquet — `/mnt/tick-storage/historical/equities/SPY/SPY_1D_2000-01-03_2026-07-14.parquet`  ",
        "**Bars:** 6,671 daily bars (2000-01-03 → 2026-07-14)  ",
        "",
        "---",
        "",
        "## Full Grid — Ranked by Net Sharpe (CRITICAL → LOW)",
        "",
        "| Rank | Period | Sens | Trades | Gross Ret | Net Ret | Sharpe | MaxDD | Win Rate | Exp/Trade | Avg Hold |",
        "|------|--------|------|--------|-----------|---------|--------|-------|----------|-----------|----------|",
    ]
    for i, r in enumerate(sorted_r, 1):
        lines.append(
            f"| {i} | {r['period']} | {r['sensitivity']} | {r['trades']} "
            f"| {r['gross_return']*100:+.1f}% | {r['net_return']*100:+.1f}% "
            f"| {r['sharpe']:+.3f} | {r['max_drawdown']*100:.1f}% "
            f"| {r['win_rate']*100:.1f}% | {r['expectancy_per_trade']*100:+.3f}% | {r['avg_hold_days']:.1f}d |"
        )

    lines += [
        "",
        "---",
        "",
        "## Top 3 vs Median Comparison",
        "",
        "| | Period/Sens | Net Sharpe | Net Return | Trades | Win Rate | Exp/Trade |",
        "|---|---|---|---|---|---|---|",
    ]
    for rank, r in enumerate(top3, 1):
        lines.append(
            f"| Top {rank} | {r['period']}/{r['sensitivity']} | {r['sharpe']:+.3f} "
            f"| {r['net_return']*100:+.1f}% | {r['trades']} "
            f"| {r['win_rate']*100:.1f}% | {r['expectancy_per_trade']*100:+.3f}% |"
        )
    lines.append(
        f"| Median | {median['period']}/{median['sensitivity']} | {median['sharpe']:+.3f} "
        f"| {median['net_return']*100:+.1f}% | {median['trades']} "
        f"| {median['win_rate']*100:.1f}% | {median['expectancy_per_trade']*100:+.3f}% |"
    )

    lines += [
        "",
        "---",
        "",
        "## Neighbor Check — Best Cell",
        "",
        f"**Best cell:** period={best['period']}, sensitivity={best['sensitivity']} "
        f"(Sharpe={best['sharpe']:+.3f}, exp/trade={best['expectancy_per_trade']*100:+.3f}%)",
        "",
        "8 nearest neighbors (±1 step in period/sensitivity grid):",
        "",
        "| Period | Sens | Sharpe | Exp/Trade | Positive? |",
        "|--------|------|--------|-----------|-----------|",
    ]
    for nb in neighbors:
        pos_flag = "✓" if nb["expectancy_per_trade"] > 0 else "✗"
        lines.append(
            f"| {nb['period']} | {nb['sensitivity']} | {nb['sharpe']:+.3f} "
            f"| {nb['expectancy_per_trade']*100:+.3f}% | {pos_flag} |"
        )

    support_str = "supported by neighbors" if supported else "isolated — likely overfit"
    lines += [
        "",
        f"**The best cell is [{support_str}].**",
        "",
        "---",
        "",
        "## Comparison to Baselines",
        "",
        "| Config | Source | Trades | Net Return | Sharpe | Exp/Trade |",
        "|--------|--------|--------|------------|--------|-----------|",
    ]
    # Find 10/1.0 and 14/3.0 in results
    b1 = next((r for r in results if r["period"] == 10 and r["sensitivity"] == 1.0), None)
    b2 = next((r for r in results if r["period"] == 14 and r["sensitivity"] == 3.0), None)
    if b1:
        lines.append(
            f"| 10/1.0 (baseline) | this sweep | {b1['trades']} "
            f"| {b1['net_return']*100:+.1f}% | {b1['sharpe']:+.3f} "
            f"| {b1['expectancy_per_trade']*100:+.3f}% |"
        )
    if b2:
        lines.append(
            f"| 14/3.0 (live) | this sweep | {b2['trades']} "
            f"| {b2['net_return']*100:+.1f}% | {b2['sharpe']:+.3f} "
            f"| {b2['expectancy_per_trade']*100:+.3f}% |"
        )

    lines += [
        "",
        "*(Prior run baseline for 10/1.0: gross -28.6%, net -37.3%, 645 trades — measured with options engine; "
        "this sweep uses equity simulation which will differ.)*",
        "",
        "---",
        "",
        "## Honest Verdict",
        "",
    ]
    if verdict_yes:
        cells_with_edge = sorted(positive_expectancy, key=lambda x: x["sharpe"], reverse=True)
        cell_str = ", ".join(f"{r['period']}/{r['sensitivity']}" for r in cells_with_edge[:5])
        lines += [
            f"**YES — positive net expectancy per trade after 1 bp costs exists at: {cell_str}**",
            "",
            f"Of 36 parameterizations tested, {len(positive_expectancy)} show positive expectancy per trade. "
            f"The best cell ({best['period']}/{best['sensitivity']}) has expectancy "
            f"{best['expectancy_per_trade']*100:+.4f}% per trade, Sharpe {best['sharpe']:+.3f}, "
            f"over {best['trades']} trades (2000–2026). "
            f"Neighbor check: the best cell is **{support_str}**.",
        ]
    else:
        lines += [
            "**NO — No parameterization tested shows positive net expectancy. "
            "The signal does not have edge on daily SPY.**",
            "",
            f"All 36 cells show negative expectancy per trade after 1 bp costs. "
            f"The best Sharpe ({best['sharpe']:+.3f}) belongs to {best['period']}/{best['sensitivity']} "
            f"with expectancy {best['expectancy_per_trade']*100:+.4f}% per trade. "
            "This signal is a trend-follower that historically loses more than it gains on mean-reverting SPY.",
        ]

    lines += [
        "",
        "---",
        "",
        "## Supabase Persistence",
        "",
        f"Rows written to `backtest_results`: **{supabase_written}/36**  ",
        "Schema note: existing table uses `total_return_pct`, `sharpe_ratio`, `total_trades`, `win_rate_pct` columns; "
        "sweep-specific fields (`gross_return`, `net_return`, `fee_drag_pct`, `expectancy_per_trade`, "
        "`data_provenance`) stored in `params` jsonb.",
        "",
        "---",
        f"*Generated: 2026-07-16 | Branch: research/turnover-sweep*",
    ]

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(lines))
    print(f"Markdown written: {OUTPUT_MD}")


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("Loading SPY parquet...")
    df = load_spy()
    print(f"  {len(df)} bars from {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
    print(f"  Columns: {list(df.columns)}")
    print(f"  data_provenance: real_parquet ✓")
    print()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(PERIODS) * len(SENSITIVITIES)
    done = 0

    for period in PERIODS:
        for sensitivity in SENSITIVITIES:
            cell = run_cell(df, period, sensitivity)
            results.append(cell)
            done += 1
            print(
                f"  [{done:2d}/{total}] p={period:2d} s={sensitivity:.1f} | "
                f"trades={cell['trades']:4d} | gross={cell['gross_return']*100:+7.2f}% | "
                f"net={cell['net_return']*100:+7.2f}% | sharpe={cell['sharpe']:+6.3f} | "
                f"exp/trade={cell['expectancy_per_trade']*100:+.4f}%"
            )

    # Save JSON
    OUTPUT_JSON.write_text(json.dumps(results, indent=2))
    print(f"\nJSON written: {OUTPUT_JSON}")

    # Sort by net sharpe
    sorted_r = sorted(results, key=lambda x: x["sharpe"], reverse=True)
    top3 = sorted_r[:3]
    median_idx = len(sorted_r) // 2
    median = sorted_r[median_idx]
    best = sorted_r[0]

    print("\n── TOP 3 CELLS ──────────────────────────────────────────────")
    for i, r in enumerate(top3, 1):
        print(f"  {i}. period={r['period']}, sens={r['sensitivity']} | sharpe={r['sharpe']:+.3f} | "
              f"net={r['net_return']*100:+.2f}% | trades={r['trades']} | "
              f"exp/trade={r['expectancy_per_trade']*100:+.4f}%")

    print(f"\n── MEDIAN CELL ──────────────────────────────────────────────")
    print(f"  period={median['period']}, sens={median['sensitivity']} | sharpe={median['sharpe']:+.3f} | "
          f"net={median['net_return']*100:+.2f}% | trades={median['trades']} | "
          f"exp/trade={median['expectancy_per_trade']*100:+.4f}%")

    # Neighbor check
    supported, neighbors = neighbor_check(results, best)
    support_str = "supported" if supported else "isolated"
    pos_neighbors = [nb for nb in neighbors if nb["expectancy_per_trade"] > 0]
    print(f"\n── NEIGHBOR CHECK (best={best['period']}/{best['sensitivity']}) ──")
    print(f"  {len(pos_neighbors)}/{len(neighbors)} neighbors have positive expectancy → {support_str}")

    # Supabase
    print("\nPushing to Supabase...")
    written, status = push_to_supabase(results)
    print(f"  {written}/36 rows written ({status})")

    # Markdown
    write_markdown(results, top3, median, best, supported, neighbors, written)

    # Final summary
    positive_cells = [r for r in results if r["expectancy_per_trade"] > 0]
    print("\n" + "=" * 65)
    print("FINAL REPORT")
    print("=" * 65)
    print(f"  BEST_CELL:       {best['period']}/{best['sensitivity']} | sharpe={best['sharpe']:+.3f} | trades={best['trades']}")
    print(f"  MEDIAN_CELL:     {median['period']}/{median['sensitivity']} | sharpe={median['sharpe']:+.3f} | trades={median['trades']}")
    print(f"  NEIGHBOR_CHECK:  {support_str}")
    if positive_cells:
        top_pos = sorted(positive_cells, key=lambda x: x["sharpe"], reverse=True)[0]
        print(f"  VERDICT:         YES positive edge exists at {top_pos['period']}/{top_pos['sensitivity']} and {len(positive_cells)-1} other(s)")
    else:
        print("  VERDICT:         NO no edge found")
    print(f"  SUPABASE_ROWS:   {written}/36 written")
    print(f"  DATA_PROVENANCE: real_parquet confirmed")
    print("=" * 65)


if __name__ == "__main__":
    main()
