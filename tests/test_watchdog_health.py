from datetime import datetime, timedelta, timezone

from scripts.watchdog_runner import functional_health_alerts
from src.trading.component_health import ComponentHealth, HealthRegistry, aggregate

NOW = datetime.now(timezone.utc)


def rec(name, *, success=NOW, metadata=None):
    return ComponentHealth(name, 0 if name == "trading_executor" else 1, 42, "instance", NOW.isoformat(),
        status="HEALTHY", last_heartbeat_at=NOW.isoformat(),
        last_success_at=success.isoformat() if success else None, max_staleness_seconds=60,
        metadata=metadata or {})


def test_tmux_session_with_dead_child_is_false_green(tmp_path):
    registry = HealthRegistry(tmp_path); registry.write(rec("run_agents"))
    alerts, result = functional_health_alerts(registry, required={"run_agents"}, alive=lambda _: False)
    assert result["components"]["run_agents"]["status"] == "FAILED"
    assert "WATCHDOG_FALSE_GREEN_DETECTED" in alerts[0]


def test_running_container_with_stalled_application_is_false_green(tmp_path):
    registry = HealthRegistry(tmp_path)
    registry.write(rec("trading_executor", success=NOW - timedelta(minutes=5), metadata={"container_running": True}))
    alerts, result = functional_health_alerts(registry, required={"trading_executor"}, alive=lambda _: True)
    assert result["components"]["trading_executor"]["status"] == "STALE"
    assert alerts


def test_news_process_alive_but_fetch_stale_is_not_healthy():
    result = aggregate({"news": rec("news", success=NOW - timedelta(hours=4))}, {"news"},
                       now=NOW, alive=lambda _: True)
    assert result["components"]["news"]["status"] == "STALE"


def test_failed_intermediate_stage_does_not_advance_successful_cycle():
    previous = NOW - timedelta(seconds=30)
    agent = rec("run_agents", success=previous, metadata={"cycle_id": "cycle-2", "failed_stage": "risk"})
    agent.status = "FAILED"; agent.last_failure_at = NOW.isoformat(); agent.reason = "risk stage failed"
    result = aggregate({"run_agents": agent}, {"run_agents"}, now=NOW, alive=lambda _: True)
    assert agent.last_success_at == previous.isoformat()
    assert result["components"]["run_agents"]["status"] == "FAILED"
    assert not result["entry_allowed"]


def test_watchdog_never_contains_broker_mutation_calls():
    source = open("scripts/watchdog_runner.py").read()
    for forbidden in ("submit_order(", "close_position(", "sell_to_close(", "buy_to_open("):
        assert forbidden not in source
