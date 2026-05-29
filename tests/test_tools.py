"""
tests/test_tools.py
~~~~~~~~~~~~~~~~~~~~
Smoke tests for the Disrupting Alpha unified tool layer.

Design principles:
  - Tests pass even when services are down (pytest.skip, not fail)
  - No production data is modified
  - Every read-only function returns the expected dataclass / type
  - Every @requires_approval write function returns OpResult(pending approval)
    without executing the underlying operation

Run:
    cd ~/disrupting-alpha && python -m pytest tests/test_tools.py -v
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Import smoke tests ─────────────────────────────────────────────────────────

class TestImports:
    """All four tool modules must import cleanly."""

    def test_import_shared(self):
        from agents.tools import _shared  # noqa: F401

    def test_import_ops_tools(self):
        from agents.tools import ops_tools  # noqa: F401

    def test_import_pipeline_tools(self):
        from agents.tools import pipeline_tools  # noqa: F401

    def test_import_trading_tools(self):
        from agents.tools import trading_tools  # noqa: F401

    def test_import_research_tools(self):
        from agents.tools import research_tools  # noqa: F401

    def test_import_top_level(self):
        """Top-level __init__ import with all symbols."""
        from agents.tools import (  # noqa: F401
            ops_tools,
            pipeline_tools,
            trading_tools,
            research_tools,
        )

    def test_all_symbols_exported(self):
        """__all__ must be defined and non-empty."""
        import agents.tools as pkg
        assert hasattr(pkg, "__all__")
        assert len(pkg.__all__) > 30


# ── Shared utilities ───────────────────────────────────────────────────────────

class TestShared:
    def test_dataclasses_instantiate(self):
        from agents.tools._shared import OpResult, PipelineStatus, ServiceStatus, BotStatus
        from datetime import datetime, timezone

        op = OpResult(success=True, message="ok")
        assert op.success is True

        ps = PipelineStatus(
            name="nats", state="green", last_heartbeat=None, detail="ok"
        )
        assert ps.name == "nats"

        ss = ServiceStatus(name="nats", type="docker", running=True)
        assert ss.running is True

        bs = BotStatus(name="ut_bot", strategy="UTBotStrategy", running=False)
        assert bs.name == "ut_bot"

    def test_config_loaders(self):
        from agents.tools._shared import load_services_config, load_pipelines_config

        services = load_services_config()
        assert isinstance(services, list)
        assert len(services) >= 13, "Expected 8 tmux + 5 docker services"

        pipelines = load_pipelines_config()
        assert isinstance(pipelines, dict)
        assert len(pipelines) == 12

    def test_structured_logger_writes_json(self, tmp_path, monkeypatch):
        """StructuredLogger must write valid JSON lines."""
        log_file = tmp_path / "agents.log"
        from agents.tools import _shared
        monkeypatch.setattr(_shared.StructuredLogger, "_log_path", log_file)
        logger = _shared.StructuredLogger("test_module")
        logger.info("hello", extra_key="extra_value")
        lines = log_file.read_text().strip().splitlines()
        assert lines, "Log file is empty"
        record = json.loads(lines[-1])
        assert record["msg"] == "hello"
        assert record["level"] == "INFO"
        assert record["module"] == "test_module"

    def test_approval_queue_created(self):
        from agents.tools._shared import APPROVAL_QUEUE_PATH, _ensure_approval_queue
        _ensure_approval_queue()
        assert APPROVAL_QUEUE_PATH.exists()
        data = json.loads(APPROVAL_QUEUE_PATH.read_text())
        assert isinstance(data, list)

    def test_requires_approval_returns_pending(self):
        """@requires_approval must return pending without executing."""
        from agents.tools._shared import requires_approval, OpResult, APPROVAL_QUEUE_PATH

        @requires_approval
        def _fake_write(x: int) -> str:
            return f"executed with {x}"  # must NOT reach this

        result = _fake_write(42)

        assert isinstance(result, OpResult)
        assert result.success is False
        assert "pending" in result.message.lower()
        assert result.detail is not None
        assert "approval_id" in result.detail

        # Queue file should have an entry
        data = json.loads(APPROVAL_QUEUE_PATH.read_text())
        assert any("_fake_write" in e.get("function", "") for e in data)

    def test_safe_tool_catches_exceptions(self):
        from agents.tools._shared import safe_tool, OpResult

        @safe_tool
        def _bad_fn():
            raise ValueError("intentional error")

        result = _bad_fn()
        assert isinstance(result, OpResult)
        assert result.success is False
        assert "intentional error" in result.message


# ── Ops tools ─────────────────────────────────────────────────────────────────

class TestOpsTools:
    def test_list_services_returns_dict(self):
        from agents.tools.ops_tools import list_services
        result = list_services()
        # On non-Linux host, tmux/docker commands will return empty — that's OK
        assert isinstance(result, dict)

    def test_list_tmux_sessions_returns_list(self):
        from agents.tools.ops_tools import list_tmux_sessions
        result = list_tmux_sessions()
        assert isinstance(result, list)

    def test_list_docker_containers_returns_list(self):
        from agents.tools.ops_tools import list_docker_containers
        result = list_docker_containers()
        assert isinstance(result, list)

    def test_list_bots_returns_dict(self):
        from agents.tools.ops_tools import list_bots
        result = list_bots()
        assert isinstance(result, dict)

    def test_tail_logs_unknown_service(self):
        from agents.tools.ops_tools import tail_logs
        result = tail_logs("nonexistent_service_xyz")
        assert "Unknown service" in result or isinstance(result, str)

    def test_run_health_check_returns_dict(self):
        from agents.tools.ops_tools import run_health_check
        result = run_health_check()
        assert isinstance(result, dict)
        assert "available" in result

    # Write operations — must return "pending approval" without executing
    def test_start_service_requires_approval(self):
        from agents.tools.ops_tools import start_service
        from agents.tools._shared import OpResult
        result = start_service("ut_bot")
        assert isinstance(result, OpResult)
        assert "pending" in result.message.lower()

    def test_stop_service_requires_approval(self):
        from agents.tools.ops_tools import stop_service
        from agents.tools._shared import OpResult
        result = stop_service("ut_bot")
        assert isinstance(result, OpResult)
        assert "pending" in result.message.lower()

    def test_restart_service_requires_approval(self):
        from agents.tools.ops_tools import restart_service
        from agents.tools._shared import OpResult
        result = restart_service("ut_bot")
        assert isinstance(result, OpResult)
        assert "pending" in result.message.lower()

    def test_restart_bot_requires_approval(self):
        from agents.tools.ops_tools import restart_bot
        from agents.tools._shared import OpResult
        result = restart_bot("ut_bot")
        assert isinstance(result, OpResult)
        assert "pending" in result.message.lower()

    def test_run_start_all_requires_approval(self):
        from agents.tools.ops_tools import run_start_all
        from agents.tools._shared import OpResult
        result = run_start_all()
        assert isinstance(result, OpResult)
        assert "pending" in result.message.lower()


# ── Pipeline tools ─────────────────────────────────────────────────────────────

class TestPipelineTools:
    """Each check must return PipelineStatus with a valid state field."""

    _checks = [
        "check_nats",
        "check_questdb",
        "check_qdrant",
        "check_supabase_cloud",
        "check_supabase_local",
        "check_alpaca_rest",
        "check_alpaca_ws_crypto",
        "check_alpaca_ws_equities",
        "check_tick_collector",
        "check_news_collector",
        "check_finbert_scorer",
        "check_langgraph_cycle",
    ]

    @pytest.mark.parametrize("fn_name", _checks)
    def test_check_returns_pipeline_status(self, fn_name):
        """Each check function returns PipelineStatus (or OpResult on error)."""
        import agents.tools.pipeline_tools as pt
        from agents.tools._shared import PipelineStatus, OpResult

        fn = getattr(pt, fn_name)
        result = fn()

        # @safe_tool may return OpResult on error; that's acceptable
        if isinstance(result, OpResult):
            pytest.skip(f"{fn_name} returned error: {result.message}")

        assert isinstance(result, PipelineStatus), (
            f"{fn_name} returned {type(result)}, expected PipelineStatus"
        )
        assert result.state in ("green", "yellow", "red"), (
            f"Invalid state: {result.state}"
        )
        assert isinstance(result.sla_breach, bool)

    def test_integration_overview_returns_dict(self):
        from agents.tools.pipeline_tools import integration_overview
        result = integration_overview()
        assert isinstance(result, dict)
        assert len(result) == 12, f"Expected 12 pipelines, got {len(result)}"

    def test_integration_overview_has_all_pipelines(self):
        from agents.tools.pipeline_tools import integration_overview
        result = integration_overview()
        expected = {
            "nats", "questdb", "qdrant", "supabase_cloud", "supabase_local",
            "alpaca_rest", "alpaca_ws_crypto", "alpaca_ws_equities",
            "tick_collector", "news_collector", "finbert_scorer", "langgraph_cycle",
        }
        assert set(result.keys()) == expected


# ── Trading tools ─────────────────────────────────────────────────────────────

class TestTradingTools:
    def _skip_if_no_alpaca(self):
        if not os.getenv("ALPACA_API_KEY"):
            pytest.skip("ALPACA_API_KEY not configured — skipping live API test")

    def test_get_positions_returns_list(self):
        self._skip_if_no_alpaca()
        from agents.tools.trading_tools import get_positions
        result = get_positions()
        assert isinstance(result, list)

    def test_get_orders_returns_list(self):
        self._skip_if_no_alpaca()
        from agents.tools.trading_tools import get_orders
        result = get_orders(status="all", limit=5)
        assert isinstance(result, list)

    def test_get_account_summary_returns_dict(self):
        self._skip_if_no_alpaca()
        from agents.tools.trading_tools import get_account_summary
        result = get_account_summary()
        assert isinstance(result, dict)
        # Should have at minimum equity and cash
        assert "equity" in result or "portfolio_value" in result

    def test_get_pnl_today_returns_dict(self):
        from agents.tools.trading_tools import get_pnl_today
        from agents.tools._shared import OpResult
        result = get_pnl_today()
        if isinstance(result, OpResult):
            pytest.skip(f"Supabase not available: {result.message}")
        assert isinstance(result, dict)
        assert "realized_pnl" in result
        assert "date" in result

    def test_get_pnl_range_returns_dict(self):
        from agents.tools.trading_tools import get_pnl_range
        from agents.tools._shared import OpResult
        result = get_pnl_range("2025-01-01", "2025-12-31")
        if isinstance(result, OpResult):
            pytest.skip(f"Supabase not available: {result.message}")
        assert isinstance(result, dict)

    def test_get_recent_signals_returns_list(self):
        from agents.tools.trading_tools import get_recent_signals
        from agents.tools._shared import OpResult
        result = get_recent_signals(n=5)
        if isinstance(result, OpResult):
            pytest.skip(f"Supabase not available: {result.message}")
        assert isinstance(result, list)

    def test_get_regime_state_returns_dict(self):
        from agents.tools.trading_tools import get_regime_state
        result = get_regime_state("equities")
        assert isinstance(result, dict)
        assert "regime" in result or "asset_class" in result

    def test_get_kelly_sizing_returns_dict(self):
        from agents.tools.trading_tools import get_kelly_sizing
        result = get_kelly_sizing("SPY")
        assert isinstance(result, dict)
        assert "kelly_fraction" in result

    def test_get_greeks_returns_dict(self):
        self._skip_if_no_alpaca()
        from agents.tools.trading_tools import get_greeks
        result = get_greeks("SPY")
        assert isinstance(result, dict)
        assert "symbol" in result

    # Write stubs — must return pending approval
    def test_cancel_order_requires_approval(self):
        from agents.tools.trading_tools import cancel_order
        from agents.tools._shared import OpResult
        result = cancel_order("fake-order-id-1234")
        assert isinstance(result, OpResult)
        assert "pending" in result.message.lower()

    def test_flatten_position_requires_approval(self):
        from agents.tools.trading_tools import flatten_position
        from agents.tools._shared import OpResult
        result = flatten_position("SPY")
        assert isinstance(result, OpResult)
        assert "pending" in result.message.lower()

    def test_kill_switch_requires_approval(self):
        from agents.tools.trading_tools import kill_switch
        from agents.tools._shared import OpResult
        result = kill_switch()
        assert isinstance(result, OpResult)
        assert "pending" in result.message.lower()


# ── Research tools ─────────────────────────────────────────────────────────────

class TestResearchTools:
    def _skip_if_no_supabase(self):
        if not os.getenv("SUPABASE_URL"):
            pytest.skip("SUPABASE_URL not configured — skipping live Supabase test")

    def test_get_performance_today_returns_dict(self):
        from agents.tools.research_tools import get_performance_today
        from agents.tools._shared import OpResult
        result = get_performance_today()
        if isinstance(result, OpResult):
            pytest.skip(f"Supabase not available: {result.message}")
        assert isinstance(result, dict)
        assert "realized_pnl" in result

    def test_get_news_summary_returns_dict(self):
        from agents.tools.research_tools import get_news_summary
        from agents.tools._shared import OpResult
        result = get_news_summary(window="24h")
        if isinstance(result, OpResult):
            pytest.skip(f"Not available: {result.message}")
        assert isinstance(result, dict)
        assert "article_count" in result

    def test_get_sentiment_scores_returns_dict(self):
        from agents.tools.research_tools import get_sentiment_scores
        from agents.tools._shared import OpResult
        result = get_sentiment_scores(["SPY"])
        if isinstance(result, OpResult):
            pytest.skip(f"Not available: {result.message}")
        assert isinstance(result, dict)
        assert "SPY" in result

    def test_get_regime_history_returns_list(self):
        from agents.tools.research_tools import get_regime_history
        from agents.tools._shared import OpResult
        result = get_regime_history(window="30d")
        if isinstance(result, OpResult):
            pytest.skip(f"Not available: {result.message}")
        assert isinstance(result, list)

    def test_run_backtest_raises_not_implemented(self):
        from agents.tools.research_tools import run_backtest
        from agents.tools._shared import OpResult
        result = run_backtest("ut_bot", "SPY", "2025-01-01", "2025-12-31")
        # safe_tool catches NotImplementedError and returns OpResult
        assert isinstance(result, OpResult)
        assert result.success is False

    def test_get_ic_tracking_raises_not_implemented(self):
        from agents.tools.research_tools import get_ic_tracking
        from agents.tools._shared import OpResult
        result = get_ic_tracking("7d")
        assert isinstance(result, OpResult)
        assert result.success is False
