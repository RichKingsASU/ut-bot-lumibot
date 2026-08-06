import pytest
from unittest.mock import AsyncMock, patch
from replication.gcp_replicator_daemon import GCPReplicationDaemon

@pytest.mark.asyncio
async def test_t01_nominal_path():
    """T01: Happy path streaming to GCP, updating the compound cursor correctly."""
    daemon = GCPReplicationDaemon()
    with patch("replication.gcp_replicator_daemon._fetch_supabase_rows", return_value=[{"id": 1, "created_at": "2026-08-01T00:00:00Z"}]):
        with patch("replication.gcp_replicator_daemon._GCPClient.stream_to_bq", new_callable=AsyncMock) as mock_gcp:
            mock_gcp.return_value = True
            await daemon.sync_once()
            
    # Cursor should advance
    created_at, row_id = daemon._state.get_compound_cursor("bar_log")
    assert row_id == 1
    assert created_at == "2026-08-01T00:00:00Z"

@pytest.mark.asyncio
async def test_t02_gcp_outage():
    """T02: GCP API returns 500s. Circuit breaker opens, cursor halts, no records lost."""
    daemon = GCPReplicationDaemon()
    with patch("replication.gcp_replicator_daemon._fetch_supabase_rows", return_value=[{"id": 2, "created_at": "2026-08-01T00:01:00Z"}]):
        with patch("replication.gcp_replicator_daemon._GCPClient.stream_to_bq", side_effect=Exception("500 Internal Error")):
            await daemon.sync_once()
            
    assert daemon._circuit.is_open() is True
    assert len(daemon._state.get_wal_entries("bar_log")) == 1
    # Cursor should NOT advance
    created_at, row_id = daemon._state.get_compound_cursor("bar_log")
    assert row_id == 0

@pytest.mark.asyncio
async def test_t03_reconnection_drain():
    """T03: Reconnecting triggers sequential deduplicated sync from saved cursor."""
    daemon = GCPReplicationDaemon()
    daemon._state.buffer_to_wal("bar_log", {"id": 3, "created_at": "2026-08-01T00:02:00Z"})
    
    with patch("replication.gcp_replicator_daemon._fetch_supabase_rows", return_value=[]):
        with patch("replication.gcp_replicator_daemon._GCPClient.stream_to_bq", new_callable=AsyncMock) as mock_gcp:
            mock_gcp.return_value = True
            await daemon.sync_once()
            
    assert len(daemon._state.get_wal_entries("bar_log")) == 0
    assert mock_gcp.call_count == 1

@pytest.mark.asyncio
async def test_t04_crash_safety():
    """T04: Mid-stream abort rolls back SQLite transactions preventing unsynced states."""
    daemon = GCPReplicationDaemon()
    # Simulate a crash during the atomic update
    with patch("replication.gcp_replicator_daemon._StateTracker.update_cursor_and_drain_wal", side_effect=Exception("Hard Crash")):
        with patch("replication.gcp_replicator_daemon._fetch_supabase_rows", return_value=[{"id": 4, "created_at": "2026-08-01T00:03:00Z"}]):
            with pytest.raises(Exception, match="Hard Crash"):
                await daemon.sync_once()
    
    # Verify cursor remains unchanged due to rollback
    created_at, row_id = daemon._state.get_compound_cursor("bar_log")
    assert row_id == 0
