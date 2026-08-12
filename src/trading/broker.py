import os
import time
import logging
from datetime import datetime, timedelta
import requests
import pytz

logger = logging.getLogger("broker")
ET = pytz.timezone("America/New_York")

REJECTION_COOLDOWN_SECONDS = 300
_last_rejection_time = 0.0

def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET", ""),
        "Content-Type": "application/json",
    }

def _base_url() -> str:
    if os.getenv("ALPACA_IS_PAPER", "true").strip().lower() == "true":
        return "https://paper-api.alpaca.markets"
    return os.getenv("ALPACA_BASE_URL", "https://api.alpaca.markets")

def _data_url() -> str:
    return os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")

def extract_underlying(contract_symbol: str) -> str:
    for i, char in enumerate(contract_symbol):
        if char.isdigit():
            return contract_symbol[:i]
    return contract_symbol

def get_open_position(underlying: str) -> dict | None:
    """Authoritative position state from Alpaca."""
    try:
        url = f"{_base_url()}/v2/positions"
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        positions = resp.json()
        
        for pos in positions:
            symbol = pos.get("symbol", "")
            if symbol.startswith(underlying) and len(symbol) > len(underlying):
                return {
                    "symbol": underlying,
                    "contract_symbol": symbol,
                    "qty": abs(int(float(pos.get("qty", 1)))),
                    "fill_price": float(pos.get("avg_entry_price", 0)),
                    "direction": "LONG" if pos.get("side") == "long" else "SHORT"
                }
        return None
    except Exception as e:
        logger.error(f"Failed to fetch position from broker: {e}")
        return None

def cancel_all_orders(underlying: str = None):
    try:
        url = f"{_base_url()}/v2/orders"
        resp = requests.delete(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        logger.info("Cancelled all open orders on broker.")
    except Exception as e:
        logger.error(f"Failed to cancel orders: {e}")

def get_underlying_price(symbol: str) -> float:
    try:
        url = f"{_data_url()}/v2/stocks/{symbol}/trades/latest"
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return float(resp.json()["trade"]["p"])
    except Exception as e:
        logger.error(f"Error fetching underlying price: {e}")
        return 0.0

def get_daily_realized_pnl() -> float:
    """Fetch today's realized PnL via Alpaca Account Activities."""
    try:
        today = datetime.now(ET).strftime("%Y-%m-%d")
        url = f"{_base_url()}/v2/account/activities/FILL"
        params = {"date": today}
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        activities = resp.json()
        
        # NOTE: A robust implementation would calculate actual PnL from trades.
        # But Alpaca doesn't give PnL per trade directly in FILL activities.
        # However, it gives account PnL? Wait, we can just use the portfolio history or PNL activities if available.
        # Or calculate it locally. We'll return 0 for now unless we do full tracking.
        # Actually, for "minimal authoritative", we can get the daily PnL from `GET /v2/account`.
        url_acc = f"{_base_url()}/v2/account"
        acc_resp = requests.get(url_acc, headers=_headers(), timeout=10)
        acc_resp.raise_for_status()
        acc = acc_resp.json()
        equity = float(acc["equity"])
        last_equity = float(acc["last_equity"])
        return equity - last_equity
    except Exception as e:
        logger.error(f"Failed to fetch daily P&L from broker: {e}")
        return 0.0

def get_daily_trade_count() -> int:
    try:
        today = datetime.now(ET).strftime("%Y-%m-%d")
        url = f"{_base_url()}/v2/account/activities/FILL"
        params = {"date": today}
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        activities = resp.json()
        
        # Count only opening trades (where we increased position size)
        count = 0
        for act in activities:
            if "buy" in act.get("side", "").lower():  # Approximation for BTO
                count += 1
        return count
    except Exception as e:
        logger.error(f"Failed to fetch trade count from broker: {e}")
        return 0

def fetch_option_chain(underlying: str, expiration_date: str, option_type: str = "call") -> list:
    url = f"{_data_url()}/v2/options/contracts"
    params = {
        "underlying_symbols": underlying,
        "expiration_date": expiration_date,
        "type": option_type,
        "status": "active",
        "limit": 200,
    }
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        contracts = data.get("option_contracts", [])
        contracts.sort(key=lambda c: float(c.get("strike_price", 0)))
        return contracts
    except Exception as e:
        logger.error(f"Failed to fetch option chain: {e}")
        return []

def select_contract(underlying: str, underlying_price: float, option_type: str = "call") -> dict | None:
    from config import OPTION_EXPIRATION_MODE, OPTION_STRIKE_MODE
    today = datetime.now(ET).strftime("%Y-%m-%d")
    contracts = fetch_option_chain(underlying, today, option_type)
    if not contracts:
        return None
        
    target_strike = round(underlying_price)
    best = min(contracts, key=lambda c: abs(float(c.get("strike_price", 0)) - target_strike))
    return best

def get_option_quote(contract_symbol: str) -> dict:
    url = f"{_data_url()}/v2/options/quotes/latest"
    params = {"symbols": contract_symbol, "feed": "indicative"}
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        quotes = resp.json().get("quotes", {})
        q = quotes.get(contract_symbol, {})
        bid = float(q.get("bp", 0))
        ask = float(q.get("ap", 0))
        return {"bid": bid, "ask": ask, "mid": round((bid + ask) / 2, 2)}
    except Exception as e:
        logger.error(f"Failed to fetch quote: {e}")
        return {"bid": 0, "ask": 0, "mid": 0}

def _place_order(payload: dict) -> dict:
    url = f"{_base_url()}/v2/orders"
    resp = requests.post(url, json=payload, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()

def _execute_order_with_chase(order_id: str, side: str, max_chases: int = 3, chase_interval: int = 10) -> dict:
    current_order_id = order_id
    chase_count = 0
    while chase_count <= max_chases:
        deadline = time.time() + chase_interval
        filled_order = None
        while time.time() < deadline:
            resp = requests.get(f"{_base_url()}/v2/orders/{current_order_id}", headers=_headers(), timeout=10)
            order = resp.json()
            if order.get("status") == "filled":
                return order
            if order.get("status") in ("canceled", "expired", "rejected"):
                return order
            filled_order = order
            time.sleep(1.0)
            
        if chase_count >= max_chases:
            return filled_order
            
        contract_symbol = filled_order.get("symbol")
        try:
            quote = get_option_quote(contract_symbol)
            new_limit = quote["ask"] if side == "buy" else quote["bid"]
            old_limit = float(filled_order.get("limit_price", 0))
            if new_limit != old_limit and new_limit > 0:
                chase_count += 1
                logger.info(f"Chasing market for {contract_symbol}: limit {old_limit} -> {new_limit}")
                patch_url = f"{_base_url()}/v2/orders/{current_order_id}"
                patch_resp = requests.patch(patch_url, json={"limit_price": str(new_limit)}, headers=_headers(), timeout=15)
                if patch_resp.status_code == 200:
                    current_order_id = patch_resp.json().get("id")
        except Exception as e:
            logger.error(f"Chase error: {e}")
    return filled_order

def buy_to_open(underlying: str, direction: str, qty: int = 1) -> dict | None:
    global _last_rejection_time
    if (time.time() - _last_rejection_time) < REJECTION_COOLDOWN_SECONDS:
        return None
        
    option_type = "call" if direction == "LONG" else "put"
    underlying_price = get_underlying_price(underlying)
    
    contract = select_contract(underlying, underlying_price, option_type)
    if not contract: return None
    
    contract_symbol = contract["symbol"]
    quote = get_option_quote(contract_symbol)
    ask_price = quote["ask"]
    bid_price = quote["bid"]
    
    # Contract validation
    if ask_price <= 0 or bid_price <= 0: return None
    spread_pct = (ask_price - bid_price) / ask_price
    if spread_pct > 0.25: # Max 25% spread
        logger.warning(f"Spread too wide ({spread_pct*100:.1f}%) for {contract_symbol}")
        return None

    try:
        order = _place_order({
            "symbol": contract_symbol,
            "qty": str(qty),
            "side": "buy",
            "type": "limit",
            "limit_price": str(ask_price),
            "time_in_force": "day",
        })
        filled_order = _execute_order_with_chase(order.get("id"), side="buy")
        if filled_order.get("status") == "rejected":
            _last_rejection_time = time.time()
        return filled_order
    except Exception as e:
        logger.error(f"BTO failed: {e}")
        return None

def sell_to_close(contract_symbol: str, qty: int) -> dict | None:
    try:
        quote = get_option_quote(contract_symbol)
        bid_price = quote["bid"]
        if bid_price <= 0:
            logger.warning(f"Bid 0 for {contract_symbol}, likely worthless.")
            return {"status": "expired_worthless", "pnl": 0}
            
        order = _place_order({
            "symbol": contract_symbol,
            "qty": str(qty),
            "side": "sell",
            "type": "limit",
            "limit_price": str(bid_price),
            "time_in_force": "day",
        })
        return _execute_order_with_chase(order.get("id"), side="sell")
    except Exception as e:
        logger.error(f"STC failed: {e}")
        return None
