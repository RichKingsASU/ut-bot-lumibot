#!/usr/bin/env python3
import os
import sys
import subprocess
import httpx
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/home/k2/ut-bot-lumibot/.env')

alerts = []

# --- CHECK 1: Agent signals flowing in last 30min ---
try:
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        alerts.append("ALERT: Supabase credentials missing in .env")
    else:
        h = {'apikey': key, 'Authorization': f'Bearer {key}'}
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        r = httpx.get(f'{url}/rest/v1/agent_signals', headers=h,
                      params={'select':'created_at','order':'created_at.desc','limit':'1'},
                      timeout=10)
        if r.status_code != 200:
            alerts.append(f"ALERT: agent signals check HTTP error {r.status_code}")
        else:
            rows = r.json()
            if not rows or rows[0]['created_at'] < cutoff:
                alerts.append('ALERT: agent signals stalled')
except Exception as e:
    alerts.append(f'ALERT: agent signals check failed - {e}')

# --- CHECK 2: Bot heartbeat fresh ---
try:
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if url and key:
        h = {'apikey': key, 'Authorization': f'Bearer {key}'}
        r = httpx.get(f'{url}/rest/v1/bot_status', headers=h,
                      params={'select':'last_heartbeat','limit':'1'},
                      timeout=10)
        if r.status_code != 200:
            alerts.append(f"ALERT: bot status check HTTP error {r.status_code}")
        else:
            rows = r.json()
            if rows:
                cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
                if rows[0]['last_heartbeat'] < cutoff:
                    alerts.append('ALERT: bot heartbeat stale')
            else:
                alerts.append('ALERT: bot heartbeat check returned no rows')
except Exception as e:
    alerts.append(f'ALERT: bot heartbeat check failed - {e}')

# --- CHECK 3: Critical sessions alive ---
try:
    sessions = [
        ("agents", "ALERT: agents session dead"),
        ("crypto-bot", "ALERT: crypto-bot dead"),
        ("trading-bot", "ALERT: trading-bot dead")
    ]
    for session, alert_msg in sessions:
        res = subprocess.run(f"tmux has-session -t {session} 2>/dev/null", shell=True)
        if res.returncode != 0:
            alerts.append(alert_msg)
except Exception as e:
    alerts.append(f'ALERT: tmux check failed - {e}')

# --- CHECK 4: Docker containers running ---
try:
    docker_cmd = 'docker ps --filter "status=exited" --format "{{.Names}}" | grep -v supabase'
    res = subprocess.run(docker_cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        for name in res.stdout.splitlines():
            name = name.strip()
            if name:
                alerts.append(f"ALERT: {name} container exited")
except Exception as e:
    alerts.append(f'ALERT: docker check failed - {e}')

# --- CHECK 5: Alpaca accessible ---
try:
    alpaca_url = os.getenv("ALPACA_BASE_URL")
    api_key = os.getenv('ALPACA_API_KEY')
    api_secret = os.getenv('ALPACA_API_SECRET')
    if not alpaca_url or not api_key or not api_secret:
        alerts.append("ALERT: Alpaca credentials missing in .env")
    else:
        r = httpx.get(
            f'{alpaca_url}/v2/account',
            headers={
                'APCA-API-KEY-ID': api_key,
                'APCA-API-SECRET-KEY': api_secret
            }, timeout=5)
        if r.status_code != 200:
            alerts.append(f"ALERT: Alpaca HTTP error {r.status_code}")
        else:
            equity = float(r.json().get('equity', 0))
            if equity < 50000:
                alerts.append(f'ALERT: equity low ${equity:,.0f}')
except Exception as e:
    alerts.append(f'ALERT: Alpaca unreachable {e}')

# --- PROCESS ALERTS ---
if alerts:
    # 1. Print alerts to stdout
    for alert in alerts:
        print(alert)

    # 2. Send Telegram to chat ID 8641189809
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in .env", file=sys.stderr)
        sys.exit(1)

    # Get current Eastern Time (ET)
    try:
        et_time = subprocess.check_output("TZ=America/New_York date +%H:%M", shell=True).decode().strip()
    except Exception:
        # Fallback to local time if date command fails
        et_time = datetime.now().strftime('%H:%M')

    alerts_list = "\n".join(alerts)
    msg = f"⚠️ Watchdog Alert {et_time} ET\n{alerts_list}\nCheck tmux/docker immediately."

    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        payload = {
            "chat_id": "8641189809",
            "text": msg
        }
        resp = httpx.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"ERROR: Telegram message failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to send Telegram: {e}", file=sys.stderr)
        sys.exit(1)
