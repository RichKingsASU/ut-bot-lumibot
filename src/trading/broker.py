import os
import time
import logging
from datetime import datetime, timedelta
import requests
import pytz
import dateutil.parser

try:
    from .execution_lease import require_execution_lease
except ImportError:  # Direct canonical invocation: python src/trading/executor.py
    from execution_lease import require_execution_lease

logger = logging.getLogger("broker")
ET = pytz.timezone("America/New_York")

REJECTION_COOLDOWN_SECONDS = 300
MAX_OPTION_SPREAD_PCT = 0.25
MAX_OPTION_QUOTE_AGE_SECONDS = 60
_last_rejection_time = 0.0

def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET", ""),
        "Content-Type": "application/json",
    }

def _base_url() -> str:
    is_paper = os.getenv("ALPACA_IS_PAPER", "true").strip().lower() == "true"
    allow_live = os.getenv("ALLOW_LIVE_TRADING", "").strip() == "YES_I_UNDERSTAND"
    
    if is_paper:
        return "https://paper-api.alpaca.markets"
        
    if not allow_live:
        logger.error("CRITICAL: ALLOW_LIVE_TRADING != YES_I_UNDERSTAND. Refusing live endpoint.")
        return "https://paper-api.alpaca.markets" # Fail safe to paper
        
    return os.getenv("ALPACA_BASE_URL", "https://api.alpaca.markets")

# Add a startup log check
is_paper = os.getenv("ALPACA_IS_PAPER", "true").strip().lower() == "true"
logger.info("========================================")
logger.info(f"TRADING MODE: {'PAPER' if is_paper else 'LIVE'}")
logger.info(f"BROKER ENDPOINT: {_base_url()}")
logger.info("========================================")

def _data_url() -> str:
    return os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")

def extract_underlying(contract_symbol: str) -> str:
    for i, char in enumerate(contract_symbol):
        if char.isdigit():
            return contract_symbol[:i]
    return contract_symbol

def get_open_position(underlying: str) -> dict:
    """Authoritative position state from Alpaca. Returns dict with 'valid' and 'position'."""
    try:
        url = f"{_base_url()}/v2/positions"
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        positions = resp.json()
        
        for pos in positions:
            symbol = pos.get("symbol", "")
            if symbol.startswith(underlying) and len(symbol) > len(underlying):
                return {
                    "valid": True,
                    "position": {
                        "symbol": underlying,
                        "contract_symbol": symbol,
                        "qty": abs(int(float(pos.get("qty", 1)))),
                        "fill_price": float(pos.get("avg_entry_price", 0)),
                        "direction": "LONG" if pos.get("side") == "long" else "SHORT"
                    }
                }
        return {"valid": True, "position": None}
    except Exception as e:
        logger.error(f"Failed to fetch position from broker: {e}")
        return {"valid": False, "position": None}

def get_active_orders(underlying: str) -> dict:
    try:
        url = f"{_base_url()}/v2/orders"
        params = {"status": "open", "nested": "true"}
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        orders = resp.json()
        
        active = []
        for o in orders:
            symbol = o.get("symbol", "")
            if symbol.startswith(underlying):
                active.append(o)
                
        return {"valid": True, "orders": active}
    except Exception as e:
        logger.error(f"Failed to fetch active orders: {e}")
        return {"valid": False, "orders": []}

def get_account() -> dict:
    """Fetch account identity; exceptions deliberately propagate to reconciliation."""
    resp = requests.get(f"{_base_url()}/v2/account", headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_all_positions() -> list:
    resp = requests.get(f"{_base_url()}/v2/positions", headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_relevant_orders(after: str = None) -> list:
    params = {"status": "all", "nested": "true", "limit": 500}
    if after:
        params["after"] = after
    resp = requests.get(f"{_base_url()}/v2/orders", headers=_headers(), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_order_by_client_id(client_order_id: str) -> dict | None:
    resp = requests.get(f"{_base_url()}/v2/orders:by_client_order_id", headers=_headers(),
                        params={"client_order_id": client_order_id}, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()

class AlpacaRESTBroker:
    """Minimal canonical adapter consumed by broker reconciliation."""
    def account(self): return get_account()
    def positions(self): return get_all_positions()
    def orders(self): return get_relevant_orders()
    def order_by_client_id(self, value): return get_order_by_client_id(value)
    def submit(self, payload): return _place_order(payload)

def cancel_all_orders(underlying: str = None):
    require_execution_lease("cancel_all_orders")
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

def get_daily_realized_pnl() -> dict:
    """Fetch today's account equity change as a proxy for circuit breaker."""
    try:
        url_acc = f"{_base_url()}/v2/account"
        acc_resp = requests.get(url_acc, headers=_headers(), timeout=10)
        acc_resp.raise_for_status()
        acc = acc_resp.json()
        equity = float(acc["equity"])
        last_equity = float(acc["last_equity"])
        return {"valid": True, "value": equity - last_equity, "timestamp": datetime.now(ET).isoformat()}
    except Exception as e:
        logger.error(f"Failed to fetch daily P&L from broker: {e}")
        return {"valid": False, "value": 0.0, "reason": str(e), "timestamp": datetime.now(ET).isoformat()}

def get_daily_trade_count() -> dict:
    try:
        today = datetime.now(ET).strftime("%Y-%m-%d")
        url = f"{_base_url()}/v2/orders"
        params = {"status": "all", "after": f"{today}T00:00:00Z"}
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        orders = resp.json()
        
        # Count only filled opening orders to be deterministic
        count = 0
        for o in orders:
            # We assume "buy" is opening for our simple model (can be enhanced if shorting options)
            if o.get("side", "").lower() == "buy" and o.get("status") in ("filled", "partially_filled"):
                count += 1
        return {"valid": True, "count": count}
    except Exception as e:
        logger.error(f"Failed to fetch trade count from broker: {e}")
        return {"valid": False, "count": 0}

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
        
        # Explicit contract validation
        valid_contracts = []
        for c in contracts:
            if c.get("status") == "active" and c.get("tradable") and c.get("multiplier") == "100":
                valid_contracts.append(c)
                
        valid_contracts.sort(key=lambda c: float(c.get("strike_price", 0)))
        return valid_contracts
    except Exception as e:
        logger.error(f"Failed to fetch option chain: {e}")
        return []

def select_contract(underlying: str, underlying_price: float, option_type: str = "call") -> dict | None:
    today = datetime.now(ET).strftime("%Y-%m-%d")
    contracts = fetch_option_chain(underlying, today, option_type)
    if not contracts:
        return None
        
    target_strike = round(underlying_price)
    best = min(contracts, key=lambda c: abs(float(c.get("strike_price", 0)) - target_strike))
    logger.info(f"Selected contract: {best.get('symbol')} Strike: {best.get('strike_price')}")
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
        ts_str = q.get("t")
        
        valid = True
        reason = ""
        
        if bid <= 0 or ask <= 0 or ask < bid:
            valid = False
            reason = "invalid_bid_ask"
            
        mid = (bid + ask) / 2
        if mid <= 0:
            valid = False
            reason = "invalid_mid"
            
        spread_pct = (ask - bid) / ask if ask > 0 else 1.0
        if spread_pct > MAX_OPTION_SPREAD_PCT:
            valid = False
            reason = "spread_too_wide"
            
        if ts_str:
            try:
                quote_time = dateutil.parser.isoparse(ts_str)
                age = (datetime.now(pytz.utc) - quote_time).total_seconds()
                if age > MAX_OPTION_QUOTE_AGE_SECONDS:
                    valid = False
                    reason = "quote_stale"
            except Exception:
                pass
                
        return {"valid": valid, "bid": bid, "ask": ask, "mid": round(mid, 2), "reason": reason}
    except Exception as e:
        logger.error(f"Failed to fetch quote: {e}")
        return {"valid": False, "bid": 0, "ask": 0, "mid": 0, "reason": "api_error"}

def _place_order(payload: dict) -> dict:
    require_execution_lease("submit_order")
    url = f"{_base_url()}/v2/orders"
    resp = requests.post(url, json=payload, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()

def _execute_order_with_chase(order_id: str, side: str, max_chases: int = 3, chase_interval: int = 10) -> dict:
    require_execution_lease("replace_order")
    current_order_id = order_id
    chase_count = 0
    while chase_count <= max_chases:
        deadline = time.time() + chase_interval
        filled_order = None
        while time.time() < deadline:
            resp = requests.get(f"{_base_url()}/v2/orders/{current_order_id}", headers=_headers(), timeout=10)
            order = resp.json()
            status = order.get("status")
            
            # Partial fills are tricky, we only consider it completely done if 'filled' or dead state
            if status == "filled":
                return order
            if status in ("canceled", "expired", "rejected", "replaced"):
                # If it was partially filled and then canceled, it's effectively "partially_filled" overall but let's return it
                return order
                
            filled_order = order
            time.sleep(1.0)
            
        if chase_count >= max_chases:
            return filled_order
            
        contract_symbol = filled_order.get("symbol")
        try:
            quote = get_option_quote(contract_symbol)
            if not quote["valid"]:
                logger.warning(f"Quote invalid during chase: {quote['reason']}")
                break
                
            new_limit = quote["ask"] if side == "buy" else quote["bid"]
            old_limit = float(filled_order.get("limit_price", 0))
            if new_limit != old_limit and new_limit > 0:
                chase_count += 1
                logger.info(f"Chasing market for {contract_symbol}: limit {old_limit} -> {new_limit}")
                patch_url = f"{_base_url()}/v2/orders/{current_order_id}"
                require_execution_lease("replace_order")
                requested = float(filled_order.get("qty", 0) or 0)
                filled = float(filled_order.get("filled_qty", 0) or 0)
                remaining = max(0.0, requested - filled)
                if remaining <= 0:
                    return filled_order
                patch_resp = requests.patch(patch_url, json={"limit_price": str(new_limit), "qty": str(remaining)}, headers=_headers(), timeout=15)
                if patch_resp.status_code == 200:
                    current_order_id = patch_resp.json().get("id")
        except Exception as e:
            logger.error(f"Chase error: {e}")
            break
            
    return filled_order

def buy_to_open(underlying: str, direction: str, qty: int = 1, client_order_id: str = None) -> dict | None:
    require_execution_lease("buy_to_open")
    global _last_rejection_time
    if (time.time() - _last_rejection_time) < REJECTION_COOLDOWN_SECONDS:
        return None
        
    option_type = "call" if direction == "LONG" else "put"
    underlying_price = get_underlying_price(underlying)
    
    contract = select_contract(underlying, underlying_price, option_type)
    if not contract: return None
    
    contract_symbol = contract["symbol"]
    quote = get_option_quote(contract_symbol)
    
    if not quote["valid"]:
        logger.warning(f"BTO blocked. Invalid quote for {contract_symbol}: {quote['reason']}")
        return None
        
    ask_price = quote["ask"]

    try:
        payload = {
            "symbol": contract_symbol,
            "qty": str(qty),
            "side": "buy",
            "type": "limit",
            "limit_price": str(ask_price),
            "time_in_force": "day",
        }
        if client_order_id:
            payload["client_order_id"] = client_order_id
        try:
            order = _place_order(payload)
        except Exception:
            # Resolve an ambiguous POST using the same deterministic correlation ID.
            if not client_order_id:
                raise
            order = get_order_by_client_id(client_order_id)
            if order is None:
                raise RuntimeError("submit outcome absent; do not retry with a new client order ID")
            logger.warning("LOST_RESPONSE_RECOVERED client_order_id=%s broker_order_id=%s",
                           client_order_id, order.get("id"))
        filled_order = _execute_order_with_chase(order.get("id"), side="buy")
        if filled_order.get("status") == "rejected":
            _last_rejection_time = time.time()
        return filled_order
    except Exception as e:
        logger.error(f"BTO failed: {e}")
        return None

def sell_to_close(contract_symbol: str, qty: int) -> dict | None:
    require_execution_lease("sell_to_close")
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
