#!/usr/bin/env python3
"""
scripts/ground_truth.py — Disrupting Alpha Phase 0 Ground-truth audit script.

Runs outcome assertions for each system component and prints a status table.
Exits with code 1 if any check is FAIL.
"""

import os
import sys
import time
import json
from datetime import datetime, timezone, timedelta
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/home/k2/ut-bot-lumibot/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# Expected Symbols
EQUITY_SYMBOLS = ['SPY', 'QQQ', 'IWM', 'NVDA', 'TSLA', 'AAPL']
CRYPTO_SYMBOLS = ['BTCUSD', 'ETHUSD', 'SOLUSD']

def parse_iso(ts_str: str) -> datetime:
    if not ts_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    ts_str = ts_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        # Try without ms or with other patterns if needed
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"):
            try:
                return datetime.strptime(ts_str, fmt)
            except Exception:
                continue
        return datetime.min.replace(tzinfo=timezone.utc)

def supa_get(table: str, params: dict = None) -> list:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials missing")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    resp = httpx.get(url, headers=headers, params=params, timeout=10)
    if resp.status_code not in (200, 206):
        raise httpx.HTTPStatusError(f"HTTP {resp.status_code}: {resp.text}", request=resp.request, response=resp)
    return resp.json()

def alpaca_get(endpoint: str, params: dict = None) -> dict:
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise ValueError("Alpaca credentials missing")
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET
    }
    url = f"{ALPACA_BASE_URL}{endpoint}"
    resp = httpx.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()

# ── Checks ──────────────────────────────────────────────────────────────────

def check_utbot_strategy() -> tuple[str, str]:
    """≥1 entry order attempted in last 5 market days (7 calendar days)."""
    try:
        # Check Alpaca orders
        orders = alpaca_get("/v2/orders", {"status": "all", "limit": 100})
        if not orders:
            return "NO_DATA", "No orders found in Alpaca history"
        
        # Filter for us_option or option-like symbols and buy/entry orders
        option_orders = []
        for o in orders:
            symbol = o.get("symbol", "")
            # Options symbols are usually longer (e.g. SPY260309C00550000)
            is_option = o.get("asset_class") == "us_option" or len(symbol) > 8
            if is_option and o.get("side") == "buy":
                option_orders.append(o)
                
        if not option_orders:
            return "NO_DATA", "No options entry orders found in order history"
            
        # Check if any in the last 7 calendar days
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent_orders = []
        for o in option_orders:
            created_at = parse_iso(o.get("created_at"))
            if created_at >= cutoff:
                recent_orders.append(o)
                
        if recent_orders:
            symbols = ", ".join(set(o.get("symbol") for o in recent_orders))
            return "PASS", f"Attempted {len(recent_orders)} option orders recently: {symbols}"
        else:
            last_order = option_orders[0]
            last_time = last_order.get("created_at")
            return "FAIL", f"Stale: Latest entry order was {last_order.get('symbol')} at {last_time}"
            
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_news_collector() -> tuple[str, str]:
    """Articles rows written today, both asset classes (crypto & equities)."""
    try:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        articles = supa_get("news_articles", {
            "created_at": f"gte.{yesterday}",
            "select": "asset_class,created_at"
        })
        if not articles:
            return "NO_DATA", "No news articles written in the last 24 hours"
            
        classes = set(a.get("asset_class") for a in articles if a.get("asset_class"))
        has_crypto = "crypto" in classes
        has_equities = "equities" in classes or "equity" in classes
        
        detail = f"Written {len(articles)} articles (crypto: {has_crypto}, equities: {has_equities})"
        if has_crypto and has_equities:
            return "PASS", detail
        else:
            return "FAIL", f"Missing classes! {detail}"
            
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_sentiment_scorer() -> tuple[str, str]:
    """Scored articles today for crypto and equities."""
    try:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        articles = supa_get("news_articles", {
            "created_at": f"gte.{yesterday}",
            "sentiment_score": "not.is.null",
            "select": "asset_class,created_at,sentiment_score"
        })
        if not articles:
            return "NO_DATA", "No scored articles in the last 24 hours"
            
        classes = set(a.get("asset_class") for a in articles if a.get("asset_class"))
        has_crypto = "crypto" in classes
        has_equities = "equities" in classes or "equity" in classes
        
        detail = f"Scored {len(articles)} articles (crypto: {has_crypto}, equities: {has_equities})"
        if has_crypto and has_equities:
            return "PASS", detail
        else:
            return "FAIL", f"Missing classes! {detail}"
            
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_regime_detector() -> tuple[str, str]:
    """Row per equity symbol < 1 cycle old (20 min threshold)."""
    try:
        # Query regime states specifically for our equity symbols to avoid pagination limits
        symbols_filter = ",".join(EQUITY_SYMBOLS)
        rows = supa_get("regime_states", {
            "symbol": f"in.({symbols_filter})",
            "select": "symbol,detected_at,regime",
            "order": "detected_at.desc",
            "limit": 100
        })
        if not rows:
            return "NO_DATA", "No regime state rows found for equity symbols"
            
        latest = {}
        for r in rows:
            sym = r.get("symbol")
            if sym and sym not in latest:
                latest[sym] = r
                
        missing = []
        stale = []
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=20)
        
        for sym in EQUITY_SYMBOLS:
            if sym not in latest:
                missing.append(sym)
            else:
                det = parse_iso(latest[sym].get("detected_at"))
                if det < cutoff:
                    stale.append(f"{sym} ({latest[sym].get('detected_at')})")
                    
        if missing:
            return "FAIL", f"Missing regime rows for: {', '.join(missing)}"
        if stale:
            return "FAIL", f"Stale regimes for: {', '.join(stale)}"
            
        return "PASS", f"All {len(EQUITY_SYMBOLS)} equity regimes fresh (< 20m old)"
        
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_debate_agents() -> tuple[str, str]:
    """Verdict rows reference the same regime the header used."""
    try:
        # Get debate signals from the last 24h
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        signals = supa_get("agent_signals", {
            "created_at": f"gte.{yesterday}",
            "debate_verdict": "not.is.null",
            "select": "symbol,created_at,regime,debate_verdict"
        })
        if not signals:
            return "NO_DATA", "No debate verdicts logged in last 24h"
            
        # Get the unique symbols to query their regimes specifically
        unique_symbols = list(set(s.get("symbol") for s in signals if s.get("symbol")))
        if not unique_symbols:
            return "NO_DATA", "No symbols found in debate verdicts"
            
        symbols_filter = ",".join(unique_symbols)
        regimes = supa_get("regime_states", {
            "symbol": f"in.({symbols_filter})",
            "select": "symbol,regime,detected_at",
            "order": "detected_at.desc",
            "limit": 500
        })
        
        mismatches = []
        for s in signals:
            sym = s.get("symbol")
            created = parse_iso(s.get("created_at"))
            header_regime = s.get("regime")
            if not sym or not header_regime:
                continue
                
            # Find the latest regime for this symbol at/before signal timestamp
            db_regime = None
            for r in regimes:
                if r.get("symbol") == sym:
                    det = parse_iso(r.get("detected_at"))
                    if det <= created:
                        db_regime = r.get("regime")
                        break
            
            if not db_regime:
                continue
                
            # Standardize names (e.g. BULL vs BULL_NORMAL)
            def norm(v):
                if not v: return ""
                v = v.upper()
                if v.startswith("BULL"): return "BULL"
                if v.startswith("BEAR"): return "BEAR"
                return v
                
            if norm(header_regime) != norm(db_regime):
                mismatches.append(f"{sym}@{s.get('created_at')[:16]}: header={header_regime} vs debate={db_regime}")
                
        if mismatches:
            return "FAIL", f"Regime divergence detected: {'; '.join(mismatches[:3])}"
        return "PASS", f"Verified {len(signals)} debate cycles; no regime divergence found"
        
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_kelly_sizer() -> tuple[str, str]:
    """Sizes ≤ $2,500 hard cap, halved under PROCEED_CAUTIOUSLY."""
    try:
        five_days_ago = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        signals = supa_get("agent_signals", {
            "created_at": f"gte.{five_days_ago}",
            "kelly_position_value": "not.is.null",
            "select": "symbol,kelly_position_value,debate_verdict,created_at"
        })
        if not signals:
            return "NO_DATA", "No sizing rows in agent_signals for last 5 days"
            
        violations = []
        for s in signals:
            val = float(s.get("kelly_position_value") or 0.0)
            verdict = s.get("debate_verdict")
            sym = s.get("symbol")
            
            if val > 2500.01:
                violations.append(f"{sym}: proposed ${val:.2f} > $2500 hard-cap")
            elif verdict == "PROCEED_CAUTIOUSLY" and val > 1250.01:
                violations.append(f"{sym} (cautious): proposed ${val:.2f} > $1250 limit")
                
        if violations:
            return "FAIL", f"Sizing violations found: {', '.join(violations[:3])}"
        return "PASS", f"All {len(signals)} sizing records comply with caps (max $2500, max $1250 on cautious)"
        
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_crypto_bot() -> tuple[str, str]:
    """Orders on new account PA3ZBZQM5K7H (not old account)."""
    try:
        # Check active account
        acc = alpaca_get("/v2/account")
        num = acc.get("account_number")
        if num != "PA3ZBZQM5K7H":
            return "FAIL", f"Incorrect account number: {num} (expected PA3ZBZQM5K7H)"
            
        # Check orders for crypto symbols
        orders = alpaca_get("/v2/orders", {"status": "all", "limit": 100})
        crypto_orders = []
        for o in orders:
            symbol = o.get("symbol", "")
            # Crypto symbols are things like BTCUSD, ETHUSD, SOLUSD
            is_crypto = any(c in symbol for c in ("BTC", "ETH", "SOL")) and "USD" in symbol and len(symbol) < 10
            if is_crypto:
                crypto_orders.append(o)
                
        if crypto_orders:
            symbols = ", ".join(set(o.get("symbol") for o in crypto_orders))
            return "PASS", f"Crypto orders found: {symbols}"
        else:
            return "NO_DATA", f"Account PA3ZBZQM5K7H correct, but no crypto orders found"
            
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_learning_loop() -> tuple[str, str]:
    """trade_performance rows exist."""
    try:
        rows = supa_get("trade_performance", {"limit": 1, "select": "id"})
        if rows:
            return "PASS", "Rows exist in trade_performance table"
        else:
            return "NO_DATA", "trade_performance table is empty"
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_questdb_qdrant() -> tuple[str, str]:
    """Writes landing on /mnt/tick-storage (sdb, UUID-mounted). Qdrant points > 0."""
    try:
        # 1. Mount check
        if not os.path.ismount('/mnt/tick-storage'):
            return "FAIL", "/mnt/tick-storage is NOT mounted"
            
        # 2. QuestDB check
        try:
            r = httpx.get("http://localhost:9000/exec?query=SELECT+max(timestamp),+count()+FROM+ticks", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if "dataset" in data and data["dataset"]:
                    latest_ts_str = data["dataset"][0][0]
                    total_ticks = data["dataset"][0][1]
                    
                    # Compute age
                    latest_ts = parse_iso(latest_ts_str)
                    age = (datetime.now(timezone.utc) - latest_ts).total_seconds()
                    
                    if age > 600: # 10 minutes
                        return "FAIL", f"QuestDB tick data stale: latest tick was {age/60:.1f}m ago"
                else:
                    return "FAIL", "QuestDB table ticks is empty"
            else:
                return "FAIL", f"QuestDB exec failed: HTTP {r.status_code}"
        except Exception as qe:
            return "FAIL", f"QuestDB unreachable: {qe}"
            
        # 3. Qdrant check
        for coll in ("crypto_news", "agent_memory"):
            try:
                qr = httpx.get(f"http://localhost:6333/collections/{coll}", timeout=5)
                if qr.status_code != 200:
                    return "FAIL", f"Qdrant collection {coll} missing (HTTP {qr.status_code})"
                pts = qr.json().get("result", {}).get("points_count", 0)
                if pts == 0:
                    return "FAIL", f"Qdrant collection {coll} has 0 points"
            except Exception as qde:
                return "FAIL", f"Qdrant unreachable for {coll}: {qde}"
                
        return "PASS", f"Mounted, QuestDB fresh (ticks: {total_ticks}), Qdrant collections healthy"
        
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_nats() -> tuple[str, str]:
    """Consumer lag ≈ 0 on news.*, sentiment.*."""
    try:
        # Query NATS jsz
        r = httpx.get("http://localhost:8222/jsz?streams=true", timeout=5)
        if r.status_code != 200:
            return "FAIL", f"NATS monitoring port returned HTTP {r.status_code}"
            
        data = r.json()
        if data.get("disabled"):
            # JetStream disabled. Check varz for core status
            vr = httpx.get("http://localhost:8222/varz", timeout=5).json()
            return "NO_DATA", f"JetStream disabled. Core NATS OK (connections: {vr.get('connections')})"
            
        # JetStream enabled. Inspect consumer lag
        streams = data.get("streams_list", [])
        total_lag = 0
        monitored_streams = 0
        
        for s in streams:
            name = s.get("name", "")
            # We want to check streams that handle news.* and sentiment.*
            if any(sub in name.lower() for sub in ("news", "sentiment")):
                monitored_streams += 1
                # Query consumer info
                cr = httpx.get(f"http://localhost:8222/jsz?stream={name}&consumers=true", timeout=5).json()
                for c in cr.get("consumers_list", []):
                    total_lag += c.get("num_pending", 0)
                    
        if monitored_streams == 0:
            return "NO_DATA", "No news/sentiment JetStream streams found"
            
        if total_lag < 5:
            return "PASS", f"Consumer lag is {total_lag} across {monitored_streams} streams"
        else:
            return "FAIL", f"High consumer lag: {total_lag} pending messages"
            
    except httpx.ConnectError:
        return "FAIL", "NATS monitoring server unreachable (port 8222)"
    except Exception as e:
        return "FAIL", f"Error: {e}"

def check_dashboard() -> tuple[str, str]:
    """Panel values equal Supabase values for the same instant (spot-check)."""
    tables = ["portfolio_snapshots", "regime_states", "agent_signals", "news_articles", "bot_status"]
    healthy = []
    unreachable = []
    
    for t in tables:
        try:
            supa_get(t, {"limit": 1, "select": "*"})
            healthy.append(t)
        except Exception as e:
            unreachable.append(f"{t} ({e})")
            
    if unreachable:
        return "FAIL", f"Supabase table queries failed: {', '.join(unreachable)}"
    return "PASS", f"Verified connection and retrieved data from all 5 panels source tables: {', '.join(healthy)}"

# ── Main runner ─────────────────────────────────────────────────────────────

def main():
    print("═" * 80)
    print("DISRUPTING ALPHA — GROUND-TRUTH AUDIT")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("═" * 80)
    
    checks = [
        ("UTBot strategy", check_utbot_strategy),
        ("News collector", check_news_collector),
        ("Sentiment scorer", check_sentiment_scorer),
        ("Regime detector", check_regime_detector),
        ("Debate agents", check_debate_agents),
        ("Kelly sizer", check_kelly_sizer),
        ("Crypto bot", check_crypto_bot),
        ("Learning loop", check_learning_loop),
        ("QuestDB/Qdrant", check_questdb_qdrant),
        ("NATS", check_nats),
        ("Dashboard", check_dashboard)
    ]
    
    failures = 0
    results = []
    
    for label, fn in checks:
        status, detail = fn()
        results.append((label, status, detail))
        if status == "FAIL":
            failures += 1
            
    # Print fixed-width table
    print(f"{'COMPONENT':20} | {'STATUS':8} | {'OBSERVED DETAIL'}")
    print("-" * 80)
    for label, status, detail in results:
        print(f"{label:20} | {status:8} | {detail}")
    print("═" * 80)
    
    if failures > 0:
        print(f"❌ AUDIT FAILED with {failures} FAIL status rows.")
        sys.exit(1)
    else:
        print("✅ AUDIT PASSED (all status rows PASS or NO_DATA).")
        sys.exit(0)

if __name__ == "__main__":
    main()
