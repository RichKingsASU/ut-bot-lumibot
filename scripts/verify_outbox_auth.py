#!/usr/bin/env python3
import os
import sys
import httpx

def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("FAIL: SUPABASE_URL and a key (SECRET_KEY or SERVICE_ROLE_KEY) must be set.")
        sys.exit(1)

    url = url.rstrip("/")

    # Detect branch
    if key.startswith("sb_"):
        branch = "apikey ONLY (sb_ prefix)"
    else:
        parts = key.split(".")
        if len(parts) == 3 and parts[0].startswith("eyJ"):
            branch = "apikey AND Authorization: Bearer (JWT)"
        else:
            branch = "apikey ONLY (unrecognized format)"

    print(f"Detected key branch: {branch}")

    try:
        # Request 1: apikey only
        h1 = {"apikey": key, "Accept": "application/json"}
        r1 = httpx.get(f"{url}/rest/v1/telegram_outbox", headers=h1, params={"limit": 1}, timeout=10)
        print(f"Request 1 (apikey only) status code: {r1.status_code}")

        # Request 2: apikey + Bearer
        h2 = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
        r2 = httpx.get(f"{url}/rest/v1/telegram_outbox", headers=h2, params={"limit": 1}, timeout=10)
        print(f"Request 2 (apikey + Bearer) status code: {r2.status_code}")

        if r1.status_code in (200, 201, 204) or r2.status_code in (200, 201, 204):
            print("Verdict: PASS")
        else:
            print("Verdict: FAIL")

    except Exception as e:
        print("Verdict: FAIL (Exception occurred)")
        sys.exit(1)

if __name__ == "__main__":
    main()
