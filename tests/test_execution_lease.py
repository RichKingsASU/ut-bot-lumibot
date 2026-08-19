import multiprocessing
import os
import subprocess
import sys
import types
import signal
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Keep this safety suite runnable in the minimal audit image. Production still
# installs the real packages from requirements.txt.
if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.get = Mock(); requests_stub.post = Mock()
    requests_stub.patch = Mock(); requests_stub.delete = Mock()
    sys.modules["requests"] = requests_stub
if "pytz" not in sys.modules:
    pytz_stub = types.ModuleType("pytz")
    pytz_stub.timezone = lambda _name: timezone.utc
    pytz_stub.utc = timezone.utc
    sys.modules["pytz"] = pytz_stub
if "dateutil" not in sys.modules:
    dateutil_stub = types.ModuleType("dateutil")
    parser_stub = types.ModuleType("dateutil.parser")
    parser_stub.isoparse = lambda value: __import__("datetime").datetime.fromisoformat(value)
    dateutil_stub.parser = parser_stub
    sys.modules["dateutil"] = dateutil_stub
    sys.modules["dateutil.parser"] = parser_stub

from src.trading import broker
from src.trading.execution_lease import (
    ExecutionLease,
    ExecutionLeaseDenied,
    ExecutionLeaseError,
    ExecutionMutationBlocked,
    install_execution_lease,
    resolve_trading_mode,
)


def _hold_lease(runtime_dir, ready, release, crash=False):
    lease = ExecutionLease("acct-a", "paper", "child", Path(runtime_dir)).acquire()
    ready.set()
    release.wait(10)
    if crash:
        os._exit(23)
    lease.release()


def _acquire_then_raise(runtime_dir, ready):
    ExecutionLease("acct-a", "paper", "exception", Path(runtime_dir)).acquire()
    ready.set()
    raise RuntimeError("uncaught test exception")


@pytest.fixture(autouse=True)
def clear_installed_lease():
    install_execution_lease(None)
    yield
    install_execution_lease(None)


def test_first_process_acquires_and_releases(tmp_path):
    lease = ExecutionLease("acct-a", "paper", runtime_dir=tmp_path).acquire()
    assert lease.owned
    assert lease.lock_path.exists()
    lease.release()
    assert not lease.owned


@pytest.mark.parametrize("owner_path", ["systemd", "docker", "manual"])
def test_cross_launch_second_process_denied(tmp_path, owner_path):
    # Launch labels do not affect authority: all routes converge on this flock.
    first = ExecutionLease("acct-a", "paper", owner_path, tmp_path).acquire()
    with pytest.raises(ExecutionLeaseDenied, match="already held"):
        ExecutionLease("acct-a", "paper", "manual", tmp_path).acquire()
    first.release()


def test_kernel_releases_after_normal_process_exit(tmp_path):
    ready, release = multiprocessing.Event(), multiprocessing.Event()
    proc = multiprocessing.Process(target=_hold_lease, args=(tmp_path, ready, release))
    proc.start(); assert ready.wait(5); release.set(); proc.join(5)
    assert proc.exitcode == 0
    with ExecutionLease("acct-a", "paper", runtime_dir=tmp_path) as lease:
        assert lease.owned


def test_stale_lockfile_does_not_block_after_crash(tmp_path):
    ready, crash = multiprocessing.Event(), multiprocessing.Event()
    proc = multiprocessing.Process(target=_hold_lease, args=(tmp_path, ready, crash, True))
    proc.start(); assert ready.wait(5); crash.set(); proc.join(5)
    assert proc.exitcode == 23
    assert (tmp_path / "alpaca-acct-a-paper.lock").exists()
    with ExecutionLease("acct-a", "paper", runtime_dir=tmp_path) as lease:
        assert lease.owned


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_kernel_releases_after_termination_signal(tmp_path, signum):
    ready, never = multiprocessing.Event(), multiprocessing.Event()
    proc = multiprocessing.Process(target=_hold_lease, args=(tmp_path, ready, never))
    proc.start(); assert ready.wait(5); os.kill(proc.pid, signum); proc.join(5)
    assert proc.exitcode != 0
    with ExecutionLease("acct-a", "paper", runtime_dir=tmp_path) as lease:
        assert lease.owned


def test_kernel_releases_after_uncaught_exception(tmp_path):
    ready = multiprocessing.Event()
    proc = multiprocessing.Process(target=_acquire_then_raise, args=(tmp_path, ready))
    proc.start(); assert ready.wait(5); proc.join(5)
    assert proc.exitcode != 0
    with ExecutionLease("acct-a", "paper", runtime_dir=tmp_path) as lease:
        assert lease.owned


@pytest.mark.parametrize("operation,call", [
    ("submit", lambda: broker._place_order({"symbol": "SPY"})),
    ("cancel", lambda: broker.cancel_all_orders()),
    ("replace", lambda: broker._execute_order_with_chase("id", "buy", 1, 0)),
    ("close", lambda: broker.sell_to_close("SPY000", 1)),
    ("flatten", lambda: broker.cancel_all_orders()),
])
def test_mutations_without_lease_never_reach_http(operation, call):
    with patch.object(broker.requests, "post") as post, \
         patch.object(broker.requests, "delete") as delete, \
         patch.object(broker.requests, "patch") as replace:
        if operation == "replace":
            # Force the chase path to the mutation; the guard must stop PATCH.
            with patch.object(broker.requests, "get") as get, \
                 patch.object(broker, "get_option_quote", return_value={"valid": True, "ask": 2, "bid": 1}):
                get.return_value.json.return_value = {"symbol": "SPY000", "limit_price": "1", "status": "new"}
                with pytest.raises(ExecutionMutationBlocked): call()
        else:
            with pytest.raises(ExecutionMutationBlocked): call()
        post.assert_not_called(); delete.assert_not_called(); replace.assert_not_called()


def test_read_only_broker_query_does_not_require_lease():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = []
    with patch.object(broker.requests, "get", return_value=response) as get:
        assert broker.get_open_position("SPY") == {"valid": True, "position": None}
        get.assert_called_once()


def test_paper_and_live_have_distinct_identities(tmp_path):
    paper = ExecutionLease("acct-a", "paper", runtime_dir=tmp_path)
    live = ExecutionLease("acct-a", "live", runtime_dir=tmp_path)
    assert paper.identity != live.identity
    with paper, live:
        assert paper.owned and live.owned


@pytest.mark.parametrize("value", [None, "", "yes", "paper", "tru"])
def test_ambiguous_mode_fails_closed(monkeypatch, value):
    monkeypatch.delenv("ALPACA_IS_PAPER", raising=False)
    with pytest.raises(ExecutionLeaseError):
        resolve_trading_mode(value)


def test_direct_python_duplicate_exits_nonzero_without_order_request(tmp_path):
    owner = ExecutionLease("acct-a", "paper", "systemd", tmp_path).acquire()
    code = (
        "from pathlib import Path; from src.trading.execution_lease import ExecutionLease; "
        f"ExecutionLease('acct-a','paper','manual',Path({str(tmp_path)!r})).acquire()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=Path(__file__).parents[1],
        capture_output=True, text=True, check=False,
    )
    owner.release()
    assert result.returncode != 0
    assert "execution lease already held" in result.stderr


def test_duplicate_launch_cannot_install_authority_or_submit(tmp_path):
    owner = ExecutionLease("acct-a", "paper", "docker", tmp_path).acquire()
    duplicate = ExecutionLease("acct-a", "paper", "manual", tmp_path)
    with patch.object(broker.requests, "post") as post:
        with pytest.raises(ExecutionLeaseDenied):
            duplicate.acquire()
        with pytest.raises(ExecutionMutationBlocked):
            broker._place_order({"symbol": "SPY"})
        post.assert_not_called()
    owner.release()
