"""Persistent, broker-confirmed emergency kill and EOD flatten workflow.

Local files are operator intent and workflow checkpoints, never evidence that the
broker is flat.  Only a successful positions/orders reconciliation can establish
``KILLED_FLAT``.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Protocol
from zoneinfo import ZoneInfo

try:
    from .execution_lease import require_execution_lease
    from .order_state import OrderIntent, OrderState, OrderStatus, WORKING_STATUSES, client_order_id
except ImportError:  # canonical direct invocation
    from execution_lease import require_execution_lease
    from order_state import OrderIntent, OrderState, OrderStatus, WORKING_STATUSES, client_order_id

logger = logging.getLogger("kill_flatten")
ET = ZoneInfo("America/New_York")
TERMINAL = {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.EXPIRED,
            OrderStatus.REJECTED, OrderStatus.REPLACED, OrderStatus.DONE_FOR_DAY}


class KillState(str, Enum):
    ENABLED = "ENABLED"
    KILL_REQUESTED = "KILL_REQUESTED"
    ENTRY_BLOCKED = "ENTRY_BLOCKED"
    CANCELING_OPEN_ORDERS = "CANCELING_OPEN_ORDERS"
    FLATTENING = "FLATTENING"
    VERIFYING_FLAT = "VERIFYING_FLAT"
    KILLED_FLAT = "KILLED_FLAT"
    KILL_FAILED = "KILL_FAILED"


class KillReason(str, Enum):
    EOD_FLATTEN = "EOD_FLATTEN"
    EMERGENCY_KILL = "EMERGENCY_KILL"


@dataclass
class KillRecord:
    state: str = KillState.ENABLED.value
    reason: Optional[str] = None
    requested_at: Optional[str] = None
    attempts: int = 0
    last_error: Optional[str] = None


class SafetyBroker(Protocol):
    def positions(self) -> list[dict[str, Any]]: ...
    def orders(self) -> list[dict[str, Any]]: ...
    def cancel(self, order_id: str) -> Any: ...
    def order(self, order_id: str) -> dict[str, Any]: ...
    def submit(self, payload: dict[str, Any]) -> dict[str, Any]: ...


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    fd, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        os.fchmod(fd, 0o640)
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


class KillStore:
    """Two-layer state: durable reboot intent plus a runtime entry interlock."""
    def __init__(self, durable: str | Path = "/var/lib/disrupting-alpha/trading-disabled",
                 runtime: str | Path = "/run/disrupting-alpha/trading-disabled",
                 enable_request: str | Path = "/var/lib/disrupting-alpha/trading-enable-requested"):
        self.durable, self.runtime, self.enable_request = Path(durable), Path(runtime), Path(enable_request)

    def load(self) -> KillRecord:
        try:
            raw = json.loads(self.durable.read_text())
            record = KillRecord(**{k: raw.get(k) for k in asdict(KillRecord())})
            self.materialize_runtime()
            return record
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return KillRecord()

    def save(self, record: KillRecord) -> None:
        _atomic_json(self.durable, asdict(record)); self.materialize_runtime()

    def materialize_runtime(self) -> None:
        self.runtime.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.runtime.touch(mode=0o640, exist_ok=True)

    def clear_after_verified_enable(self) -> None:
        self.durable.unlink(missing_ok=True); self.runtime.unlink(missing_ok=True)
        self.enable_request.unlink(missing_ok=True)

    @property
    def active(self) -> bool:
        return self.durable.exists() or self.runtime.exists()


def _event(name: str, record: KillRecord, **fields: Any) -> None:
    logger.info("%s", json.dumps({"event": name, "reason": record.reason,
        "attempt": record.attempts, "timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_live": "paper" if os.getenv("ALPACA_IS_PAPER", "true").lower() == "true" else "live",
        **fields}, default=str, sort_keys=True))


class KillFlattenWorkflow:
    def __init__(self, broker: SafetyBroker, store: KillStore, *, max_attempts: int = 5,
                 retry_seconds: float = 2, sleep: Callable[[float], None] = time.sleep):
        self.broker, self.store = broker, store
        self.max_attempts, self.retry_seconds, self.sleep = max_attempts, retry_seconds, sleep
        self.record = store.load()
        self.broker_position_qty: Optional[float] = None
        self.working_entry_orders: Optional[int] = None

    def request(self, reason: KillReason) -> None:
        # Emergency always supersedes EOD; neither request can clear a kill.
        if self.record.reason == KillReason.EMERGENCY_KILL.value and reason is KillReason.EOD_FLATTEN:
            return
        self.record = KillRecord(KillState.KILL_REQUESTED.value, reason.value,
                                 datetime.now(timezone.utc).isoformat())
        self.store.save(self.record)
        _event("KILL_REQUESTED" if reason is KillReason.EMERGENCY_KILL else "EOD_FLATTEN_STARTED", self.record)
        _event("KILL_STATE_PERSISTED", self.record); _event("ENTRY_DISABLED", self.record)

    def recover(self) -> None:
        if self.store.active:
            self.store.materialize_runtime()
            _event("KILL_RECOVERED_AFTER_RESTART", self.record)
            if self.record.state not in (KillState.KILLED_FLAT.value, KillState.ENABLED.value):
                _event("FLATTEN_RECOVERED_AFTER_RESTART", self.record)

    def run(self) -> KillState:
        if not self.store.active:
            return KillState.ENABLED
        # Exhaustion is critical for this bounded batch, but a future executor
        # iteration can resume after broker recovery without enabling entries.
        if self.record.attempts >= self.max_attempts:
            self.record.attempts = 0
        self.record.state = KillState.ENTRY_BLOCKED.value; self.store.save(self.record)
        while self.record.attempts < self.max_attempts:
            self.record.attempts += 1
            try:
                require_execution_lease("kill_flatten")
                raw_orders = self.broker.orders()
                orders = [OrderState.from_broker(item) for item in raw_orders]
                opening = [o for o in orders if o.status in WORKING_STATUSES and o.intent in (OrderIntent.ENTRY, OrderIntent.UNKNOWN)]
                self.working_entry_orders = len(opening)
                self.record.state = KillState.CANCELING_OPEN_ORDERS.value; self.store.save(self.record)
                for order in opening:
                    _event("OPENING_ORDER_CANCEL_REQUESTED", self.record, broker_order_id=order.broker_order_id,
                           client_order_id=order.client_order_id, quantity=order.remaining_qty)
                    self.broker.cancel(order.broker_order_id)
                    confirmed = OrderState.from_broker(self.broker.order(order.broker_order_id))
                    if confirmed.status not in TERMINAL:
                        raise RuntimeError(f"cancel unverified for {order.broker_order_id}: {confirmed.status.value}")
                    _event("OPENING_ORDER_CANCELED", self.record, broker_order_id=order.broker_order_id,
                           client_order_id=order.client_order_id, quantity=confirmed.remaining_qty)

                positions = self.broker.positions()  # authoritative quantity immediately before every attempt
                quantities = [(p, abs(float(p.get("qty", 0)))) for p in positions if abs(float(p.get("qty", 0))) > 0]
                self.broker_position_qty = sum(q for _, q in quantities)
                if quantities:
                    self.record.state = KillState.FLATTENING.value; self.store.save(self.record)
                    _event("FLATTEN_STARTED", self.record, quantity=self.broker_position_qty)
                    for position, qty in quantities:
                        cid = client_order_id("safety", datetime.now(ET).date(), f"{self.record.reason}:{position['symbol']}",
                                              OrderIntent.FLATTEN, min(self.record.attempts, 99))
                        payload = {"symbol": position["symbol"], "qty": str(qty),
                                   "side": "sell" if str(position.get("side", "long")) == "long" else "buy",
                                   "type": "market",
                                   "time_in_force": "day", "client_order_id": cid}
                        raw = self.broker.submit(payload)
                        _event("FLATTEN_ORDER_SUBMITTED", self.record, broker_order_id=raw.get("id"),
                               client_order_id=cid, quantity=qty)
                        if str(raw.get("status", "")).lower() == "rejected":
                            _event("FLATTEN_REJECTED", self.record, broker_order_id=raw.get("id"), quantity=qty)
                self.record.state = KillState.VERIFYING_FLAT.value; self.store.save(self.record)
                self.sleep(self.retry_seconds)
                verify_positions = self.broker.positions()
                remaining = sum(abs(float(p.get("qty", 0))) for p in verify_positions)
                verify_orders = [OrderState.from_broker(o) for o in self.broker.orders()]
                prohibited = [o for o in verify_orders if o.status in WORKING_STATUSES and o.intent in (OrderIntent.ENTRY, OrderIntent.UNKNOWN)]
                self.broker_position_qty, self.working_entry_orders = remaining, len(prohibited)
                if remaining == 0 and not prohibited:
                    self.record.state, self.record.last_error = KillState.KILLED_FLAT.value, None
                    self.store.save(self.record); _event("FLATTEN_COMPLETE", self.record, remaining_quantity=0)
                    return KillState.KILLED_FLAT
                _event("FLATTEN_PARTIAL_FILL", self.record, remaining_quantity=remaining)
                raise RuntimeError(f"broker not flat: qty={remaining}, opening_orders={len(prohibited)}")
            except Exception as exc:
                self.record.last_error = f"{type(exc).__name__}: {exc}"
                self.store.save(self.record)
                _event("FLATTEN_RETRY", self.record, remaining_quantity=self.broker_position_qty, error=self.record.last_error)
                if self.record.attempts < self.max_attempts: self.sleep(self.retry_seconds)
        self.record.state = KillState.KILL_FAILED.value; self.store.save(self.record)
        _event("FLATTEN_FAILED", self.record, remaining_quantity=self.broker_position_qty, error=self.record.last_error)
        return KillState.KILL_FAILED

    def process_enable_request(self) -> bool:
        if not self.store.enable_request.exists(): return False
        # The executor alone clears intent, and only after a fresh broker proof.
        require_execution_lease("enable_trading")
        positions, orders = self.broker.positions(), [OrderState.from_broker(o) for o in self.broker.orders()]
        unsafe = positions or any(o.status in WORKING_STATUSES for o in orders)
        if self.record.state != KillState.KILLED_FLAT.value or unsafe:
            raise RuntimeError("enable denied: unresolved broker/safety state")
        self.store.clear_after_verified_enable(); self.record = KillRecord()
        _event("TRADING_ENABLED_BY_OPERATOR", self.record)
        return True

    def health(self) -> dict[str, Any]:
        active = self.store.active
        return {"kill_active": active, "kill_state": self.record.state,
                "kill_reason": self.record.reason, "kill_requested_at": self.record.requested_at,
                "flatten_required": active and self.record.state != KillState.KILLED_FLAT.value,
                "flatten_state": self.record.state, "flatten_attempts": self.record.attempts,
                "flatten_last_error": self.record.last_error,
                "broker_position_qty": self.broker_position_qty,
                "working_entry_orders": self.working_entry_orders}


@dataclass(frozen=True)
class SessionTimes:
    close: datetime
    entry_cutoff: datetime
    flatten_time: datetime


def session_times(calendar: Any, now: datetime, entry_minutes: int = 15, flatten_minutes: int = 5) -> Optional[SessionTimes]:
    """Calculate NYSE cutoffs from the maintained calendar (including early closes)."""
    local = now.astimezone(ET)
    schedule = calendar.schedule(start_date=local.date(), end_date=local.date())
    if schedule.empty: return None
    close = schedule.iloc[0]["market_close"].to_pydatetime().astimezone(ET)
    return SessionTimes(close, close - timedelta(minutes=entry_minutes), close - timedelta(minutes=flatten_minutes))
