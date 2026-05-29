# Disrupting Alpha — Unified Tool Layer: Implementation Plan

*Document generated: 2026-05-28 | Author: Antigravity*

---

## Overview

This document describes the architecture and implementation of the **Unified Tool Layer** for
the Disrupting Alpha multi-agent trading system. It is the canonical reference for
all future agent development.

Every agent in the system calls functions from `agents/tools/` — no business logic lives anywhere else.

---

## Directory Structure

```
agents/
├── __init__.py
├── config/
│   ├── services.yaml        # Service registry (tmux + docker + systemctl)
│   └── pipelines.yaml       # SLA thresholds for 12 integration checks
├── tools/
│   ├── __init__.py          # Public API (explicit __all__)
│   ├── __main__.py          # CLI: status / services / positions / health
│   ├── _shared.py           # Config loaders, logger, decorators, dataclasses
│   ├── ops_tools.py         # Service lifecycle management
│   ├── pipeline_tools.py    # 12 integration health checks (async)
│   ├── trading_tools.py     # Alpaca read + write stubs
│   └── research_tools.py    # Performance / news / sentiment / regime
├── interfaces/              # Reserved for agent interface definitions
│   └── __init__.py
└── agents/                  # Reserved for individual agent implementations
    └── __init__.py

tests/
└── test_tools.py            # Smoke tests for all four modules

docs/
└── implementation_plan.md   # This file
```

---

## Module Reference

### `agents/tools/_shared.py`

Core utilities shared by all tool modules.

| Export | Type | Description |
|---|---|---|
| `load_services_config()` | `list[dict]` | Cached YAML loader for `agents/config/services.yaml` |
| `load_pipelines_config()` | `dict` | Cached YAML loader for `agents/config/pipelines.yaml` |
| `StructuredLogger` | class | JSON-lines logger → `logs/agents.log` |
| `@safe_tool` | decorator | Catches all exceptions, returns `OpResult(success=False)` |
| `@requires_approval` | decorator | Queues to `.approval_queue.json`, returns `pending` |
| `OpResult` | dataclass | `{ success, message, detail }` |
| `PipelineStatus` | dataclass | `{ name, state, last_heartbeat, detail, metrics, sla_breach }` |
| `ServiceStatus` | dataclass | `{ name, type, running, pid, uptime_seconds }` |
| `BotStatus` | dataclass | `{ name, strategy, running, last_iteration, last_signal, open_positions }` |

### `agents/tools/ops_tools.py`

Wraps `scripts/health_check.py` and `scripts/start_all.sh` via subprocess.
Auto-detects log source per service type (tmux / docker / systemctl).

**Read (always executes):**
- `list_services()` → `dict[str, ServiceStatus]`
- `list_tmux_sessions()` → `list[str]`
- `list_docker_containers()` → `list[ServiceStatus]`
- `list_bots()` → `dict[str, BotStatus]`
- `tail_logs(service, lines=100)` → `str`
- `run_health_check()` → `dict`

**Write (require approval, return `pending`):**
- `start_service(name)`
- `stop_service(name)`
- `restart_service(name)`
- `restart_bot(strategy_name)`
- `run_start_all()`

### `agents/tools/pipeline_tools.py`

Async health checks for all 12 integrations.

| Function | Check type | SLA |
|---|---|---|
| `check_nats()` | HTTP /healthz | — |
| `check_questdb()` | HTTP /status | 60s (market hours) |
| `check_qdrant()` | HTTP /healthz | 900s |
| `check_supabase_cloud()` | Alpaca REST | 3600s |
| `check_supabase_local()` | HTTP REST | connection |
| `check_alpaca_rest()` | HTTP /v2/account | 2s response |
| `check_alpaca_ws_crypto()` | Heartbeat file | 30s |
| `check_alpaca_ws_equities()` | Heartbeat file | 30s (market hours) |
| `check_tick_collector()` | Heartbeat file | 60s |
| `check_news_collector()` | Heartbeat file | 600s |
| `check_finbert_scorer()` | Heartbeat file | 900s |
| `check_langgraph_cycle()` | Heartbeat file | 1200s |

`integration_overview()` runs all 12 via `asyncio.gather` (< 6s total).

### `agents/tools/trading_tools.py`

**Read (fully implemented):**
- `get_positions(account="paper")` — Alpaca `/v2/positions`
- `get_orders(status, limit)` — Alpaca `/v2/orders`
- `get_account_summary()` — Alpaca `/v2/account`
- `get_recent_signals(n, side)` — Supabase `paper_trades`
- `get_pnl_today()` — Supabase EXIT aggregation
- `get_pnl_range(start, end)` — Supabase range query
- `get_regime_state(asset_class)` — Supabase `regime_state`
- `get_kelly_sizing(symbol)` — Computed from Supabase win-rate
- `get_greeks(symbol)` — Alpaca position + stub greeks

**Write stubs (require approval):**
- `cancel_order(order_id)` — `NotImplementedError` stub
- `flatten_position(symbol)` — `NotImplementedError` stub
- `kill_switch()` — `NotImplementedError` stub

### `agents/tools/research_tools.py`

**Implemented:**
- `get_performance_today()` — Supabase EXIT aggregation + Sharpe
- `get_news_summary(window, symbols)` — Supabase `news_articles`
- `get_sentiment_scores(symbols)` — Supabase `sentiment_scores`
- `get_regime_history(window)` — Supabase `regime_state`

**Stubs (NotImplementedError):**
- `run_backtest(strategy, symbol, start, end)`
- `get_ic_tracking(window)`

---

## Configuration Reference

### `agents/config/services.yaml`

Defines all 8 tmux sessions + 5 docker containers with:
- `name`, `type`, `identifier`, `restart_command`, `log_command`, `healthcheck`

### `agents/config/pipelines.yaml`

Defines SLA thresholds for all 12 integration checks with:
- `last_*_sla` (seconds), `timeout_seconds`, `market_hours_only`, `check_type`

---

## Approval Queue Protocol

All `@requires_approval` functions:
1. Write a JSON entry to `agents/.approval_queue.json`
2. Return `OpResult(success=False, message="pending approval")` immediately
3. **Never execute** the underlying operation

An orchestrator can approve operations by:
1. Reading the queue file
2. Marking entries as `approved`
3. Calling `fn.__wrapped__(*args, **kwargs)` directly

---

## Security Constraints

- **Secrets are never logged.** `StructuredLogger` writes only what callers pass.
- **No `.env` values are exposed** in logs or outputs.
- **Write operations require human approval** via the queue protocol.
- **Protected files** (`strategies/`, `signal_engine/`, `scripts/health_check.py`,
  `scripts/start_all.sh`) are never modified.

---

## CLI Usage

```bash
# All 12 pipelines
python -m agents.tools status

# All 13 services (8 tmux + 5 docker)
python -m agents.tools services

# Current Alpaca paper positions
python -m agents.tools positions

# Run health_check.py and print output
python -m agents.tools health
```

---

## Testing

```bash
cd ~/disrupting-alpha
python -m pytest tests/test_tools.py -v
```

Tests use `pytest.skip` (not `fail`) when a service is unavailable.
All write-operation tests verify the approval decorator without touching production.

---

## Verification Checklist

- [ ] `python -m agents.tools status` → table with 12 pipelines
- [ ] `python -m agents.tools services` → table with 13 services
- [ ] `python -m agents.tools positions` → Alpaca paper positions
- [ ] `python -m agents.tools health` → parsed health_check output
- [ ] `python -m pytest tests/test_tools.py -v` → 0 failures
- [ ] Clean import: `from agents.tools import ops_tools, pipeline_tools, trading_tools, research_tools`
- [ ] `git status` shows changes only under `agents/`, `tests/`, `docs/`, `requirements.txt`
- [ ] `agents/.approval_queue.json` exists (initially `[]`)
- [ ] `logs/agents.log` writes structured JSON
- [ ] `@requires_approval` returns `pending` without executing
- [ ] `integration_overview()` completes in < 6 seconds
