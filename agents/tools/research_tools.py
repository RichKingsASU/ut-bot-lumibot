"""
agents/tools/research_tools.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Research and analytics tools.

Partially implemented — functions that can be built from existing
Supabase data are implemented; others are stubbed with NotImplementedError.

Python ≤ 3.11 compatible.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from agents.tools._shared import (
    StructuredLogger,
    safe_tool,
)

log = StructuredLogger("research_tools")


# ── Supabase helpers (local to this module) ────────────────────────────────────

def _supa_headers() -> Dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _supa_get(table: str, **params) -> List[Dict]:
    url_base = os.getenv("SUPABASE_URL", "")
    if not url_base:
        return []
    url = f"{url_base}/rest/v1/{table}"
    resp = requests.get(url, headers=_supa_headers(), params=params, timeout=5)
    resp.raise_for_status()
    return resp.json()


def _parse_window(window: str) -> str:
    """
    Convert a window string like '24h', '7d', '30d' to an ISO8601 datetime
    for use in Supabase `gte` filters.
    """
    now = datetime.now(timezone.utc)
    if window.endswith("h"):
        delta = timedelta(hours=int(window[:-1]))
    elif window.endswith("d"):
        delta = timedelta(days=int(window[:-1]))
    elif window.endswith("w"):
        delta = timedelta(weeks=int(window[:-1]))
    else:
        delta = timedelta(hours=24)
    return (now - delta).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── Implemented functions ──────────────────────────────────────────────────────

@safe_tool
def get_performance_today() -> Dict[str, Any]:
    """
    Return a full performance summary for today.

    Aggregates from Supabase paper_trades (EXIT rows from today).

    Returns:
        Dict with realized_pnl, trade_count, win_rate, avg_trade, best_trade,
        worst_trade, sharpe (approx), and individual trade list.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = _supa_get(
        "paper_trades",
        side="eq.EXIT",
        created_at=f"gte.{today}T00:00:00",
        select="trade_pnl,contract_symbol,direction,exit_reason,created_at",
        order="created_at.asc",
    )

    pnls = [float(r.get("trade_pnl") or 0) for r in rows]
    realized_pnl = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    # Approx Sharpe (daily, no risk-free rate)
    import statistics
    sharpe = None
    if len(pnls) >= 2:
        try:
            mu = statistics.mean(pnls)
            sigma = statistics.stdev(pnls)
            sharpe = round(mu / sigma, 3) if sigma > 0 else None
        except Exception:
            pass

    return {
        "date": today,
        "realized_pnl": round(realized_pnl, 2),
        "trade_count": len(pnls),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0,
        "avg_trade": round(realized_pnl / len(pnls), 2) if pnls else 0.0,
        "best_trade": round(max(pnls), 2) if pnls else 0.0,
        "worst_trade": round(min(pnls), 2) if pnls else 0.0,
        "sharpe_approx": sharpe,
        "trades": rows,
    }


@safe_tool
def get_news_summary(
    window: str = "24h",
    symbols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Return a summary of recent news articles from Supabase.

    Args:
        window:  Lookback window, e.g. "24h", "7d"
        symbols: Optional list of symbols to filter by (e.g. ["SPY", "QQQ"])

    Returns:
        Dict with article_count, top_articles, symbols_covered, avg_sentiment
    """
    since = _parse_window(window)
    params: Dict[str, Any] = {
        "created_at": f"gte.{since}",
        "select": "title,source,url,published_at,sentiment_score,summary",
        "order": "published_at.desc",
        "limit": 50,
    }

    try:
        rows = _supa_get("news_articles", **params)
        for r in rows:
            if "title" in r:
                r["headline"] = r["title"]
    except Exception as exc:
        log.warning(f"news_articles table not available: {exc}")
        rows = []

    # Client-side symbol filter
    if symbols and rows:
        sym_set = {s.upper() for s in symbols}
        rows = [
            r for r in rows
            if any(s in f"{r.get('title') or ''} {r.get('summary') or ''}".upper() for s in sym_set)
        ]

    sentiments = [
        float(r["sentiment_score"])
        for r in rows
        if r.get("sentiment_score") is not None
    ]

    return {
        "window": window,
        "symbols_filter": symbols,
        "article_count": len(rows),
        "avg_sentiment": round(sum(sentiments) / len(sentiments), 4) if sentiments else None,
        "top_articles": rows[:10],
    }


@safe_tool
def get_sentiment_scores(symbols: List[str]) -> Dict[str, Any]:
    """
    Return the latest FinBERT sentiment scores for a list of symbols.

    Reads from the sentiment_scores table in Supabase.

    Args:
        symbols: List of ticker symbols, e.g. ["SPY", "QQQ"]

    Returns:
        Dict mapping symbol → { score, label, article_count, updated_at }
    """
    result: Dict[str, Any] = {}
    for sym in symbols:
        try:
            rows = _supa_get(
                "sentiment_scores",
                symbol=f"eq.{sym.upper()}",
                order="updated_at.desc",
                limit=1,
            )
            if rows:
                result[sym] = rows[0]
            else:
                result[sym] = {
                    "symbol": sym,
                    "score": None,
                    "label": None,
                    "updated_at": None,
                    "note": "No sentiment data available",
                }
        except Exception as exc:
            log.warning(f"sentiment_scores unavailable for {sym}: {exc}")
            result[sym] = {
                "symbol": sym,
                "score": None,
                "label": None,
                "updated_at": None,
                "note": f"Error: {exc}",
            }
    return result


@safe_tool
def get_regime_history(window: str = "30d") -> List[Dict[str, Any]]:
    """
    Return regime state history over a time window.

    Args:
        window: Lookback window, e.g. "30d", "7d"

    Returns:
        List of regime state records ordered by updated_at desc
    """
    since = _parse_window(window)
    try:
        rows = _supa_get(
            "regime_state",
            updated_at=f"gte.{since}",
            order="updated_at.desc",
            limit=200,
        )
        return rows
    except Exception as exc:
        log.warning(f"regime_state table not available: {exc}")
        return []


# ── Stubs (not yet implemented) ────────────────────────────────────────────────

@safe_tool
def run_backtest(
    strategy: str,
    symbol: str,
    start: str,
    end: str,
) -> Dict[str, Any]:
    """
    Run a historical backtest for a given strategy and symbol.

    NOT IMPLEMENTED — requires backtest engine integration.

    Args:
        strategy: Strategy name, e.g. "ut_bot"
        symbol:   Underlying symbol, e.g. "SPY"
        start:    ISO date string, e.g. "2024-01-01"
        end:      ISO date string, e.g. "2024-12-31"
    """
    raise NotImplementedError(
        "run_backtest is not yet implemented. "
        "Requires integration with the backtest engine (run_backtest.py)."
    )


@safe_tool
def get_ic_tracking(window: str = "7d") -> Dict[str, Any]:
    """
    Return Information Coefficient (IC) tracking stats for signals.

    NOT IMPLEMENTED — requires signal vs. outcome correlation table.

    Args:
        window: Rolling window, e.g. "7d", "30d"
    """
    raise NotImplementedError(
        "get_ic_tracking is not yet implemented. "
        "Requires the ic_tracking table or signal correlation pipeline."
    )
