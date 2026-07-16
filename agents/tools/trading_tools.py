"""
agents/tools/trading_tools.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only trading data tools + write stubs.

Read functions are fully implemented and hit Alpaca REST + Supabase.
Write functions are stubbed with @requires_approval and raise
NotImplementedError if somehow called after approval — intentional,
as they should be implemented separately when the write layer is ready.

Python ≤ 3.11 compatible.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from agents.tools._shared import (
    OpResult,
    StructuredLogger,
    requires_approval,
    safe_tool,
)

log = StructuredLogger("trading_tools")

# ── Alpaca helpers ─────────────────────────────────────────────────────────────

def _alpaca_headers() -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET", ""),
        "Content-Type": "application/json",
    }


def _base_url(account: str = "paper") -> str:
    """Return Alpaca base URL. `account` can be 'paper' or 'live'."""
    if account == "live":
        return os.getenv("ALPACA_LIVE_URL", "https://api.alpaca.markets")
    return os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")


def _data_url() -> str:
    return os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")


def _alpaca_get(path: str, account: str = "paper", **params) -> Any:
    """GET a path from the Alpaca API with 5-second timeout."""
    url = f"{_base_url(account)}{path}"
    resp = requests.get(url, headers=_alpaca_headers(), params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()


# ── Supabase helpers ───────────────────────────────────────────────────────────

def _supa_headers() -> Dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _supa_get(table: str, **params) -> List[Dict]:
    """GET rows from a Supabase table via REST API."""
    url_base = os.getenv("SUPABASE_URL", "")
    if not url_base:
        return []
    url = f"{url_base}/rest/v1/{table}"
    resp = requests.get(url, headers=_supa_headers(), params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()


# ── Read-only functions (fully implemented) ────────────────────────────────────

@safe_tool
def get_positions(account: str = "paper") -> List[Dict[str, Any]]:
    """
    Return current open positions from Alpaca.

    Args:
        account: "paper" (default) or "live"

    Returns:
        List of position dicts as returned by Alpaca /v2/positions
    """
    positions = _alpaca_get("/v2/positions", account=account)
    log.info(f"get_positions({account}): {len(positions)} positions")
    return positions


@safe_tool
def get_orders(status: str = "all", limit: int = 50) -> List[Dict[str, Any]]:
    """
    Return recent orders from Alpaca.

    Args:
        status: "open" | "closed" | "all"
        limit: max number of orders to return

    Returns:
        List of order dicts
    """
    orders = _alpaca_get("/v2/orders", status=status, limit=limit)
    log.info(f"get_orders(status={status}, limit={limit}): {len(orders)} orders")
    return orders


@safe_tool
def get_account_summary() -> Dict[str, Any]:
    """
    Return a summary of the Alpaca paper account.

    Returns:
        Account dict with portfolio_value, buying_power, cash, equity, etc.
    """
    account = _alpaca_get("/v2/account")
    summary = {
        "portfolio_value": account.get("portfolio_value"),
        "equity": account.get("equity"),
        "cash": account.get("cash"),
        "buying_power": account.get("buying_power"),
        "long_market_value": account.get("long_market_value"),
        "short_market_value": account.get("short_market_value"),
        "day_trade_count": account.get("daytrade_count"),
        "pattern_day_trader": account.get("pattern_day_trader"),
        "account_blocked": account.get("account_blocked"),
        "trading_blocked": account.get("trading_blocked"),
        "currency": account.get("currency"),
    }
    log.info("get_account_summary: OK", equity=summary.get("equity"))
    return summary


@safe_tool
def get_recent_signals(
    n: int = 10, side: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Return the most recent trading signals from Supabase paper_trades.

    Args:
        n:    Number of records to return
        side: Filter by "ENTRY", "EXIT", or None for all

    Returns:
        List of trade/signal dicts ordered by created_at desc
    """
    params: Dict[str, Any] = {
        "order": "created_at.desc",
        "limit": n,
    }
    if side:
        params["side"] = f"eq.{side.upper()}"

    rows = _supa_get("paper_trades", **params)
    log.info(f"get_recent_signals(n={n}, side={side}): {len(rows)} rows")
    return rows


@safe_tool
def get_pnl_today() -> Dict[str, Any]:
    """
    Return today's P&L summary from Supabase paper_trades.

    Returns:
        { date, realized_pnl, trade_count, win_count, loss_count, avg_pnl }
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = _supa_get(
        "paper_trades",
        side="eq.EXIT",
        created_at=f"gte.{today}",
        select="trade_pnl,contract_symbol,direction,exit_reason",
    )
    realized_pnl = sum(float(r.get("trade_pnl") or 0) for r in rows)
    win_count = sum(1 for r in rows if float(r.get("trade_pnl") or 0) > 0)
    loss_count = sum(1 for r in rows if float(r.get("trade_pnl") or 0) < 0)
    return {
        "date": today,
        "realized_pnl": round(realized_pnl, 2),
        "trade_count": len(rows),
        "win_count": win_count,
        "loss_count": loss_count,
        "avg_pnl": round(realized_pnl / len(rows), 2) if rows else 0.0,
    }


@safe_tool
def get_pnl_range(start: str, end: str) -> Dict[str, Any]:
    """
    Return P&L summary for a date range from Supabase.

    Args:
        start: ISO date string, e.g. "2025-01-01"
        end:   ISO date string, e.g. "2025-12-31"

    Returns:
        Aggregated P&L stats for the range
    """
    rows = _supa_get(
        "paper_trades",
        side="eq.EXIT",
        created_at=f"gte.{start}T00:00:00",
        select="trade_pnl,contract_symbol,direction,created_at",
        order="created_at.asc",
    )
    # Filter end date client-side (Supabase REST doesn't support AND easily)
    end_dt = f"{end}T23:59:59"
    rows = [r for r in rows if (r.get("created_at") or "") <= end_dt]

    realized_pnl = sum(float(r.get("trade_pnl") or 0) for r in rows)
    win_count = sum(1 for r in rows if float(r.get("trade_pnl") or 0) > 0)
    loss_count = sum(1 for r in rows if float(r.get("trade_pnl") or 0) < 0)
    return {
        "start": start,
        "end": end,
        "realized_pnl": round(realized_pnl, 2),
        "trade_count": len(rows),
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_count / len(rows) * 100, 1) if rows else 0.0,
        "avg_pnl": round(realized_pnl / len(rows), 2) if rows else 0.0,
    }


@safe_tool
def get_regime_state(asset_class: str) -> Dict[str, Any]:
    """
    Return the current market regime for an asset class or symbol.

    Reads from the regime_states table in Supabase if available.

    Args:
        asset_class: e.g. "equities", "crypto", "SPY", "BTC/USD"
    """
    try:
        query_key = "symbol"
        query_val = asset_class
        if asset_class.lower() in ("equities", "crypto"):
            query_key = "asset_class"

        params = {
            query_key: f"eq.{query_val}",
            "order": "detected_at.desc",
            "limit": 1
        }

        rows = _supa_get("regime_states", **params)
        if rows:
            row = rows[0]
            return {
                "asset_class": row.get("asset_class"),
                "regime": row.get("regime"),
                "confidence": float(row.get("regime_probability")) if row.get("regime_probability") is not None else None,
                "updated_at": row.get("detected_at"),
                "symbol": row.get("symbol"),
                "volatility": float(row.get("volatility")) if row.get("volatility") is not None else None,
                "volume_ratio": float(row.get("volume_ratio")) if row.get("volume_ratio") is not None else None,
            }
    except Exception as exc:
        log.warning(f"regime_states table not available: {exc}")

    return {
        "asset_class": asset_class,
        "regime": "unknown",
        "confidence": None,
        "updated_at": None,
        "detail": "Regime states table not available or empty",
    }


@safe_tool
def get_kelly_sizing(symbol: str) -> Dict[str, Any]:
    """
    Return Kelly Criterion sizing recommendation for a symbol.

    Reads win-rate and avg-pnl from Supabase paper_trades to compute
    a simplified Kelly fraction. Returns 0 if insufficient data.

    Args:
        symbol: Underlying symbol, e.g. "SPY"
    """
    try:
        rows = _supa_get(
            "paper_trades",
            side="eq.EXIT",
            select="trade_pnl,symbol",
        )
        sym_rows = [r for r in rows if r.get("symbol") == symbol]
    except Exception as exc:
        log.warning(f"Kelly sizing data unavailable: {exc}")
        sym_rows = []

    if len(sym_rows) < 5:
        return {
            "symbol": symbol,
            "kelly_fraction": 0.0,
            "win_rate": None,
            "avg_win": None,
            "avg_loss": None,
            "sample_size": len(sym_rows),
            "note": "Insufficient data (< 5 trades)",
        }

    wins = [float(r["trade_pnl"]) for r in sym_rows if float(r.get("trade_pnl") or 0) > 0]
    losses = [float(r["trade_pnl"]) for r in sym_rows if float(r.get("trade_pnl") or 0) < 0]
    win_rate = len(wins) / len(sym_rows)
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 1
    kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss) if avg_loss else 0
    return {
        "symbol": symbol,
        "kelly_fraction": round(max(kelly, 0), 4),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(-avg_loss, 2),
        "sample_size": len(sym_rows),
    }


@safe_tool
def get_greeks(symbol: str) -> Dict[str, Any]:
    """
    Return approximate option greeks for the current open position in `symbol`.

    Fetches the current open position from Alpaca and computes greeks
    if available. Returns stub if no open position exists.

    Args:
        symbol: Underlying symbol, e.g. "SPY"
    """
    positions = _alpaca_get("/v2/positions")
    target = next(
        (p for p in positions if p.get("symbol", "").startswith(symbol)), None
    )
    if target is None:
        return {
            "symbol": symbol,
            "position_found": False,
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
            "note": "No open position for symbol",
        }
    return {
        "symbol": symbol,
        "position_found": True,
        "contract_symbol": target.get("symbol"),
        "qty": target.get("qty"),
        "avg_entry_price": target.get("avg_entry_price"),
        "current_price": target.get("current_price"),
        "unrealized_pl": target.get("unrealized_pl"),
        # True greeks require options pricing model — stub values here
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "note": "Greeks require options pricing model integration (not yet implemented)",
    }


# ── Write stubs (require approval + not yet implemented) ──────────────────────

@requires_approval
@safe_tool
def cancel_order(order_id: str) -> OpResult:
    """
    Cancel a specific order by ID.

    NOT IMPLEMENTED — stub only. Decorated with @requires_approval so
    any call returns "pending approval" without touching the broker.

    Args:
        order_id: Alpaca order UUID
    """
    raise NotImplementedError(
        "cancel_order is not yet implemented. "
        "This stub exists to define the interface and enforce approval gating."
    )


@requires_approval
@safe_tool
def flatten_position(symbol: str) -> OpResult:
    """
    Flatten (close) all positions in `symbol` at market.

    NOT IMPLEMENTED — stub only.

    Args:
        symbol: Underlying or contract symbol to flatten
    """
    raise NotImplementedError(
        "flatten_position is not yet implemented. "
        "This stub exists to define the interface and enforce approval gating."
    )


@requires_approval
@safe_tool
def kill_switch() -> OpResult:
    """
    Emergency kill switch — flatten ALL open positions and block new orders.

    NOT IMPLEMENTED — stub only. Highest-risk operation; requires explicit
    human approval before the underlying function can be called.
    """
    raise NotImplementedError(
        "kill_switch is not yet implemented. "
        "This stub exists to define the interface and enforce approval gating. "
        "Do NOT implement without thorough review and testing."
    )
