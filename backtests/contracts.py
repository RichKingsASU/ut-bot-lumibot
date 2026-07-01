"""
Contract selection + OCC symbol construction.

Reuses the SELECTION RULES from ``strategies/options_executor.py``:
  * ``_compute_strike_offset()``  → strike-mode offset table
  * ``select_contract()``         → target strike = round(price) + offset,
                                     nearest listed strike on the step grid
  * expiry math analogous to ``_compute_target_expiration()`` but parameterized
    by an explicit DTE (the backtest sweeps DTE {3,4,5}).

IMPORTANT (per task): we do NOT call the live ``/v2/options/contracts`` chain
endpoint for historical dates — it only returns *currently active* contracts.
Instead we apply the selection rules to compute the target strike + expiry and
construct the OCC symbol directly, in the exact format parsed by
``sync_state_with_broker`` (SYMBOL + YYMMDD + C/P + strike*1000 zero-padded to
8 digits). That symbol is then handed to the quote provider for historical
pricing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Strike-mode offsets — copied from options_executor._compute_strike_offset()
_STRIKE_OFFSETS = {
    "ITM3": -3, "ITM2": -2, "ITM1": -1,
    "ATM": 0,
    "OTM1": 1, "OTM2": 2, "OTM3": 3,
}


@dataclass(frozen=True)
class Contract:
    symbol: str          # OCC symbol, e.g. IWM240705C00200000
    underlying: str
    option_type: str     # "call" | "put"
    strike: float
    expiry: date
    dte: int             # actual calendar DTE from entry to expiry


def strike_offset(strike_mode: str, strike_step: float) -> float:
    """options_executor._compute_strike_offset() — offset in *dollars*."""
    return _STRIKE_OFFSETS.get(strike_mode, 0) * strike_step


def target_strike(underlying_price: float, strike_mode: str, strike_step: float,
                  option_type: str) -> float:
    """Target strike per options_executor.select_contract().

    Production computes ``round(price) + offset`` where the offset table is
    expressed in strike-steps *toward ITM* (negative = ITM). For a PUT, "ITM"
    is above spot, so the sign of the moneyness offset flips. The offset table
    is defined for calls; we mirror it for puts so ITM1 is genuinely in-the-money
    on both sides.
    """
    off = strike_offset(strike_mode, strike_step)
    if option_type == "put":
        off = -off
    raw = round(underlying_price) + off
    # Snap to the listed strike grid (nearest multiple of strike_step).
    return round(raw / strike_step) * strike_step


def resolve_expiry(entry_day: date, dte: int) -> date:
    """Target expiration = entry + dte calendar days, snapped to a business day.

    IWM lists daily/weekly expirations (Mon-Fri) plus monthlies. Without a
    historical chain endpoint we assume a listed expiry exists on the target
    business day; if the target lands on a weekend we roll forward to Monday
    (documented in the Assumptions block).
    """
    d = entry_day + timedelta(days=dte)
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d += timedelta(days=1)
    return d


def build_occ_symbol(underlying: str, expiry: date, option_type: str,
                     strike: float) -> str:
    """OCC symbol in the exact format parsed by sync_state_with_broker().

    SYMBOL + YYMMDD + C/P + int(round(strike*1000)) zero-padded to 8 digits.
    """
    cp = "C" if option_type == "call" else "P"
    strike_int = int(round(strike * 1000))
    return f"{underlying}{expiry:%y%m%d}{cp}{strike_int:08d}"


def select_contract(underlying: str, underlying_price: float, direction: str,
                    entry_day: date, dte: int, strike_mode: str,
                    strike_step: float) -> Contract:
    """Full selection: direction → type → strike → expiry → OCC symbol."""
    option_type = "call" if direction == "LONG" else "put"
    strike = target_strike(underlying_price, strike_mode, strike_step, option_type)
    expiry = resolve_expiry(entry_day, dte)
    symbol = build_occ_symbol(underlying, expiry, option_type, strike)
    actual_dte = (expiry - entry_day).days
    return Contract(
        symbol=symbol,
        underlying=underlying,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        dte=actual_dte,
    )
