from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest

from src.trading.execution_lease import ExecutionLease, install_execution_lease
from src.trading.kill_flatten import (KillFlattenWorkflow, KillReason, KillState,
                                      KillStore, session_times)


def order(oid="o1", intent="e", status="new", qty=4, filled=0):
    return {"id": oid, "client_order_id": f"da-utbot-20260819-{intent}-0123456789ab-01",
            "symbol": "SPYOPT", "side": "buy" if intent == "e" else "sell",
            "qty": str(qty), "filled_qty": str(filled), "status": status}


class Broker:
    def __init__(self, qty=0, orders=None, fills=None, reject=0, unavailable=0):
        self.qty, self._orders = qty, list(orders or [])
        self.fills, self.reject, self.unavailable = list(fills or []), reject, unavailable
        self.submitted, self.canceled = [], []

    def positions(self):
        if self.unavailable:
            self.unavailable -= 1; raise ConnectionError("broker unavailable")
        return [] if self.qty == 0 else [{"symbol": "SPYOPT", "qty": str(self.qty), "side": "long"}]

    def orders(self): return list(self._orders)
    def cancel(self, oid):
        self.canceled.append(oid)
        for item in self._orders:
            if item["id"] == oid: item["status"] = "canceled"
    def order(self, oid): return next(item for item in self._orders if item["id"] == oid)
    def submit(self, payload):
        self.submitted.append(payload)
        if self.reject:
            self.reject -= 1; return {"id": f"f{len(self.submitted)}", "status": "rejected"}
        self.qty = self.fills.pop(0) if self.fills else 0
        return {"id": f"f{len(self.submitted)}", "status": "filled"}


@pytest.fixture
def authority(tmp_path):
    lease = ExecutionLease("acct", "paper", runtime_dir=tmp_path / "lease").acquire()
    install_execution_lease(lease)
    yield lease
    install_execution_lease(None); lease.release()


def workflow(tmp_path, broker, attempts=4):
    store = KillStore(tmp_path / "state/trading-disabled", tmp_path / "run/trading-disabled",
                      tmp_path / "state/enable-request")
    return KillFlattenWorkflow(broker, store, max_attempts=attempts, retry_seconds=0, sleep=lambda _: None)


def test_kill_while_flat_is_only_confirmed_by_broker(tmp_path, authority):
    flow = workflow(tmp_path, Broker())
    flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT
    assert flow.health()["kill_active"] and not flow.health()["flatten_required"]


def test_kill_with_position_uses_broker_quantity(tmp_path, authority):
    broker = Broker(qty=4)
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT
    assert broker.submitted[0]["qty"] == "4.0"


@pytest.mark.parametrize("pending", [order(), order(status="partially_filled", filled=2)])
def test_pending_and_partially_filled_entry_canceled_then_flattened(tmp_path, authority, pending):
    broker = Broker(qty=2 if pending["status"] == "partially_filled" else 0, orders=[pending])
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT
    assert broker.canceled == ["o1"]


def test_pending_exit_is_not_blindly_canceled(tmp_path, authority):
    broker = Broker(orders=[order(intent="x")])
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT
    assert broker.canceled == []


def test_cancel_fill_race_reconciles_resulting_position(tmp_path, authority):
    broker = Broker(orders=[order()])
    original = broker.cancel
    def race(oid): original(oid); broker.qty = 1
    broker.cancel = race
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT and broker.submitted[0]["qty"] == "1.0"


def test_partial_flatten_continues_with_remaining_broker_qty(tmp_path, authority):
    broker = Broker(qty=4, fills=[2, 0])
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT
    assert [x["qty"] for x in broker.submitted] == ["4.0", "2.0"]


def test_rejection_reconciles_and_retries(tmp_path, authority):
    broker = Broker(qty=1, reject=1)
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT and len(broker.submitted) == 2


def test_repeated_failure_stays_killed(tmp_path, authority):
    broker = Broker(qty=1, reject=9)
    flow = workflow(tmp_path, broker, attempts=2); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILL_FAILED
    assert flow.store.active and flow.health()["kill_active"]


def test_broker_unavailable_is_not_flat(tmp_path, authority):
    broker = Broker(qty=1, unavailable=1)
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT
    assert flow.record.attempts == 2


def test_no_lease_prevents_mutation_and_fails_closed(tmp_path):
    broker = Broker(qty=1)
    flow = workflow(tmp_path, broker, attempts=1); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILL_FAILED and broker.submitted == []


def test_durable_restart_resumes_partial_flatten(tmp_path, authority):
    broker = Broker(qty=4, fills=[2])
    first = workflow(tmp_path, broker, attempts=1); first.request(KillReason.EMERGENCY_KILL)
    assert first.run() is KillState.KILL_FAILED and broker.qty == 2
    second = workflow(tmp_path, broker, attempts=3); second.recover()
    assert second.run() is KillState.KILLED_FLAT


def test_explicit_enable_requires_verified_flat(tmp_path, authority):
    broker = Broker()
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL); flow.run()
    flow.store.enable_request.parent.mkdir(parents=True, exist_ok=True)
    flow.store.enable_request.touch()
    assert flow.process_enable_request() and not flow.store.active


def test_invalid_enable_fails_and_keeps_interlock(tmp_path, authority):
    broker = Broker(qty=1)
    flow = workflow(tmp_path, broker); flow.request(KillReason.EMERGENCY_KILL)
    flow.store.enable_request.touch()
    with pytest.raises(RuntimeError): flow.process_enable_request()
    assert flow.store.active


class Calendar:
    def __init__(self, close=None, error=False): self.close, self.error = close, error
    def schedule(self, **_):
        if self.error: raise RuntimeError("calendar down")
        if self.close is None: return Schedule(None)
        return Schedule(datetime.fromisoformat(self.close))

class Stamp:
    def __init__(self, value): self.value = value
    def to_pydatetime(self): return self.value
class Row:
    def __init__(self, value): self.value = value
    def __getitem__(self, _): return Stamp(self.value)
class ILoc:
    def __init__(self, value): self.value = value
    def __getitem__(self, _): return Row(self.value)
class Schedule:
    def __init__(self, value): self.value = value; self.iloc = ILoc(value)
    @property
    def empty(self): return self.value is None


@pytest.mark.parametrize("close,cutoff,flatten", [
    ("2026-08-19 20:00:00+00:00", (15, 45), (15, 55)),
    ("2026-11-27 18:00:00+00:00", (12, 45), (12, 55)),
])
def test_normal_and_early_close_calendar(close, cutoff, flatten):
    result = session_times(Calendar(close), datetime(2026, 8, 19, 12, tzinfo=ZoneInfo("America/New_York")))
    assert (result.entry_cutoff.hour, result.entry_cutoff.minute) == cutoff
    assert (result.flatten_time.hour, result.flatten_time.minute) == flatten


def test_weekend_or_holiday_has_no_session():
    assert session_times(Calendar(), datetime.now(ZoneInfo("America/New_York"))) is None


def test_calendar_failure_is_explicit():
    with pytest.raises(RuntimeError): session_times(Calendar(error=True), datetime.now(ZoneInfo("America/New_York")))


def test_emergency_reason_has_priority_over_eod(tmp_path, authority):
    flow = workflow(tmp_path, Broker()); flow.request(KillReason.EMERGENCY_KILL)
    flow.request(KillReason.EOD_FLATTEN)
    assert flow.record.reason == KillReason.EMERGENCY_KILL.value


def test_cross_process_durable_intent_reload(tmp_path):
    durable, runtime = tmp_path / "state/kill", tmp_path / "run/kill"
    code = ("from src.trading.kill_flatten import *; import sys; "
            "s=KillStore(sys.argv[1],sys.argv[2]); "
            "s.save(KillRecord(state='FLATTENING',reason='EMERGENCY_KILL',requested_at='now',attempts=1))")
    subprocess.run([sys.executable, "-c", code, str(durable), str(runtime)], check=True)
    result = subprocess.run([sys.executable, "-c",
        "from src.trading.kill_flatten import *; import sys; print(KillStore(sys.argv[1],sys.argv[2]).load().state)",
        str(durable), str(runtime)], check=True, text=True, capture_output=True)
    assert result.stdout.strip() == "FLATTENING" and durable.exists() and runtime.exists()


def test_cloud_environment_is_irrelevant_to_local_safety(tmp_path, authority, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://invalid.invalid")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "unavailable")
    flow = workflow(tmp_path, Broker(qty=1)); flow.request(KillReason.EMERGENCY_KILL)
    assert flow.run() is KillState.KILLED_FLAT
