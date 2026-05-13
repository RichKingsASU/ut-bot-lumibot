import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

def check_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return "FAIL: Missing Supabase credentials"
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}"
    }
    
    tables = ["bot_status", "sessions", "system_alerts", "system_audit"]
    results = {}
    for table in tables:
        try:
            # Check if table is queryable
            resp = httpx.get(f"{url}/rest/v1/{table}?select=count", headers=headers, timeout=5)
            if resp.status_code == 200:
                results[table] = "PASS"
            else:
                results[table] = f"FAIL (HTTP {resp.status_code})"
        except Exception as e:
            results[table] = f"ERROR ({str(e)})"
    return results

def check_alpaca():
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")
    is_paper = os.getenv("ALPACA_IS_PAPER", "true").lower() == "true"
    base_url = "https://paper-api.alpaca.markets" if is_paper else "https://api.alpaca.markets"
    
    if not api_key or not api_secret:
        return "FAIL: Missing Alpaca credentials"
    
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }
    
    try:
        resp = httpx.get(f"{base_url}/v2/account", headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "connection": "PASS",
                "status": data.get("status"),
                "is_paper": is_paper,
                "trading_blocked": data.get("trading_blocked"),
                "account_number": data.get("account_number")
            }
        else:
            return f"FAIL (HTTP {resp.status_code}: {resp.text})"
    except Exception as e:
        return f"ERROR ({str(e)})"

if __name__ == "__main__":
    print("--- PREFLIGHT CHECK ---")
    print("\n[SUPABASE TABLES]")
    sb = check_supabase()
    for t, res in sb.items():
        print(f"  {t}: {res}")
        
    print("\n[ALPACA CONNECTION]")
    alp = check_alpaca()
    if isinstance(alp, dict):
        for k, v in alp.items():
            print(f"  {k}: {v}")
    else:
        print(f"  {alp}")
