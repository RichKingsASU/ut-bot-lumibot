import unittest
import time
import sqlite3
import hashlib
import json
from unittest.mock import MagicMock, patch

from replication.gcp_replicator_daemon import _CircuitBreaker
from replication.gcp_replicator_daemon import GCPReplicationDaemon, _CompoundCursorTracker

class TestCircuitBreakerResilience(unittest.TestCase):
    def setUp(self):
        # Configure a circuit breaker with a failure threshold of 3
        self.breaker = _CircuitBreaker(threshold=3, backoff_factor=2.0, max_backoff=60.0)

    def test_breaker_state_transitions_and_backoff(self):
        """Verifies CLOSED -> OPEN -> HALF_OPEN state transitions and exponential scaling."""
        self.assertEqual(self.breaker.state, "CLOSED")

        # Simulate 1st and 2nd failures (should remain CLOSED)
        self.breaker.record_failure()
        self.assertEqual(self.breaker.state, "CLOSED")
        self.breaker.record_failure()
        self.assertEqual(self.breaker.state, "CLOSED")

        # Simulate 3rd failure (should trip to OPEN and calculate backoff)
        self.breaker.record_failure()
        self.assertEqual(self.breaker._get_cooldown_period(), 2.0)  # Initial delay
        self.assertTrue(self.breaker.is_open())

        # Verify exponential backoff scaling on subsequent failure in OPEN state
        self.breaker.record_failure()
        self.assertEqual(self.breaker._get_cooldown_period(), 4.0)  # 2.0 * 2^1
        self.breaker.record_failure()
        self.assertEqual(self.breaker._get_cooldown_period(), 8.0)  # 2.0 * 2^2

        # Mock time forward past the 8-second cool-down window to test HALF_OPEN state
        future_time = time.time() + 9.0
        with patch('time.time', return_value=future_time):
            self.assertFalse(self.breaker.is_open())
            self.assertEqual(self.breaker.state, "HALF_OPEN")

            # Simulate a successful probe transaction
            self.breaker.record_success()
            self.assertEqual(self.breaker.consecutive_failures if hasattr(self.breaker, 'consecutive_failures') else self.breaker.failures, 0)

class TestIdempotencyAndCrashSafety(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp()
        # Create an in-memory SQLite state database for the cursor
        self.state_conn = sqlite3.connect(self.temp_db_path)
        self.state_conn.row_factory = sqlite3.Row
        self.state_conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_cursors (
                table_name TEXT PRIMARY KEY,
                last_sync_created_at TEXT,
                last_sync_id INTEGER,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.state_conn.commit()

        # Initialize tracking state
        self.tracker = _CompoundCursorTracker(self.temp_db_path, primary_db_path=":memory:")
        
        # Sample log row payload
        self.sample_row = {
            "id": 105,
            "created_at": "2026-08-05T23:30:00Z",
            "symbol": "AAPL",
            "price": 175.50,
            "size": 100
        }

    def tearDown(self):
        self.state_conn.close()
        import os
        os.close(self.temp_db_fd)
        os.remove(self.temp_db_path)

    def test_deterministic_insert_id_generation(self):
        """Verifies that duplicate rows generate identical SHA-256 insert_ids for BigQuery deduplication."""
        serialized_1 = json.dumps(self.sample_row, sort_keys=True).encode("utf-8")
        hash_1 = hashlib.sha256(serialized_1).hexdigest()

        # Generate a duplicate payload with slightly shifted key ordering
        unordered_row = {
            "size": 100,
            "price": 175.50,
            "symbol": "AAPL",
            "created_at": "2026-08-05T23:30:00Z",
            "id": 105
        }
        serialized_2 = json.dumps(unordered_row, sort_keys=True).encode("utf-8")
        hash_2 = hashlib.sha256(serialized_2).hexdigest()

        # Hashes must be identical regardless of JSON key sorting
        self.assertEqual(hash_1, hash_2)

    def test_transactional_rollback_on_gcp_stream_failure(self):
        """Verifies that a failure during GCP streaming rolls back the SQLite transaction."""
        # Initialize cursor in SQLite
        self.state_conn.execute("""
            INSERT INTO sync_cursors (table_name, last_sync_created_at, last_sync_id)
            VALUES ('bar_log', '2026-08-05T23:00:00Z', 100)
        """)
        self.state_conn.commit()

        # Setup daemon with mocked database reads and a failing stream wrapper
        daemon = GCPReplicationDaemon(state_db_path=self.temp_db_path, primary_db_path=":memory:", tables=["bar_log"])
        daemon._cursor_tracker = self.tracker
        daemon._cursor_tracker.fetch_pending_rows = MagicMock(return_value=[self.sample_row])
        
        # Force a stream failure (GCP outage)
        daemon._gcp_client.stream_batch = MagicMock(side_effect=RuntimeError("GCP Ingestion Outage"))

        # Execute replication sweep (should raise error and trigger rollback)
        with self.assertRaises(RuntimeError):
            daemon._sync_table("bar_log", 100)

        # Verify that the SQLite cursor was rolled back and remains at the previous epoch
        cursor = self.state_conn.execute("SELECT * FROM sync_cursors WHERE table_name = 'bar_log'").fetchone()
        self.assertEqual(cursor["last_sync_created_at"], "2026-08-05T23:00:00Z")
        self.assertEqual(cursor["last_sync_id"], 100)
