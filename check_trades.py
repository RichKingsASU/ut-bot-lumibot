import httpx
import os
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

try:
    resp = httpx.get(f"{url}/rest/v1/paper_trades?limit=5", headers={
        "apikey": key,
        "Authorization": f"Bearer {key}"
    })
    print(f"Status Code: {resp.status_code}")
    print(f"Data: {resp.text[:1000]}")
except Exception as e:
    print(f"Error: {e}")
