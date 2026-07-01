"""
Fill / cost model — the whole point of the harness.

Realism rules (per task):
  * ENTER at the ASK, EXIT at the BID (pay the full bid-ask spread).
  * Add a configurable extra slippage haircut (default 1 tick) on each side.
  * SEPARATELY track a mid-to-mid "gross" P&L so the spread cost is explicit.
  * Report the average spread paid per trade and the % of gross edge lost to
    the spread — the headline number.

All prices are per-share; option contracts carry a 100x multiplier.
"""

from __future__ import annotations

from dataclasses import dataclass

from .quotes import Quote


@dataclass
class Fill:
    """A single side of a trade after costs."""

    price: float          # actual fill (ask+slip on entry, bid-slip on exit)
    mid: float            # mid at the same instant (for gross P&L)
    bid: float
    ask: float
    priced_via: str


def entry_fill(quote: Quote, cfg) -> Fill:
    """Buy-to-open: fill at ASK + slippage (mirrors options_executor buy_to_open,
    which submits a limit at the ask)."""
    slip = cfg.slippage_ticks * cfg.tick_size
    return Fill(
        price=round(quote.ask + slip, 4),
        mid=quote.mid,
        bid=quote.bid,
        ask=quote.ask,
        priced_via=quote.priced_via,
    )


def exit_fill(quote: Quote, cfg) -> Fill:
    """Sell-to-close: fill at BID - slippage (mirrors options_executor
    sell_to_close, which submits a limit at the bid)."""
    slip = cfg.slippage_ticks * cfg.tick_size
    return Fill(
        price=max(0.0, round(quote.bid - slip, 4)),
        mid=quote.mid,
        bid=quote.bid,
        ask=quote.ask,
        priced_via=quote.priced_via,
    )


@dataclass
class TradeCosts:
    gross_pnl: float          # mid-to-mid, per position ($)
    net_pnl: float            # ask->bid + slippage + commission ($)
    spread_paid: float        # $ lost to bid-ask + slippage (gross - net less commission)
    commission: float         # $
    entry_spread: float       # per-share ask-bid at entry
    exit_spread: float        # per-share ask-bid at exit


def compute_costs(entry: Fill, exit_: Fill, qty: int, cfg) -> TradeCosts:
    """Compute gross (mid-to-mid) and net ($ paid) P&L for a long-premium trade.

    Both call and put backtests are *long premium* (buy CALL for LONG, buy PUT
    for SHORT), so P&L is always (exit - entry) on the option price.
    """
    mult = cfg.contract_multiplier * qty

    gross = (exit_.mid - entry.mid) * mult
    commission = 2 * cfg.commission_per_contract * qty  # entry + exit
    net = (exit_.price - entry.price) * mult - commission

    # Spread+slippage cost = the gap between the mid-to-mid ideal and the actual
    # cash fills, excluding commission (reported separately).
    spread_paid = gross - (net + commission)

    return TradeCosts(
        gross_pnl=round(gross, 2),
        net_pnl=round(net, 2),
        spread_paid=round(spread_paid, 2),
        commission=round(commission, 2),
        entry_spread=round(entry.ask - entry.bid, 4),
        exit_spread=round(exit_.ask - exit_.bid, 4),
    )
