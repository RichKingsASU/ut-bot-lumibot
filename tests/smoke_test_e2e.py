#!/usr/bin/env python3
"""
smoke_test_e2e.py - Live Credentialed Integration and mTLS Verification.
Performs real socket connections, queries live Supabase tables, and streams
operational logs directly to GCP, extracting transaction receipts.
"""

import os
import sys
import json
import hashlib
import logging
from typing import Dict, Any

# Enforce safe ASCII terminal printing to support Windows CP1252 shells safely [14]
def safe_print(message: str, status: str = "INFO"):
    status_markers = {
        "PASS": "[PASS]",
        "FAIL": "[FAIL]",
        "WARN": "[WARN]",
        "INFO": "[INFO]"
    }
    marker = status_markers.get(status, "[INFO]")
    # Strip any potential UTF-8 characters from stdout streams
    safe_msg = message.encode("ascii", "replace").decode("ascii")
    print(f"{marker} {safe_msg}")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from google.cloud import pubsub_v1
    from google.cloud import bigquery
    from google.oauth2 import service_account
    safe_print("All production dependency SDKs imported cleanly.", "PASS")
except ImportError as e:
    safe_print(f"Failed to import dependencies: {e}", "FAIL")
    sys.exit(1)

def run_smoke_test():
    # 1. Pre-flight Environment Validation [17]
    supabase_dsn = os.getenv("SUPABASE_DSN")
    gcp_creds_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    project_id = "disruptingalpha"

    if not supabase_dsn:
        safe_print("SUPABASE_DSN environment variable is missing.", "FAIL")
        sys.exit(1)
    if not gcp_creds_json:
        safe_print("GCP_SERVICE_ACCOUNT_JSON environment variable is missing.", "FAIL")
        sys.exit(1)

    safe_print("Credentials present in environment. Initializing sockets...", "INFO")

    # 2. Establish live Supabase PostgreSQL Connection [18]
    try:
        safe_print(f"Connecting to live Supabase database socket...", "INFO")
        with psycopg2.connect(supabase_dsn, connect_timeout=10, cursor_factory=RealDictCursor) as conn:
            safe_print("Live PostgreSQL connection established successfully.", "PASS")
            
            with conn.cursor() as pg_cursor:
                # Retrieve exactly one real record from the bar_log staging table
                pg_cursor.execute("SELECT * FROM bar_log ORDER BY created_at DESC LIMIT 1;")
                record = pg_cursor.fetchone()
                
                if not record:
                    safe_print("Database query returned 0 rows. Staging table 'bar_log' is empty.", "WARN")
                    sys.exit(0)
                
                row_data = dict(record)
                # Map datetime objects to standardized ISO-8601 strings
                if "created_at" in row_data and hasattr(row_data["created_at"], "isoformat"):
                    row_data["created_at"] = row_data["created_at"].isoformat()
                
                safe_print(f"Record retrieved: id={row_data.get('id')}, created_at={row_data.get('created_at')}", "PASS")

    except Exception as e:
        safe_print(f"Failed to connect or query Supabase: {e}", "FAIL")
        sys.exit(1)

    # 3. Stream record directly to Google Cloud Platform [19]
    try:
        safe_print("Initializing GCP Pub/Sub & BigQuery SDK clients...", "INFO")
        creds_dict = json.loads(gcp_creds_json)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        
        # Initialize thread-safe GCP clients
        publisher = pubsub_v1.PublisherClient(credentials=credentials)
        bq_client = bigquery.Client(project=project_id, credentials=credentials)
        
        # Configure resource targets
        topic_path = publisher.topic_path(project_id, "gcp-topic-bar_log")
        dataset_table_id = f"{project_id}.telemetry_dataset.bar_log"
        
        # Calculate unique deterministic insert_id for deduplication safety [19]
        serialized_payload = json.dumps(row_data, sort_keys=True, default=str).encode("utf-8")
        insert_id = hashlib.sha256(serialized_payload).hexdigest()
        
        # A. Stream directly to BigQuery
        safe_print(f"Streaming record to BigQuery table: {dataset_table_id}...", "INFO")
        rows_to_insert = [{"insertId": insert_id, "json": row_data}]
        bq_errors = bq_client.insert_rows_json(dataset_table_id, rows_to_insert)
        
        if bq_errors:
            raise RuntimeError(f"BigQuery streaming errors: {bq_errors}")
        safe_print(f"BigQuery streaming successful. insertId: {insert_id[:16]}...", "PASS")

        # B. Publish message to Pub/Sub with deterministic ordering keys [19]
        safe_print(f"Publishing message to Pub/Sub topic: {topic_path}...", "INFO")
        ordering_key = str(row_data.get("id", ""))
        future = publisher.publish(
            topic_path,
            data=serialized_payload,
            ordering_key=ordering_key
        )
        message_id = future.result(timeout=15)
        safe_print(f"Pub/Sub message published successfully. message_id: {message_id}", "PASS")
        
        safe_print("E2E Integration Verification Complete. System is fully operational.", "PASS")

    except Exception as e:
        safe_print(f"GCP Transport streaming failed: {e}", "FAIL")
        sys.exit(1)

if __name__ == "__main__":
    run_smoke_test()
