"""
agents/tools/_shared.py
~~~~~~~~~~~~~~~~~~~~~~~
Shared utilities for all Disrupting Alpha tool modules.

Provides:
  - Config loaders  (YAML, cached)
  - StructuredLogger  (JSON lines → logs/agents.log)
  - @safe_tool decorator  (catch-all → structured OpResult on error)
  - @requires_approval decorator  (queues operation, returns pending)
  - Common dataclasses: OpResult, PipelineStatus, ServiceStatus, BotStatus

Python ≤ 3.11 compatible (Lumibot constraint).
"""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar

import yaml

# ── Path resolution ────────────────────────────────────────────────────────────
# PROJECT_ROOT is the repo root (~/disrupting-alpha on the edge server).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = PROJECT_ROOT / "agents"
CONFIG_DIR = AGENTS_DIR / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
APPROVAL_QUEUE_PATH = AGENTS_DIR / ".approval_queue.json"

# ── Ensure log dir exists ──────────────────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Config caching ─────────────────────────────────────────────────────────────
_config_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()


def load_services_config() -> List[Dict[str, Any]]:
    """Load and cache agents/config/services.yaml.  Returns list of service dicts."""
    return _load_yaml("services")["services"]


def load_pipelines_config() -> Dict[str, Any]:
    """Load and cache agents/config/pipelines.yaml.  Returns dict of pipeline configs."""
    return _load_yaml("pipelines")["pipelines"]


def _load_yaml(name: str) -> Dict[str, Any]:
    with _cache_lock:
        if name not in _config_cache:
            path = CONFIG_DIR / f"{name}.yaml"
            if not path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")
            with open(path, "r", encoding="utf-8") as fh:
                _config_cache[name] = yaml.safe_load(fh)
        return _config_cache[name]


def _bust_config_cache() -> None:
    """Force reload of YAML configs on next access (useful in tests)."""
    with _cache_lock:
        _config_cache.clear()


# ── StructuredLogger ───────────────────────────────────────────────────────────

class StructuredLogger:
    """
    JSON-lines logger that writes to logs/agents.log.

    Every line is a JSON object with at minimum:
      { "ts": ISO8601, "level": str, "module": str, "msg": str, ...extra }

    Secrets are never written — callers must sanitise before passing kwargs.
    """

    _log_path = LOGS_DIR / "agents.log"
    _file_lock = threading.Lock()

    def __init__(self, module: str) -> None:
        self.module = module
        # Also mirror to stdlib logger so existing log handlers pick it up
        self._stdlib = logging.getLogger(f"da.{module}")

    def _emit(self, level: str, msg: str, **extra: Any) -> None:
        record: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "level": level,
            "module": self.module,
            "msg": msg,
        }
        record.update(extra)
        line = json.dumps(record, default=str)
        with self._file_lock:
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        getattr(self._stdlib, level.lower(), self._stdlib.info)(msg)

    def info(self, msg: str, **extra: Any) -> None:
        self._emit("INFO", msg, **extra)

    def warning(self, msg: str, **extra: Any) -> None:
        self._emit("WARNING", msg, **extra)

    def error(self, msg: str, **extra: Any) -> None:
        self._emit("ERROR", msg, **extra)

    def debug(self, msg: str, **extra: Any) -> None:
        self._emit("DEBUG", msg, **extra)


# Module-level convenience logger
log = StructuredLogger("_shared")


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class OpResult:
    """Result of any operational (write) action."""
    success: bool
    message: str
    detail: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineStatus:
    """Health/SLA status of a single integration pipeline."""
    name: str
    state: Literal["green", "yellow", "red"]
    last_heartbeat: Optional[datetime]
    detail: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    sla_breach: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # datetime is not JSON-serialisable by default
        if isinstance(self.last_heartbeat, datetime):
            d["last_heartbeat"] = self.last_heartbeat.isoformat()
        return d


@dataclass
class ServiceStatus:
    """Runtime state of a tmux session, docker container, or systemctl unit."""
    name: str
    type: str        # "tmux" | "docker" | "systemctl"
    running: bool
    pid: Optional[int] = None
    uptime_seconds: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BotStatus:
    """Runtime state of a trading bot (strategy)."""
    name: str
    strategy: str
    running: bool
    last_iteration: Optional[datetime] = None
    last_signal: Optional[datetime] = None
    open_positions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.last_iteration, datetime):
            d["last_iteration"] = self.last_iteration.isoformat()
        if isinstance(self.last_signal, datetime):
            d["last_signal"] = self.last_signal.isoformat()
        return d


# ── Approval queue ─────────────────────────────────────────────────────────────

_queue_lock = threading.Lock()


def _ensure_approval_queue() -> None:
    """Create the approval queue file if it does not exist."""
    with _queue_lock:
        if not APPROVAL_QUEUE_PATH.exists():
            APPROVAL_QUEUE_PATH.write_text("[]", encoding="utf-8")


def _write_to_approval_queue(entry: Dict[str, Any]) -> None:
    """Append an approval request to the JSON queue file (thread-safe)."""
    _ensure_approval_queue()
    with _queue_lock:
        try:
            data: List[Dict[str, Any]] = json.loads(
                APPROVAL_QUEUE_PATH.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            data = []
        data.append(entry)
        APPROVAL_QUEUE_PATH.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )


# ── Decorators ─────────────────────────────────────────────────────────────────

F = TypeVar("F", bound=Callable[..., Any])


def safe_tool(fn: F) -> F:
    """
    Decorator that wraps any tool function.

    On *any* unhandled exception the function returns an OpResult with
    success=False and the exception message — it never raises.
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.error(
                f"safe_tool caught exception in {fn.__qualname__}",
                exc=str(exc),
                exc_type=type(exc).__name__,
            )
            return OpResult(
                success=False,
                message=f"Error in {fn.__name__}: {exc}",
                detail={"exc_type": type(exc).__name__, "exc": str(exc)},
            )
    return wrapper  # type: ignore[return-value]


def requires_approval(fn: F) -> F:
    """
    Decorator for write operations that must be approved before executing.

    When called the decorator:
      1. Writes a structured entry to agents/.approval_queue.json
      2. Returns OpResult(success=False, message="pending approval") immediately
      3. Does NOT execute the underlying function

    An orchestrator can then read the queue, approve entries, and call the
    underlying function directly (bypassing this decorator via fn.__wrapped__).
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> OpResult:
        entry = {
            "id": _make_approval_id(),
            "function": fn.__qualname__,
            "module": fn.__module__,
            "args": [repr(a) for a in args],
            "kwargs": {k: repr(v) for k, v in kwargs.items()},
            "requested_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "status": "pending",
        }
        try:
            _write_to_approval_queue(entry)
            log.warning(
                f"requires_approval: queued {fn.__qualname__}",
                approval_id=entry["id"],
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to write approval queue", exc=str(exc))

        return OpResult(
            success=False,
            message="pending approval",
            detail={"approval_id": entry["id"], "function": fn.__qualname__},
        )

    # Expose the raw function so orchestrators can call it after approval
    wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]


def _make_approval_id() -> str:
    import uuid
    return str(uuid.uuid4())


# ── Initialise approval queue on import ────────────────────────────────────────
_ensure_approval_queue()
