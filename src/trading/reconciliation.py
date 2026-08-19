"""REST-based, fail-closed reconstruction of broker state."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

try:
    from .order_state import (
        MetadataConfidence, OrderIntent, OrderState, OrderStatus, PositionState,
        ReconciliationResult, WORKING_STATUSES, client_order_id,
    )
except ImportError:  # canonical direct invocation
    from order_state import (
        MetadataConfidence, OrderIntent, OrderState, OrderStatus, PositionState,
        ReconciliationResult, WORKING_STATUSES, client_order_id,
    )

logger = logging.getLogger("broker_reconciliation")


class BrokerReader(Protocol):
    def account(self) -> dict[str, Any]: ...
    def positions(self) -> list[dict[str, Any]]: ...
    def orders(self) -> list[dict[str, Any]]: ...


class BrokerWriter(BrokerReader, Protocol):
    def submit(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def order_by_client_id(self, value: str) -> Optional[dict[str, Any]]: ...


class DurableState:
    """Versioned local metadata cache; broker facts always overwrite it."""
    VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text())
            return value if value.get("version") == self.VERSION else {"version": self.VERSION}
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return {"version": self.VERSION}

    def save(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": self.VERSION, **value}
        fd, temporary = tempfile.mkstemp(prefix=self.path.name, dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def _event(name: str, **fields: Any) -> None:
    safe = {"event": name, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
    logger.info("broker_event %s", json.dumps(safe, default=str, sort_keys=True))


class BrokerReconciler:
    def __init__(self, broker: BrokerReader, state: DurableState, lease_owned: Callable[[], bool], mode: str):
        self.broker, self.state, self.lease_owned, self.mode = broker, state, lease_owned, mode
        self.last_result: Optional[ReconciliationResult] = None

    def reconcile(self) -> ReconciliationResult:
        synced = datetime.now(timezone.utc).isoformat()
        _event("BROKER_RECONCILIATION_STARTED", paper_live=self.mode)
        local = self.state.load()
        reasons: list[str] = []
        mismatches: list[dict[str, Any]] = []
        try:
            account = self.broker.account()
            if not account.get("id"):
                raise RuntimeError("account identity unavailable")
        except Exception as exc:
            return self._failed(synced, "ACCOUNT_QUERY_FAILED", exc)
        try:
            raw_positions = self.broker.positions()
        except Exception as exc:
            return self._failed(synced, "POSITION_QUERY_FAILED", exc)
        try:
            raw_orders = self.broker.orders()
        except Exception as exc:
            return self._failed(synced, "ORDER_QUERY_FAILED", exc)

        orders = tuple(OrderState.from_broker(item, synced) for item in raw_orders)
        positions = tuple(self._position(item, orders) for item in raw_positions if abs(float(item.get("qty", 0))) > 0)
        working = tuple(item for item in orders if item.status in WORKING_STATUSES)
        partial = tuple(item for item in orders if item.status is OrderStatus.PARTIALLY_FILLED)
        unknown = tuple(item for item in orders if item.status is OrderStatus.UNKNOWN_BROKER_STATE)
        unclassified = tuple(item for item in working if item.intent is OrderIntent.UNKNOWN)

        previous_positions = local.get("positions", [])
        previous_orders = {item.get("broker_order_id"): item for item in local.get("orders", [])}
        if bool(previous_positions) != bool(positions):
            mismatches.append({"type": "POSITION_MISMATCH", "local_open": bool(previous_positions), "broker_open": bool(positions)})
            _event("POSITION_MISMATCH", local_open=bool(previous_positions), broker_open=bool(positions), paper_live=self.mode)
        for item in orders:
            _event("ORDER_DISCOVERED", client_order_id=item.client_order_id,
                   broker_order_id=item.broker_order_id, contract=item.contract_symbol,
                   qty=item.requested_qty, filled_qty=item.filled_qty, status=item.status.value,
                   strategy=item.strategy_id, paper_live=self.mode)
            lifecycle_event = {
                OrderStatus.PARTIALLY_FILLED: "ORDER_PARTIAL_FILL",
                OrderStatus.FILLED: "ORDER_FILLED",
                OrderStatus.CANCELED: "ORDER_CANCELED",
                OrderStatus.REJECTED: "ORDER_REJECTED",
                OrderStatus.REPLACED: "ORDER_REPLACED",
            }.get(item.status)
            if lifecycle_event:
                _event(lifecycle_event, client_order_id=item.client_order_id,
                       broker_order_id=item.broker_order_id, contract=item.contract_symbol,
                       qty=item.requested_qty, filled_qty=item.filled_qty, status=item.status.value,
                       strategy=item.strategy_id, paper_live=self.mode)
            previous = previous_orders.get(item.broker_order_id)
            if previous and (previous.get("status") != item.status.value or float(previous.get("filled_qty", 0)) != item.filled_qty):
                mismatch = {"type": "ORDER_STATE_CHANGED", "broker_order_id": item.broker_order_id,
                            "local_status": previous.get("status"), "broker_status": item.status.value}
                mismatches.append(mismatch)
                _event("ORDER_STATE_CHANGED", **mismatch, client_order_id=item.client_order_id, paper_live=self.mode)
        if unknown:
            reasons.append("UNKNOWN_BROKER_STATE")
            for item in unknown:
                _event("ORDER_UNKNOWN", client_order_id=item.client_order_id, broker_order_id=item.broker_order_id,
                       contract=item.contract_symbol, qty=item.requested_qty, filled_qty=item.filled_qty,
                       status=item.status.value, strategy=item.strategy_id, paper_live=self.mode)
                _event("UNKNOWN_BROKER_STATE", client_order_id=item.client_order_id,
                       broker_order_id=item.broker_order_id, contract=item.contract_symbol,
                       qty=item.requested_qty, filled_qty=item.filled_qty, status=item.status.value,
                       strategy=item.strategy_id, paper_live=self.mode)
        if unclassified:
            reasons.append("UNCLASSIFIED_WORKING_ORDER")
        if positions and any(value is MetadataConfidence.UNKNOWN for pos in positions for value in pos.metadata.values()):
            reasons.append("DEGRADED_POSITION_STATE")
        if working:
            reasons.append("WORKING_ORDER")
        if positions:
            reasons.append("POSITION_OPEN")
        if not self.lease_owned():
            reasons.append("EXECUTION_LEASE_NOT_OWNED")

        valid = not unknown and not unclassified
        entry_allowed = valid and self.lease_owned() and not positions and not working
        result = ReconciliationResult(valid, entry_allowed, positions, working, partial, unknown,
                                      tuple(mismatches), {"account_id": str(account["id"]), "orders": len(orders)},
                                      tuple(dict.fromkeys(reasons)), synced)
        self.state.save({**local, "last_sync": synced, "positions": [self._position_dict(p) for p in positions],
                         "orders": [o.to_dict() for o in orders]})
        self.last_result = result
        for position in positions:
            _event("POSITION_DISCOVERED", contract=position.contract_symbol, qty=position.qty,
                   strategy=position.strategy_id, paper_live=self.mode)
            _event("POSITION_RECOVERED", contract=position.contract_symbol, qty=position.qty,
                   strategy=position.strategy_id, paper_live=self.mode)
        _event("BROKER_RECONCILIATION_COMPLETE", valid=valid, entry_allowed=entry_allowed,
               positions=len(positions), working_orders=len(working), partial_orders=len(partial),
               unknown_orders=len(unknown), paper_live=self.mode)
        return result

    def _failed(self, synced: str, reason: str, exc: Exception) -> ReconciliationResult:
        _event("BROKER_RECONCILIATION_FAILED", reason=reason, error=type(exc).__name__, paper_live=self.mode)
        result = ReconciliationResult(False, False, (), (), (), (), (), {}, (reason,), synced)
        self.last_result = result
        return result

    @staticmethod
    def _position(raw: dict[str, Any], orders: tuple[OrderState, ...]) -> PositionState:
        symbol = str(raw.get("symbol") or "")
        attributed = next((o for o in reversed(orders) if o.contract_symbol == symbol and o.intent is OrderIntent.ENTRY), None)
        return PositionState(
            contract_symbol=symbol, qty=abs(float(raw.get("qty", 0))),
            average_fill_price=float(raw.get("avg_entry_price", 0)), side=str(raw.get("side") or ""),
            strategy_id=attributed.strategy_id if attributed else None,
            metadata={
                "entry_underlying_price": MetadataConfidence.UNKNOWN,
                "entry_rsi": MetadataConfidence.UNKNOWN,
                "signal_date": MetadataConfidence.DERIVED if attributed else MetadataConfidence.UNKNOWN,
                "direction": MetadataConfidence.RECOVERED,
                "strategy_version": MetadataConfidence.RECOVERED if attributed else MetadataConfidence.UNKNOWN,
            },
        )

    @staticmethod
    def _position_dict(position: PositionState) -> dict[str, Any]:
        return {**position.__dict__, "metadata": {key: value.value for key, value in position.metadata.items()}}

    def health(self) -> dict[str, Any]:
        result = self.last_result
        if result is None:
            return {"broker_state_valid": False, "broker_reconciled": False, "last_broker_sync": None,
                    "position_open": None, "position_qty": None, "working_orders": None,
                    "partial_orders": None, "unknown_orders": None,
                    "reconciliation_errors": ["RECONCILIATION_INCOMPLETE"], "entry_allowed": False,
                    "entry_block_reason": "RECONCILIATION_INCOMPLETE"}
        query_failed = any(code.endswith("QUERY_FAILED") for code in result.reason_codes)
        return {"broker_state_valid": result.valid, "broker_reconciled": result.valid,
                "last_broker_sync": result.last_sync,
                "position_open": None if query_failed else bool(result.positions),
                "position_qty": None if query_failed else sum(p.qty for p in result.positions),
                "working_orders": None if query_failed else len(result.working_orders),
                "partial_orders": None if query_failed else len(result.partial_orders),
                "unknown_orders": None if query_failed else len(result.unknown_orders),
                "reconciliation_errors": list(result.reason_codes) if not result.valid else [],
                "entry_allowed": result.entry_allowed,
                "entry_block_reason": None if result.entry_allowed else (result.reason_codes[0] if result.reason_codes else "ENTRY_BLOCKED_RECONCILIATION")}


class OrderLifecycleService:
    """Idempotent entry boundary layered over authoritative reconciliation."""

    def __init__(self, broker: BrokerWriter, reconciler: BrokerReconciler, state: DurableState):
        self.broker, self.reconciler, self.state = broker, reconciler, state

    def submit_entry(self, *, strategy_id: str, session: str, signal_id: str,
                     symbol: str, qty: float, limit_price: float, attempt: int = 1) -> OrderState:
        correlation = client_order_id(strategy_id, session, signal_id, OrderIntent.ENTRY, attempt)
        snapshot = self.reconciler.reconcile()
        if not snapshot.valid:
            _event("ENTRY_BLOCKED_RECONCILIATION", client_order_id=correlation,
                   status="BLOCKED", strategy=strategy_id, paper_live=self.reconciler.mode)
            raise RuntimeError("entry blocked: broker reconciliation invalid")
        all_known = (*snapshot.working_orders, *snapshot.partial_orders)
        persisted = self.state.load().get("consumed_signals", [])
        if any(item.client_order_id == correlation for item in all_known) or correlation in persisted:
            _event("DUPLICATE_ENTRY_BLOCKED", client_order_id=correlation, contract=symbol,
                   qty=qty, strategy=strategy_id, paper_live=self.reconciler.mode)
            raise RuntimeError("duplicate logical entry blocked")
        if not snapshot.entry_allowed:
            raise RuntimeError("entry blocked: position or working order exists")

        payload = {"symbol": symbol, "qty": str(qty), "side": "buy", "type": "limit",
                   "limit_price": str(limit_price), "time_in_force": "day", "client_order_id": correlation}
        try:
            raw = self.broker.submit(payload)
        except Exception as submit_error:
            # A timeout is an ambiguous commit, never permission to create a new ID.
            try:
                raw = self.broker.order_by_client_id(correlation)
            except Exception as lookup_error:
                _event("ENTRY_BLOCKED_RECONCILIATION", client_order_id=correlation,
                       status="UNKNOWN", strategy=strategy_id, paper_live=self.reconciler.mode)
                raise RuntimeError("submit outcome unknown; entry blocked") from lookup_error
            if raw is None:
                raise RuntimeError("submit not found at broker; explicit retry with same ID required") from submit_error
            _event("LOST_RESPONSE_RECOVERED", client_order_id=correlation,
                   broker_order_id=raw.get("id"), contract=symbol, qty=qty,
                   filled_qty=raw.get("filled_qty", 0), status=raw.get("status"),
                   strategy=strategy_id, paper_live=self.reconciler.mode)

        order = OrderState.from_broker(raw)
        stored = self.state.load()
        consumed = list(dict.fromkeys([*stored.get("consumed_signals", []), correlation]))
        self.state.save({**stored, "consumed_signals": consumed})
        self.reconciler.reconcile()
        return order

    @staticmethod
    def replacement_qty(order: OrderState) -> float:
        """Only broker-reported unfilled quantity may be chased/replaced."""
        return order.remaining_qty
