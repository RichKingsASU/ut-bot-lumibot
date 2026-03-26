"""
Options Execution Layer for UT Bot Strategy.

Handles the complete options trade lifecycle via Alpaca REST API:
  - Option chain fetch and ATM strike selection
  - Buy-to-open (calls and puts)
  - Sell-to-close (same contract)
  - Position tracking, error handling, cooldown logic
"""

import os
import time
import logging
import threading
from datetime import datetime, timedelta

import requests
import pytz

logger = logging.getLogger("options_executor")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(_handler)

ET = pytz.timezone("America/New_York")

# ── Module-level position state ──────────────────────────────────────────────
open_position: dict = {}
# When populated:
# {
#     "contract_symbol": "SPY260326C00580000",
#     "strike": 580.0,
#     "expiration": "2026-03-26",
#     "option_type": "call" | "put",
#     "qty": 1,
#     "fill_price": 2.35,
#     "entry_time": datetime,
#     "entry_underlying_price": 580.12,
#     "entry_rsi": 62.4,
#     "direction": "LONG" | "SHORT",
# }

# Cooldown state — after a rejected order, wait before retrying
_last_rejection_time: float = 0.0
REJECTION_COOLDOWN_SECONDS = 300  # 5 minutes


def _headers() -> dict:
    """Build Alpaca auth headers from environment."""
    api_key = os.getenv("ALPACA_API_KEY", "")
    api_secret = os.getenv("ALPACA_API_SECRET", "")
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")


def _data_url() -> str:
    return os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")


# ── Supabase fire-and-forget logging ─────────────────────────────────────────

def _log_trade_to_supabase(trade_record: dict):
    """Fire-and-forget trade log to Supabase. Never blocks the trade loop."""
    supa_url = os.getenv("SUPABASE_URL")
    supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supa_url or not supa_key:
        return
    try:
        from supabase import create_client
        client = create_client(supa_url, supa_key)
        client.table("trade_log").insert(trade_record).execute()
        logger.info("Trade logged to Supabase")
    except Exception as e:
        logger.warning("Supabase log failed (non-blocking): %s", e)


def log_trade_async(trade_record: dict):
    """Spawn a daemon thread so Supabase write never blocks."""
    t = threading.Thread(target=_log_trade_to_supabase, args=(trade_record,), daemon=True)
    t.start()


# ── Option chain + pricing ───────────────────────────────────────────────────

def get_underlying_price(symbol: str = "SPY") -> float:
    """Fetch latest trade price for the underlying via Alpaca data API."""
    url = f"{_data_url()}/v2/stocks/{symbol}/trades/latest"
    resp = requests.get(url, headers=_headers(), timeout=10)
    resp.raise_for_status()
    return float(resp.json()["trade"]["p"])


def fetch_option_chain(underlying: str, expiration_date: str,
                       option_type: str = "call") -> list[dict]:
    """
    Fetch option contracts from Alpaca for a given underlying, expiration, and type.
    Returns a list of contract dicts sorted by strike price.
    """
    url = f"{_data_url()}/v2/options/contracts"
    params = {
        "underlying_symbols": underlying,
        "expiration_date": expiration_date,
        "type": option_type,
        "status": "active",
        "limit": 200,
    }
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    contracts = data.get("option_contracts", data.get("contracts", []))
    if not contracts:
        logger.warning("No %s contracts found for %s exp %s",
                        option_type, underlying, expiration_date)
        return []
    contracts.sort(key=lambda c: float(c.get("strike_price", 0)))
    return contracts


def select_atm_contract(underlying: str, underlying_price: float,
                        option_type: str = "call",
                        expiration_date: str | None = None) -> dict | None:
    """
    Select the at-the-money contract:
      - expiration defaults to today (0DTE) in ET
      - ATM = nearest strike to round(underlying_price)
    Returns the contract dict or None.
    """
    if expiration_date is None:
        expiration_date = datetime.now(ET).strftime("%Y-%m-%d")

    contracts = fetch_option_chain(underlying, expiration_date, option_type)
    if not contracts:
        return None

    target_strike = round(underlying_price)
    best = min(contracts,
               key=lambda c: abs(float(c.get("strike_price", 0)) - target_strike))
    logger.info("ATM %s selected: strike=%.2f  symbol=%s  exp=%s",
                option_type.upper(),
                float(best.get("strike_price", 0)),
                best.get("symbol", "?"),
                expiration_date)
    return best


def get_option_quote(contract_symbol: str) -> dict:
    """
    Fetch latest quote (bid/ask) for a specific option contract.
    Returns {"bid": float, "ask": float, "mid": float}.
    """
    url = f"{_data_url()}/v2/options/quotes/latest"
    params = {"symbols": contract_symbol, "feed": "indicative"}
    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    quotes = data.get("quotes", {})
    q = quotes.get(contract_symbol, {})
    bid = float(q.get("bp", 0))
    ask = float(q.get("ap", 0))
    return {"bid": bid, "ask": ask, "mid": round((bid + ask) / 2, 2)}


# ── Order placement ──────────────────────────────────────────────────────────

def _place_order(payload: dict) -> dict:
    """Submit an order to Alpaca and return the response JSON."""
    url = f"{_base_url()}/v2/orders"
    resp = requests.post(url, json=payload, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def _wait_for_fill(order_id: str, timeout: int = 30, poll_interval: float = 1.0) -> dict:
    """Poll order status until filled or timeout."""
    url = f"{_base_url()}/v2/orders/{order_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        order = resp.json()
        status = order.get("status", "")
        if status == "filled":
            return order
        if status in ("canceled", "expired", "rejected", "suspended"):
            return order
        time.sleep(poll_interval)
    resp = requests.get(url, headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()


# ── Buy-to-Open ──────────────────────────────────────────────────────────────

def buy_to_open(underlying: str, direction: str, qty: int = 1,
                underlying_price: float | None = None,
                current_rsi: float | None = None) -> dict | None:
    """
    Place a buy-to-open order for a CALL (direction=LONG) or PUT (direction=SHORT).

    Steps:
      1. Guard: no double-entry, cooldown check
      2. Fetch underlying price if not provided
      3. Select ATM 0DTE contract
      4. Fetch ask price
      5. Submit limit buy order at the ask
      6. Wait for fill
      7. Store in open_position
      8. Return order dict

    Returns the filled order dict, or None on failure.
    """
    global open_position, _last_rejection_time

    # ── Guard: no double entry ───────────────────────────────────────────
    if open_position:
        logger.warning("buy_to_open blocked — position already open: %s",
                        open_position.get("contract_symbol"))
        return None

    # ── Guard: rejection cooldown ────────────────────────────────────────
    elapsed = time.time() - _last_rejection_time
    if elapsed < REJECTION_COOLDOWN_SECONDS:
        remaining = REJECTION_COOLDOWN_SECONDS - elapsed
        logger.warning("buy_to_open blocked — cooldown active (%.0fs remaining)", remaining)
        return None

    option_type = "call" if direction == "LONG" else "put"

    try:
        # 1. Underlying price
        if underlying_price is None:
            underlying_price = get_underlying_price(underlying)
        logger.info("Underlying %s price: %.2f", underlying, underlying_price)

        # 2. Select ATM contract (0DTE)
        contract = select_atm_contract(underlying, underlying_price, option_type)
        if contract is None:
            logger.error("No ATM %s contract found — skipping entry", option_type)
            return None

        contract_symbol = contract["symbol"]
        strike = float(contract.get("strike_price", 0))
        expiration = contract.get("expiration_date", "")

        # 3. Fetch ask price
        quote = get_option_quote(contract_symbol)
        ask_price = quote["ask"]
        if ask_price <= 0:
            logger.error("Ask price is zero for %s — skipping entry", contract_symbol)
            return None
        logger.info("Quote for %s: bid=%.2f ask=%.2f", contract_symbol,
                     quote["bid"], ask_price)

        # 4. Submit limit buy
        order_payload = {
            "symbol": contract_symbol,
            "qty": str(qty),
            "side": "buy",
            "type": "limit",
            "limit_price": str(ask_price),
            "time_in_force": "day",
        }
        logger.info("Submitting BUY-TO-OPEN: %s qty=%d @ %.2f",
                     contract_symbol, qty, ask_price)
        order = _place_order(order_payload)
        order_id = order.get("id", "")

        # 5. Wait for fill
        filled_order = _wait_for_fill(order_id, timeout=30)
        status = filled_order.get("status", "")

        if status != "filled":
            logger.error("Order %s not filled — status=%s", order_id, status)
            if status == "rejected":
                _last_rejection_time = time.time()
                logger.error("Rejection reason: %s",
                             filled_order.get("reject_reason", "unknown"))
            return None

        fill_price = float(filled_order.get("filled_avg_price", ask_price))
        filled_qty = int(filled_order.get("filled_qty", qty))

        # 6. Store position
        open_position = {
            "contract_symbol": contract_symbol,
            "strike": strike,
            "expiration": expiration,
            "option_type": option_type,
            "qty": filled_qty,
            "fill_price": fill_price,
            "entry_time": datetime.now(ET),
            "entry_underlying_price": underlying_price,
            "entry_rsi": current_rsi,
            "direction": direction,
            "order_id": order_id,
        }
        logger.info("POSITION OPENED: %s %s strike=%.2f qty=%d fill=%.2f",
                     direction, contract_symbol, strike, filled_qty, fill_price)
        return filled_order

    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error during buy_to_open: %s", e)
        if e.response is not None and e.response.status_code in (403, 422):
            _last_rejection_time = time.time()
        return None
    except Exception as e:
        logger.error("Unexpected error during buy_to_open: %s", e)
        return None


# ── Sell-to-Close ────────────────────────────────────────────────────────────

def sell_to_close(exit_reason: str = "signal") -> dict | None:
    """
    Close the current open position by selling the SAME contract.

    Steps:
      1. Guard: must have open position
      2. Fetch current bid for the held contract
      3. Submit limit sell at the bid
      4. Wait for fill
      5. Log trade (P&L) to Supabase fire-and-forget
      6. Clear open_position
      7. Return order dict

    Returns the filled order dict, or None on failure.
    """
    global open_position

    if not open_position:
        logger.warning("sell_to_close called but no open position")
        return None

    contract_symbol = open_position["contract_symbol"]
    qty = open_position["qty"]

    try:
        # 1. Fetch bid price for the SAME contract
        quote = get_option_quote(contract_symbol)
        bid_price = quote["bid"]

        # Handle expired-worthless: bid is 0
        if bid_price <= 0:
            logger.warning("Bid is 0 for %s — contract likely expired worthless",
                           contract_symbol)
            # Log the loss and clear position
            pnl = -(open_position["fill_price"] * qty * 100)
            trade_record = _build_trade_record(0.0, pnl, exit_reason)
            log_trade_async(trade_record)
            logger.info("POSITION CLOSED (expired worthless): P&L=$%.2f", pnl)
            open_position = {}
            return {"status": "expired_worthless", "pnl": pnl}

        # 2. Submit limit sell
        order_payload = {
            "symbol": contract_symbol,
            "qty": str(qty),
            "side": "sell",
            "type": "limit",
            "limit_price": str(bid_price),
            "time_in_force": "day",
        }
        logger.info("Submitting SELL-TO-CLOSE: %s qty=%d @ %.2f  reason=%s",
                     contract_symbol, qty, bid_price, exit_reason)
        order = _place_order(order_payload)
        order_id = order.get("id", "")

        # 3. Wait for fill
        filled_order = _wait_for_fill(order_id, timeout=30)
        status = filled_order.get("status", "")

        if status != "filled":
            logger.error("Sell order %s not filled — status=%s", order_id, status)
            return None

        exit_price = float(filled_order.get("filled_avg_price", bid_price))

        # 4. Calculate P&L (per contract = 100 shares)
        pnl = (exit_price - open_position["fill_price"]) * qty * 100
        if open_position["direction"] == "SHORT":
            # For puts, profit when price goes down, but we're buying a put
            # so P&L is simply exit - entry (same formula, put value increases
            # when underlying drops)
            pass

        # 5. Log to Supabase (fire-and-forget)
        trade_record = _build_trade_record(exit_price, pnl, exit_reason)
        log_trade_async(trade_record)

        logger.info("POSITION CLOSED: %s exit=%.2f P&L=$%.2f reason=%s",
                     contract_symbol, exit_price, pnl, exit_reason)

        # 6. Clear position
        open_position = {}
        return filled_order

    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error during sell_to_close: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error during sell_to_close: %s", e)
        return None


def _build_trade_record(exit_price: float, pnl: float, exit_reason: str) -> dict:
    """Build a trade log record from the current open_position."""
    return {
        "contract_symbol": open_position.get("contract_symbol"),
        "direction": open_position.get("direction"),
        "option_type": open_position.get("option_type"),
        "strike": open_position.get("strike"),
        "expiration": open_position.get("expiration"),
        "qty": open_position.get("qty"),
        "entry_price": open_position.get("fill_price"),
        "exit_price": exit_price,
        "pnl": round(pnl, 2),
        "entry_time": open_position.get("entry_time", "").isoformat()
            if hasattr(open_position.get("entry_time", ""), "isoformat") else "",
        "exit_time": datetime.now(ET).isoformat(),
        "exit_reason": exit_reason,
        "entry_underlying_price": open_position.get("entry_underlying_price"),
    }


# ── Utility: check if position is open ───────────────────────────────────────

def has_open_position() -> bool:
    return bool(open_position)


def get_open_position() -> dict:
    return dict(open_position)


def is_in_cooldown() -> bool:
    return (time.time() - _last_rejection_time) < REJECTION_COOLDOWN_SECONDS
