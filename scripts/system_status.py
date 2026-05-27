#!/usr/bin/env python3
import subprocess
import os
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')

def check_tmux(session):
    return subprocess.run(['tmux', 'has-session', '-t', session], capture_output=True).returncode == 0

def check_docker(container):
    result = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', container], capture_output=True, text=True)
    return result.stdout.strip() == 'true'

def check_supabase():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key: return False
    try:
        r = httpx.get(f'{url}/rest/v1/', headers={'apikey': key}, timeout=2.0)
        return r.status_code == 200
    except:
        return False

def check_alpaca():
    key = os.getenv('APCA_API_KEY_ID')
    secret = os.getenv('APCA_API_SECRET_KEY')
    if not key or not secret: return False
    try:
        r = httpx.get('https://paper-api.alpaca.markets/v2/account', headers={'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret}, timeout=2.0)
        return r.status_code == 200
    except:
        return False

sessions = ["crypto-bot", "trading-bot", "sentiment", "vectors", "options", "agents", "telegram-bot"]
containers = ["ut-bot-lumibot-questdb-1", "ut-bot-lumibot-nats-1", "ut-bot-lumibot-qdrant-1", "tick-collector", "news-collector"]

print("--- SYSTEM STATUS ---")
s_ok = all(check_tmux(s) for s in sessions)
print(f"All tmux sessions: {'✅' if s_ok else '❌'}")
c_ok = all(check_docker(c) for c in containers)
print(f"Docker containers: {'✅' if c_ok else '❌'}")
sup_ok = check_supabase()
print(f"Supabase reachable: {'✅' if sup_ok else '❌'}")
alp_ok = check_alpaca()
print(f"Alpaca reachable: {'✅' if alp_ok else '❌'}")

try:
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    headers = {'apikey': key, 'Authorization': f'Bearer {key}', 'Prefer': 'count=exact'}
    now = datetime.now(timezone.utc)
    
    r_agent = httpx.get(f'{url}/rest/v1/agent_signals?select=created_at&order=created_at.desc&limit=1', headers=headers, timeout=2.0)
    if r_agent.status_code == 200 and r_agent.json():
        last_agent = datetime.fromisoformat(r_agent.json()[0]['created_at'].replace('Z', '+00:00'))
        agent_ago = int((now - last_agent).total_seconds() / 60)
        print(f"Agent last cycle: {agent_ago} minutes ago")
    else:
        print("Agent last cycle: Unknown")

    r_hb = httpx.get(f'{url}/rest/v1/bot_status?select=last_heartbeat&order=last_heartbeat.desc&limit=1', headers=headers, timeout=2.0)
    if r_hb.status_code == 200 and r_hb.json():
        last_hb = datetime.fromisoformat(r_hb.json()[0]['last_heartbeat'].replace('Z', '+00:00'))
        hb_ago = int((now - last_hb).total_seconds())
        print(f"Bot heartbeat: {hb_ago} seconds ago")
    else:
        print("Bot heartbeat: Unknown")
except Exception as e:
    print(f"Agent last cycle: Error ({e})")
    print(f"Bot heartbeat: Error ({e})")

overall = '🟢' if (s_ok and c_ok and sup_ok and alp_ok) else '🔴'
print(f"Overall: {overall}")
