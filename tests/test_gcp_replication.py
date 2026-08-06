import unittest
from unittest.mock import MagicMock, patch
import sqlite3
REAL_CONNECT = sqlite3.connect
import os
import sys
import tempfile
import time

# Ensure imports resolve
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from replication.gcp_replicator_daemon import GCPReplicationDaemon, _CircuitBreaker
from tests.gcp_sandbox_mock import GCPSandbox, SandboxException

class TestGCPReplication(unittest.TestCase):
    def setUp(self):
        self.state_db_fd, self.state_db_path = tempfile.mkstemp()
        self.primary_db_fd, self.primary_db_path = tempfile.mkstemp()
        
        self.sandbox = GCPSandbox()
        
        self.daemon = GCPReplicationDaemon(
            state_db_path=self.state_db_path, 
            primary_db_path=self.primary_db_path,
            tables=["bar_log", "signal_log", "paper_trades"]
        )
        
        # Inject the sandbox mocks into the GCP client wrapper
        self.daemon._gcp_client.publisher = self.sandbox.publisher
        self.daemon._gcp_client.bq_client = self.sandbox.bq_client
        self.daemon._gcp_client.project_id = "test_project"
        
        # Setup State DB
        conn = sqlite3.connect(self.state_db_path)
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sync_cursors (
                    table_name TEXT PRIMARY KEY,
                    last_sync_created_at TIMESTAMP,
                    last_sync_id INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('INSERT INTO sync_cursors (table_name, last_sync_created_at, last_sync_id) VALUES (?, ?, ?)',
                         ('bar_log', '1970-01-01T00:00:00Z', 0))
        conn.close()
        
        # Setup Primary DB with some records
        conn = sqlite3.connect(self.primary_db_path)
        with conn:
            for table in ["bar_log", "signal_log", "paper_trades"]:
                conn.execute(f'''
                    CREATE TABLE IF NOT EXISTS {table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TIMESTAMP,
                        payload TEXT
                    )
                ''')
                conn.execute(f"INSERT INTO {table} (created_at, payload) VALUES ('2026-08-01T00:01:00Z', 'payload1')")
                conn.execute(f"INSERT INTO {table} (created_at, payload) VALUES ('2026-08-01T00:02:00Z', 'payload2')")
        conn.close()

    def tearDown(self):
        os.close(self.state_db_fd)
        os.remove(self.state_db_path)
        os.close(self.primary_db_fd)
        os.remove(self.primary_db_path)

    def test_multi_table_loop(self):
        """Test Multi-Table Loop: All three tables sync in sequence, maintaining separate cursors."""
        self.daemon.sync_once()

        # Check that PubSub published 6 messages (2 per table)
        self.assertEqual(len(self.sandbox.publisher.published_messages), 6)
        # Check BigQuery
        self.assertEqual(len(self.sandbox.bq_client.inserted_rows), 6)
        
        # Check Cursors independently advanced
        c1 = self.daemon._cursor_tracker.get_cursor('bar_log')
        c2 = self.daemon._cursor_tracker.get_cursor('signal_log')
        c3 = self.daemon._cursor_tracker.get_cursor('paper_trades')
        
        self.assertEqual(c1[1], 2)
        self.assertEqual(c2[1], 2)
        self.assertEqual(c3[1], 2)

    @patch('time.time')
    def test_backoff_scaling(self, mock_time):
        """Test Backoff Scaling: Circuit breaker exponential backoff delay intervals increase correctly across 3 consecutive failures."""
        cb = _CircuitBreaker(threshold=3, backoff_factor=2.0, max_backoff=60.0)
        
        mock_time.return_value = 1000.0
        
        cb.record_failure()
        self.assertFalse(cb.is_open())
        
        cb.record_failure()
        self.assertFalse(cb.is_open())
        
        cb.record_failure() # 3rd failure triggers OPEN
        self.assertTrue(cb.is_open())
        self.assertEqual(cb.state, "OPEN")
        
        # Cooldown period should be 2.0^1 = 2.0 seconds
        mock_time.return_value = 1001.0
        self.assertTrue(cb.is_open()) # Not enough time passed
        
        mock_time.return_value = 1002.0
        self.assertFalse(cb.is_open()) # HALF_OPEN state achieved
        self.assertEqual(cb.state, "HALF_OPEN")
        
        cb.record_failure()
        self.assertTrue(cb.is_open())
        self.assertEqual(cb.state, "OPEN")
        
        # Now failures = 4, cooldown period should be 2.0^2 = 4.0 seconds
        mock_time.return_value = 1003.0
        self.assertTrue(cb.is_open())
        
        mock_time.return_value = 1006.0
        self.assertFalse(cb.is_open()) # HALF_OPEN again
        
    @patch('replication.gcp_replicator_daemon.sqlite3.connect')
    def test_downstream_deduplication_and_rollback(self, mock_connect):
        """Test Downstream Deduplication: Simulating a crashed network connection mid-batch correctly rolls back the local cursor transaction, and upon retry, the sandbox mock identifies and discards duplicate insert_ids."""
        
        # Fake a failure during the cursor update using mock_connect
        connect_count = 0
        def fake_connect(*args, **kwargs):
            nonlocal connect_count
            if args[0] == self.state_db_path:
                connect_count += 1
                if connect_count == 2:
                    # 1st time is in sync_once() -> get_cursor(). 
                    # 2nd time is in sync_once() -> _update_cursor().
                    mock_fail_conn = MagicMock()
                    mock_fail_conn.__enter__.return_value = mock_fail_conn
                    mock_fail_conn.execute.side_effect = Exception("Hard Crash")
                    return mock_fail_conn
            return REAL_CONNECT(*args, **kwargs)
            
        mock_connect.side_effect = fake_connect
        
        self.daemon.tables = ["bar_log"]
        
        # Run sync_once, it will stream to GCP (PubSub & BigQuery), then crash on SQLite update
        with self.assertRaises(Exception):
            self.daemon.sync_once()

        # Cursor should remain at epoch because the transaction crashed
        cursor = self.daemon._cursor_tracker.get_cursor('bar_log')
        self.assertEqual(cursor[1], 0)
        
        # GCP should have 2 rows inserted
        self.assertEqual(len(self.sandbox.bq_client.inserted_rows), 2)
        
        # NOW, restore connection to normal and retry
        mock_connect.side_effect = REAL_CONNECT
        self.daemon._circuit_breaker.record_success() # Force breaker closed
        
        # Retry the sync
        self.daemon.sync_once()
        
        # Cursor should now be advanced
        cursor = self.daemon._cursor_tracker.get_cursor('bar_log')
        self.assertEqual(cursor[1], 2)
        
        # Sandbox should STILL only have 2 rows in BigQuery because of deduplication!
        self.assertEqual(len(self.sandbox.bq_client.inserted_rows), 2)

    @patch('replication.gcp_replicator_daemon.logger.warning')
    def test_schema_validation_and_quarantine(self, mock_logger):
        """Test Schema Validation & Quarantine: If a row has a corrupt payload, it is quarantined to an anomaly table/log, allowing the sync loop to proceed without crashing."""
        
        # Insert a corrupt row into primary db
        conn = sqlite3.connect(self.primary_db_path)
        with conn:
            # Our fetch uses standard rows, if we inject a row with null ID, it will be missing 'id' key if we simulate it or we can just drop the column temporarily for a query? No, SQLite rows have the columns. We can just insert NULL for id, which violates NOT NULL, but we can update the table to remove NOT NULL if needed. 
            # Or we can just mock fetch_pending_rows for this test.
            pass
        conn.close()
        
        # Let's mock fetch_pending_rows just for this test to yield missing keys
        with patch.object(self.daemon._cursor_tracker, 'fetch_pending_rows') as mock_fetch:
            mock_fetch.return_value = [
                {"id": 3, "payload": "missing_created_at"}, # missing created_at
                {"created_at": "2026-08-01T00:03:00Z", "payload": "missing_id"}, # missing id
                {"id": 5, "created_at": "2026-08-01T00:04:00Z", "payload": "valid"} # valid
            ]
            
            self.daemon.tables = ["bar_log"]
            self.daemon.sync_once()
            
            # Should stream only 1 valid row
            self.assertEqual(len(self.sandbox.publisher.published_messages), 1)
            self.assertEqual(self.sandbox.publisher.published_messages[0]["data"]["id"], 5)
            
            # Warning logger should be called twice for the quarantines
            self.assertEqual(mock_logger.call_count, 2)


if __name__ == '__main__':
    unittest.main()
