"""
agents/tools/__init__.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Public API for the Disrupting Alpha unified tool layer.

Every future agent imports from here, never directly from sub-modules.
__all__ makes the public surface explicit.
"""

from __future__ import annotations

# ── Shared utilities ───────────────────────────────────────────────────────────
from agents.tools._shared import (
    BotStatus,
    OpResult,
    PipelineStatus,
    ServiceStatus,
    StructuredLogger,
    load_pipelines_config,
    load_services_config,
    requires_approval,
    safe_tool,
)

# ── Ops tools ─────────────────────────────────────────────────────────────────
from agents.tools import ops_tools
from agents.tools.ops_tools import (
    list_bots,
    list_docker_containers,
    list_services,
    list_tmux_sessions,
    restart_bot,
    restart_service,
    run_health_check,
    run_start_all,
    start_service,
    stop_service,
    tail_logs,
)

# ── Pipeline tools ─────────────────────────────────────────────────────────────
from agents.tools import pipeline_tools
from agents.tools.pipeline_tools import (
    check_alpaca_rest,
    check_alpaca_ws_crypto,
    check_alpaca_ws_equities,
    check_finbert_scorer,
    check_langgraph_cycle,
    check_nats,
    check_news_collector,
    check_qdrant,
    check_questdb,
    check_supabase_cloud,
    check_supabase_local,
    check_tick_collector,
    integration_overview,
)

# ── Trading tools ─────────────────────────────────────────────────────────────
from agents.tools import trading_tools
from agents.tools.trading_tools import (
    cancel_order,
    flatten_position,
    get_account_summary,
    get_greeks,
    get_kelly_sizing,
    get_orders,
    get_pnl_range,
    get_pnl_today,
    get_positions,
    get_recent_signals,
    get_regime_state,
    kill_switch,
)

# ── Research tools ─────────────────────────────────────────────────────────────
from agents.tools import research_tools
from agents.tools.research_tools import (
    get_ic_tracking,
    get_news_summary,
    get_performance_today,
    get_regime_history,
    get_sentiment_scores,
    run_backtest,
)

__all__ = [
    # Shared
    "BotStatus",
    "OpResult",
    "PipelineStatus",
    "ServiceStatus",
    "StructuredLogger",
    "load_pipelines_config",
    "load_services_config",
    "requires_approval",
    "safe_tool",
    # Modules (for isinstance checks and direct module access)
    "ops_tools",
    "pipeline_tools",
    "trading_tools",
    "research_tools",
    # Ops
    "list_bots",
    "list_docker_containers",
    "list_services",
    "list_tmux_sessions",
    "restart_bot",
    "restart_service",
    "run_health_check",
    "run_start_all",
    "start_service",
    "stop_service",
    "tail_logs",
    # Pipeline
    "check_alpaca_rest",
    "check_alpaca_ws_crypto",
    "check_alpaca_ws_equities",
    "check_finbert_scorer",
    "check_langgraph_cycle",
    "check_nats",
    "check_news_collector",
    "check_qdrant",
    "check_questdb",
    "check_supabase_cloud",
    "check_supabase_local",
    "check_tick_collector",
    "integration_overview",
    # Trading (read)
    "get_account_summary",
    "get_greeks",
    "get_kelly_sizing",
    "get_orders",
    "get_pnl_range",
    "get_pnl_today",
    "get_positions",
    "get_recent_signals",
    "get_regime_state",
    # Trading (write stubs)
    "cancel_order",
    "flatten_position",
    "kill_switch",
    # Research (implemented)
    "get_news_summary",
    "get_performance_today",
    "get_regime_history",
    "get_sentiment_scores",
    # Research (stubs)
    "get_ic_tracking",
    "run_backtest",
]
