"""
Performance metrics + equity curve.

Computes the summary block the task requires: trade count, win rate, avg win/
loss, profit factor, expectancy ($ and %), max drawdown, Sharpe, gross vs net
totals, total spread cost, avg spread paid, and the headline % of gross edge
lost to spread.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Summary:
    trades: int
    wins: int
    losses: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy_dollar: float
    expectancy_pct: float
    gross_total: float
    net_total: float
    total_spread_cost: float
    total_commission: float
    avg_spread_per_trade: float
    pct_edge_lost_to_spread: float
    max_drawdown: float
    sharpe: float
    bs_priced_pct: float
    cagr: float
    mc_drawdown_95: float
    data_provenance: Optional[str] = None
    data_rows: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _sharpe(returns: pd.Series) -> float:
    """Per-trade Sharpe annualized by trade count (sqrt of #trades)."""
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(len(returns)))


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    dd = equity - running_max
    return float(dd.min())


def equity_curve(df: pd.DataFrame, starting: float = 0.0) -> pd.Series:
    """Cumulative net P&L indexed by exit time."""
    if df.empty:
        return pd.Series(dtype=float)
    s = df.sort_values("exit_time")
    eq = starting + s["net_pnl"].cumsum()
    eq.index = pd.to_datetime(s["exit_time"])
    return eq

def calc_cagr(equity: pd.Series, initial_capital: float = 10000.0) -> float:
    if equity.empty or len(equity) < 2: return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days < 1: return 0.0
    final = initial_capital + equity.iloc[-1]
    if final <= 0: return -1.0
    return float((final / initial_capital) ** (365.25 / days) - 1.0)

def monte_carlo_max_dd(trades_df: pd.DataFrame, n_simulations: int = 1000) -> float:
    if len(trades_df) < 2: return 0.0
    net = trades_df["net_pnl"].values
    max_dds = []
    for _ in range(n_simulations):
        sim_net = np.random.choice(net, size=len(net), replace=True)
        eq = np.cumsum(sim_net)
        running_max = np.maximum.accumulate(eq)
        dd = eq - running_max
        max_dds.append(dd.min())
    return float(np.percentile(max_dds, 5))

def summarize(df: pd.DataFrame) -> Summary:
    if df.empty:
        return Summary(*([0] * 3), *([0.0] * 17))

    net = df["net_pnl"]
    wins = df[net > 0]["net_pnl"]
    losses = df[net <= 0]["net_pnl"]

    gross_total = float(df["gross_pnl"].sum())
    net_total = float(net.sum())
    total_spread = float(df["spread_paid"].sum())
    total_comm = float(df["commission"].sum())

    profit_factor = (
        float(wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float("inf")
    )

    # expectancy % is per-trade net return on premium risked (entry cost basis)
    cost_basis = df["entry_fill"] * df["qty"] * 100.0
    pct_returns = np.where(cost_basis > 0, net / cost_basis, 0.0)

    eq = equity_curve(df)
    pct_edge_lost = (total_spread / gross_total * 100.0) if gross_total > 0 else float("nan")

    return Summary(
        trades=int(len(df)),
        wins=int(len(wins)),
        losses=int(len(losses)),
        win_rate=round(len(wins) / len(df), 4),
        avg_win=round(float(wins.mean()) if len(wins) else 0.0, 2),
        avg_loss=round(float(losses.mean()) if len(losses) else 0.0, 2),
        profit_factor=round(profit_factor, 3),
        expectancy_dollar=round(net_total / len(df), 2),
        expectancy_pct=round(float(np.mean(pct_returns)) * 100.0, 3),
        gross_total=round(gross_total, 2),
        net_total=round(net_total, 2),
        total_spread_cost=round(total_spread, 2),
        total_commission=round(total_comm, 2),
        avg_spread_per_trade=round(total_spread / len(df), 2),
        pct_edge_lost_to_spread=round(pct_edge_lost, 2) if not np.isnan(pct_edge_lost) else float("nan"),
        max_drawdown=round(max_drawdown(eq), 2),
        sharpe=round(_sharpe(pd.Series(pct_returns)), 3),
        bs_priced_pct=round(float((df["priced_via"] == "bs").mean()) * 100.0, 1),
        cagr=round(calc_cagr(eq) * 100.0, 2),
        mc_drawdown_95=round(monte_carlo_max_dd(df), 2)
    )
