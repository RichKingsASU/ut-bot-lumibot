import httpx
import os
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print(f"URL: {url}")
print(f"Key present: {bool(key)}")

try:
    resp = httpx.get(f"{url}/rest/v1/bot_status", headers={
        "apikey": key,
        "Authorization": f"Bearer {key}"
    })
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
