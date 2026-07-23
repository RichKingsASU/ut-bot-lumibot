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

    from common.supabase_auth import get_supabase_headers
    headers = get_supabase_headers(key, extra={"Accept": "application/json"})

    if "Authorization" in headers:
        branch = "apikey AND Authorization: Bearer (JWT)"
    else:
        branch = "apikey ONLY (sb_ prefix or other)"

    print(f"Detected key branch: {branch}")

    try:
        r = httpx.get(f"{url}/rest/v1/telegram_outbox", headers=headers, params={"limit": 1}, timeout=10)
        print(f"Request status code: {r.status_code}")

        if r.status_code in (200, 201, 204):
            print("Verdict: PASS")
        else:
            print("Verdict: FAIL")

    except Exception as e:
        print("Verdict: FAIL (Exception occurred)")
        sys.exit(1)

if __name__ == "__main__":
    main()

