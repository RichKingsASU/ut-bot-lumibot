from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from src.trading.order_state import OrderIntent, OrderState, OrderStatus, client_order_id, normalize_status
from src.trading.reconciliation import BrokerReconciler, DurableState, OrderLifecycleService


def order(status="new", *, side="buy", qty="4", filled="0", client=None, oid="o-1"):
    return {"id": oid, "client_order_id": client or client_order_id("utbot", "2026-08-19", "signal-1", OrderIntent.ENTRY),
            "symbol": "SPY260819C00600000", "side": side, "qty": qty, "filled_qty": filled,
            "filled_avg_price": "1.25" if float(filled) else None, "status": status}


def position(qty="2"):
    return {"symbol": "SPY260819C00600000", "qty": qty, "avg_entry_price": "1.25", "side": "long"}


class FakeBroker:
    def __init__(self, positions=None, orders=None):
        self.position_values = positions or []
        self.order_values = orders or []
        self.fail = None
        self.submit_error = None
        self.lookup = None
        self.submissions = []

    def account(self):
        if self.fail == "account": raise OSError("offline")
        return {"id": "paper-account"}

    def positions(self):
        if self.fail == "positions": raise OSError("offline")
        return self.position_values

    def orders(self):
        if self.fail == "orders": raise OSError("offline")
        return self.order_values

    def submit(self, payload):
        self.submissions.append(payload)
        if self.submit_error: raise self.submit_error
        created = order(client=payload["client_order_id"], qty=payload["qty"])
        self.order_values.append(created)
        return created

    def order_by_client_id(self, value):
        return self.lookup


def reconciler(tmp_path, broker, lease=True):
    state = DurableState(tmp_path / "state.json")
    return BrokerReconciler(broker, state, lambda: lease, "paper"), state


def test_startup_flat_no_orders_allows_entry(tmp_path):
    value, _ = reconciler(tmp_path, FakeBroker())
    result = value.reconcile()
    assert result.valid and result.entry_allowed and not result.positions


def test_startup_open_position_is_recovered_and_degraded(tmp_path):
    value, _ = reconciler(tmp_path, FakeBroker([position()]))
    result = value.reconcile()
    assert result.positions[0].qty == 2 and not result.entry_allowed
    assert "DEGRADED_POSITION_STATE" in result.reason_codes


@pytest.mark.parametrize("status,partial", [("accepted", False), ("partially_filled", True)])
def test_startup_working_or_partial_entry_blocks(tmp_path, status, partial):
    value, _ = reconciler(tmp_path, FakeBroker([position()] if partial else [], [order(status, filled="2" if partial else "0")]))
    result = value.reconcile()
    assert not result.entry_allowed and len(result.partial_orders) == int(partial)
    if partial:
        assert result.partial_orders[0].remaining_qty == 2


def test_startup_working_exit_blocks_duplicate(tmp_path):
    exit_id = client_order_id("utbot", "2026-08-19", "signal-1", OrderIntent.EXIT)
    value, _ = reconciler(tmp_path, FakeBroker([position("4")], [order("accepted", side="sell", client=exit_id)]))
    result = value.reconcile()
    assert result.working_orders[0].intent is OrderIntent.EXIT and not result.entry_allowed


@pytest.mark.parametrize("local_open,broker_open", [(False, True), (True, False)])
def test_local_broker_position_mismatch_broker_wins(tmp_path, local_open, broker_open):
    value, state = reconciler(tmp_path, FakeBroker([position()] if broker_open else []))
    state.save({"positions": [position()] if local_open else [], "orders": []})
    result = value.reconcile()
    assert bool(result.positions) is broker_open
    assert result.mismatches[0]["type"] == "POSITION_MISMATCH"


def test_lost_submit_response_existing_order_is_recovered(tmp_path):
    broker = FakeBroker(); value, state = reconciler(tmp_path, broker)
    broker.submit_error = TimeoutError(); broker.lookup = order("accepted")
    result = OrderLifecycleService(broker, value, state).submit_entry(
        strategy_id="utbot", session="2026-08-19", signal_id="signal-1",
        symbol="SPY260819C00600000", qty=4, limit_price=1.2)
    assert result.status is OrderStatus.ACCEPTED and len(broker.submissions) == 1


def test_lost_submit_response_absent_does_not_retry(tmp_path):
    broker = FakeBroker(); value, state = reconciler(tmp_path, broker)
    broker.submit_error = TimeoutError(); broker.lookup = None
    with pytest.raises(RuntimeError, match="not found"):
        OrderLifecycleService(broker, value, state).submit_entry(
            strategy_id="utbot", session="2026-08-19", signal_id="signal-1",
            symbol="SPY260819C00600000", qty=4, limit_price=1.2)
    assert len(broker.submissions) == 1


@pytest.mark.parametrize("failure,reason", [("positions", "POSITION_QUERY_FAILED"), ("orders", "ORDER_QUERY_FAILED")])
def test_query_failure_is_not_flat_and_fails_closed(tmp_path, failure, reason):
    broker = FakeBroker(); broker.fail = failure
    value, _ = reconciler(tmp_path, broker)
    result = value.reconcile()
    assert not result.valid and not result.entry_allowed and reason in result.reason_codes
    assert value.health()["position_open"] is None


def test_unknown_broker_state_is_explicit_and_blocks(tmp_path):
    value, _ = reconciler(tmp_path, FakeBroker(orders=[order("mystery")]))
    result = value.reconcile()
    assert result.unknown_orders[0].status is OrderStatus.UNKNOWN_BROKER_STATE
    assert not result.valid and not result.entry_allowed


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_partial_entry_and_exit_accounting(tmp_path, side):
    intent = OrderIntent.ENTRY if side == "buy" else OrderIntent.EXIT
    raw = order("partially_filled", side=side, filled="2",
                client=client_order_id("utbot", "2026-08-19", "signal-1", intent))
    state = OrderState.from_broker(raw)
    assert state.filled_qty == 2 and state.remaining_qty == 2
    assert OrderLifecycleService.replacement_qty(state) == 2


@pytest.mark.parametrize("terminal", ["canceled", "replaced"])
def test_partial_fill_then_cancel_or_replace_preserves_fill(terminal):
    state = OrderState.from_broker(order(terminal, filled="2"))
    assert state.status.value == terminal.upper() and state.filled_qty == 2 and state.remaining_qty == 2


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_rejected_entry_or_exit_is_explicit(side):
    assert OrderState.from_broker(order("rejected", side=side)).status is OrderStatus.REJECTED


def test_same_signal_second_entry_is_durably_blocked(tmp_path):
    broker = FakeBroker(); value, state = reconciler(tmp_path, broker)
    service = OrderLifecycleService(broker, value, state)
    kwargs = dict(strategy_id="utbot", session="2026-08-19", signal_id="signal-1",
                  symbol="SPY260819C00600000", qty=4, limit_price=1.2)
    service.submit_entry(**kwargs)
    broker.order_values = []  # even absent from current window, durable consumed ID blocks
    with pytest.raises(RuntimeError, match="duplicate"):
        service.submit_entry(**kwargs)
    assert len(broker.submissions) == 1


def test_local_filled_or_canceled_never_overrides_broker(tmp_path):
    broker = FakeBroker(orders=[order("partially_filled", filled="2")])
    value, state = reconciler(tmp_path, broker)
    cached = OrderState.from_broker(order("filled", filled="4")).to_dict()
    state.save({"positions": [], "orders": [cached]})
    result = value.reconcile()
    assert result.partial_orders[0].filled_qty == 2 and result.mismatches
    broker.order_values = [order("filled", filled="4")]
    state.save({"positions": [], "orders": [OrderState.from_broker(order("canceled")).to_dict()]})
    assert value.reconcile().mismatches[0]["broker_status"] == "FILLED"


def test_close_submitted_is_not_flat_until_position_qty_zero(tmp_path):
    exit_id = client_order_id("utbot", "2026-08-19", "signal-1", OrderIntent.EXIT)
    broker = FakeBroker([position("2")], [order("filled", side="sell", filled="4", client=exit_id)])
    value, _ = reconciler(tmp_path, broker)
    assert value.reconcile().positions[0].qty == 2
    broker.position_values = []
    assert not value.reconcile().positions


def test_no_execution_lease_blocks_entry(tmp_path):
    value, _ = reconciler(tmp_path, FakeBroker(), lease=False)
    assert not value.reconcile().entry_allowed


def test_cloud_outage_irrelevant_to_reconciliation(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://unreachable.invalid")
    value, _ = reconciler(tmp_path, FakeBroker())
    assert value.reconcile().valid


def _restart_worker(path, phase, queue):
    broker = FakeBroker([position()], [order("partially_filled", filled="2")])
    value = BrokerReconciler(broker, DurableState(path), lambda: True, "paper")
    result = value.reconcile()
    queue.put((phase, len(result.positions), result.partial_orders[0].remaining_qty, result.entry_allowed))


def test_process_level_restart_reconstructs_partial_and_does_not_duplicate(tmp_path):
    path = str(tmp_path / "durable.json")
    context = multiprocessing.get_context("spawn")
    for phase in ("A", "B"):
        queue = context.Queue(); process = context.Process(target=_restart_worker, args=(path, phase, queue))
        process.start(); process.join(10)
        assert process.exitcode == 0
        assert queue.get(timeout=2) == (phase, 1, 2.0, False)
    assert json.loads(Path(path).read_text())["version"] == 1


def test_all_required_statuses_and_id_constraint():
    expected = {"NEW", "ACCEPTED", "PENDING_NEW", "PARTIALLY_FILLED", "FILLED", "PENDING_CANCEL",
                "CANCELED", "EXPIRED", "REJECTED", "PENDING_REPLACE", "REPLACED"}
    assert all(normalize_status(item.lower()).value == item for item in expected)
    assert len(client_order_id("strategy-long-name", "2026-08-19", "secret signal", OrderIntent.ENTRY)) <= 48
