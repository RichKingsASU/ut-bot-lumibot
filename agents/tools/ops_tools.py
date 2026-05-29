"""
agents/tools/ops_tools.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Operational tools — service lifecycle management.

Wraps existing scripts (health_check.py, start_all.sh) via subprocess.
Never rewrites their logic.

All write operations are decorated with @requires_approval and return
OpResult(success=False, message="pending approval") without executing.

Python ≤ 3.11 compatible.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.tools._shared import (
    PROJECT_ROOT,
    BotStatus,
    OpResult,
    ServiceStatus,
    StructuredLogger,
    load_services_config,
    requires_approval,
    safe_tool,
)

log = StructuredLogger("ops_tools")

# ── Internal helpers ───────────────────────────────────────────────────────────

def _run(cmd: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a shell command and return the CompletedProcess result."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _service_cfg(name: str) -> Optional[Dict[str, Any]]:
    """Lookup a service config entry by name. Returns None if not found."""
    for svc in load_services_config():
        if svc["name"] == name:
            return svc
    return None


# ── Read-only functions ────────────────────────────────────────────────────────

@safe_tool
def list_tmux_sessions() -> List[str]:
    """Return a list of running tmux session names."""
    result = _run("tmux list-sessions -F '#{session_name}' 2>/dev/null")
    if result.returncode != 0:
        return []
    return [s.strip() for s in result.stdout.splitlines() if s.strip()]


@safe_tool
def list_docker_containers() -> List[ServiceStatus]:
    """
    Return ServiceStatus for every known docker container defined in services.yaml.
    Uses `docker inspect` to determine running state.
    """
    docker_services = [
        s for s in load_services_config() if s["type"] == "docker"
    ]
    statuses: List[ServiceStatus] = []
    for svc in docker_services:
        container = svc["identifier"]
        result = _run(
            f"docker inspect --format='{{{{.State.Running}}}}:{{{{.State.Pid}}}}:{{{{.State.StartedAt}}}}'"
            f" {container} 2>/dev/null"
        )
        running = False
        pid: Optional[int] = None
        uptime: Optional[int] = None
        if result.returncode == 0:
            parts = result.stdout.strip().replace("'", "").split(":")
            running = parts[0].lower() == "true"
            if len(parts) > 1:
                try:
                    pid = int(parts[1])
                except ValueError:
                    pass
            if running and len(parts) > 2:
                started_str = ":".join(parts[2:])
                try:
                    started = datetime.fromisoformat(
                        started_str.replace("Z", "+00:00")
                    )
                    uptime = int((datetime.now(started.tzinfo) - started).total_seconds())
                except Exception:
                    pass
        statuses.append(
            ServiceStatus(
                name=svc["name"],
                type="docker",
                running=running,
                pid=pid if running else None,
                uptime_seconds=uptime,
            )
        )
    return statuses


@safe_tool
def list_services() -> Dict[str, ServiceStatus]:
    """
    Return a dict mapping service name → ServiceStatus for ALL services.

    Handles tmux sessions, docker containers, and systemctl units.
    """
    all_services: Dict[str, ServiceStatus] = {}

    # tmux sessions
    running_sessions = set(list_tmux_sessions())  # type: ignore[arg-type]
    for svc in load_services_config():
        if svc["type"] != "tmux":
            continue
        running = svc["identifier"] in running_sessions
        # Try to get PID from tmux session
        pid: Optional[int] = None
        uptime: Optional[int] = None
        if running:
            pid_result = _run(
                f"tmux list-panes -t {svc['identifier']} -F '{{{{pane_pid}}}}' 2>/dev/null"
            )
            if pid_result.returncode == 0:
                pids = pid_result.stdout.strip().splitlines()
                if pids:
                    try:
                        pid = int(pids[0].strip())
                    except ValueError:
                        pass
        all_services[svc["name"]] = ServiceStatus(
            name=svc["name"],
            type="tmux",
            running=running,
            pid=pid,
            uptime_seconds=uptime,
        )

    # docker containers
    for status in list_docker_containers():  # type: ignore[union-attr]
        all_services[status.name] = status

    # systemctl units (if any)
    for svc in load_services_config():
        if svc["type"] != "systemctl":
            continue
        result = _run(f"systemctl is-active {svc['identifier']} 2>/dev/null")
        running = result.stdout.strip() == "active"
        all_services[svc["name"]] = ServiceStatus(
            name=svc["name"],
            type="systemctl",
            running=running,
        )

    return all_services


@safe_tool
def list_bots() -> Dict[str, BotStatus]:
    """
    Return BotStatus for known trading bots.

    Determines running state from tmux sessions.
    Signal/iteration timestamps are parsed from log files where available.
    """
    bot_map = {
        "ut_bot": {"strategy": "UTBotStrategy", "session": "ut_bot"},
        "ut_bot_crypto": {"strategy": "UTBotCrypto", "session": "ut_bot_crypto"},
    }
    running_sessions = set(list_tmux_sessions())  # type: ignore[arg-type]
    result: Dict[str, BotStatus] = {}
    for bot_name, meta in bot_map.items():
        running = meta["session"] in running_sessions
        result[bot_name] = BotStatus(
            name=bot_name,
            strategy=meta["strategy"],
            running=running,
        )
    return result


@safe_tool
def tail_logs(service: str, lines: int = 100) -> str:
    """
    Return the last `lines` log entries for `service`.

    Auto-detects the log mechanism from services.yaml:
      - tmux  → tmux capture-pane
      - docker → docker logs --tail N
      - systemctl → journalctl -u unit --no-pager -n N
    """
    svc = _service_cfg(service)
    if svc is None:
        return f"Unknown service: {service}"

    stype = svc["type"]
    identifier = svc["identifier"]

    if stype == "tmux":
        result = _run(
            f"tmux capture-pane -pt {identifier} -S -{lines} 2>/dev/null"
        )
    elif stype == "docker":
        result = _run(f"docker logs --tail {lines} {identifier} 2>&1")
    elif stype == "systemctl":
        result = _run(
            f"journalctl -u {identifier} --no-pager -n {lines} 2>/dev/null"
        )
    else:
        return f"Unsupported service type: {stype}"

    if result.returncode != 0 and not result.stdout:
        return result.stderr or f"No log output for {service}"
    return result.stdout or result.stderr or "(empty)"


@safe_tool
def run_health_check() -> Dict[str, Any]:
    """
    Run scripts/health_check.py via subprocess and parse its output.

    Returns a dict with the raw output and any parsed sections.
    """
    script = PROJECT_ROOT / "scripts" / "health_check.py"
    if not script.exists():
        log.warning("health_check.py not found — returning stub result")
        return {
            "available": False,
            "reason": f"Script not found: {script}",
            "raw": "",
        }

    result = _run(
        f"{sys.executable} {script}",
        timeout=60,
    )
    output = result.stdout + result.stderr
    return {
        "available": True,
        "returncode": result.returncode,
        "raw": output,
        "lines": output.splitlines(),
        "ok": result.returncode == 0,
    }


# ── Write operations (all require approval) ────────────────────────────────────

@requires_approval
@safe_tool
def start_service(name: str) -> OpResult:
    """Start a stopped service by name (looks up restart_command from services.yaml)."""
    svc = _service_cfg(name)
    if svc is None:
        return OpResult(success=False, message=f"Unknown service: {name}")
    cmd = svc.get("restart_command", "")
    if not cmd:
        return OpResult(success=False, message=f"No restart_command for: {name}")
    result = _run(cmd, timeout=30)
    ok = result.returncode == 0
    return OpResult(
        success=ok,
        message=f"start_service({name}) {'succeeded' if ok else 'failed'}",
        detail={"stdout": result.stdout[:500], "stderr": result.stderr[:500]},
    )


@requires_approval
@safe_tool
def stop_service(name: str) -> OpResult:
    """Stop a running service by name."""
    svc = _service_cfg(name)
    if svc is None:
        return OpResult(success=False, message=f"Unknown service: {name}")
    stype = svc["type"]
    identifier = svc["identifier"]

    if stype == "tmux":
        cmd = f"tmux kill-session -t {identifier}"
    elif stype == "docker":
        cmd = f"docker stop {identifier}"
    elif stype == "systemctl":
        cmd = f"systemctl stop {identifier}"
    else:
        return OpResult(success=False, message=f"Cannot stop service type: {stype}")

    result = _run(cmd, timeout=30)
    ok = result.returncode == 0
    return OpResult(
        success=ok,
        message=f"stop_service({name}) {'succeeded' if ok else 'failed'}",
        detail={"cmd": cmd, "stdout": result.stdout[:500], "stderr": result.stderr[:500]},
    )


@requires_approval
@safe_tool
def restart_service(name: str) -> OpResult:
    """Restart a service by name using its configured restart_command."""
    svc = _service_cfg(name)
    if svc is None:
        return OpResult(success=False, message=f"Unknown service: {name}")
    cmd = svc.get("restart_command", "")
    if not cmd:
        return OpResult(success=False, message=f"No restart_command for: {name}")
    result = _run(cmd, timeout=60)
    ok = result.returncode == 0
    return OpResult(
        success=ok,
        message=f"restart_service({name}) {'succeeded' if ok else 'failed'}",
        detail={"stdout": result.stdout[:500], "stderr": result.stderr[:500]},
    )


@requires_approval
@safe_tool
def restart_bot(strategy_name: str) -> OpResult:
    """
    Restart a trading bot by strategy name.

    Maps strategy name to the corresponding tmux session and re-launches it.
    """
    strategy_to_session = {
        "ut_bot": "ut_bot",
        "ut_bot_crypto": "ut_bot_crypto",
        "UTBotStrategy": "ut_bot",
        "UTBotCrypto": "ut_bot_crypto",
    }
    session = strategy_to_session.get(strategy_name)
    if session is None:
        return OpResult(success=False, message=f"Unknown strategy: {strategy_name}")
    return restart_service(session)  # type: ignore[return-value]


@requires_approval
@safe_tool
def run_start_all() -> OpResult:
    """
    Run scripts/start_all.sh via subprocess.

    Wraps the script without modifying it.
    """
    script = PROJECT_ROOT / "scripts" / "start_all.sh"
    if not script.exists():
        return OpResult(
            success=False,
            message=f"start_all.sh not found: {script}",
        )
    result = _run(f"bash {script}", timeout=120)
    ok = result.returncode == 0
    return OpResult(
        success=ok,
        message=f"run_start_all() {'succeeded' if ok else 'failed'}",
        detail={
            "stdout": result.stdout[:1000],
            "stderr": result.stderr[:500],
        },
    )
