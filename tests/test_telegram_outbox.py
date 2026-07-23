import os
import logging
from common.supabase_auth import get_supabase_headers
from adapters.telegram_alerts import _send, _resolve_message_type, _tee_outbox
import adapters.telegram_alerts
import tools.telegram_mcp.server as mcp_server
import pytest
from unittest.mock import patch, MagicMock

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
    # A body containing BOTH "summary" and an alert marker, passed with explicit message_type="alert", stays "alert".
    # _tee_outbox uses explicit value if present
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    # We can test this by calling _tee_outbox
    with patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        
        with patch("adapters.telegram_alerts.get_supabase_headers") as mock_headers:
            mock_headers.return_value = {}
            with patch("adapters.telegram_alerts.logger.error") as mock_err:
                _tee_outbox("summary 🚨", "test_chat", True, 123, None, message_type="alert")
                
                # Check that requests.post was called with json having message_type = alert
                args, kwargs = mock_post.call_args
                assert kwargs["json"]["message_type"] == "alert"

def test_tee_resilience_success(caplog, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    with patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        
        _tee_outbox("test", "test", True, 123, None, message_type="other")
        
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["send_ok"] is True
        assert kwargs["json"]["error"] is None

def test_tee_resilience_http_error(caplog, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    with patch("adapters.telegram_alerts.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp
        
        with caplog.at_level(logging.WARNING):
            _tee_outbox("test", "test", True, 123, None, message_type="other")
        
        assert any("outbox tee write failed" in r.message for r in caplog.records)

def test_tee_resilience_exception(caplog, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test")
    with patch("adapters.telegram_alerts.requests.post", side_effect=Exception("network error")):
        with caplog.at_level(logging.ERROR):
            _tee_outbox("test", "test", True, 123, None, message_type="other")
            
        assert any("outbox tee error: network error" in r.message for r in caplog.records)

def test_tee_resilience_missing_credentials(caplog, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with patch("adapters.telegram_alerts.requests.post") as mock_post:
        with caplog.at_level(logging.WARNING):
            _tee_outbox("test", "test", True, 123, None, message_type="other")
        
        mock_post.assert_not_called()
        assert any("outbox tee skipped" in r.message for r in caplog.records)

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
