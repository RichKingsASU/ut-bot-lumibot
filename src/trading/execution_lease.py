"""Kernel-owned, account-scoped authority for Alpaca mutations.

The lease is deliberately independent of any launcher.  Broker adapters must
call :func:`require_execution_lease` immediately before every HTTP mutation.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("execution_lease")
DEFAULT_RUNTIME_DIR = Path("/run/disrupting-alpha")
_SAFE_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class ExecutionLeaseError(RuntimeError):
    """Base class for fail-closed execution authority errors."""


class ExecutionLeaseDenied(ExecutionLeaseError):
    """Another process owns the requested account lease."""


class ExecutionMutationBlocked(ExecutionLeaseError):
    """A broker mutation was attempted without authority."""


def resolve_trading_mode(value: Optional[str] = None) -> str:
    """Return ``paper``/``live`` and reject missing or ambiguous values."""
    raw = value if value is not None else os.getenv("ALPACA_IS_PAPER")
    if raw is None:
        raise ExecutionLeaseError("ALPACA_IS_PAPER must be explicitly true or false")
    normalized = raw.strip().lower()
    if normalized == "true":
        return "paper"
    if normalized == "false":
        return "live"
    raise ExecutionLeaseError("ALPACA_IS_PAPER must be explicitly true or false")


def resolve_account_alias(value: Optional[str] = None) -> str:
    alias = value if value is not None else os.getenv("ALPACA_ACCOUNT_ALIAS")
    if not alias or not _SAFE_ALIAS.fullmatch(alias):
        raise ExecutionLeaseError(
            "ALPACA_ACCOUNT_ALIAS is required and must contain only non-secret safe characters"
        )
    return alias.lower()


@dataclass
class ExecutionLease:
    account_alias: str
    mode: str
    process_name: str = "unknown"
    runtime_dir: Path = DEFAULT_RUNTIME_DIR
    broker: str = "alpaca"
    _fd: Optional[int] = None
    _owner_pid: Optional[int] = None

    @classmethod
    def from_environment(cls, **kwargs) -> "ExecutionLease":
        return cls(
            account_alias=resolve_account_alias(),
            mode=resolve_trading_mode(),
            **kwargs,
        )

    def __post_init__(self) -> None:
        self.account_alias = resolve_account_alias(self.account_alias)
        self.mode = resolve_trading_mode("true" if self.mode == "paper" else "false" if self.mode == "live" else self.mode)
        self.runtime_dir = Path(self.runtime_dir)

    @property
    def identity(self) -> str:
        return f"{self.broker}:{self.account_alias}:{self.mode}"

    @property
    def lock_path(self) -> Path:
        return self.runtime_dir / f"{self.broker}-{self.account_alias}-{self.mode}.lock"

    @property
    def owned(self) -> bool:
        return self._fd is not None and self._owner_pid == os.getpid()

    def _event(self, event: str, level: int = logging.INFO) -> None:
        logger.log(level, "%s", json.dumps({
            "event": event, "broker": self.broker,
            "account_alias": self.account_alias, "mode": self.mode,
            "pid": os.getpid(), "process": self.process_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, sort_keys=True))

    def acquire(self) -> "ExecutionLease":
        if self.owned:
            return self
        try:
            self.runtime_dir.mkdir(mode=0o750, parents=True, exist_ok=True)
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o640)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                os.close(fd)
                self._event("EXECUTION_LEASE_DENIED", logging.CRITICAL)
                self._event("DUPLICATE_EXECUTOR_BLOCKED", logging.CRITICAL)
                raise ExecutionLeaseDenied(f"execution lease already held: {self.identity}") from exc
            os.ftruncate(fd, 0)
            os.write(fd, f"pid={os.getpid()} process={self.process_name}\n".encode())
            self._fd, self._owner_pid = fd, os.getpid()
            self._event("EXECUTION_LEASE_ACQUIRED")
            return self
        except ExecutionLeaseDenied:
            raise
        except Exception as exc:
            self._event("EXECUTION_LEASE_DENIED", logging.CRITICAL)
            raise ExecutionLeaseError(f"cannot acquire execution lease: {exc}") from exc

    def release(self) -> None:
        if self._fd is not None:
            fd, self._fd, self._owner_pid = self._fd, None, None
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
            self._event("EXECUTION_LEASE_RELEASED")

    def __enter__(self) -> "ExecutionLease":
        return self.acquire()

    def __exit__(self, *_args) -> None:
        self.release()


_execution_lease: Optional[ExecutionLease] = None


def install_execution_lease(lease: Optional[ExecutionLease]) -> None:
    global _execution_lease
    _execution_lease = lease


def execution_lease_state() -> dict:
    lease = _execution_lease
    return {
        "execution_lease_owned": bool(lease and lease.owned),
        "execution_lease_identity": lease.identity if lease else None,
    }


def require_execution_lease(operation: str) -> ExecutionLease:
    lease = _execution_lease
    if not lease or not lease.owned:
        alias = lease.account_alias if lease else os.getenv("ALPACA_ACCOUNT_ALIAS", "unresolved")
        try:
            mode = lease.mode if lease else resolve_trading_mode()
        except ExecutionLeaseError:
            mode = "unresolved"
        logger.critical("%s", json.dumps({
            "event": "EXECUTION_MUTATION_BLOCKED", "operation": operation,
            "broker": "alpaca", "account_alias": alias, "mode": mode,
            "pid": os.getpid(), "process": os.getenv("DA_PROCESS_NAME", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, sort_keys=True))
        raise ExecutionMutationBlocked(f"{operation} requires an owned execution lease")
    return lease
