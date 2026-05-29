"""
agents/tools/__main__.py
~~~~~~~~~~~~~~~~~~~~~~~~~
CLI entrypoint for the Disrupting Alpha tool layer.

Usage:
    python -m agents.tools status     → integration_overview() as table
    python -m agents.tools services   → list_services() as table
    python -m agents.tools positions  → get_positions() as table
    python -m agents.tools health     → run_health_check() summary

Requires: rich>=13.0.0
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.text import Text

console = Console()


# ── Formatters ─────────────────────────────────────────────────────────────────

def _state_color(state: str) -> str:
    return {"green": "bold green", "yellow": "bold yellow", "red": "bold red"}.get(
        state, "white"
    )


def _bool_icon(val: bool) -> str:
    return "[green]●[/green]" if val else "[red]○[/red]"


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_status() -> None:
    """Print integration_overview() as a rich table."""
    from agents.tools.pipeline_tools import integration_overview

    console.print(Panel("[bold cyan]Integration Overview[/bold cyan] — all 12 pipelines", expand=False))
    with console.status("Running checks…", spinner="dots"):
        overview = integration_overview()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Pipeline", style="bold", min_width=22)
    table.add_column("State", justify="center", min_width=8)
    table.add_column("SLA Breach", justify="center", min_width=10)
    table.add_column("Last Heartbeat", min_width=22)
    table.add_column("Detail")

    for name, status in sorted(overview.items()):
        if isinstance(status, dict):
            state = status.get("state", "?")
            breach = status.get("sla_breach", False)
            last_hb = status.get("last_heartbeat") or "—"
            detail = status.get("detail", "")
        else:
            state, breach, last_hb, detail = "?", False, "—", str(status)

        table.add_row(
            name,
            Text(state.upper(), style=_state_color(state)),
            "[red]YES[/red]" if breach else "[green]no[/green]",
            str(last_hb)[:19] if last_hb and last_hb != "—" else "—",
            detail,
        )

    console.print(table)


def cmd_services() -> None:
    """Print list_services() as a rich table."""
    from agents.tools.ops_tools import list_services

    console.print(Panel("[bold cyan]Service Registry[/bold cyan] — tmux + docker", expand=False))
    with console.status("Querying services…", spinner="dots"):
        services = list_services()

    if isinstance(services, Exception) or not services:
        console.print("[yellow]No service data available (is this running on the edge server?)[/yellow]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Service", style="bold", min_width=18)
    table.add_column("Type", min_width=10)
    table.add_column("Running", justify="center", min_width=8)
    table.add_column("PID", justify="right", min_width=7)
    table.add_column("Uptime", justify="right", min_width=10)

    for name, status in sorted(services.items()):
        if hasattr(status, "running"):
            running = status.running
            stype = status.type
            pid = str(status.pid) if status.pid else "—"
            uptime = f"{status.uptime_seconds}s" if status.uptime_seconds else "—"
        elif isinstance(status, dict):
            running = status.get("running", False)
            stype = status.get("type", "?")
            pid = str(status.get("pid") or "—")
            uptime = f"{status.get('uptime_seconds')}s" if status.get("uptime_seconds") else "—"
        else:
            running, stype, pid, uptime = False, "?", "—", "—"

        table.add_row(
            name,
            stype,
            _bool_icon(running),
            pid,
            uptime,
        )

    console.print(table)


def cmd_positions() -> None:
    """Print get_positions() as a rich table."""
    from agents.tools.trading_tools import get_positions

    console.print(Panel("[bold cyan]Open Positions[/bold cyan] — Alpaca Paper", expand=False))
    with console.status("Fetching positions…", spinner="dots"):
        positions = get_positions()

    if not positions or isinstance(positions, Exception):
        console.print("[yellow]No open positions (or Alpaca credentials not configured)[/yellow]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="bold", min_width=20)
    table.add_column("Side", justify="center")
    table.add_column("Qty", justify="right")
    table.add_column("Avg Entry", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Unrealized P&L", justify="right")
    table.add_column("P&L %", justify="right")

    for pos in positions:
        sym = pos.get("symbol", "?")
        side = pos.get("side", "?")
        qty = pos.get("qty", "?")
        avg_entry = f"${float(pos.get('avg_entry_price', 0)):.4f}"
        current = f"${float(pos.get('current_price', 0)):.4f}"
        unreal_pl = float(pos.get("unrealized_pl", 0))
        unreal_plpc = float(pos.get("unrealized_plpc", 0)) * 100
        pl_color = "green" if unreal_pl >= 0 else "red"

        table.add_row(
            sym, side, str(qty), avg_entry, current,
            Text(f"${unreal_pl:.2f}", style=pl_color),
            Text(f"{unreal_plpc:.2f}%", style=pl_color),
        )

    console.print(table)


def cmd_health() -> None:
    """Print run_health_check() output."""
    from agents.tools.ops_tools import run_health_check

    console.print(Panel("[bold cyan]Health Check[/bold cyan] — scripts/health_check.py", expand=False))
    with console.status("Running health_check.py…", spinner="dots"):
        result = run_health_check()

    if not result.get("available"):
        console.print(f"[yellow]{result.get('reason', 'health_check.py not available')}[/yellow]")
        console.print("[dim]Note: This script lives on the edge server. Run this CLI there.[/dim]")
        return

    ok = result.get("ok", False)
    rc = result.get("returncode", -1)
    color = "green" if ok else "red"
    console.print(f"Return code: [{color}]{rc}[/{color}]")
    console.rule()
    for line in (result.get("lines") or []):
        console.print(line)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    commands = {
        "status": cmd_status,
        "services": cmd_services,
        "positions": cmd_positions,
        "health": cmd_health,
    }

    args = sys.argv[1:]
    if not args or args[0] not in commands:
        console.print(
            Panel(
                "[bold]Available commands:[/bold]\n"
                "  [cyan]status[/cyan]    — integration_overview() table (12 pipelines)\n"
                "  [cyan]services[/cyan]  — list_services() table (tmux + docker)\n"
                "  [cyan]positions[/cyan] — get_positions() table (Alpaca paper)\n"
                "  [cyan]health[/cyan]    — run_health_check() output\n\n"
                "Usage:  python -m agents.tools <command>",
                title="Disrupting Alpha Tool Layer",
                border_style="cyan",
            )
        )
        sys.exit(0)

    commands[args[0]]()


if __name__ == "__main__":
    main()
