import os
import sys
import subprocess
import httpx
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Ensure we can import send_telegram
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from send_telegram import send_message

# ── Staleness thresholds (named constants) ───────────────────────────────────
AGENT_SIGNALS_STALE_MIN = 30   # Check 1: agent_signals freshness
BOT_HEARTBEAT_STALE_MIN = 5    # Check 2: global bot_status heartbeat freshness
ALPACA_MIN_EQUITY = 50000      # Check 5: minimum account equity

# Check 6: component-level heartbeat freshness (component_status table).
# Per-process because cadences differ:
#   - 'main'       beats every 30s   → 300s (5 min) gives a 10x margin.
#   - 'run_agents' beats only at the END of each ~15min cycle → 1500s (25 min)
#     = one cycle interval + ~10 min margin for a long-running cycle.
# Only processes that ACTUALLY emit a component heartbeat belong here; adding a
# process that does not write one would produce a permanent false alarm. The
# collectors (news/tick/option/sentiment/vectors) are not yet wired to emit
# heartbeats — wire them in component_heartbeat first, then add them here.
COMPONENT_STALENESS_SECONDS = {
    "main": 300,
    "run_agents": 1500,
}

def run_check1():
    load_dotenv('/home/k2/ut-bot-lumibot/.env')
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        return "ALERT: Supabase credentials missing"
    h = {'apikey': key, 'Authorization': f'Bearer {key}'}
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=AGENT_SIGNALS_STALE_MIN)).isoformat()
    try:
        r = httpx.get(f'{url}/rest/v1/agent_signals', headers=h,
            params={'select':'created_at','order':'created_at.desc','limit':'1'},
            timeout=10)
        rows = r.json()
        if not rows or rows[0]['created_at'] < cutoff:
            return "ALERT: agent signals stalled"
    except Exception as e:
        return f"ALERT: agent signals check failed: {e}"
    return "OK"

def run_check2():
    load_dotenv('/home/k2/ut-bot-lumibot/.env')
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        return "ALERT: Supabase credentials missing"
    h = {'apikey': key, 'Authorization': f'Bearer {key}'}
    try:
        r = httpx.get(f'{url}/rest/v1/bot_status', headers=h,
            params={'select':'last_heartbeat','limit':'1'},
            timeout=10)
        rows = r.json()
        if rows:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=BOT_HEARTBEAT_STALE_MIN)).isoformat()
            if rows[0]['last_heartbeat'] < cutoff:
                return "ALERT: bot heartbeat stale"
        else:
            return "ALERT: no bot status records found"
    except Exception as e:
        return f"ALERT: bot heartbeat check failed: {e}"
    return "OK"

def run_check3():
    alerts = []
    for session in ["agents", "crypto-bot", "trading-bot"]:
        res = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
        if res.returncode != 0:
            alerts.append(f"ALERT: {session} session dead")
    return alerts

def run_check4():
    alerts = []
    try:
        res = subprocess.run(
            'docker ps --filter "status=exited" --format "{{.Names}}"',
            shell=True, capture_output=True, text=True
        )
        if res.returncode == 0:
            for line in res.stdout.strip().split('\n'):
                name = line.strip()
                if name and 'supabase' not in name:
                    alerts.append(f"ALERT: {name} container exited")
    except Exception as e:
        alerts.append(f"ALERT: docker check failed: {e}")
    return alerts

def run_check5():
    load_dotenv('/home/k2/ut-bot-lumibot/.env')
    try:
        r = httpx.get(
            f'{os.getenv("ALPACA_BASE_URL")}/v2/account',
            headers={
                'APCA-API-KEY-ID': os.getenv('ALPACA_API_KEY'),
                'APCA-API-SECRET-KEY': os.getenv('ALPACA_API_SECRET')
            }, timeout=5)
        if r.status_code != 200:
            return f"ALERT: Alpaca unreachable status code {r.status_code}"
        equity = float(r.json().get('equity', 0))
        if equity < ALPACA_MIN_EQUITY:
            return f"ALERT: equity low ${equity:,.0f}"
    except Exception as e:
        return f"ALERT: Alpaca unreachable {e}"
    return "OK"

def run_check6():
    """Component-level freshness: detects PARTIAL failure (one process dead
    while the global heartbeat stays fresh)."""
    load_dotenv('/home/k2/ut-bot-lumibot/.env')
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        return ["ALERT: Supabase credentials missing"]
    h = {'apikey': key, 'Authorization': f'Bearer {key}'}
    try:
        r = httpx.get(f'{url}/rest/v1/component_status', headers=h,
            params={'select': 'process_name,last_heartbeat,last_successful_cycle_id,status'},
            timeout=10)
        rows = {row['process_name']: row for row in r.json()}
    except Exception as e:
        return [f"ALERT: component_status check failed: {e}"]

    alerts = []
    now = datetime.now(timezone.utc)
    for proc, max_age in COMPONENT_STALENESS_SECONDS.items():
        row = rows.get(proc)
        if not row:
            alerts.append(f"ALERT: component '{proc}' has no heartbeat row")
            continue
        cutoff = (now - timedelta(seconds=max_age)).isoformat()
        if not row.get('last_heartbeat') or row['last_heartbeat'] < cutoff:
            alerts.append(f"ALERT: component '{proc}' heartbeat stale (>{max_age}s)")
        # run_agents writes its heartbeat only on successful cycle completion,
        # so a missing cycle id means no cycle has ever succeeded.
        if proc == 'run_agents' and row.get('last_successful_cycle_id') is None:
            alerts.append("ALERT: run_agents has no successful cycle recorded")
    return alerts

def main():
    verbose = "--verbose" in sys.argv
    alerts = []
    
    # Check 1
    c1 = run_check1()
    if verbose:
        print(f"Check 1 (Agent Signals): {c1}")
    if c1.startswith("ALERT"):
        alerts.append(c1)
        
    # Check 2
    c2 = run_check2()
    if verbose:
        print(f"Check 2 (Bot Heartbeat): {c2}")
    if c2.startswith("ALERT"):
        alerts.append(c2)
        
    # Check 3
    c3 = run_check3()
    if verbose:
        print(f"Check 3 (Tmux Sessions): {c3 if c3 else 'OK'}")
    alerts.extend(c3)
    
    # Check 4
    c4 = run_check4()
    if verbose:
        print(f"Check 4 (Docker Containers): {c4 if c4 else 'OK'}")
    alerts.extend(c4)
    
    # Check 5
    c5 = run_check5()
    if verbose:
        print(f"Check 5 (Alpaca): {c5}")
    if c5.startswith("ALERT"):
        alerts.append(c5)

    # Check 6
    c6 = run_check6()
    if verbose:
        print(f"Check 6 (Component Heartbeats): {c6 if c6 else 'OK'}")
    alerts.extend(c6)

    if alerts:
        # Get ET timezone time formatted as HH:MM
        utc_now = datetime.now(timezone.utc)
        et_now = utc_now - timedelta(hours=4)
        time_str = et_now.strftime("%H:%M")
        
        msg_lines = [f"⚠️ Watchdog Alert {time_str} ET"]
        for alert in alerts:
            msg_lines.append(alert)
        msg_lines.append("Check tmux/docker immediately.")
        
        msg = "\n".join(msg_lines)
        print("ALERTS DETECTED:")
        print(msg)
        send_message(msg)
    else:
        if verbose:
            print("All checks passed. Silent.")
        else:
            # Silent output as requested by prompt
            pass

if __name__ == "__main__":
    main()
