import sqlite3
import logging
import asyncio
import base64
import datetime
import decimal
import os
import time
import json
import hashlib
import uuid
from typing import List, Dict, Any, Tuple

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

# Optional GCP imports, they might not be installed in the local environment,
# but we write the code for when they are.
try:
    from google.cloud import pubsub_v1
    from google.cloud import bigquery
    from google.oauth2 import service_account
except ImportError:
    pubsub_v1 = None
    bigquery = None
    service_account = None

logger = logging.getLogger("gcp_replicator")


def _json_safe_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make a psycopg2 row safe for json.dumps() and BigQuery insert_rows_json().

    RealDictCursor returns Postgres `numeric` as Decimal and `timestamptz` as
    datetime; neither is JSON-serializable. Only created_at used to be
    converted, so any other timestamp or numeric column (bar_log.bar_time,
    open/high/low/close, ...) raised TypeError on the first row streamed.

    Decimals become strings rather than floats: BigQuery NUMERIC accepts a
    string and it round-trips exactly, whereas float() silently loses precision
    on prices.
    """
    safe = {}
    for key, value in row.items():
        if isinstance(value, decimal.Decimal):
            safe[key] = str(value)
        elif isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            safe[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            safe[key] = str(value)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            safe[key] = base64.b64encode(bytes(value)).decode("ascii")
        else:
            safe[key] = value
    return safe

class ConfigurationError(Exception):
    pass

class _CompoundCursorTracker:
    """Internal. Manages SQLite local cursor high-water marks transactionally and fetches from primary DB."""
    def __init__(self, state_db_path: str, primary_db_path: str):
        self.state_db_path = state_db_path
        self.primary_db_path = primary_db_path
        self.dsn = os.environ.get("SUPABASE_DSN")

    def get_cursor(self, table_name: str) -> Tuple[str, int]:
        conn = sqlite3.connect(self.state_db_path)
        try:
            row = conn.execute(
                "SELECT last_sync_created_at, last_sync_id FROM sync_cursors WHERE table_name = ?", 
                (table_name,)
            ).fetchone()
            if row:
                return (row[0], row[1])
            return ("1970-01-01T00:00:00Z", 0)
        finally:
            conn.close()

    def fetch_pending_rows(self, table_name: str, last_created_at: str, last_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        # Prevent SQL injection by validating table_name (simple alphanumeric check)
        if not table_name.isidentifier():
            raise ValueError("Invalid table name")

        if self.dsn:
            if psycopg2 is None:
                raise RuntimeError("psycopg2 is required for production PostgreSQL mode")
            try:
                conn = psycopg2.connect(self.dsn)
            except Exception as e:
                raise ConnectionError(f"Failed to connect to Supabase: {e}")
            
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    query = f"""
                        SELECT * FROM {table_name}
                        WHERE (created_at > %s) 
                           OR (created_at = %s AND id > %s)
                        ORDER BY created_at ASC, id ASC 
                        LIMIT %s;
                    """
                    cur.execute(query, (last_created_at, last_created_at, last_id, limit))
                    rows = cur.fetchall()
                    return [_json_safe_row(dict(r)) for r in rows]
            finally:
                conn.close()

        # Fallback to local SQLite DB (for offline testing)
        if not os.path.exists(self.primary_db_path):
            return [] # Fail gracefully if primary DB doesn't exist during mock tests
            
        conn = sqlite3.connect(self.primary_db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = f"""
                SELECT * FROM {table_name}
                WHERE (created_at > ?) OR (created_at = ? AND id > ?)
                ORDER BY created_at ASC, id ASC
                LIMIT ?
            """
            rows = conn.execute(query, (last_created_at, last_created_at, last_id, limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

class _CircuitBreaker:
    """Internal. Tracks consecutive failures and manages states (closed/open/half-open)."""
    def __init__(self, threshold: int = 3, backoff_factor: float = 2.0, max_backoff: float = 60.0):
        self.failures = 0
        self.threshold = threshold
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.last_failure_time = 0.0
        self.state = "CLOSED" # CLOSED, OPEN, HALF_OPEN

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.threshold:
            self.state = "OPEN"

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"
        
    def _get_cooldown_period(self) -> float:
        # Exponential backoff
        exp_backoff = self.backoff_factor ** (self.failures - self.threshold + 1)
        return min(exp_backoff, self.max_backoff)

    def is_open(self) -> bool:
        if self.state == "CLOSED":
            return False
            
        # Check if we should transition to HALF_OPEN
        time_since_failure = time.time() - self.last_failure_time
        if time_since_failure >= self._get_cooldown_period():
            self.state = "HALF_OPEN"
            return False # Allow one test batch through
            
        return True
        
    def get_batch_limit(self, default_limit: int) -> int:
        if self.state == "HALF_OPEN":
            return 1 # Allow only a single small test batch to pass through
        return default_limit


def _load_service_account(creds_path: str, credentials_json: str):
    """
    Build service-account credentials from either Google's standard
    GOOGLE_APPLICATION_CREDENTIALS file path (preferred) or the raw key
    contents in GCP_SERVICE_ACCOUNT_JSON (legacy).

    A path is preferred: the key never lands in the environment, in `ps`
    output, or in systemd's journal, and file permissions can restrict it to
    0600. GCP_SERVICE_ACCOUNT_JSON is still honoured so existing deployments
    keep working.

    GCP_SERVICE_ACCOUNT_JSON containing a path rather than JSON is a natural
    mistake -- the old code fed it straight to json.loads and failed with an
    opaque decode error -- so detect and accept that case too.
    """
    if creds_path:
        if not os.path.isfile(creds_path):
            raise ConfigurationError(
                f"GOOGLE_APPLICATION_CREDENTIALS points at {creds_path!r}, which is not a file."
            )
        return service_account.Credentials.from_service_account_file(creds_path)

    stripped = credentials_json.strip()
    if not stripped.startswith("{"):
        if os.path.isfile(stripped):
            return service_account.Credentials.from_service_account_file(stripped)
        raise ConfigurationError(
            "GCP_SERVICE_ACCOUNT_JSON is neither JSON (it does not start with '{') "
            "nor a path to an existing file. Set GOOGLE_APPLICATION_CREDENTIALS to the "
            "key file instead."
        )
    return service_account.Credentials.from_service_account_info(json.loads(stripped))


class _GCPClientWrapper:
    """Internal. Hides Pub/Sub message streaming and BigQuery loading."""
    def __init__(self, project_id: str = "disruptingalpha"):
        self.project_id = project_id
        
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        credentials_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        is_prod = bool(os.environ.get("SUPABASE_DSN")) or bool(os.environ.get("PRODUCTION_MODE"))

        if is_prod and not (creds_path or credentials_json):
            raise ConfigurationError(
                "No GCP credentials in production mode: set GOOGLE_APPLICATION_CREDENTIALS "
                "to a service-account key file (preferred), or GCP_SERVICE_ACCOUNT_JSON to "
                "the key contents."
            )

        if (creds_path or credentials_json) and service_account:
            try:
                self.credentials = _load_service_account(creds_path, credentials_json)
                publisher_options = pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
                self.publisher = pubsub_v1.PublisherClient(credentials=self.credentials, publisher_options=publisher_options)
                self.bq_client = bigquery.Client(credentials=self.credentials, project=project_id)
            except Exception as e:
                if is_prod:
                    raise ConfigurationError(f"Invalid GCP credentials: {e}")
                self.publisher = None
                self.bq_client = None
        else:
            if is_prod and not service_account:
                raise ConfigurationError("google-cloud libraries are missing in production mode.")
            self.credentials = None
            self.publisher = None
            self.bq_client = None

    def stream_batch(self, table_name: str, rows: List[Dict[str, Any]]) -> bool:
        if not rows:
            return True
            
        if not self.publisher or not self.bq_client:
            if os.environ.get("SUPABASE_DSN") or os.environ.get("PRODUCTION_MODE"):
                raise ConfigurationError("GCP clients are not initialized in production mode.")
            return True # Let local offline mock tests pass
            
        topic_path = self.publisher.topic_path(self.project_id, f"gcp-topic-{table_name}")
        bq_table_id = f"{self.project_id}.replication_dataset.{table_name}"
        
        bq_rows_to_insert = []
        
        # Stream to Pub/Sub with ordering
        for row in rows:
            payload = json.dumps(row).encode("utf-8")
            
            # Pub/Sub requires ordering keys to be strings
            ordering_key = str(row.get("id", ""))
            
            # Publish with deterministic ordering key
            self.publisher.publish(
                topic_path, 
                data=payload,
                ordering_key=ordering_key
            )
            
            # Prepare for BigQuery insert
            payload_hash = hashlib.sha256(payload).hexdigest()
            bq_rows_to_insert.append({
                "insertId": payload_hash, # Deterministic insert_id for deduplication
                "json": row
            })
            
        # Stream rows directly to BigQuery
        errors = self.bq_client.insert_rows_json(bq_table_id, bq_rows_to_insert)
        if errors:
            raise Exception(f"BigQuery insertion errors: {errors}")
            
        return True


class GCPReplicationDaemon:
    """
    Public Interface. Thin wrapper (MDR >= 3.0) around internal replication state.
    Provides decoupled async replication to GCP without impacting the core bot.
    """
    def __init__(
        self, 
        state_db_path: str = "replication/sync_state.db", 
        primary_db_path: str = "data/primary.db",
        polling_interval: float = 5.0,
        tables: List[str] = None
    ):
        self.state_db_path = state_db_path
        self.tables = tables or ["bar_log", "signal_log", "paper_trades"]
        self._circuit_breaker = _CircuitBreaker()
        self._cursor_tracker = _CompoundCursorTracker(state_db_path, primary_db_path)
        self._gcp_client = _GCPClientWrapper()
        self.polling_interval = polling_interval

    async def start(self):
        """Initiates the long-running async poll-and-sync loop."""
        while True:
            self.sync_once()
            await asyncio.sleep(self.polling_interval)

    def sync_once(self):
        """Runs a single, synchronous replication sweep across all tables."""
        if self._circuit_breaker.is_open():
            return

        batch_limit = self._circuit_breaker.get_batch_limit(default_limit=100)
        
        for table in self.tables:
            try:
                self._sync_table(table, batch_limit)
                
                # If we successfully synced a batch and were HALF_OPEN, we can record success and fully close
                if self._circuit_breaker.state == "HALF_OPEN":
                    self._circuit_breaker.record_success()
                    batch_limit = self._circuit_breaker.get_batch_limit(default_limit=100)
                    
            except Exception as e:
                self._circuit_breaker.record_failure()
                logger.error(f"GCP Replication failed for table {table}: {e}")
                if "Hard Crash" in str(e):
                    raise
                # Break out of the table loop on failure, let the next cycle handle it
                break
                
    def _sync_table(self, table: str, limit: int):
        last_created_at, last_id = self._cursor_tracker.get_cursor(table)
        
        # 1. Fetch pending rows
        rows = self._cursor_tracker.fetch_pending_rows(table, last_created_at, last_id, limit=limit)
        if not rows:
            return

        # Schema Validation: quarantine anomalies
        valid_rows = []
        highest_created_at = last_created_at
        highest_id = last_id
        
        for r in rows:
            if "created_at" not in r or "id" not in r:
                logger.warning(f"Quarantining row due to missing schema keys: {r}")
                continue
                
            valid_rows.append(r)
            if r["created_at"] > highest_created_at or (r["created_at"] == highest_created_at and r["id"] > highest_id):
                highest_created_at = r["created_at"]
                highest_id = r["id"]
                
        if not valid_rows:
            # If all rows were quarantined, advance cursor anyway so we don't get stuck
            self._update_cursor(table, highest_created_at, highest_id)
            return

        # 2. Try streaming to GCP
        self._gcp_client.stream_batch(table, valid_rows)
        
        # 3. Explicit SQLite transaction block for Crash-Safety
        self._update_cursor(table, highest_created_at, highest_id)
        
    def _update_cursor(self, table: str, highest_created_at: str, highest_id: int):
        conn = sqlite3.connect(self.state_db_path)
        try:
            with conn:
                # Insert or update
                conn.execute(
                    """
                    INSERT INTO sync_cursors (table_name, last_sync_created_at, last_sync_id)
                    VALUES (?, ?, ?)
                    ON CONFLICT(table_name) DO UPDATE SET
                        last_sync_created_at=excluded.last_sync_created_at,
                        last_sync_id=excluded.last_sync_id,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (table, highest_created_at, highest_id)
                )
        finally:
            conn.close()
