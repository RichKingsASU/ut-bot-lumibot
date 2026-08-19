import os
import time
import logging
from datetime import datetime
import pytz
import json

import pandas_market_calendars as mcal
import pandas as pd

from broker import (
    get_open_position, get_daily_realized_pnl, get_daily_trade_count,
    buy_to_open, sell_to_close, cancel_all_orders, get_active_orders, AlpacaRESTBroker
)
from order_state import OrderIntent, client_order_id
from reconciliation import BrokerReconciler, DurableState
from signal_engine import evaluate_signal
from risk_supervisor import RiskSupervisor
from execution_lease import (
    ExecutionLease, ExecutionLeaseError, execution_lease_state,
    install_execution_lease,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("executor")
ET = pytz.timezone("America/New_York")

RUNTIME_STATE_FILE = "/run/disrupting-alpha/runtime_state.json"
LAST_SIGNAL_FILE = "/run/disrupting-alpha/last_signal.json"
BROKER_STATE_FILE = os.getenv("BROKER_STATE_FILE", "/run/disrupting-alpha/broker_state.v1.json")

# Simple local state to supplement authoritative broker state
_local_state = {
    "entry_underlying_price": None,
    "entry_rsi": None,
    "last_signal_time": None
}

def acquire_execution_authority() -> ExecutionLease:
    """Acquire authority before constructing any money-moving runtime."""
    lease = ExecutionLease.from_environment(process_name="canonical-executor")
    lease.acquire()
    install_execution_lease(lease)
    return lease

def write_runtime_state(state: dict):
    os.makedirs(os.path.dirname(RUNTIME_STATE_FILE), exist_ok=True)
    try:
        with open(RUNTIME_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write runtime state: {e}")

def load_last_signal():
    try:
        if os.path.exists(LAST_SIGNAL_FILE):
            with open(LAST_SIGNAL_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load last signal: {e}")
    return {"date": None, "direction": 0}

def save_last_signal(date_str, direction):
    os.makedirs(os.path.dirname(LAST_SIGNAL_FILE), exist_ok=True)
    try:
        with open(LAST_SIGNAL_FILE, "w") as f:
            json.dump({"date": date_str, "direction": direction}, f)
    except Exception as e:
        logger.error(f"Failed to save last signal: {e}")

def get_market_times():
    nyse = mcal.get_calendar('NYSE')
    now = datetime.now(ET)
    schedule = nyse.schedule(start_date=now.date(), end_date=now.date())
    if schedule.empty:
        return None
        
    market_close = schedule.iloc[0]['market_close'].astimezone(ET)
    return market_close

def verify_and_flatten(symbol: str, supervisor):
    logger.info("EOD Flatten started. Entering verification loop.")
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        logger.info(f"EOD Flatten Check {retry_count+1}/{max_retries}")
        # 1. Cancel active orders
        cancel_all_orders(symbol)
        time.sleep(1)
        
        # 2. Check position
        pos_result = get_open_position(symbol)
        position = pos_result.get("position")
        if not position and pos_result.get("valid"):
            logger.info("EOD_FLATTEN_COMPLETE. Position is flat.")
            return True
            
        # 3. Submit close
        if position:
            logger.info(f"Position found during flatten. Submitting STC for {position['qty']} {position['contract_symbol']}")
            sell_to_close(position["contract_symbol"], position["qty"])
        
        # 4. Wait
        time.sleep(5)
        retry_count += 1
        
    logger.error("CRITICAL: EOD_FLATTEN_FAILED. Max retries exceeded.")
    return False

def main_loop():
    lease = acquire_execution_authority()
    
    # Configuration
    config = {
        "SYMBOL": "SPY",
        "MAX_DAILY_LOSS": os.getenv("MAX_DAILY_LOSS", "500.0"),
        "MAX_TRADES_PER_DAY": os.getenv("MAX_TRADES_PER_DAY", "10"),
        "MAX_POSITION_SIZE": int(os.getenv("MAX_POSITION_SIZE", "1")),
        "ENTRY_CUTOFF_MINUTES": int(os.getenv("ENTRY_CUTOFF_MINUTES_BEFORE_CLOSE", "15")),
        "FLATTEN_MINUTES": int(os.getenv("FLATTEN_MINUTES_BEFORE_CLOSE", "5")),
        "RSI_STEP_THRESH": os.getenv("RSI_STEP_THRESH", "5.0"),
        "STOP_PCT": os.getenv("STOP_PCT", "0.005")
    }
    
    supervisor = RiskSupervisor(broker=None, config=config)
    symbol = config["SYMBOL"]
    reconciler = BrokerReconciler(AlpacaRESTBroker(), DurableState(BROKER_STATE_FILE),
                                  lambda: lease.owned,
                                  "paper" if os.getenv("ALPACA_IS_PAPER", "true").lower() == "true" else "live")

    # Startup is not readiness: REST account, position and order reconstruction
    # must complete after lease acquisition and before an entry can be considered.
    startup_reconciliation = reconciler.reconcile()
    if not startup_reconciliation.valid:
        logger.error("ENTRY_BLOCKED_RECONCILIATION: %s", startup_reconciliation.reason_codes)
    
    logger.info("Starting Execution Engine Loop...")
    
    while True:
        try:
            # 1. RISK SUPERVISOR CADENCE (Every 5 seconds)
            time.sleep(5)
            
            # Authoritative State Sync
            pos_result = get_open_position(symbol)
            orders_result = get_active_orders(symbol)
            daily_pnl_result = get_daily_realized_pnl()
            daily_trades_result = get_daily_trade_count()
            
            reconciliation = reconciler.reconcile()
            broker_state_valid = (pos_result.get("valid", False) and orders_result.get("valid", False)
                                  and reconciliation.valid)
            position = pos_result.get("position")
            active_orders = orders_result.get("orders", [])
            daily_pnl = daily_pnl_result.get("value", 0.0)
            daily_trades = daily_trades_result.get("count", 0)
            pnl_valid = daily_pnl_result.get("valid", False)
            
            # Reconstruct local entry state if we have a position
            if position:
                position["entry_underlying_price"] = _local_state["entry_underlying_price"]
                position["entry_rsi"] = _local_state["entry_rsi"]
            else:
                _local_state["entry_underlying_price"] = None
                _local_state["entry_rsi"] = None
                
            entry_allowed = broker_state_valid and pnl_valid and lease.owned and reconciliation.entry_allowed
            entry_block_reason = None
            if not broker_state_valid:
                entry_block_reason = "BROKER_STATE_INVALID"
            elif not pnl_valid:
                entry_block_reason = "PNL_INVALID"
                
            has_opening_orders = any(o.get("side") == "buy" for o in active_orders)
            if has_opening_orders:
                entry_allowed = False
                entry_block_reason = "ACTIVE_OPENING_ORDER"
            
            # Local Kill Switch
            if supervisor.is_kill_switch_active():
                logger.error("KILL_SWITCH_ACTIVATED")
                cancel_all_orders(symbol)
                if position:
                    sell_to_close(position["contract_symbol"], position["qty"])
                write_runtime_state({
                    "process_alive": True, "kill_switch_active": True, "entry_allowed": False, 
                    "entry_block_reason": "KILL_SWITCH", **execution_lease_state()
                })
                continue # Block all further processing
                
            # EOD Flatten / Market Hours
            market_close = get_market_times()
            now_et = datetime.now(ET)
            eod_flatten_triggered = False
            
            if market_close:
                flatten_time = market_close - pd.Timedelta(minutes=config["FLATTEN_MINUTES"])
                entry_cutoff_time = market_close - pd.Timedelta(minutes=config["ENTRY_CUTOFF_MINUTES"])
                
                if now_et >= flatten_time:
                    eod_flatten_triggered = True
                    entry_allowed = False
                    entry_block_reason = "EOD_FLATTEN"
                elif now_et >= entry_cutoff_time:
                    entry_allowed = False
                    entry_block_reason = "EOD_ENTRY_CUTOFF"
            else:
                # Market closed today
                entry_allowed = False
                entry_block_reason = "MARKET_CLOSED"
                
            if eod_flatten_triggered and (position or active_orders):
                logger.info("EOD_FLATTEN_STARTED")
                success = verify_and_flatten(symbol, supervisor)
                write_runtime_state({
                    "process_alive": True, "kill_switch_active": False, "entry_allowed": False, 
                    "eod_flatten_required": not success, **execution_lease_state()
                })
                continue
                
            # Evaluate Data & Signals
            sig_snapshot = evaluate_signal(symbol)
            if not sig_snapshot.valid:
                entry_allowed = False
                entry_block_reason = f"MARKET_DATA_INVALID: {sig_snapshot.reason}"
                logger.warning(f"MARKET_DATA_STALE: {sig_snapshot.reason}")
            
            current_price = sig_snapshot.underlying_price
            current_rsi = sig_snapshot.rsi_5m
            signal = sig_snapshot.signal
            
            # Position Management (Exit Logic)
            if position:
                exit_reason = supervisor.check_exit_triggers(position, current_price, current_rsi)
                if exit_reason:
                    logger.info(f"Exit triggered: {exit_reason}")
                    sell_to_close(position["contract_symbol"], position["qty"])
                elif signal != 0:
                    # Strategy flip or close signal (e.g. signal=-1 while LONG)
                    if (position["direction"] == "LONG" and signal == -1) or \
                       (position["direction"] == "SHORT" and signal == 1):
                        logger.info("Signal flipped. Exiting position.")
                        sell_to_close(position["contract_symbol"], position["qty"])
            
            # Entry Logic (If no position)
            last_sig = load_last_signal()
            signal_date_str = sig_snapshot.daily_bar_timestamp.strftime("%Y-%m-%d") if sig_snapshot.daily_bar_timestamp else ""
            
            if entry_allowed and not position and not has_opening_orders:
                if signal != 0:
                    if last_sig.get("date") == signal_date_str and last_sig.get("direction") == signal:
                        logger.info("SIGNAL_ALREADY_CONSUMED")
                        entry_allowed = False
                        entry_block_reason = "SIGNAL_ALREADY_CONSUMED"
                    elif not supervisor.enforce_limits(daily_pnl, daily_trades):
                        entry_allowed = False
                        entry_block_reason = "RISK_LIMITS"
                    else:
                        # EXECUTE ENTRY
                        direction = "LONG" if signal == 1 else "SHORT"
                        logger.info(f"ENTRY_SUBMITTED: {direction} {symbol}.")
                        
                        save_last_signal(signal_date_str, signal)
                        
                        correlation_id = client_order_id("utbot", signal_date_str, f"{signal}:{signal_date_str}",
                                                         OrderIntent.ENTRY, 1)
                        res = buy_to_open(symbol, direction, config["MAX_POSITION_SIZE"], correlation_id)
                        if res and res.get("status") in ("filled", "partially_filled"):
                            _local_state["entry_underlying_price"] = current_price
                            _local_state["entry_rsi"] = current_rsi
                            logger.info(f"ENTRY_FILLED successfully.")
                        else:
                            logger.warning(f"ENTRY_REJECTED or failed.")
            else:
                if signal != 0 and entry_allowed is False:
                    logger.info(f"ENTRY_BLOCKED: {entry_block_reason}")
            
            write_runtime_state({
                "process_alive": True,
                "trading_mode": "paper" if os.getenv("ALPACA_IS_PAPER", "true").lower() == "true" else "live",
                "broker_state_valid": broker_state_valid,
                "market_data_valid": sig_snapshot.valid,
                "position_open": position is not None,
                "working_orders": len(active_orders),
                "kill_switch_active": False,
                **execution_lease_state(),
                "entry_allowed": entry_allowed,
                "entry_block_reason": entry_block_reason,
                "eod_flatten_required": False,
                "last_broker_sync": datetime.now(ET).isoformat(),
                "last_signal": signal,
                "last_consumed_signal": last_sig,
                **reconciler.health(),
            })
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(5) # Prevent tight crash loop
            
if __name__ == "__main__":
    try:
        main_loop()
    except ExecutionLeaseError as exc:
        logger.critical("CRITICAL: %s", exc)
        raise SystemExit(2)
