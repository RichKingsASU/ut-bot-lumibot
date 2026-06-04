#!/usr/bin/env python3
import os
import sys
import httpx
import subprocess
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

def main():
    env_path = '/home/k2/ut-bot-lumibot/.env'
    load_dotenv(env_path)
    
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    alpaca_url = os.getenv('ALPACA_BASE_URL')
    alpaca_key = os.getenv('ALPACA_API_KEY')
    alpaca_secret = os.getenv('ALPACA_API_SECRET')
    
    alerts = []
    
    # ── CHECK 1 — Agent signals flowing in last 30min ──
    try:
        h = {'apikey': key, 'Authorization': f'Bearer {key}'}
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        r = httpx.get(f'{url}/rest/v1/agent_signals', headers=h,
            params={'select':'created_at','order':'created_at.desc','limit':'1'}, timeout=10)
        r.raise_for_status()
        rows = r.json()
        if not rows or rows[0]['created_at'] < cutoff:
            alerts.append('ALERT: agent signals stalled')
    except Exception as e:
        alerts.append(f'ALERT: agent signals check failed: {e}')
        
    # ── CHECK 2 — Bot heartbeat fresh ──
    try:
        h = {'apikey': key, 'Authorization': f'Bearer {key}'}
        r = httpx.get(f'{url}/rest/v1/bot_status', headers=h,
            params={'select':'last_heartbeat','limit':'1'}, timeout=10)
        r.raise_for_status()
        rows = r.json()
        if rows:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            if rows[0]['last_heartbeat'] < cutoff:
                alerts.append('ALERT: bot heartbeat stale')
    except Exception as e:
        alerts.append(f'ALERT: bot heartbeat check failed: {e}')
        
    # ── CHECK 3 — Critical services alive ──
    for service, unit, expected_msg in [
        ('agents', 'da-agents', 'ALERT: agents service dead'),
        ('crypto-bot', 'da-crypto-bot', 'ALERT: crypto-bot dead'),
        ('trading-bot', 'da-trading-bot', 'ALERT: trading-bot dead')
    ]:
        res = subprocess.run(['systemctl', 'is-active', '--quiet', unit])
        if res.returncode != 0:
            alerts.append(expected_msg)
            
    # ── CHECK 4 — Docker containers running ──
    try:
        res = subprocess.run(
            'docker ps --filter "status=exited" --format "{{.Names}}"',
            shell=True, capture_output=True, text=True
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                name = line.strip()
                if name and 'supabase' not in name:
                    alerts.append(f'ALERT: {name} container exited')
    except Exception as e:
        alerts.append(f'ALERT: docker check failed: {e}')
        
    # ── CHECK 5 — Alpaca accessible ──
    try:
        r = httpx.get(
            f'{alpaca_url}/v2/account',
            headers={
                'APCA-API-KEY-ID': alpaca_key,
                'APCA-API-SECRET-KEY': alpaca_secret
            }, timeout=5)
        r.raise_for_status()
        equity = float(r.json().get('equity', 0))
        if equity < 50000:
            alerts.append(f'ALERT: equity low ${equity:,.0f}')
    except Exception as e:
        alerts.append(f'ALERT: Alpaca unreachable {e}')
        
    # Process alerts
    if alerts:
        # Calculate current time in Eastern Time (ET)
        # EDT (May) is UTC - 4 hours
        et_now = datetime.now(timezone.utc) - timedelta(hours=4)
        time_str = et_now.strftime('%H:%M')
        
        alert_lines = '\n'.join(alerts)
        message = f"⚠️ Watchdog Alert {time_str} ET\n{alert_lines}\nCheck tmux/docker immediately."
        
        print("ALERTS DETECTED:")
        print(message)
        
        # Send Telegram
        if telegram_token:
            chat_id = "8641189809"
            tg_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message
            }
            try:
                tg_res = httpx.post(tg_url, json=payload, timeout=10)
                if tg_res.status_code == 200:
                    print("Telegram alert sent successfully.")
                else:
                    print(f"Failed to send Telegram alert: {tg_res.status_code} - {tg_res.text}", file=sys.stderr)
            except Exception as e:
                print(f"Error sending Telegram alert: {e}", file=sys.stderr)
        else:
            print("TELEGRAM_BOT_TOKEN not found in environment, could not send Telegram message", file=sys.stderr)
    else:
        print("OK: No alerts detected")

if __name__ == '__main__':
    main()
