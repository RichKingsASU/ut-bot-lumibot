"""Local, fail-safe evidence of component *work*, not merely process life."""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("component_health")


class HealthStatus(str, Enum):
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    FAILED = "FAILED"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


class Criticality(IntEnum):
    TIER_0 = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


@dataclass
class ComponentHealth:
    component: str
    criticality: int
    process_id: int
    instance_id: str
    started_at: str
    status: str = HealthStatus.STARTING.value
    last_heartbeat_at: str | None = None
    last_work_started_at: str | None = None
    last_work_completed_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_output_at: str | None = None
    last_output_id: str | None = None
    work_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    expected_interval_seconds: float = 60
    max_staleness_seconds: float = 120
    reason: str = "awaiting useful work"
    metadata: dict[str, Any] = field(default_factory=dict)


class HealthRegistry:
    """One atomic JSON record per component; telemetry failure never raises."""

    def __init__(self, root: str | Path | None = None, *, clock: Callable[[], datetime] = utc_now):
        self.root = Path(root or os.getenv("DA_HEALTH_DIR", "/run/disrupting-alpha/health"))
        self.clock = clock

    def path(self, component: str) -> Path:
        safe = "".join(c for c in component if c.isalnum() or c in "-_")
        if not safe or safe != component:
            raise ValueError("invalid component name")
        return self.root / f"{safe}.json"

    def write(self, record: ComponentHealth) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o750)
            fd, temporary = tempfile.mkstemp(prefix=f".{record.component}.", dir=self.root)
            try:
                with os.fdopen(fd, "w") as stream:
                    json.dump(asdict(record), stream, sort_keys=True)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, 0o640)
                os.replace(temporary, self.path(record.component))
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return True
        except Exception as exc:
            logger.warning("health telemetry write failed for %s: %s", record.component, exc)
            return False

    def read(self, component: str) -> ComponentHealth | None:
        try:
            return ComponentHealth(**json.loads(self.path(component).read_text()))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def read_all(self) -> dict[str, ComponentHealth]:
        records: dict[str, ComponentHealth] = {}
        try:
            paths = self.root.glob("*.json")
        except OSError:
            return records
        for path in paths:
            record = self.read(path.stem)
            if record:
                records[record.component] = record
        return records


class ComponentReporter:
    def __init__(self, component: str, criticality: Criticality, *, registry: HealthRegistry | None = None,
                 expected_interval_seconds: float = 60, max_staleness_seconds: float = 120,
                 process_id: int | None = None, instance_id: str | None = None):
        now = utc_now()
        self.registry = registry or HealthRegistry()
        self.record = ComponentHealth(component, int(criticality), process_id or os.getpid(),
            instance_id or str(uuid.uuid4()), _iso(now) or "", last_heartbeat_at=_iso(now),
            expected_interval_seconds=expected_interval_seconds, max_staleness_seconds=max_staleness_seconds)
        self.registry.write(self.record)
        logger.info("COMPONENT_STARTED component=%s instance_id=%s", component, self.record.instance_id)

    def heartbeat(self, **metadata: Any) -> None:
        self.record.last_heartbeat_at = _iso(utc_now())
        self.record.metadata.update(metadata)
        self.registry.write(self.record)
        logger.debug("COMPONENT_HEARTBEAT component=%s", self.record.component)

    def work_started(self, output_id: str | None = None, **metadata: Any) -> None:
        now = _iso(utc_now())
        self.record.last_heartbeat_at = now
        self.record.last_work_started_at = now
        self.record.last_output_id = output_id
        self.record.metadata.update(metadata)
        self.registry.write(self.record)
        logger.info("COMPONENT_WORK_STARTED component=%s output_id=%s", self.record.component, output_id)

    def work_succeeded(self, output_id: str | None = None, **metadata: Any) -> None:
        previous = self.record.status
        now = _iso(utc_now())
        self.record.last_heartbeat_at = self.record.last_work_completed_at = self.record.last_success_at = now
        self.record.last_output_at, self.record.last_output_id = now, output_id or self.record.last_output_id
        self.record.work_count += 1
        self.record.consecutive_failures = 0
        self.record.status, self.record.reason = HealthStatus.HEALTHY.value, "useful work completed"
        self.record.metadata.update(metadata)
        self.registry.write(self.record)
        logger.info("%s component=%s output_id=%s",
                    "COMPONENT_RECOVERED" if previous in {"STALE", "FAILED", "DEGRADED"} else "COMPONENT_WORK_SUCCEEDED",
                    self.record.component, self.record.last_output_id)

    def work_failed(self, reason: str, **metadata: Any) -> None:
        now = _iso(utc_now())
        self.record.last_heartbeat_at = self.record.last_work_completed_at = self.record.last_failure_at = now
        self.record.failure_count += 1
        self.record.consecutive_failures += 1
        self.record.status, self.record.reason = HealthStatus.FAILED.value, reason
        self.record.metadata.update(metadata)
        self.registry.write(self.record)
        logger.error("COMPONENT_WORK_FAILED component=%s reason=%s", self.record.component, reason)


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def evaluate(record: ComponentHealth | None, *, now: datetime | None = None,
             expected_instance_id: str | None = None, alive: Callable[[int], bool] = process_alive,
             work_expected: bool = True) -> dict[str, Any]:
    now = now or utc_now()
    if record is None:
        return {"status": HealthStatus.UNKNOWN.value, "reason": "health record missing", "entry_blocking": True}
    heartbeat = _parse(record.last_heartbeat_at)
    useful = _parse(record.last_success_at)
    heartbeat_age = (now - heartbeat).total_seconds() if heartbeat else None
    useful_age = (now - useful).total_seconds() if useful else None
    reason, status = record.reason, HealthStatus(record.status)
    if expected_instance_id and record.instance_id != expected_instance_id:
        status, reason = HealthStatus.FAILED, "health record belongs to previous instance"
    elif not alive(record.process_id):
        status, reason = HealthStatus.FAILED, "component process is not alive"
    elif heartbeat_age is None or heartbeat_age > record.max_staleness_seconds:
        status, reason = HealthStatus.STALE, "heartbeat stale"
    elif work_expected and (useful_age is None or useful_age > record.max_staleness_seconds):
        status, reason = HealthStatus.STALE, "useful work stale"
    elif not work_expected and status not in {HealthStatus.FAILED, HealthStatus.DISABLED}:
        status, reason = HealthStatus.HEALTHY, "no output expected in current market session"
    entry_blocking = record.criticality <= int(Criticality.TIER_1) and status not in {HealthStatus.HEALTHY, HealthStatus.DISABLED}
    if status is HealthStatus.STALE and record.status != HealthStatus.STALE.value:
        logger.warning("COMPONENT_STALE component=%s reason=%s", record.component, reason)
    return {**asdict(record), "status": status.value, "reason": reason,
            "heartbeat_age_seconds": heartbeat_age, "useful_work_age_seconds": useful_age,
            "entry_blocking": entry_blocking}


def aggregate(records: dict[str, ComponentHealth], required: set[str], *, now: datetime | None = None,
              alive: Callable[[int], bool] = process_alive, work_expected: dict[str, bool] | None = None) -> dict[str, Any]:
    work_expected = work_expected or {}
    components = {name: evaluate(records.get(name), now=now, alive=alive,
                    work_expected=work_expected.get(name, True)) for name in required | records.keys()}
    blockers = [name for name in required if components[name]["status"] != HealthStatus.HEALTHY.value]
    optional_bad = [name for name, result in components.items() if name not in required and result["status"] not in
                    {HealthStatus.HEALTHY.value, HealthStatus.DISABLED.value}]
    if any(components[name].get("criticality") == 0 and name in blockers for name in blockers):
        overall = "CRITICAL"
    elif blockers:
        overall = "NOT_READY"
    elif optional_bad:
        overall = "DEGRADED"
    else:
        overall = "TRADING_READY"
    return {"status": overall, "entry_allowed": not blockers, "reasons":
            [f"{name.upper()}_{components[name]['status']}" for name in blockers], "components": components}


def broker_capability_health(capabilities: dict[str, bool], required: set[str]) -> tuple[HealthStatus, str]:
    missing = sorted(name for name in required if not capabilities.get(name, False))
    return ((HealthStatus.FAILED, "required broker capabilities unavailable: " + ",".join(missing))
            if missing else (HealthStatus.HEALTHY, "all required broker capabilities available"))
