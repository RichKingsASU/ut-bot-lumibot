#!/usr/bin/env python3
"""
preflight_validator.py - Pre-Flight Env & Token Budget Validator
Verifies networking routes, credentials formatting, and token budget allocations
before running live integration sockets.
"""

import os
import json
import socket
from urllib.parse import urlparse

# Ensure we read .env.staging directly
env_staging_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.staging")
if os.path.exists(env_staging_path):
    with open(env_staging_path, "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

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
    # 1. Check SUPABASE_DSN
    supabase_dsn = os.getenv("SUPABASE_DSN")
    if not supabase_dsn:
        safe_print("SUPABASE_DSN is missing from the environment.", "FAIL")
    elif not supabase_dsn.startswith("postgresql://"):
        safe_print("SUPABASE_DSN does not begin with 'postgresql://'.", "FAIL")
    else:
        safe_print("SUPABASE_DSN format is valid.", "PASS")
        
        # Test TCP connection to Supabase host
        try:
            parsed = urlparse(supabase_dsn)
            host = parsed.hostname
            port = parsed.port or 5432
            if host:
                if check_tcp_port(host, port):
                    safe_print(f"TCP connection to Supabase database {host}:{port} successful.", "PASS")
                else:
                    safe_print(f"TCP connection to Supabase database {host}:{port} failed.", "FAIL")
        except Exception as e:
            safe_print(f"Failed to parse or test Supabase DSN host: {e}", "FAIL")

    # 2. Check GCP_SERVICE_ACCOUNT_JSON
    gcp_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not gcp_json:
        safe_print("GCP_SERVICE_ACCOUNT_JSON is missing from the environment.", "FAIL")
    else:
        try:
            creds = json.loads(gcp_json)
            missing_keys = [k for k in ("private_key", "client_email", "token_uri") if k not in creds]
            if missing_keys:
                safe_print(f"GCP_SERVICE_ACCOUNT_JSON is missing core keys: {missing_keys}", "FAIL")
            else:
                safe_print("GCP_SERVICE_ACCOUNT_JSON is valid and contains core keys.", "PASS")
        except json.JSONDecodeError:
            safe_print("GCP_SERVICE_ACCOUNT_JSON is not a valid JSON string.", "FAIL")

    # 3. Test TCP connection to Google Cloud API
    if check_tcp_port("pubsub.googleapis.com", 443):
        safe_print("TCP connection to Google Cloud API (port 443) successful.", "PASS")
    else:
        safe_print("TCP connection to Google Cloud API (port 443) failed.", "FAIL")

    # 4. Token Budget Allocation Calculation
    # Token_Limit_Total = Budget_System_Instruction + Budget_Dynamic_Retrieval + Budget_Tool_Schemas + Budget_Output_Space
    budget_sys = 5000
    budget_dyn = 20000
    budget_tool = 5000
    budget_out = 8000
    total_limit = budget_sys + budget_dyn + budget_tool + budget_out
    
    safe_print(f"Token Budget Allocations:", "INFO")
    safe_print(f"  System Instruction: {budget_sys}", "INFO")
    safe_print(f"  Dynamic Retrieval:  {budget_dyn}", "INFO")
    safe_print(f"  Tool Schemas:       {budget_tool}", "INFO")
    safe_print(f"  Output Space:       {budget_out}", "INFO")
    safe_print(f"  Total Token Limit:  {total_limit}", "INFO")

if __name__ == "__main__":
    validate_environment()
