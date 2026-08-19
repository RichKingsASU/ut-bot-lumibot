from datetime import datetime, timedelta, timezone

from src.trading.component_health import (
    ComponentHealth, ComponentReporter, Criticality, HealthRegistry, HealthStatus,
    aggregate, broker_capability_health, evaluate,
)

NOW = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)


def record(name="run_agents", *, tier=1, pid=123, heartbeat=NOW, success=NOW,
           status="HEALTHY", stale=60, instance="current", metadata=None):
    return ComponentHealth(name, tier, pid, instance, (NOW - timedelta(hours=1)).isoformat(),
        status=status, last_heartbeat_at=heartbeat.isoformat() if heartbeat else None,
        last_success_at=success.isoformat() if success else None,
        max_staleness_seconds=stale, reason="useful work completed", metadata=metadata or {})


def test_fresh_main_does_not_mask_dead_agents():
    result = aggregate({"main": record("main", tier=0), "run_agents": record(pid=999)},
                       {"main", "run_agents"}, now=NOW, alive=lambda pid: pid != 999)
    assert result["status"] == "NOT_READY"
    assert not result["entry_allowed"]
    assert result["components"]["run_agents"]["status"] == "FAILED"


def test_alive_agent_without_completed_cycle_is_stale():
    result = evaluate(record(success=None), now=NOW, alive=lambda _: True)
    assert result["status"] == "STALE"
    assert result["reason"] == "useful work stale"


def test_fresh_heartbeat_cannot_mask_stale_work():
    result = evaluate(record(success=NOW - timedelta(minutes=5)), now=NOW, alive=lambda _: True)
    assert result["heartbeat_age_seconds"] == 0
    assert result["status"] == "STALE"


def test_old_file_from_dead_or_previous_instance_fails():
    old = record(instance="old")
    assert evaluate(old, now=NOW, expected_instance_id="new", alive=lambda _: True)["status"] == "FAILED"
    assert evaluate(old, now=NOW, alive=lambda _: False)["status"] == "FAILED"


def test_atomic_registry_and_telemetry_failure_is_nonfatal(tmp_path):
    registry = HealthRegistry(tmp_path)
    assert registry.write(record())
    assert registry.read("run_agents").instance_id == "current"
    assert oct(registry.path("run_agents").stat().st_mode & 0o777) == "0o640"
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("x")
    assert not HealthRegistry(blocked).write(record())


def test_component_recovery_emits_current_success(tmp_path, caplog):
    caplog.set_level("INFO")
    reporter = ComponentReporter("agents", Criticality.TIER_1, registry=HealthRegistry(tmp_path),
                                 process_id=123, max_staleness_seconds=60)
    reporter.work_failed("timeout")
    reporter.record.status = "STALE"
    reporter.work_succeeded("cycle-2")
    current = evaluate(reporter.record, alive=lambda _: True)
    assert current["status"] == "HEALTHY"
    assert "COMPONENT_RECOVERED" in caplog.text


def test_market_closed_suppresses_equity_output_staleness_only():
    equity = record("market_data", tier=0, success=NOW - timedelta(hours=8))
    assert evaluate(equity, now=NOW, alive=lambda _: True, work_expected=False)["status"] == "HEALTHY"
    assert evaluate(equity, now=NOW, alive=lambda _: True, work_expected=True)["status"] == "STALE"


def test_crypto_is_continuous_and_connected_without_data_is_stale():
    crypto = record("crypto_market_data", tier=0, success=None, metadata={"connected": True})
    assert evaluate(crypto, now=NOW, alive=lambda _: True, work_expected=True)["status"] == "STALE"


def test_broker_health_requires_each_capability_not_just_account():
    status, reason = broker_capability_health(
        {"account_rest": True, "positions_rest": True, "orders_rest": False},
        {"account_rest", "positions_rest", "orders_rest"})
    assert status is HealthStatus.FAILED
    assert "orders_rest" in reason


def test_optional_telemetry_failure_degrades_without_blocking_core():
    records = {"executor": record("executor", tier=0), "telegram": record("telegram", tier=2, pid=999)}
    result = aggregate(records, {"executor"}, now=NOW, alive=lambda pid: pid != 999)
    assert result["status"] == "DEGRADED"
    assert result["entry_allowed"]
