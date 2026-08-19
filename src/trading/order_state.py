"""Broker-authoritative order lifecycle types and deterministic correlation IDs."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional


class OrderStatus(str, Enum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    PENDING_NEW = "PENDING_NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    PENDING_REPLACE = "PENDING_REPLACE"
    REPLACED = "REPLACED"
    SUSPENDED = "SUSPENDED"
    CALCULATED = "CALCULATED"
    STOPPED = "STOPPED"
    DONE_FOR_DAY = "DONE_FOR_DAY"
    UNKNOWN_BROKER_STATE = "UNKNOWN_BROKER_STATE"


class OrderIntent(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    FLATTEN = "FLATTEN"
    UNKNOWN = "UNKNOWN"


class MetadataConfidence(str, Enum):
    RECOVERED = "RECOVERED"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"


_STATUS_MAP = {status.value.lower(): status for status in OrderStatus if status is not OrderStatus.UNKNOWN_BROKER_STATE}
WORKING_STATUSES = frozenset({
    OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.PENDING_NEW,
    OrderStatus.PARTIALLY_FILLED, OrderStatus.PENDING_CANCEL,
    OrderStatus.PENDING_REPLACE, OrderStatus.SUSPENDED, OrderStatus.STOPPED,
})


def normalize_status(value: Any) -> OrderStatus:
    """Map an Alpaca status without ever treating an unknown value as terminal."""
    return _STATUS_MAP.get(str(value or "").strip().lower(), OrderStatus.UNKNOWN_BROKER_STATE)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso(value: Any, fallback: str) -> str:
    return str(value) if value else fallback


@dataclass(frozen=True)
class OrderState:
    broker_order_id: str
    client_order_id: str
    strategy_id: Optional[str]
    signal_id: Optional[str]
    symbol: str
    contract_symbol: str
    side: str
    intent: OrderIntent
    requested_qty: float
    filled_qty: float
    remaining_qty: float
    average_fill_price: Optional[float]
    status: OrderStatus
    submitted_at: str
    updated_at: str
    last_broker_sync: str
    parent_order_id: Optional[str] = None
    replacement_order_id: Optional[str] = None

    @classmethod
    def from_broker(cls, raw: dict[str, Any], synced_at: Optional[str] = None) -> "OrderState":
        now = synced_at or datetime.now(timezone.utc).isoformat()
        client_id = str(raw.get("client_order_id") or "")
        correlation = parse_client_order_id(client_id)
        requested = _number(raw.get("qty"))
        filled = min(requested, max(0.0, _number(raw.get("filled_qty")))) if requested else max(0.0, _number(raw.get("filled_qty")))
        avg = raw.get("filled_avg_price")
        intent = correlation.get("intent", OrderIntent.UNKNOWN)
        return cls(
            broker_order_id=str(raw.get("id") or ""), client_order_id=client_id,
            strategy_id=correlation.get("strategy_id"), signal_id=correlation.get("signal_id"),
            symbol=str(raw.get("symbol") or ""), contract_symbol=str(raw.get("symbol") or ""),
            side=str(raw.get("side") or "").lower(), intent=intent,
            requested_qty=requested, filled_qty=filled, remaining_qty=max(0.0, requested - filled),
            average_fill_price=_number(avg) if avg not in (None, "") else None,
            status=normalize_status(raw.get("status")),
            submitted_at=_iso(raw.get("submitted_at") or raw.get("created_at"), now),
            updated_at=_iso(raw.get("updated_at"), now), last_broker_sync=now,
            parent_order_id=raw.get("replaces"), replacement_order_id=raw.get("replaced_by"),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["intent"] = self.intent.value
        result["status"] = self.status.value
        return result


@dataclass(frozen=True)
class PositionState:
    contract_symbol: str
    qty: float
    average_fill_price: float
    side: str
    strategy_id: Optional[str] = None
    metadata: dict[str, MetadataConfidence] = field(default_factory=dict)


@dataclass(frozen=True)
class ReconciliationResult:
    valid: bool
    entry_allowed: bool
    positions: tuple[PositionState, ...]
    working_orders: tuple[OrderState, ...]
    partial_orders: tuple[OrderState, ...]
    unknown_orders: tuple[OrderState, ...]
    mismatches: tuple[dict[str, Any], ...]
    recovered_state: dict[str, Any]
    reason_codes: tuple[str, ...]
    last_sync: str


_SAFE = re.compile(r"[^a-z0-9]+")
_CLIENT_RE = re.compile(r"^da-([a-z0-9]{1,10})-(\d{8})-([exf])-([a-f0-9]{12})-(\d{2})$")


def client_order_id(strategy_id: str, session: date | str, signal_id: str, intent: OrderIntent, attempt: int = 1) -> str:
    """Return a <=48-character, stable Alpaca client order ID.

    Format: ``da-<strategy:10>-<YYYYMMDD>-<e|x|f>-<sha256:12>-<attempt:2>``.
    """
    strategy = _SAFE.sub("", strategy_id.lower())[:10] or "unknown"
    session_text = session.strftime("%Y%m%d") if isinstance(session, date) else str(session).replace("-", "")
    if not re.fullmatch(r"\d{8}", session_text):
        raise ValueError("session must be a date or YYYY-MM-DD")
    if not 1 <= attempt <= 99:
        raise ValueError("attempt must be between 1 and 99")
    marker = {OrderIntent.ENTRY: "e", OrderIntent.EXIT: "x", OrderIntent.FLATTEN: "f"}.get(intent)
    if marker is None:
        raise ValueError("UNKNOWN intent cannot be submitted")
    digest = hashlib.sha256(f"{strategy_id}|{session_text}|{signal_id}|{intent.value}".encode()).hexdigest()[:12]
    return f"da-{strategy}-{session_text}-{marker}-{digest}-{attempt:02d}"


def parse_client_order_id(value: str) -> dict[str, Any]:
    match = _CLIENT_RE.fullmatch(value or "")
    if not match:
        return {}
    strategy, session, marker, signal_hash, attempt = match.groups()
    return {
        "strategy_id": strategy, "session": session, "signal_id": signal_hash,
        "intent": {"e": OrderIntent.ENTRY, "x": OrderIntent.EXIT, "f": OrderIntent.FLATTEN}[marker],
        "attempt": int(attempt),
    }
