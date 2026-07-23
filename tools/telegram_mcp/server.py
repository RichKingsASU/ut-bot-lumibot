#!/usr/bin/env python3
"""
tools/telegram_mcp/server.py — read-only stdio MCP server for telegram_outbox.

Exposes three READ-ONLY tools over the Model Context Protocol (stdio / JSON-RPC
2.0, newline-delimited), backed by the Supabase `telegram_outbox` audit table:

    get_recent_reports(limit=10, message_type=None)
    get_reports_since(iso_timestamp)
    get_outbox_health()

Design constraints (deliberate):
  * READ ONLY. There are no write tools, no send tool, and no calls to the
    Telegram API whatsoever. This server only reads Supabase.
  * Dependencies: Python standard library + httpx. Nothing else.
  * Credentials come from the environment. SUPABASE_URL plus either
    SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY (migration in progress).
    Keys are never logged, echoed, or hardcoded.

Run:
    python3 tools/telegram_mcp/server.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from common.supabase_auth import get_supabase_headers
from datetime import datetime, timedelta, timezone

import httpx

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "telegram-outbox"
SERVER_VERSION = "1.0.0"
TABLE = "telegram_outbox"

# ── Supabase REST helpers ────────────────────────────────────────────────────


def _creds():
    """Return (url, key) from the environment or raise a clear error.

    Accepts either SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY. The key
    itself is never included in any error message or log line.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    if not key:
        raise RuntimeError(
            "Supabase key is not set (SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY)"
        )
    return url.rstrip("/"), key


def _headers(key: str, extra: dict | None = None) -> dict:
    h = get_supabase_headers(key, {"Accept": "application/json"})
    if extra:
        h.update(extra)
    return h


def _get(params: dict, extra_headers: dict | None = None):
    """GET rows from the telegram_outbox table. Returns (json_body, response)."""
    url, key = _creds()
    resp = httpx.get(
        f"{url}/rest/v1/{TABLE}",
        headers=_headers(key, extra_headers),
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp


def _count_since(iso_ts: str, only_failed: bool = False) -> int:
    """Exact row count with sent_at >= iso_ts, via the Content-Range header."""
    params = {"select": "id", "sent_at": f"gte.{iso_ts}"}
    if only_failed:
        params["send_ok"] = "eq.false"
    resp = _get(params, {"Prefer": "count=exact", "Range": "0-0"})
    content_range = resp.headers.get("content-range", "*/0")
    total = content_range.split("/")[-1]
    try:
        return int(total)
    except (TypeError, ValueError):
        return 0


# ── Tool implementations (all read-only) ─────────────────────────────────────


def tool_get_recent_reports(limit: int = 10, message_type=None) -> dict:
    """Return the most recent outbox rows, newest first."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 200))
    params = {
        "select": "*",
        "order": "sent_at.desc",
        "limit": str(limit),
    }
    if message_type:
        params["message_type"] = f"eq.{message_type}"
    rows = _get(params).json()
    return {"count": len(rows), "rows": rows}


def tool_get_reports_since(iso_timestamp: str) -> dict:
    """Return outbox rows with sent_at >= iso_timestamp, newest first."""
    if not iso_timestamp:
        raise ValueError("iso_timestamp is required")
    params = {
        "select": "*",
        "sent_at": f"gte.{iso_timestamp}",
        "order": "sent_at.desc",
    }
    rows = _get(params).json()
    return {"since": iso_timestamp, "count": len(rows), "rows": rows}


def tool_get_outbox_health() -> dict:
    """Summarize outbox freshness: newest row, its age, 24h volume, 24h failures."""
    now = datetime.now(timezone.utc)
    since_24h = (now - timedelta(hours=24)).isoformat()

    newest_rows = _get(
        {"select": "sent_at", "order": "sent_at.desc", "limit": "1"}
    ).json()
    newest_sent_at = newest_rows[0]["sent_at"] if newest_rows else None

    age_seconds = None
    if newest_sent_at:
        try:
            parsed = datetime.fromisoformat(newest_sent_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_seconds = (now - parsed).total_seconds()
        except (TypeError, ValueError):
            age_seconds = None

    return {
        "newest_sent_at": newest_sent_at,
        "age_seconds": age_seconds,
        "count_24h": _count_since(since_24h),
        "failed_send_count_24h": _count_since(since_24h, only_failed=True),
        "checked_at": now.isoformat(),
    }


# ── MCP tool registry ────────────────────────────────────────────────────────

TOOLS = {
    "get_recent_reports": {
        "description": (
            "Return the most recent telegram_outbox rows (newest first). "
            "Optionally filter by message_type ('cycle_report' | 'alert' | 'other')."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (1-200).",
                    "default": 10,
                },
                "message_type": {
                    "type": ["string", "null"],
                    "description": "Optional message_type filter.",
                    "default": None,
                },
            },
            "additionalProperties": False,
        },
        "handler": lambda a: tool_get_recent_reports(
            a.get("limit", 10), a.get("message_type")
        ),
    },
    "get_reports_since": {
        "description": (
            "Return telegram_outbox rows with sent_at >= the given ISO 8601 "
            "timestamp (newest first)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "iso_timestamp": {
                    "type": "string",
                    "description": "ISO 8601 timestamp lower bound, e.g. 2026-07-23T00:00:00Z.",
                },
            },
            "required": ["iso_timestamp"],
            "additionalProperties": False,
        },
        "handler": lambda a: tool_get_reports_since(a.get("iso_timestamp")),
    },
    "get_outbox_health": {
        "description": (
            "Outbox freshness summary: newest sent_at, its age in seconds, the "
            "number of rows in the last 24h, and the number of failed sends in "
            "the last 24h."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "handler": lambda a: tool_get_outbox_health(),
    },
}


# ── JSON-RPC / MCP plumbing ──────────────────────────────────────────────────


def _result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _handle(request: dict):
    """Dispatch a single JSON-RPC request. Returns a response dict or None."""
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method in ("notifications/initialized", "initialized"):
        return None  # notification, no response

    if method == "ping":
        return _result(request_id, {})

    if method == "tools/list":
        tools = [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            }
            for name, spec in TOOLS.items()
        ]
        return _result(request_id, {"tools": tools})

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        spec = TOOLS.get(name)
        if spec is None:
            return _error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = spec["handler"](arguments)
            return _result(
                request_id,
                {
                    "content": [
                        {"type": "text", "text": json.dumps(payload, indent=2, default=str)}
                    ]
                },
            )
        except Exception as e:
            return _result(
                request_id,
                {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                },
            )

    if request_id is None:
        return None  # unknown notification — ignore
    return _error(request_id, -32601, f"Method not found: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
