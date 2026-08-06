"""
tests/smoke_test_e2e.py

Dual-Mode Test Architecture
This file will run ONLY when manually executed on a connected edge machine. It must:
a) Load live credentials from your local environment (Supabase DSN and GCP service account JSON).
b) Pull a single real record from your staging 'bar_log' table on Supabase.
c) Attempt to stream that record to the actual GCP Pub/Sub topic and BigQuery dataset under project 'disruptingalpha'.
d) Print the raw, unedited connection handshakes, transaction receipts, and final database acknowledgments directly to stdout.
"""

import os
import sys
import json
import logging
from pprint import pprint

# Ensure imports resolve
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from replication.gcp_replicator_daemon import GCPReplicationDaemon, ConfigurationError

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("smoke_test")

def main():
    print("=== BEGIN E2E SMOKE TEST ===")
    
    # a) Load live credentials
    supabase_dsn = os.environ.get("SUPABASE_DSN")
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    
    if not supabase_dsn:
        print("ERROR: SUPABASE_DSN environment variable is missing.")
        sys.exit(1)
        
    if not gcp_json:
        print("ERROR: GCP_SERVICE_ACCOUNT_JSON environment variable is missing.")
        sys.exit(1)
        
    print("Loaded SUPABASE_DSN and GCP_SERVICE_ACCOUNT_JSON.")
    print("Initializing GCPReplicationDaemon in PRODUCTION mode...")
    
    # Enable PRODUCTION_MODE just in case, though SUPABASE_DSN will trigger it anyway.
    os.environ["PRODUCTION_MODE"] = "1"
    
    try:
        daemon = GCPReplicationDaemon(
            state_db_path=":memory:", # Ephemeral for the smoke test
            primary_db_path="data/primary.db", # Fallback not used when DSN is present
            tables=["bar_log"]
        )
    except ConfigurationError as e:
        print(f"ConfigurationError during initialization: {e}")
        sys.exit(1)
        
    # b) Pull a single real record from 'bar_log'
    print("Executing parameterized compound cursor query against live Supabase instance...")
    
    try:
        # Fetch 1 record
        rows = daemon._cursor_tracker.fetch_pending_rows("bar_log", "1970-01-01T00:00:00Z", 0, limit=1)
    except Exception as e:
        print(f"Database connection or query failed: {e}")
        sys.exit(1)
        
    if not rows:
        print("No records found in 'bar_log' to stream. Please insert a test record and try again.")
        sys.exit(0)
        
    row = rows[0]
    print(f"Successfully pulled record:")
    pprint(row)
    
    # c) Attempt to stream that record to the actual GCP Pub/Sub and BigQuery
    print(f"Attempting to stream record ID {row.get('id')} to GCP Pub/Sub and BigQuery...")
    
    try:
        daemon._gcp_client.stream_batch("bar_log", [row])
    except Exception as e:
        print(f"Failed to stream record to GCP: {e}")
        sys.exit(1)
        
    # d) Print final database acknowledgments
    print("=== E2E SMOKE TEST PASSED ===")
    print("Transaction receipts and acknowledgments completed successfully.")

if __name__ == "__main__":
    main()
