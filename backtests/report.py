"""
Reporting: per-trade CSV, printed summary, equity-curve PNG, Assumptions block.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .engine import trades_to_frame
from .metrics import Summary, equity_curve, summarize

TRADE_COLUMNS = [
    "entry_time", "exit_time", "direction", "contract_symbol", "dte", "strike",
    "qty", "entry_bid", "entry_ask", "entry_mid", "entry_fill",
    "exit_bid", "exit_ask", "exit_mid", "exit_fill", "spread_paid",
    "gross_pnl", "net_pnl", "commission", "exit_reason", "priced_via",
    "hold_min", "entry_underlying", "exit_underlying",
]


def save_trades_csv(trades, path: Path) -> pd.DataFrame:
    df = trades_to_frame(trades)
    path.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        pd.DataFrame(columns=TRADE_COLUMNS).to_csv(path, index=False)
        return df
    cols = [c for c in TRADE_COLUMNS if c in df.columns]
    df = df[cols]
    df.to_csv(path, index=False)
    return df


def assumptions_block(cfg, underlying_source: str, quote_source: str,
                      bs_pct: Optional[float] = None, rows: Optional[int] = None) -> str:
    from core.data_provenance import DataProvenance
    try:
        prov = DataProvenance(underlying_source)
    except Exception:
        if "synthetic" in underlying_source.lower() or "gbm" in underlying_source.lower():
            prov = DataProvenance.SYNTHETIC_GBM
        elif "questdb" in underlying_source.lower():
            prov = DataProvenance.REAL_QUESTDB
        elif "alpaca" in underlying_source.lower():
            prov = DataProvenance.REAL_ALPACA
        else:
            prov = DataProvenance.REAL_PARQUET

    row_count_str = f"{rows:,}" if rows is not None else "unknown"
    if prov.is_synthetic:
        header = f"\n⚠️ DATA PROVENANCE: {prov.value.upper()} — RESULTS DO NOT REFLECT REAL MARKET DATA\n"
    else:
        header = f"\nDATA PROVENANCE: {prov.value} | rows={row_count_str} | symbol={cfg.symbol}\n"

    bs_line = ""
    if bs_pct is not None:
        bs_line = f"\n  • Black-Scholes-priced trades: {bs_pct:.1f}% of the sample"
    return f"""{header}
╔══════════════════════════════════════════════════════════════════════════╗
║  ASSUMPTIONS & LIMITATIONS                                                 ║
╠══════════════════════════════════════════════════════════════════════════╣
  DATA
  • Underlying source : {underlying_source}
  • Option pricing    : {quote_source}{bs_line}
  • If 'SYNTHETIC' / 'black-scholes' appears above, NO real market data was
    reachable in this environment (no /mnt/tick-storage mount, no Alpaca
    egress/credentials). Numbers are ILLUSTRATIVE of the harness mechanics,
    NOT a real edge estimate. Re-run in the production environment (local
    parquet + Alpaca keys) for real results.

  FILL MODEL
  • Enter at the ASK, exit at the BID (full bid-ask spread paid).
  • Extra slippage haircut: {cfg.slippage_ticks:.0f} tick(s) x ${cfg.tick_size} per side.
  • Commission: ${cfg.commission_per_contract:.2f}/contract/side.
  • Gross P&L is mid-to-mid; net is ask->bid + slippage + commission.

  SPREAD MODEL (fallback pricing only)
  • BS half-spread = max(1 tick, {cfg.spread_frac:.4f} x mid); real IWM spreads
    vary with liquidity, time-of-day and vol — this is an approximation.
  • IV = RVX-proxy base {cfg.base_iv:.2f} with light moneyness skew + short-DTE bump.

  SIGNAL
  • UT Bot ATR signal replicated VERBATIM from strategies/ut_bot.py
    (ATR_PERIOD={cfg.atr_period}, MULT={cfg.sensitivity}); production exits reproduced
    (RSI step-back, underlying %-stop, EOD flatten {cfg.eod_flatten_time} ET).
  • Applied to intraday {cfg.timeframe} bars (production runs the same math).

  LIQUIDITY / SURVIVORSHIP CAVEATS
  • No modeling of partial fills, quote staleness, or being unable to trade at
    the touch for size. One position at a time; MAX_TRADES_PER_DAY and
    MAX_POSITION_SIZE enforced.
  • Contracts constructed by OCC-symbol rule (no chain endpoint for history),
    assuming a listed expiry exists on the target business day.
  • Assignment/early-exercise and hard-to-borrow effects ignored (long premium).
╚══════════════════════════════════════════════════════════════════════════╝
"""


def format_summary(s: Summary, cfg, title: str = "OPTIONS BACKTEST SUMMARY") -> str:
    pf = "inf" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
    edge = "n/a" if s.pct_edge_lost_to_spread != s.pct_edge_lost_to_spread else f"{s.pct_edge_lost_to_spread:.1f}%"
    return f"""
════════════════════════════════════════════════════════════════════════════
{title}
  {cfg.symbol}  {cfg.timeframe}  DTE={cfg.dte}  strike={cfg.strike_mode}
  time_stop={cfg.time_stop_min}m  profit_target=+{cfg.profit_target:.0%}  premium_stop=-{cfg.premium_stop:.0%}
════════════════════════════════════════════════════════════════════════════
  Trades              : {s.trades}
  Win rate            : {s.win_rate:.1%}  ({s.wins}W / {s.losses}L)
  Avg win / avg loss  : ${s.avg_win:,.2f} / ${s.avg_loss:,.2f}
  Profit factor       : {pf}
  Expectancy / trade  : ${s.expectancy_dollar:,.2f}  ({s.expectancy_pct:+.2f}% on premium)
  Max drawdown        : ${s.max_drawdown:,.2f}
  Sharpe (per-trade)  : {s.sharpe:.2f}
  ────────────────────────────────────────────────────────────────
  GROSS total (mid)   : ${s.gross_total:,.2f}
  NET total (paid)    : ${s.net_total:,.2f}
  Total spread cost   : ${s.total_spread_cost:,.2f}
  Total commission    : ${s.total_commission:,.2f}
  Avg spread / trade  : ${s.avg_spread_per_trade:,.2f}
  >> % of gross edge lost to spread : {edge}   <<< HEADLINE
  ────────────────────────────────────────────────────────────────
  BS-priced trades    : {s.bs_priced_pct:.1f}%
════════════════════════════════════════════════════════════════════════════
"""


def save_equity_png(trades, path: Path, title: str) -> Optional[Path]:
    df = trades_to_frame(trades)
    if df.empty:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        # matplotlib is optional; the harness still emits CSV + summary without it.
        print("  [warn] matplotlib unavailable — skipping equity PNG")
        return None

    eq = equity_curve(df)
    gross_eq = df.sort_values("exit_time")["gross_pnl"].cumsum()
    gross_eq.index = pd.to_datetime(df.sort_values("exit_time")["exit_time"])

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(eq.index, eq.values, label="Net (after spread)", color="#1f77b4", lw=1.6)
    ax.plot(gross_eq.index, gross_eq.values, label="Gross (mid-to-mid)",
            color="#7f7f7f", lw=1.1, ls="--")
    ax.axhline(0, color="black", lw=0.8, alpha=0.5)
    ax.fill_between(eq.index, eq.values, 0, where=(eq.values >= 0), color="#1f77b4", alpha=0.08)
    ax.fill_between(eq.index, eq.values, 0, where=(eq.values < 0), color="#d62728", alpha=0.08)
    ax.set_title(title)
    ax.set_ylabel("Cumulative P&L ($)")
    ax.set_xlabel("Exit time")
    ax.legend(loc="best")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
