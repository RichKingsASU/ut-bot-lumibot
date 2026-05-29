"""
agents/tools/pipeline_tools.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration health checks for all 12 pipelines.

Each check function:
  - Times out at 5 seconds
  - Returns PipelineStatus with state derived from SLA in pipelines.yaml
  - Catches all exceptions internally (via @safe_tool)

integration_overview() runs all 12 checks in parallel via asyncio.gather.

Python ≤ 3.11 compatible.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp

from agents.tools._shared import (
    PROJECT_ROOT,
    PipelineStatus,
    StructuredLogger,
    load_pipelines_config,
    safe_tool,
)

log = StructuredLogger("pipeline_tools")

# ── Internal helpers ───────────────────────────────────────────────────────────

_MARKET_OPEN_HOUR = 9   # ET 09:30
_MARKET_OPEN_MIN = 30
_MARKET_CLOSE_HOUR = 16  # ET 16:00


def _is_market_hours() -> bool:
    """Return True if current ET time is within NYSE core hours."""
    import pytz
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    open_time = now.replace(hour=_MARKET_OPEN_HOUR, minute=_MARKET_OPEN_MIN, second=0)
    close_time = now.replace(hour=_MARKET_CLOSE_HOUR, minute=0, second=0)
    return open_time <= now <= close_time


def _cfg(name: str) -> Dict[str, Any]:
    """Return pipeline config for `name`; raises KeyError if not found."""
    return load_pipelines_config()[name]


def _sla_seconds(cfg: Dict[str, Any]) -> Optional[int]:
    """Extract the primary SLA value (first *_sla key) from a pipeline config."""
    for key in ("last_message_sla", "last_tick_sla", "last_bar_sla",
                "heartbeat_sla", "last_article_sla", "last_scoring_sla",
                "last_completion_sla", "last_write_sla", "connection_sla"):
        if key in cfg:
            return int(cfg[key])
    return None


def _read_heartbeat_file(relative_path: str) -> Optional[Dict[str, Any]]:
    """
    Read a JSON heartbeat file relative to PROJECT_ROOT.

    Returns the parsed dict, or None if missing / malformed.
    """
    path = PROJECT_ROOT / relative_path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _age_seconds(ts_iso: Optional[str]) -> Optional[float]:
    """Return the age in seconds of an ISO-8601 timestamp, or None if invalid."""
    if not ts_iso:
        return None
    try:
        dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None


def _state_from_age(
    age: Optional[float],
    sla: Optional[int],
    market_hours_only: bool,
) -> tuple[str, bool]:
    """
    Derive ("green"|"yellow"|"red", sla_breach) from age and SLA.

    Rules:
      - If heartbeat file is missing → red
      - If market_hours_only=True and not in market hours → yellow (no SLA)
      - If age <= sla → green
      - If age > sla → red + sla_breach=True
    """
    if age is None:
        return "red", False  # missing/no data
    if sla is None:
        return "yellow", False  # no SLA defined
    if market_hours_only and not _is_market_hours():
        return "yellow", False  # outside enforcement window
    if age <= sla:
        return "green", False
    return "red", True


# ── Heartbeat-file-based checks ────────────────────────────────────────────────

def _check_heartbeat_pipeline(name: str) -> PipelineStatus:
    """Generic check for services that write a JSON heartbeat file."""
    cfg = _cfg(name)
    hb_path = cfg.get("heartbeat_file", "")
    sla = _sla_seconds(cfg)
    market_only = cfg.get("market_hours_only", False)

    hb = _read_heartbeat_file(hb_path)
    if hb is None:
        return PipelineStatus(
            name=name,
            state="yellow",  # yellow not red — service may not be deployed yet
            last_heartbeat=None,
            detail=f"Heartbeat file not found: {hb_path}",
            sla_breach=False,
        )

    ts_iso = hb.get("ts") or hb.get("timestamp") or hb.get("last_heartbeat")
    age = _age_seconds(ts_iso)
    state, breach = _state_from_age(age, sla, market_only)

    last_hb = None
    if ts_iso:
        try:
            last_hb = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        except Exception:
            pass

    detail = f"Age: {int(age)}s | SLA: {sla}s" if age is not None else "No timestamp"
    return PipelineStatus(
        name=name,
        state=state,
        last_heartbeat=last_hb,
        detail=detail,
        metrics=hb,
        sla_breach=breach,
    )


# ── Async HTTP checks ──────────────────────────────────────────────────────────

async def _http_get(url: str, timeout: int = 5, headers: Optional[Dict] = None) -> tuple[int, str]:
    """Async GET request returning (status_code, body_text)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                headers=headers or {},
                ssl=False,
            ) as resp:
                body = await resp.text()
                return resp.status, body
    except asyncio.TimeoutError:
        return -1, "timeout"
    except Exception as exc:
        return -1, str(exc)


def _run_async(coro) -> Any:
    """Run an async coroutine synchronously (works inside sync tool functions)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an existing event loop (e.g. Jupyter / FastAPI)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── Public check functions ─────────────────────────────────────────────────────

@safe_tool
def check_nats() -> PipelineStatus:
    """Check NATS JetStream health via HTTP /healthz endpoint."""
    cfg = _cfg("nats")
    endpoint = cfg.get("endpoint", "http://localhost:4222")
    health_path = cfg.get("health_path", "/healthz")
    url = f"{endpoint}{health_path}"

    async def _check():
        status, body = await _http_get(url, timeout=5)
        if status == 200:
            return PipelineStatus(
                name="nats",
                state="green",
                last_heartbeat=datetime.now(timezone.utc),
                detail=f"HTTP {status}",
                metrics={"status_code": status},
            )
        return PipelineStatus(
            name="nats",
            state="red",
            last_heartbeat=None,
            detail=f"HTTP {status}: {body[:100]}",
            sla_breach=True,
        )

    return _run_async(_check())


@safe_tool
def check_questdb() -> PipelineStatus:
    """Check QuestDB via HTTP /status endpoint."""
    cfg = _cfg("questdb")
    endpoint = cfg.get("endpoint", "http://localhost:9000")
    url = f"{endpoint}/status"

    async def _check():
        t0 = time.monotonic()
        status, body = await _http_get(url, timeout=5)
        latency = time.monotonic() - t0
        if status == 200:
            return PipelineStatus(
                name="questdb",
                state="green",
                last_heartbeat=datetime.now(timezone.utc),
                detail=f"HTTP {status} in {latency:.2f}s",
                metrics={"latency_ms": round(latency * 1000)},
            )
        return PipelineStatus(
            name="questdb",
            state="red",
            last_heartbeat=None,
            detail=f"HTTP {status}: {body[:100]}",
            sla_breach=True,
        )

    return _run_async(_check())


@safe_tool
def check_qdrant() -> PipelineStatus:
    """Check Qdrant vector store via HTTP /healthz."""
    cfg = _cfg("qdrant")
    endpoint = cfg.get("endpoint", "http://localhost:6333")
    url = f"{endpoint}/healthz"

    async def _check():
        status, body = await _http_get(url, timeout=5)
        if status == 200:
            return PipelineStatus(
                name="qdrant",
                state="green",
                last_heartbeat=datetime.now(timezone.utc),
                detail=f"HTTP {status}",
            )
        return PipelineStatus(
            name="qdrant",
            state="red",
            last_heartbeat=None,
            detail=f"HTTP {status}: {body[:100]}",
            sla_breach=True,
        )

    return _run_async(_check())


@safe_tool
def check_supabase_cloud() -> PipelineStatus:
    """
    Check Supabase Cloud connection via REST API.

    Endpoint sourced from SUPABASE_URL env var.
    """
    supa_url = os.getenv("SUPABASE_URL", "")
    supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supa_url or not supa_key:
        return PipelineStatus(
            name="supabase_cloud",
            state="yellow",
            last_heartbeat=None,
            detail="SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured",
        )

    url = f"{supa_url}/rest/v1/"
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
    }

    async def _check():
        t0 = time.monotonic()
        status, body = await _http_get(url, timeout=5, headers=headers)
        latency = time.monotonic() - t0
        if status in (200, 201, 204):
            return PipelineStatus(
                name="supabase_cloud",
                state="green",
                last_heartbeat=datetime.now(timezone.utc),
                detail=f"Connected in {latency:.2f}s",
                metrics={"latency_ms": round(latency * 1000)},
            )
        return PipelineStatus(
            name="supabase_cloud",
            state="red",
            last_heartbeat=None,
            detail=f"HTTP {status}: {body[:100]}",
            sla_breach=True,
        )

    return _run_async(_check())


@safe_tool
def check_supabase_local() -> PipelineStatus:
    """Check Supabase Local Docker via HTTP REST endpoint."""
    cfg = _cfg("supabase_local")
    endpoint = cfg.get("endpoint", "http://localhost:54321")
    url = f"{endpoint}/rest/v1/"

    async def _check():
        status, body = await _http_get(url, timeout=5)
        # Supabase local returns 401 without auth — that's still "up"
        if status in (200, 401):
            return PipelineStatus(
                name="supabase_local",
                state="green",
                last_heartbeat=datetime.now(timezone.utc),
                detail=f"HTTP {status} (connection OK)",
            )
        return PipelineStatus(
            name="supabase_local",
            state="red",
            last_heartbeat=None,
            detail=f"HTTP {status}: {body[:100]}",
            sla_breach=True,
        )

    return _run_async(_check())


@safe_tool
def check_alpaca_rest() -> PipelineStatus:
    """
    Check Alpaca REST API by calling /v2/account.

    SLA: response must arrive within 2 seconds.
    """
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    api_key = os.getenv("ALPACA_API_KEY", "")
    api_secret = os.getenv("ALPACA_API_SECRET", "")

    if not api_key or not api_secret:
        return PipelineStatus(
            name="alpaca_rest",
            state="yellow",
            last_heartbeat=None,
            detail="ALPACA_API_KEY or ALPACA_API_SECRET not configured",
        )

    url = f"{base_url}/v2/account"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
    }

    async def _check():
        t0 = time.monotonic()
        status, body = await _http_get(url, timeout=5, headers=headers)
        latency = time.monotonic() - t0
        sla = _cfg("alpaca_rest").get("response_time_sla", 2)
        state = "green" if status == 200 and latency <= sla else (
            "yellow" if status == 200 else "red"
        )
        breach = status != 200 or latency > sla
        return PipelineStatus(
            name="alpaca_rest",
            state=state,
            last_heartbeat=datetime.now(timezone.utc) if status == 200 else None,
            detail=f"HTTP {status} in {latency:.2f}s (SLA {sla}s)",
            metrics={"latency_ms": round(latency * 1000), "status_code": status},
            sla_breach=breach,
        )

    return _run_async(_check())


@safe_tool
def check_alpaca_ws_crypto() -> PipelineStatus:
    """Check Alpaca WebSocket crypto stream via heartbeat file."""
    return _check_heartbeat_pipeline("alpaca_ws_crypto")


@safe_tool
def check_alpaca_ws_equities() -> PipelineStatus:
    """Check Alpaca WebSocket equities stream via heartbeat file."""
    return _check_heartbeat_pipeline("alpaca_ws_equities")


@safe_tool
def check_tick_collector() -> PipelineStatus:
    """Check tick data collector via heartbeat file."""
    return _check_heartbeat_pipeline("tick_collector")


@safe_tool
def check_news_collector() -> PipelineStatus:
    """Check news collector pipeline via heartbeat file."""
    return _check_heartbeat_pipeline("news_collector")


@safe_tool
def check_finbert_scorer() -> PipelineStatus:
    """Check FinBERT sentiment scorer via heartbeat file."""
    return _check_heartbeat_pipeline("finbert_scorer")


@safe_tool
def check_langgraph_cycle() -> PipelineStatus:
    """Check LangGraph orchestration cycle via heartbeat file."""
    return _check_heartbeat_pipeline("langgraph_cycle")


# ── integration_overview: all 12 in parallel ───────────────────────────────────

_ALL_CHECKS = [
    check_nats,
    check_questdb,
    check_qdrant,
    check_supabase_cloud,
    check_supabase_local,
    check_alpaca_rest,
    check_alpaca_ws_crypto,
    check_alpaca_ws_equities,
    check_tick_collector,
    check_news_collector,
    check_finbert_scorer,
    check_langgraph_cycle,
]


async def _run_all_checks_async() -> Dict[str, Any]:
    """Run all pipeline checks concurrently with individual 5-second timeouts."""
    async def run_one(fn) -> PipelineStatus:
        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, fn),
                timeout=5.0,
            )
            return result
        except asyncio.TimeoutError:
            name = fn.__name__.replace("check_", "")
            return PipelineStatus(
                name=name,
                state="red",
                last_heartbeat=None,
                detail="Check timed out after 5s",
                sla_breach=True,
            )
        except Exception as exc:
            name = fn.__name__.replace("check_", "")
            return PipelineStatus(
                name=name,
                state="red",
                last_heartbeat=None,
                detail=f"Check error: {exc}",
                sla_breach=True,
            )

    results = await asyncio.gather(*[run_one(fn) for fn in _ALL_CHECKS])
    return {r.name: r.to_dict() for r in results}


@safe_tool
def integration_overview() -> Dict[str, Any]:
    """
    Run all 12 pipeline checks in parallel.

    Returns a dict mapping pipeline name → PipelineStatus.to_dict().
    Completes in < 6 seconds (5s timeout per check + overhead).
    """
    t0 = time.monotonic()
    result = asyncio.run(_run_all_checks_async())
    elapsed = time.monotonic() - t0
    log.info("integration_overview completed", elapsed_s=round(elapsed, 2))
    return result
