"""Fail-closed semantics for inputs that may authorize new trading risk."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, Iterable, Optional, TypeVar

T = TypeVar("T")


class DataStatus(str, Enum):
    VALID = "VALID"
    NO_DATA = "NO_DATA"
    STALE = "STALE"
    ERROR = "ERROR"
    DISABLED = "DISABLED"
    MALFORMED = "MALFORMED"
    NO_QUOTE = "NO_QUOTE"
    STALE_QUOTE = "STALE_QUOTE"
    CROSSED_QUOTE = "CROSSED_QUOTE"
    ZERO_BID = "ZERO_BID"
    INVALID_SPREAD = "INVALID_SPREAD"


@dataclass(frozen=True)
class ValidatedValue(Generic[T]):
    value: Optional[T]
    status: DataStatus
    timestamp: Optional[datetime]
    source: str
    reason: str = ""
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def valid(self) -> bool:
        return self.status is DataStatus.VALID and self.value is not None

    @property
    def age_seconds(self) -> Optional[float]:
        if self.timestamp is None:
            return None
        ts = self.timestamp if self.timestamp.tzinfo else self.timestamp.replace(tzinfo=timezone.utc)
        return max(0.0, (self.observed_at - ts.astimezone(timezone.utc)).total_seconds())

    def health(self, prefix: str) -> dict[str, Any]:
        return {
            f"{prefix}_valid": self.valid,
            f"{prefix}_status": self.status.value,
            f"{prefix}_timestamp": self.timestamp.isoformat() if self.timestamp else None,
            f"{prefix}_age": self.age_seconds,
            f"{prefix}_source": self.source,
            f"{prefix}_reason": self.reason,
        }


@dataclass(frozen=True)
class EntryReadiness:
    entry_allowed: bool
    reason_codes: tuple[str, ...]
    degraded: bool = False

    @classmethod
    def evaluate(cls, mandatory: Iterable[tuple[str, ValidatedValue[Any]]],
                 *, lease_owned: bool, broker_reconciled: bool,
                 kill_active: bool = False) -> "EntryReadiness":
        reasons: list[str] = []
        if kill_active:
            reasons.append("KILL_ACTIVE")
        if not lease_owned:
            reasons.append("EXECUTION_LEASE_UNAVAILABLE")
        if not broker_reconciled:
            reasons.append("BROKER_RECONCILIATION_UNAVAILABLE")
        for reason_code, item in mandatory:
            if not item.valid:
                reasons.append(reason_code)
        return cls(not reasons, tuple(dict.fromkeys(reasons)), bool(reasons))


def parse_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    else:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
