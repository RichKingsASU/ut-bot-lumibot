import os
import logging
from common.supabase_auth import get_supabase_headers
from adapters.telegram_alerts import _send, _resolve_message_type, _tee_outbox
import adapters.telegram_alerts
import tools.telegram_mcp.server as mcp_server
import pytest
from unittest.mock import patch, MagicMock, call


# ── Autouse fixture: reset all module-level globals between tests ──────────
# _warned_unrecognized_key (supabase_auth) and _tee_failing/_tee_failure_count
# (telegram_alerts) are process-lifetime global state.  Without this fixture
# the test suite is order-dependent.

@pytest.fixture(autouse=True)
def reset_module_globals():
    """Reset warn-once flags and tee state between every test."""
    import common.supabase_auth as sa
    sa._warned_unrecognized_key = False

    import adapters.telegram_alerts as ta
    ta._tee_failing = False
    ta._tee_first_failure_ts = None
    ta._tee_failure_count = 0
    # Clear threading.local attributes if set by a prior test in same thread
    ta._tee_local.__dict__.clear()
    yield
    # Teardown: reset again in case test left dirty state
    sa._warned_unrecognized_key = False
    ta._tee_failing = False
    ta._tee_first_failure_ts = None
    ta._tee_failure_count = 0
    ta._tee_local.__dict__.clear()


# ═══════════════════════════════════════════════════════════════════════════
# Existing tests (12) — must all still pass
# ═══════════════════════════════════════════════════════════════════════════

def test_header_helper_sb_secret(caplog):
    key = "sb_secret_xxx"
    with caplog.at_level(logging.WARNING):
        headers = get_supabase_headers(key)
    assert "apikey" in headers
    assert "Authorization" not in headers
    assert headers["apikey"] == key
    # Assert key value appears nowhere in captured log output
    for record in caplog.records:
        assert key not in record.message
    # Assert no warning was logged
    assert not any("unrecognized" in record.message for record in caplog.records)

def test_header_helper_jwt(caplog):
    key = "eyJhbG.eyJzdWI.sig"
    with caplog.at_level(logging.WARNING):
        headers = get_supabase_headers(key)
    assert "apikey" in headers
    assert "Authorization" in headers
    assert headers["Authorization"] == f"Bearer {key}"
    for record in caplog.records:
        assert key not in record.message
    assert not any("unrecognized" in record.message for record in caplog.records)

def test_header_helper_garbage(caplog):
    key = "garbage"
    with caplog.at_level(logging.WARNING):
        headers = get_supabase_headers(key)
    assert "apikey" in headers
    assert "Authorization" not in headers
    for record in caplog.records:
        assert key not in record.message
    # Assert warning was logged
    assert any("unrecognized Supabase key format" in record.message for record in caplog.records)

@patch("adapters.telegram_alerts._tee_outbox")
@patch("adapters.telegram_alerts.requests.post")
@patch("adapters.telegram_alerts._init")
def test_message_type_callers(mock_init, mock_post, mock_tee_outbox, caplog):
    adapters.telegram_alerts._token = "test"
    adapters.telegram_alerts._chat_id = "test"
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"message_id": 123}}
    mock_post.return_value = mock_resp

    adapters.telegram_alerts.send_startup()
    mock_tee_outbox.assert_called_with(
        "🚀 DisruptingAlpha BOT STARTED\nStrategy: UTBotStrategy\nMode: PAPER\nSymbol: SPY\nSession: ",
        "test", True, 123, None, message_type="other"
    )

    adapters.telegram_alerts.send_alert("🚨 ERROR\ntest")
    mock_tee_outbox.assert_called_with("🚨 ERROR\ntest", "test", True, 123, None, message_type="alert")

def test_resolve_message_type_fallback(caplog):
    with caplog.at_level(logging.WARNING):
        val = _resolve_message_type("test")
    assert val == "other"
    assert any("Fallback _resolve_message_type called by" in r.message for r in caplog.records)

def test_resolve_message_type_regression(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    with patch("common.safe_write.safe_write_sync") as mock_safe_write:
        _tee_outbox("summary 🚨", "test_chat", True, 123, None, message_type="alert")
        args, kwargs = mock_safe_write.call_args
        assert kwargs["payload"]["message_type"] == "alert"

def test_tee_resilience_success(caplog, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    with patch("common.safe_write.safe_write_sync") as mock_safe_write:
        mock_safe_write.return_value = True
        _tee_outbox("test", "test", True, 123, None, message_type="other")
        args, kwargs = mock_safe_write.call_args
        assert kwargs["payload"]["send_ok"] is True
        assert kwargs["payload"]["error"] is None

def test_tee_resilience_http_error(caplog, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    with patch("common.safe_write.safe_write_sync") as mock_safe_write:
        mock_safe_write.return_value = False
        with caplog.at_level(logging.WARNING):
            _tee_outbox("test", "test", True, 123, None, message_type="other")

def test_tee_resilience_exception(caplog, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    with patch("common.safe_write.safe_write_sync", side_effect=Exception("network error")), \
         patch("adapters.telegram_alerts.requests.post") as mock_post:
        # Mock the Telegram API for the failure alert dispatch
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"message_id": 999}}
        mock_post.return_value = mock_resp
        adapters.telegram_alerts._token = "test"
        adapters.telegram_alerts._chat_id = "test"
        with caplog.at_level(logging.ERROR):
            _tee_outbox("test", "test", True, 123, None, message_type="other")
        assert any("outbox tee error: network error" in r.message for r in caplog.records)

def test_tee_resilience_missing_credentials(caplog, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with patch("common.safe_write.safe_write_sync") as mock_safe_write:
        with caplog.at_level(logging.WARNING):
            _tee_outbox("test", "test", True, 123, None, message_type="other")
        
        mock_safe_write.assert_not_called()
        assert any("outbox tee skipped" in r.message for r in caplog.records)

def test_send_tee_failure_does_not_raise(caplog, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    adapters.telegram_alerts._token = "test"
    adapters.telegram_alerts._chat_id = "test"
    with patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"message_id": 123}}
        mock_post.return_value = mock_resp
        
        with patch("common.safe_write.safe_write_sync", side_effect=Exception("tee crash")):
            with caplog.at_level(logging.ERROR):
                _send("test message")
            assert any("outbox tee error: tee crash" in r.message for r in caplog.records)

@patch("tools.telegram_mcp.server.httpx.get")
def test_mcp_server(mock_get, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_xxx")
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"id": 1, "sent_at": "2026-07-23T00:00:00Z"}]
    mock_resp.headers = {"content-range": "0-0/1"}
    mock_get.return_value = mock_resp
    
    res1 = mcp_server.tool_get_recent_reports()
    assert res1["count"] == 1
    
    res2 = mcp_server.tool_get_reports_since("2020-01-01T00:00:00Z")
    assert res2["count"] == 1
    
    res3 = mcp_server.tool_get_outbox_health()
    assert res3["count_24h"] == 1
    
    mock_get.side_effect = Exception("network error")
    try:
        mcp_server.tool_get_recent_reports()
    except Exception as e:
        pass
    
    req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_recent_reports", "arguments": {}}}
    resp = mcp_server._handle(req)
    assert "sb_secret_xxx" not in str(resp)
    
def test_migration_assertions():
    with open("supabase/migrations/20260723000000_create_telegram_outbox.sql") as f:
        content = f.read()
    
    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "CREATE POLICY" in content
    assert "anon" not in content
    assert "authenticated" not in content
    assert "DROP TABLE" not in content


# ═══════════════════════════════════════════════════════════════════════════
# New visibility tests (PR #68 remediation — Step 3)
# ═══════════════════════════════════════════════════════════════════════════

def test_tee_failure_emits_alert(caplog, monkeypatch):
    """On tee failure, a degradation alert is emitted via Telegram."""
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    adapters.telegram_alerts._token = "test"
    adapters.telegram_alerts._chat_id = "test"

    with patch("common.safe_write.safe_write_sync", side_effect=Exception("db down")), \
         patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"message_id": 900}}
        mock_post.return_value = mock_resp

        _tee_outbox("test body", "chat1", True, 100, None, message_type="alert")

        # The failure alert should have triggered a Telegram send
        # Call 0 = the failure alert itself (sent via recursive _send)
        assert mock_post.call_count >= 1
        alert_body = mock_post.call_args_list[0][1]["json"]["text"]
        assert "OUTBOX TEE DEGRADED" in alert_body
        assert "db down" in alert_body


def test_tee_dedup_consecutive_failures(caplog, monkeypatch):
    """N consecutive tee failures emit exactly ONE alert (dedup holds)."""
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    adapters.telegram_alerts._token = "test"
    adapters.telegram_alerts._chat_id = "test"

    with patch("common.safe_write.safe_write_sync", side_effect=Exception("outage")), \
         patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"message_id": 901}}
        mock_post.return_value = mock_resp

        # Fire 5 consecutive tee failures
        for _ in range(5):
            _tee_outbox("msg", "chat1", True, 100, None, message_type="other")

        # Only ONE alert should have been sent (the first transition)
        alert_calls = [
            c for c in mock_post.call_args_list
            if "OUTBOX TEE DEGRADED" in c[1].get("json", {}).get("text", "")
        ]
        assert len(alert_calls) == 1

        # Verify failure count was tracked
        assert adapters.telegram_alerts._tee_failure_count == 5


def test_tee_recovery_alert_and_heartbeat(caplog, monkeypatch):
    """Recovery after failure writes a component_heartbeat row AND emits one recovery alert."""
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    adapters.telegram_alerts._token = "test"
    adapters.telegram_alerts._chat_id = "test"

    call_log = []

    def tracking_safe_write(table, payload, component, **kwargs):
        call_log.append({"table": table, "payload": payload, "component": component})
        return True

    # Phase 1: induce failure
    with patch("common.safe_write.safe_write_sync", side_effect=Exception("outage")), \
         patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"message_id": 902}}
        mock_post.return_value = mock_resp

        _tee_outbox("msg", "chat1", True, 100, None, message_type="other")
        assert adapters.telegram_alerts._tee_failing is True

    # Phase 2: recovery — safe_write now succeeds
    with patch("common.safe_write.safe_write_sync", side_effect=tracking_safe_write), \
         patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"message_id": 903}}
        mock_post.return_value = mock_resp

        _tee_outbox("recovery msg", "chat1", True, 200, None, message_type="other")

        # State should be reset to healthy
        assert adapters.telegram_alerts._tee_failing is False

        # A component_heartbeat row should have been written
        heartbeat_writes = [c for c in call_log if c["table"] == "component_heartbeat"]
        assert len(heartbeat_writes) == 1
        hb = heartbeat_writes[0]
        assert hb["payload"]["status"] == "OK"
        assert hb["payload"]["meta"]["recovery"] is True
        assert hb["payload"]["meta"]["failure_count"] == 1

        # Recovery alert should have been sent via Telegram
        recovery_calls = [
            c for c in mock_post.call_args_list
            if "OUTBOX TEE RECOVERED" in c[1].get("json", {}).get("text", "")
        ]
        assert len(recovery_calls) == 1


def test_tee_no_reentrant_tee(caplog, monkeypatch):
    """A tee failure does not trigger a nested tee attempt (safe_write called exactly once)."""
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    adapters.telegram_alerts._token = "test"
    adapters.telegram_alerts._chat_id = "test"

    with patch("common.safe_write.safe_write_sync", side_effect=Exception("outage")) as mock_sw, \
         patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"message_id": 904}}
        mock_post.return_value = mock_resp

        # Call _send which will: POST to Telegram (ok), then _tee_outbox (fails),
        # then _on_tee_failure sends alert via _send recursively,
        # recursive _send POSTs alert to Telegram (ok), then calls _tee_outbox,
        # but the re-entrancy guard skips it.
        _send("original message")

        # safe_write_sync should be called exactly ONCE (the initial tee attempt).
        # If the guard failed, it would be called twice (once for the alert's tee).
        assert mock_sw.call_count == 1

        # Telegram POST should be called TWICE: once for original message,
        # once for the degradation alert.
        assert mock_post.call_count == 2


def test_outer_send_succeeds_when_tee_raises(caplog, monkeypatch):
    """The outer send path returns without error even when the tee raises."""
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    adapters.telegram_alerts._token = "test"
    adapters.telegram_alerts._chat_id = "test"

    with patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"message_id": 905}}
        mock_post.return_value = mock_resp

        with patch("common.safe_write.safe_write_sync", side_effect=Exception("kaboom")):
            # _send must complete without raising
            _send("test message", message_type="alert")

        # The Telegram API was called (message was delivered despite tee failure)
        assert mock_post.call_count >= 1
        # First call was the original message
        first_call_body = mock_post.call_args_list[0][1]["json"]["text"]
        assert first_call_body == "test message"
