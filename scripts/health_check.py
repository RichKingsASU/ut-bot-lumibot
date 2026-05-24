#!/usr/bin/env python3
"""
scripts/health_check.py — Disrupting Alpha V2 full-stack health check.

Audits every component of the stack and prints a clearly-sectioned report
ending in an overall GREEN / YELLOW / RED status.

Run:
    python3 scripts/health_check.py

The script is defensive: every individual check is wrapped so a single
failure never aborts the report. Issues are accumulated into RED (critical)
and YELLOW (minor) buckets that drive the final status.
"""

import glob
import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

# Explicit dotenv path so the script works from any cwd / cron / tmux.
load_dotenv("/home/k2/ut-bot-lumibot/.env")

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

QUESTDB_HTTP = "http://localhost:9000"
QDRANT_HTTP = "http://localhost:6333"
NATS_MON = "http://localhost:8222"

HIST_ROOT = "/mnt/tick-storage/historical"
EXPECTED_EQUITIES = ["SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL", "MSFT", "META", "GOOGL"]
EXPECTED_CRYPTO = ["BTCUSD", "ETHUSD", "SOLUSD"]

SUPABASE_TABLES = [
    "signal_log", "paper_trades", "agent_signals", "regime_states",
    "news_articles", "greeks_snapshots", "trade_performance",
    "portfolio_snapshots", "signal_performance", "bot_status",
]

# Core docker containers that MUST be healthy (project trading stack).
CRITICAL_CONTAINERS = {
    "tick-collector", "news-collector",
    "ut-bot-lumibot-qdrant-1", "ut-bot-lumibot-nats-1", "ut-bot-lumibot-questdb-1",
}

HEARTBEAT_MAX_AGE_SEC = 120  # heartbeat considered stale after 2 minutes

# ── Issue accumulators ──────────────────────────────────────────────────────
RED: list[str] = []
YELLOW: list[str] = []


def section(title: str):
    print(f"\n{'═' * 60}\n  {title}\n{'═' * 60}")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


# ── 1. Supabase tables ───────────────────────────────────────────────────────
def check_supabase_tables():
    section("1. SUPABASE TABLES")
    if not SUPABASE_URL or not SUPABASE_KEY:
        RED.append("Supabase credentials missing (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)")
        print("❌ Supabase credentials missing")
        return
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact",
        "Range": "0-0",
    }
    for t in SUPABASE_TABLES:
        try:
            r = httpx.get(f"{SUPABASE_URL}/rest/v1/{t}", headers=headers,
                          params={"select": "*"}, timeout=10)
            if r.status_code not in (200, 206):
                RED.append(f"Supabase table '{t}' unreachable (HTTP {r.status_code})")
                print(f"❌ {t}: HTTP {r.status_code} — {r.text[:80]}")
                continue
            cr = r.headers.get("content-range", "*/0")
            count = cr.split("/")[-1]
            print(f"✅ {t}: {count} rows")
        except Exception as e:
            RED.append(f"Supabase table '{t}' query error: {e}")
            print(f"❌ {t}: {e}")


# ── 2. Alpaca account ──────────────────────────────────────────────────────
def check_alpaca():
    section("2. ALPACA ACCOUNT")
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        RED.append("Alpaca credentials missing")
        print("❌ Alpaca credentials missing")
        return
    h = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_API_SECRET}
    try:
        r = httpx.get(f"{ALPACA_BASE_URL}/v2/account", headers=h, timeout=10)
        if r.status_code != 200:
            RED.append(f"Alpaca account fetch failed (HTTP {r.status_code})")
            print(f"❌ account: HTTP {r.status_code} — {r.text[:120]}")
            return
        d = r.json()
        print(f"✅ equity=${float(d.get('equity', 0)):,.2f}  "
              f"buying_power=${float(d.get('buying_power', 0)):,.2f}  "
              f"status={d.get('status')}")
    except Exception as e:
        RED.append(f"Alpaca account error: {e}")
        print(f"❌ account: {e}")
        return
    try:
        r = httpx.get(f"{ALPACA_BASE_URL}/v2/positions", headers=h, timeout=10)
        positions = r.json() if r.status_code == 200 else []
        if not positions:
            print("   open positions: none")
        else:
            for p in positions:
                print(f"   {p.get('symbol')}: qty={p.get('qty')} "
                      f"mv=${float(p.get('market_value', 0)):,.2f} "
                      f"P&L=${float(p.get('unrealized_pl', 0)):,.2f}")
    except Exception as e:
        YELLOW.append(f"Alpaca positions error: {e}")
        print(f"⚠️  positions: {e}")


# ── 3. QuestDB ─────────────────────────────────────────────────────────────
def _qdb_query(q: str):
    r = httpx.get(f"{QUESTDB_HTTP}/exec", params={"query": q}, timeout=10)
    r.raise_for_status()
    return r.json()


def check_questdb():
    section("3. QUESTDB (ticks)")
    try:
        total = _qdb_query("SELECT count() FROM ticks")["dataset"][0][0]
        print(f"✅ total ticks: {total}")
        if total == 0:
            RED.append("QuestDB has 0 ticks — tick-collector not ingesting")
        elif total < 50:
            YELLOW.append(f"QuestDB tick count low ({total})")
        per = _qdb_query("SELECT symbol, count() FROM ticks GROUP BY symbol")["dataset"]
        seen = {row[0]: row[1] for row in per}
        for sym in EXPECTED_CRYPTO:
            c = seen.get(sym, 0)
            mark = "✅" if c > 0 else "⚠️"
            if c == 0:
                YELLOW.append(f"QuestDB: no ticks for {sym}")
            print(f"   {mark} {sym}: {c}")
        latest = _qdb_query("SELECT max(timestamp) FROM ticks")["dataset"][0][0]
        print(f"   latest tick: {latest}")
    except Exception as e:
        RED.append(f"QuestDB unreachable: {e}")
        print(f"❌ QuestDB: {e}")


# ── 4. Qdrant ──────────────────────────────────────────────────────────────
def check_qdrant():
    section("4. QDRANT (vector store)")
    for coll in ("crypto_news", "agent_memory"):
        try:
            r = httpx.get(f"{QDRANT_HTTP}/collections/{coll}", timeout=10)
            if r.status_code != 200:
                RED.append(f"Qdrant collection '{coll}' missing (HTTP {r.status_code})")
                print(f"❌ {coll}: HTTP {r.status_code}")
                continue
            pts = r.json()["result"].get("points_count", 0)
            print(f"✅ {coll}: {pts} points")
            if coll == "crypto_news" and pts == 0:
                YELLOW.append("Qdrant crypto_news has 0 points")
        except Exception as e:
            RED.append(f"Qdrant '{coll}' error: {e}")
            print(f"❌ {coll}: {e}")


# ── 5. NATS ────────────────────────────────────────────────────────────────
def check_nats():
    section("5. NATS (message bus)")
    try:
        v = httpx.get(f"{NATS_MON}/varz", timeout=10).json()
        print(f"✅ connections: {v.get('connections')}")
        print(f"   uptime: {v.get('uptime')}")
        print(f"   subscriptions: {v.get('subscriptions')}")
        if v.get("connections", 0) == 0:
            YELLOW.append("NATS has 0 active connections")
    except Exception as e:
        RED.append(f"NATS monitoring unreachable: {e}")
        print(f"❌ NATS: {e}")


# ── 6. tmux sessions ─────────────────────────────────────────────────────────
def check_tmux():
    section("6. TMUX SESSIONS")
    try:
        out = subprocess.run(["tmux", "ls"], capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            YELLOW.append("No tmux sessions running")
            print("⚠️  no tmux sessions")
            return
        sessions = [line.split(":")[0] for line in out.stdout.strip().splitlines()]
        for s in sessions:
            cap = subprocess.run(["tmux", "capture-pane", "-t", s, "-p"],
                                 capture_output=True, text=True, timeout=10)
            lines = [ln for ln in cap.stdout.splitlines() if ln.strip()]
            last3 = lines[-3:]
            joined = "\n".join(last3)
            bad = re.search(r"\b(ERROR|CRITICAL|Traceback|Exception)\b", joined)
            mark = "❌" if bad else "✅"
            if bad:
                RED.append(f"tmux session '{s}' shows errors")
            print(f"{mark} [{s}]")
            for ln in last3:
                print(f"      {ln[:110]}")
    except Exception as e:
        YELLOW.append(f"tmux check error: {e}")
        print(f"⚠️  tmux: {e}")


# ── 7. Docker containers ─────────────────────────────────────────────────────
def check_docker():
    section("7. DOCKER CONTAINERS")
    try:
        out = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            YELLOW.append("docker ps failed")
            print(f"⚠️  docker: {out.stderr[:120]}")
            return
        for line in out.stdout.strip().splitlines():
            name, _, status = line.partition("|")
            healthy = status.startswith("Up") and "unhealthy" not in status and "Restarting" not in status
            critical = name in CRITICAL_CONTAINERS
            # Project stack = critical containers + anything from this repo's compose.
            in_project = critical or name.startswith("ut-bot-lumibot-")
            if healthy:
                print(f"✅ {name}: {status}")
            elif in_project:
                # Unhealthy project container → critical or minor depending on role.
                (RED if critical else YELLOW).append(
                    f"Docker container '{name}' not healthy: {status}")
                print(f"{'❌' if critical else '⚠️'} {name}: {status}")
            else:
                # External container (e.g. unrelated local Supabase dev stack) —
                # informational only, does NOT affect trading-stack health status.
                print(f"ℹ️  {name}: {status}  (external — not part of trading stack)")
    except Exception as e:
        YELLOW.append(f"docker check error: {e}")
        print(f"⚠️  docker: {e}")


# ── 8. Latest regime states ──────────────────────────────────────────────────
def check_regimes():
    section("8. LATEST REGIME STATES")
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️  no Supabase creds — skipped")
        return
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/regime_states", headers=h,
                      params={"select": "symbol,asset_class,regime,regime_probability,detected_at",
                              "order": "detected_at.desc", "limit": 200}, timeout=10)
        rows = r.json()
        if not rows:
            YELLOW.append("regime_states table empty")
            print("⚠️  no regime data")
            return
        latest_per_symbol = {}
        for row in rows:
            sym = row.get("symbol")
            if sym not in latest_per_symbol:
                latest_per_symbol[sym] = row
        for sym, row in latest_per_symbol.items():
            print(f"   {sym}: {row.get('regime')} "
                  f"({float(row.get('regime_probability') or 0):.0%}) @ {row.get('detected_at')}")
        regimes = [row.get("regime") for row in latest_per_symbol.values()]
        from collections import Counter
        overall = Counter(regimes).most_common(1)[0][0] if regimes else "UNKNOWN"
        print(f"✅ overall regime: {overall}")
        # staleness check on most-recent detection
        newest = parse_iso(rows[0].get("detected_at"))
        if newest:
            age_h = (now_utc() - newest).total_seconds() / 3600
            if age_h > 24:
                YELLOW.append(f"Latest regime detection is {age_h:.1f}h old")
                print(f"   ⚠️  latest detection {age_h:.1f}h old")
    except Exception as e:
        YELLOW.append(f"regime_states query error: {e}")
        print(f"⚠️  regime_states: {e}")


# ── 9. Latest agent signals ──────────────────────────────────────────────────
def check_agent_signals():
    section("9. LATEST AGENT SIGNALS (last 5)")
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️  no Supabase creds — skipped")
        return
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/agent_signals", headers=h,
                      params={"select": "action,confidence,asset_class,created_at",
                              "order": "created_at.desc", "limit": 5}, timeout=10)
        rows = r.json()
        if not rows:
            YELLOW.append("agent_signals table empty")
            print("⚠️  no agent signals")
            return
        for row in rows:
            print(f"   {row.get('created_at')}: {row.get('action')} "
                  f"| {row.get('confidence')} | {row.get('asset_class')}")
        print(f"✅ {len(rows)} recent signals")
    except Exception as e:
        YELLOW.append(f"agent_signals query error: {e}")
        print(f"⚠️  agent_signals: {e}")


# ── 10. bot_status heartbeat ─────────────────────────────────────────────────
def check_heartbeat():
    section("10. BOT_STATUS HEARTBEAT")
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️  no Supabase creds — skipped")
        return
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/bot_status", headers=h,
                      params={"select": "*", "order": "last_heartbeat.desc", "limit": 1}, timeout=10)
        rows = r.json()
        if not rows:
            YELLOW.append("bot_status table empty")
            print("⚠️  no bot_status rows")
            return
        row = rows[0]
        hb = parse_iso(row.get("last_heartbeat"))
        target = (row.get("target_status") or "").lower()
        status = (row.get("status") or "").lower()
        if hb:
            age = (now_utc() - hb).total_seconds()
            fresh = age < HEARTBEAT_MAX_AGE_SEC
            mark = "✅" if fresh else "❌"
            print(f"{mark} last_heartbeat: {row.get('last_heartbeat')} ({age:.0f}s ago)")
            if not fresh and target == "running":
                RED.append(f"bot_status heartbeat stale ({age:.0f}s) while target=running")
        else:
            YELLOW.append("bot_status has no parsable heartbeat")
            print("⚠️  no parsable heartbeat")
        # Kill switch: target_status indicates desired state
        kill_active = target in ("stopped", "kill", "killed", "halt", "halted") or status == "kill"
        print(f"   status={status} target_status={target} "
              f"{'🛑 KILL SWITCH ACTIVE' if kill_active else '(kill switch off)'}")
        if kill_active:
            RED.append(f"Kill switch active (target_status={target})")
    except Exception as e:
        YELLOW.append(f"bot_status query error: {e}")
        print(f"⚠️  bot_status: {e}")


# ── 11. Historical data coverage ─────────────────────────────────────────────
def _date_range_from_1d(symbol_dir: str, symbol: str):
    """Parse date range from the 1D filename, e.g. SYM_1D_2010-01-01_2026-05-23.parquet."""
    files = glob.glob(os.path.join(symbol_dir, f"{symbol}_1D_*.parquet"))
    if not files:
        return None
    m = re.search(r"_1D_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", os.path.basename(files[0]))
    if m:
        return m.group(1), m.group(2)
    return None


def check_historical():
    section("11. HISTORICAL DATA COVERAGE")
    for asset, base, expected in (
        ("equities", os.path.join(HIST_ROOT, "equities"), EXPECTED_EQUITIES),
        ("crypto", os.path.join(HIST_ROOT, "crypto"), EXPECTED_CRYPTO),
    ):
        print(f"  [{asset}]")
        for sym in expected:
            symbol_dir = os.path.join(base, sym)
            files = glob.glob(os.path.join(symbol_dir, "*.parquet"))
            if not files:
                RED.append(f"Historical data MISSING for {sym} ({asset})")
                print(f"   ❌ {sym}: NO FILES")
                continue
            dr = _date_range_from_1d(symbol_dir, sym)
            rng = f"{dr[0]} → {dr[1]}" if dr else "1D range unknown"
            print(f"   ✅ {sym}: {len(files)} files  ({rng})")


# ── 12. Summary ──────────────────────────────────────────────────────────────
def summary():
    section("SUMMARY")
    if RED:
        status = "🔴 RED"
    elif YELLOW:
        status = "🟡 YELLOW"
    else:
        status = "🟢 GREEN"

    if RED:
        print("CRITICAL ISSUES (RED):")
        for i in RED:
            print(f"   ❌ {i}")
    if YELLOW:
        print("MINOR ISSUES (YELLOW):")
        for i in YELLOW:
            print(f"   ⚠️  {i}")
    if not RED and not YELLOW:
        print("All systems operational.")

    print(f"\n  OVERALL STATUS: {status}")
    print(f"  {'GREEN = all operational | YELLOW = minor issues | RED = intervention needed'}")
    return status


def main():
    print(f"Disrupting Alpha V2 — Health Check @ {now_utc().isoformat()}")
    check_supabase_tables()
    check_alpaca()
    check_questdb()
    check_qdrant()
    check_nats()
    check_tmux()
    check_docker()
    check_regimes()
    check_agent_signals()
    check_heartbeat()
    check_historical()
    return summary()


if __name__ == "__main__":
    main()
