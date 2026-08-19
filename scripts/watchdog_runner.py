import os
import sys
import subprocess
import importlib
from datetime import datetime, timezone, timedelta

# Ensure the operational-only Telegram dependency is loaded only when alerting.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


class _LazyHttpx:
    """Keep local functional-health unit tests independent of cloud extras."""
    def __getattr__(self, name):
        return getattr(importlib.import_module("httpx"), name)


httpx = _LazyHttpx()


def load_dotenv(*args, **kwargs):
    return importlib.import_module("dotenv").load_dotenv(*args, **kwargs)


def send_message(message):
    return importlib.import_module("send_telegram").send_message(message)

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
    for service, unit in [("agents", "da-agents"), ("crypto-bot", "da-crypto-bot"), ("trading-bot", "da-trading-bot")]:
        res = subprocess.run(["systemctl", "is-active", "--quiet", unit])
        if res.returncode != 0:
            alerts.append(f"ALERT: {service} service dead")
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

def run_check7():
    """Sentiment data-status visibility.

    Mirrors agents/base_agent.get_recent_sentiment classification at the DB level so
    operators can see when the pipeline will BLOCK on missing sentiment. Additive:
      - Enforced classes (crypto) with zero scored articles in the freshness window
        -> ALERT (the pipeline hard-blocks).
      - Any class with zero RAW articles in the window -> ALERT (collector down).
      - Degrade-only classes (equities) with raw>0 but scored==0 are the KNOWN
        scorer gap (degrade, not block): reported as a note, never an alert, to
        avoid a permanent false alarm.
    Returns (alerts, notes)."""
    # Import enforcement policy / windows from the shared module.
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from agents import sentiment_status as ss
        freshness_hours, staleness_min = ss.FRESHNESS_HOURS, ss.STALENESS_MIN
        enforces = ss.enforces_block
    except Exception:
        freshness_hours, staleness_min = 24, 15
        enforces = lambda ac: ac == "crypto"

    load_dotenv('/home/k2/ut-bot-lumibot/.env')
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        return (["ALERT: Supabase credentials missing"], [])

    h = {'apikey': key, 'Authorization': f'Bearer {key}'}
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=freshness_hours)).isoformat()
    alerts, notes = [], []

    for ac in ("crypto", "equities"):
        try:
            base = {'asset_class': f'eq.{ac}', 'created_at': f'gt.{cutoff}'}
            rh = httpx.get(f'{url}/rest/v1/news_articles', headers=h,
                params={**base, 'select': 'created_at',
                        'order': 'created_at.desc', 'limit': '1'}, timeout=10)
            raw_rows = rh.json()
            sh = httpx.get(f'{url}/rest/v1/news_articles', headers=h,
                params={**base, 'sentiment_score': 'not.is.null',
                        'select': 'created_at', 'order': 'created_at.desc',
                        'limit': '1'}, timeout=10)
            scored_rows = sh.json()
        except Exception as e:
            alerts.append(f"ALERT: sentiment status check failed ({ac}): {e}")
            continue

        raw_count = len(raw_rows)
        scored_count = len(scored_rows)

        if scored_count == 0:
            if raw_count == 0:
                alerts.append(f"ALERT: sentiment NO_DATA ({ac}) — zero articles in {freshness_hours}h (collector down)")
            elif enforces(ac):
                alerts.append(f"ALERT: sentiment NO_DATA ({ac}) — articles present but none scored; pipeline will BLOCK {ac}")
            else:
                notes.append(f"NOTE: sentiment NO_DATA ({ac}) — not scored (degrade mode, known scorer gap)")
            continue

        # Have scored data: check staleness (degrade, not a hard failure).
        try:
            newest = str(scored_rows[0]['created_at']).replace('Z', '+00:00')
            age_min = (now - datetime.fromisoformat(newest)).total_seconds() / 60.0
            if age_min > staleness_min:
                notes.append(f"NOTE: sentiment STALE ({ac}) — newest {age_min:.0f}m old (degrade)")
        except Exception:
            pass

    return (alerts, notes)


def functional_health_alerts(registry=None, *, required=None, alive=None):
    """Safety-authoritative local useful-work check.

    Systemd/tmux/container state remains diagnostic only: it can make health
    worse, but it can never turn stale functional evidence green.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.trading.component_health import HealthRegistry, aggregate, process_alive
    registry = registry or HealthRegistry()
    required = required or {"trading_executor", "run_agents"}
    result = aggregate(registry.read_all(), set(required), alive=alive or process_alive)
    return ([f"CRITICAL: WATCHDOG_FALSE_GREEN_DETECTED {reason}" for reason in result["reasons"]], result)

def main():
    verbose = "--verbose" in sys.argv
    alerts = []
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.trading.component_health import ComponentReporter, Criticality
    watchdog_health = ComponentReporter("watchdog", Criticality.TIER_2,
        expected_interval_seconds=1800, max_staleness_seconds=2400)
    watchdog_health.work_started("periodic-audit")
    
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

    # Check 7 (Sentiment Data-Status)
    c7_alerts, c7_notes = run_check7()
    if verbose:
        status = c7_alerts if c7_alerts else 'OK'
        print(f"Check 7 (Sentiment Status): {status}")
        for note in c7_notes:
            print(f"  {note}")
    alerts.extend(c7_alerts)

    # Check 8: local useful-work proof. This runs independently of cloud
    # telemetry and is the false-green authority for active trading.
    c8, aggregate_health = functional_health_alerts()
    if verbose:
        print(f"Check 8 (Useful Work): {aggregate_health['status']}")
    alerts.extend(c8)

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
    watchdog_health.work_succeeded("periodic-audit", exit_status=0,
        alert_count=len(alerts), watchdog_last_run=datetime.now(timezone.utc).isoformat(),
        watchdog_last_success=datetime.now(timezone.utc).isoformat())

if __name__ == "__main__":
    main()
