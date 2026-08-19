import os
import time
import logging
from datetime import datetime
import pytz
import json

import pandas_market_calendars as mcal

if __package__:
    from .broker import (get_open_position, get_daily_realized_pnl, get_daily_trade_count,
                         buy_to_open, sell_to_close, cancel_all_orders, get_active_orders,
                         AlpacaRESTBroker)
    from .order_state import OrderIntent, client_order_id
    from .reconciliation import BrokerReconciler, DurableState
    from .signal_engine import evaluate_signal
    from .risk_supervisor import RiskSupervisor
    from .execution_lease import (ExecutionLease, ExecutionLeaseError,
                                  execution_lease_state, install_execution_lease)
    from .kill_flatten import (KillFlattenWorkflow, KillReason, KillState, KillStore,
                               session_times)
    from .component_health import ComponentReporter, Criticality, HealthRegistry, aggregate
else:  # Direct invocation: python src/trading/executor.py
    from broker import (get_open_position, get_daily_realized_pnl, get_daily_trade_count,
                        buy_to_open, sell_to_close, cancel_all_orders, get_active_orders,
                        AlpacaRESTBroker)
    from order_state import OrderIntent, client_order_id
    from reconciliation import BrokerReconciler, DurableState
    from signal_engine import evaluate_signal
    from risk_supervisor import RiskSupervisor
    from execution_lease import (ExecutionLease, ExecutionLeaseError,
                                 execution_lease_state, install_execution_lease)
    from kill_flatten import (KillFlattenWorkflow, KillReason, KillState, KillStore,
                              session_times)
    from component_health import ComponentReporter, Criticality, HealthRegistry, aggregate

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

def main_loop():
    lease = acquire_execution_authority()
    health_registry = HealthRegistry()
    health = ComponentReporter("trading_executor", Criticality.TIER_0, registry=health_registry,
                               expected_interval_seconds=5, max_staleness_seconds=15)
    
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
    safety_broker = AlpacaRESTBroker()
    reconciler = BrokerReconciler(safety_broker, DurableState(BROKER_STATE_FILE),
                                  lambda: lease.owned,
                                  "paper" if os.getenv("ALPACA_IS_PAPER", "true").lower() == "true" else "live")
    kill = KillFlattenWorkflow(safety_broker, KillStore(),
        max_attempts=int(os.getenv("FLATTEN_MAX_ATTEMPTS", "5")),
        retry_seconds=float(os.getenv("FLATTEN_RETRY_SECONDS", "2")))
    kill.recover()

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
            iteration_id = f"executor-{health.record.instance_id}-{health.record.work_count + 1}"
            health.work_started(iteration_id, lease_owned=lease.owned)
            
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

            # Component readiness gates new risk only. It never gates the kill,
            # flatten, reconciliation, or position-management paths below.
            required = {name.strip() for name in os.getenv("DA_REQUIRED_COMPONENTS", "run_agents").split(",") if name.strip()}
            component_state = aggregate(health_registry.read_all(), required)
            if not component_state["entry_allowed"]:
                entry_allowed = False
                entry_block_reason = "COMPONENT_HEALTH:" + ",".join(component_state["reasons"])
                logger.error("ENTRY_BLOCKED_COMPONENT_HEALTH reasons=%s", component_state["reasons"])
            
            # EOD Flatten / Market Hours
            now_et = datetime.now(ET)
            market = None
            try:
                market = session_times(mcal.get_calendar('NYSE'), now_et,
                    config["ENTRY_CUTOFF_MINUTES"], config["FLATTEN_MINUTES"])
            except Exception as exc:
                logger.critical("MARKET_CALENDAR_UNAVAILABLE: %s", exc)
                entry_allowed = False
                entry_block_reason = "MARKET_CALENDAR_UNAVAILABLE"

            if market:
                if now_et >= market.flatten_time:
                    entry_allowed = False
                    entry_block_reason = "EOD_FLATTEN"
                    if not kill.store.active:
                        logger.warning("EOD_CUTOFF_REACHED")
                        kill.request(KillReason.EOD_FLATTEN)
                elif now_et >= market.entry_cutoff:
                    entry_allowed = False
                    entry_block_reason = "EOD_ENTRY_CUTOFF"
            else:
                entry_allowed = False
                entry_block_reason = entry_block_reason or "MARKET_CLOSED"

            # A cloud command may only materialize this local request; disappearance
            # of the cloud cannot clear it. The local marker is authoritative.
            if supervisor.is_kill_switch_active() and not kill.store.durable.exists():
                kill.request(KillReason.EMERGENCY_KILL)
            if kill.store.active:
                result = kill.run()
                try: kill.process_enable_request()
                except Exception as exc: logger.error("ENABLE_REQUEST_DENIED: %s", exc)
                write_runtime_state({
                    "process_alive": True, "entry_allowed": False,
                    "entry_block_reason": "KILL_ACTIVE", **execution_lease_state(),
                    **kill.health(),
                    "market_session_close": market.close.isoformat() if market else None,
                    "entry_cutoff": market.entry_cutoff.isoformat() if market else None,
                    "flatten_time": market.flatten_time.isoformat() if market else None,
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
                # Invalid enrichment blocks only new risk. Price/RSI exits are
                # skipped when unavailable, while signal-independent kill/EOD
                # flatten remains above and broker-confirmed.
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
                **kill.health(),
                **execution_lease_state(),
                "entry_allowed": entry_allowed,
                "entry_block_reason": entry_block_reason,
                "eod_flatten_required": False,
                "market_session_close": market.close.isoformat() if market else None,
                "entry_cutoff": market.entry_cutoff.isoformat() if market else None,
                "flatten_time": market.flatten_time.isoformat() if market else None,
                "last_broker_sync": datetime.now(ET).isoformat(),
                "last_signal": signal,
                "last_consumed_signal": last_sig,
                **reconciler.health(),
                "component_health": component_state,
            })
            health.work_succeeded(iteration_id, broker_reconciliation_valid=reconciliation.valid,
                                  position_management_success=True, lease_owned=lease.owned,
                                  broker_capabilities={"account_rest": True, "positions_rest": pos_result.get("valid", False),
                                                       "orders_rest": orders_result.get("valid", False)})
            
        except Exception as e:
            if 'health' in locals():
                health.work_failed(str(e))
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(5) # Prevent tight crash loop
            
if __name__ == "__main__":
    try:
        main_loop()
    except ExecutionLeaseError as exc:
        logger.critical("CRITICAL: %s", exc)
        raise SystemExit(2)
