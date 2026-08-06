#!/usr/bin/env python3
import os
import sys
import json
import socket
from urllib.parse import urlparse
from dotenv import load_dotenv

def safe_print(message: str, status: str = "INFO"):
    status_markers = {
        "PASS": "[PASS]",
        "FAIL": "[FAIL]",
        "WARN": "[WARN]",
        "INFO": "[INFO]"
    }
    marker = status_markers.get(status, "[INFO]")
    safe_msg = message.encode("ascii", "replace").decode("ascii")
    print(f"{marker} {safe_msg}")

def check_tcp_port(host: str, port: int, timeout: int = 5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def validate_environment():
    env_path = ".env.staging"
    if not os.path.exists(env_path):
        safe_print(f"Environment file {env_path} not found.", "FAIL")
        sys.exit(1)

    safe_print(f"Loading {env_path}...", "INFO")
    load_dotenv(env_path)

    # 1. Parse SUPABASE_DSN
    supabase_dsn = os.getenv("SUPABASE_DSN")
    if not supabase_dsn:
        safe_print("SUPABASE_DSN is missing from .env.staging.", "FAIL")
        sys.exit(1)
    
    if not supabase_dsn.startswith("postgresql://"):
        safe_print("SUPABASE_DSN does not begin with 'postgresql://'.", "FAIL")
        sys.exit(1)
    
    safe_print("SUPABASE_DSN protocol format is correct.", "PASS")

    # 2. Parse GCP_SERVICE_ACCOUNT_JSON
    gcp_creds_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not gcp_creds_json:
        safe_print("GCP_SERVICE_ACCOUNT_JSON is missing from .env.staging.", "FAIL")
        sys.exit(1)
    
    try:
        creds_dict = json.loads(gcp_creds_json)
        required_keys = ['private_key', 'client_email', 'token_uri']
        missing_keys = [key for key in required_keys if key not in creds_dict]
        
        if missing_keys:
            safe_print(f"GCP_SERVICE_ACCOUNT_JSON is missing required keys: {missing_keys}", "FAIL")
            sys.exit(1)
            
        safe_print("GCP_SERVICE_ACCOUNT_JSON is valid JSON and contains required keys.", "PASS")
    except json.JSONDecodeError as e:
        safe_print(f"GCP_SERVICE_ACCOUNT_JSON is not valid JSON: {e}", "FAIL")
        sys.exit(1)

    # 3. TCP Socket Tests
    safe_print("Testing TCP connectivity to required services...", "INFO")
    
    # Extract host from Supabase DSN
    try:
        parsed_dsn = urlparse(supabase_dsn)
        supabase_host = parsed_dsn.hostname
        supabase_port = parsed_dsn.port or 5432
        
        if supabase_host:
            if check_tcp_port(supabase_host, supabase_port):
                safe_print(f"Successfully reached Supabase PostgreSQL at {supabase_host}:{supabase_port}", "PASS")
            else:
                safe_print(f"Failed to reach Supabase PostgreSQL at {supabase_host}:{supabase_port}", "FAIL")
        else:
            safe_print("Could not extract hostname from SUPABASE_DSN", "WARN")
    except Exception as e:
        safe_print(f"Error parsing SUPABASE_DSN for port check: {e}", "WARN")

    # Check Google Cloud API
    gcp_api_host = "oauth2.googleapis.com"
    if check_tcp_port(gcp_api_host, 443):
         safe_print(f"Successfully reached Google Cloud API at {gcp_api_host}:443", "PASS")
    else:
         safe_print(f"Failed to reach Google Cloud API at {gcp_api_host}:443", "FAIL")
         
    gcp_pubsub_host = "pubsub.googleapis.com"
    if check_tcp_port(gcp_pubsub_host, 443):
         safe_print(f"Successfully reached GCP Pub/Sub at {gcp_pubsub_host}:443", "PASS")
    else:
         safe_print(f"Failed to reach GCP Pub/Sub at {gcp_pubsub_host}:443", "FAIL")
         
    gcp_bq_host = "bigquery.googleapis.com"
    if check_tcp_port(gcp_bq_host, 443):
         safe_print(f"Successfully reached GCP BigQuery at {gcp_bq_host}:443", "PASS")
    else:
         safe_print(f"Failed to reach GCP BigQuery at {gcp_bq_host}:443", "FAIL")
         
    safe_print("Pre-flight validation complete.", "INFO")

if __name__ == "__main__":
    validate_environment()
