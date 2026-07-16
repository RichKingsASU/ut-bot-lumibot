"""
Backtest engine — the event loop.

Applies the production UT Bot signal to intraday IWM bars and simulates the full
long-options lifecycle with realistic fills:

  * Entry on a fresh UT crossover → buy CALL (LONG) / PUT (SHORT) at the ASK.
  * One position at a time; ``MAX_TRADES_PER_DAY`` and ``MAX_POSITION_SIZE``
    enforced exactly as in production (config.py).
  * Exits, in priority order:
      1. EOD flatten @ 15:55 ET           (production — ut_bot.py)
      2. contract expiry
      3. premium stop  (-premium_stop%)   (scalp — new)
      4. profit target (+profit_target%)  (scalp — new)
      5. hard time stop (time_stop_min)   (scalp — new)
      6. RSI step-back                    (production — ut_bot.py)
      7. underlying % stop                (production — ut_bot.py)
  * Exit fills at the BID. Gross (mid-to-mid) P&L tracked separately.

Scalp target/stop thresholds are measured on the option MID (mid-to-mid) so the
bid-ask spread alone can't trip a stop at t=0; the spread cost is still fully
paid on the actual bid/ask fills and reported separately.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional

import pandas as pd

from .contracts import Contract, select_contract
from .costs import Fill, TradeCosts, compute_costs, entry_fill, exit_fill
from .signal import compute_rsi_series, compute_ut_signal


@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    direction: str            # LONG | SHORT
    contract_symbol: str
    option_type: str
    dte: int
    strike: float
    qty: int
    # premium (per share)
    entry_bid: float
    entry_ask: float
    entry_mid: float
    entry_fill: float
    exit_bid: float
    exit_ask: float
    exit_mid: float
    exit_fill: float
    spread_paid: float        # $ (bid-ask + slippage), whole position
    gross_pnl: float          # $ mid-to-mid
    net_pnl: float            # $ after spread + slippage + commission
    commission: float
    exit_reason: str
    priced_via: str           # real | bs
    hold_min: float
    entry_underlying: float
    exit_underlying: float


@dataclass
class _Open:
    contract: Contract
    direction: str
    qty: int
    entry_ts: pd.Timestamp
    entry: Fill
    entry_rsi: float
    entry_underlying: float


def _hhmm(cfg) -> tuple[int, int]:
    h, m = cfg.eod_flatten_time.split(":")
    return int(h), int(m)


def run_backtest(df: pd.DataFrame, cfg, quote_provider) -> List[Trade]:
    """Run the event loop over resampled bars; return the list of closed trades."""
    if df.empty:
        return []

    sig = compute_ut_signal(df, cfg.atr_period, cfg.sensitivity)
    rsi = compute_rsi_series(df["close"], cfg.rsi_period)

    flatten_h, flatten_m = _hhmm(cfg)
    qty = max(1, min(cfg.contracts, cfg.max_position_size))

    trades: List[Trade] = []
    pos: Optional[_Open] = None
    trades_today = 0
    cur_day = None

    closes = sig["close"]
    signals = sig["signal"]

    for ts in sig.index:
        if cur_day != ts.date():
            cur_day = ts.date()
            trades_today = 0

        price = float(closes.loc[ts])
        cur_rsi = float(rsi.loc[ts])
        after_flatten = (ts.hour > flatten_h) or (
            ts.hour == flatten_h and ts.minute >= flatten_m
        )

        # ── Manage open position ───────────────────────────────────────
        if pos is not None:
            q = quote_provider.get_quote(pos.contract, price, ts.to_pydatetime())
            reason = None

            if after_flatten:
                reason = "eod_flatten"
            elif ts.date() >= pos.contract.expiry:
                reason = "expiry"
            elif q is not None and pos.entry.mid > 0:
                pnl_pct = (q.mid - pos.entry.mid) / pos.entry.mid
                hold_min = (ts - pos.entry_ts).total_seconds() / 60.0
                if pnl_pct <= -cfg.premium_stop:
                    reason = "premium_stop"
                elif pnl_pct >= cfg.profit_target:
                    reason = "profit_target"
                elif hold_min >= cfg.time_stop_min:
                    reason = "time_stop"

            if reason is None:
                # production exits (ut_bot._check_exit_triggers)
                rsi_drop = pos.entry_rsi - cur_rsi
                if rsi_drop >= cfg.rsi_step_thresh:
                    reason = "rsi_stepback"
                elif pos.direction == "LONG" and price <= pos.entry_underlying * (1 - cfg.stop_pct):
                    reason = "underlying_stop_long"
                elif pos.direction == "SHORT" and price >= pos.entry_underlying * (1 + cfg.stop_pct):
                    reason = "underlying_stop_short"

            if reason is not None and q is not None:
                xfill = exit_fill(q, cfg)
                costs = compute_costs(pos.entry, xfill, pos.qty, cfg)
                trades.append(_close_trade(pos, ts, xfill, costs, price, reason))
                pos = None

        # ── Entry (flat, fresh signal, within limits, before flatten) ──
        sig_val = int(signals.loc[ts])
        if pos is None and sig_val != 0 and not after_flatten:
            if trades_today >= cfg.max_trades_per_day:
                continue
            direction = "LONG" if sig_val == 1 else "SHORT"
            contract = select_contract(
                underlying=cfg.symbol,
                underlying_price=price,
                direction=direction,
                entry_day=ts.date(),
                dte=cfg.dte,
                strike_mode=cfg.strike_mode,
                strike_step=cfg.strike_step,
            )
            q = quote_provider.get_quote(contract, price, ts.to_pydatetime())
            if q is None or q.ask <= 0:
                continue
            efill = entry_fill(q, cfg)
            pos = _Open(
                contract=contract,
                direction=direction,
                qty=qty,
                entry_ts=ts,
                entry=efill,
                entry_rsi=cur_rsi,
                entry_underlying=price,
            )
            trades_today += 1

    return trades


def _close_trade(pos: _Open, ts: pd.Timestamp, xfill: Fill, costs: TradeCosts,
                 exit_underlying: float, reason: str) -> Trade:
    return Trade(
        entry_time=pos.entry_ts.to_pydatetime(),
        exit_time=ts.to_pydatetime(),
        direction=pos.direction,
        contract_symbol=pos.contract.symbol,
        option_type=pos.contract.option_type,
        dte=pos.contract.dte,
        strike=pos.contract.strike,
        qty=pos.qty,
        entry_bid=pos.entry.bid,
        entry_ask=pos.entry.ask,
        entry_mid=pos.entry.mid,
        entry_fill=pos.entry.price,
        exit_bid=xfill.bid,
        exit_ask=xfill.ask,
        exit_mid=xfill.mid,
        exit_fill=xfill.price,
        spread_paid=costs.spread_paid,
        gross_pnl=costs.gross_pnl,
        net_pnl=costs.net_pnl,
        commission=costs.commission,
        exit_reason=reason,
        priced_via=pos.entry.priced_via,
        hold_min=round((ts - pos.entry_ts).total_seconds() / 60.0, 1),
        entry_underlying=round(pos.entry_underlying, 4),
        exit_underlying=round(exit_underlying, 4),
    )


def trades_to_frame(trades: List[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    return pd.DataFrame([asdict(t) for t in trades])
