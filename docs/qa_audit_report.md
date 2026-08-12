# Disrupting Alpha — Edge Server QA/QC Validation Audit (READ-ONLY)

- **Auditor role:** Principal QA/QC Engineer (read-only validation pass)
- **Host:** edge server, server TZ = MST
- **Working dir / repo:** `/home/k2/ut-bot-lumibot` (confirmed via `git rev-parse --show-toplevel`)
- **Branch / commit:** `main` @ `d357845` — *"fix: refuse stack startup if tick-storage not mounted"*
- **Telegram bug-fix commit `1f50df4` in history:** ✅ YES (present in `git log`)
- **Audit timestamp:** 2026-06-02 ~04:21 UTC / 2026-06-01 ~21:21 MST
- **System uptime at audit:** ~15 min (host rebooted ~21:02 MST)
- **State changes made:** NONE. Every start/stop command below is **DOCUMENTED, NOT EXECUTED**. The only file written is this report.

---

## A. Executive Summary

### 🔴 OVERALL RAG STATUS: **RED**

The **data-infrastructure layer is fully healthy** (QuestDB, Qdrant, NATS, both collectors, full local Supabase stack, real 7.3 TB tick drive correctly mounted). However, the **entire trading / agent / Telegram layer is DOWN** and has been for ~3 days. The `@reboot` `start_all.sh` launched its 8 tmux sessions ~15 min ago, but **all 8 sessions died within 20 seconds** — the script's own embedded health check reported `0/8 sessions` and overall **RED**. The live cloud `bot_status` heartbeat is **75.8 h stale**.

The specific failure mode that was recently fixed (services silently writing tick data to the root disk because the drive wasn't mounted) is **NOT occurring** — the drive is a genuine mount, the `check_mount.sh` guard is present and sourced, and QuestDB/Qdrant data is confirmed landing on `/mnt/tick-storage`. ✅

### Status tally

| Status | Count |
|--------|-------|
| ✅ PASS | 18 |
| ⚠️ WARN | 6 |
| 🔴 FAIL | 11 |
| ⏭️ SKIPPED | 2 |

### Top findings (detail in §D)
1. 🔴 **All 8 tmux app sessions down** (agents, trading-bot, crypto-bot, sentiment, vectors, options, telegram-bot, watchdog) — crash-on-launch. Trading/agent pipeline NOT running.
2. 🔴 **Cloud `bot_status` heartbeat stale 75.8 h** (last 2026-05-30T00:29Z) → trading bot offline ~3 days; consistent with regime-detection 75.7 h old.
3. 🔴 **`supabase_edge_runtime_Antigravity` exited 255, down ~9 days, `restart=no`** — never auto-recovers.
4. ⚠️ **No watchdog / hardener in cron** — watchdog is only a tmux session (down); no root crontab.
5. ⚠️ **`ohlcv_1m` QuestDB table empty (0 rows)**; tick throughput very low (~0.03 ticks/s).
6. ⚠️ **Finnhub API key is a placeholder** — that news source is skipped.

---

## B. Component Inventory Table

> Start/Stop commands are **DOCUMENTED, NOT EXECUTED** (read-only pass). Health-check commands were executed and are evidenced in §C.

| # | Component | Layer | Status | Health-check cmd | Start cmd (NOT EXECUTED) | Stop cmd (NOT EXECUTED) | Evidence |
|---|-----------|-------|--------|------------------|--------------------------|--------------------------|----------|
| 1 | `/mnt/tick-storage` (sda2, 7.3T) | Host/Storage | ✅ PASS | `mountpoint /mnt/tick-storage` | `sudo mount -a` | `sudo umount /mnt/tick-storage` | E1 |
| 2 | Root disk (nvme0n1p2, 915G) | Host/Storage | ✅ PASS | `df -h /` | n/a | n/a | E1 |
| 3 | `check_mount.sh` guard | Host/Storage | ✅ PASS | `cat scripts/check_mount.sh` | n/a (sourced by start_all.sh:2) | n/a | E2 |
| 4 | QuestDB (`ut-bot-lumibot-questdb-1`) | Data | ✅ PASS | `curl :9000/exec?query=SHOW TABLES` | `docker compose up -d questdb` | `docker compose stop questdb` | E3,E7 |
| 5 | Qdrant (`ut-bot-lumibot-qdrant-1`) | Data | ✅ PASS | `curl :6333/healthz` | `docker compose up -d qdrant` | `docker compose stop qdrant` | E3,E7 |
| 6 | NATS (`ut-bot-lumibot-nats-1`) | Data/Bus | ✅ PASS | `curl :8222/varz` | `docker compose up -d nats` | `docker compose stop nats` | E3,E7 |
| 7 | tick-collector (container) | Collector | ⚠️ WARN | `docker logs --tail 20 tick-collector` | `docker compose up -d tick-collector` | `docker compose stop tick-collector` | E4,E7 |
| 8 | news-collector (container) | Collector | ⚠️ WARN | `docker logs --tail 20 news-collector` | `docker compose up -d news-collector` | `docker compose stop news-collector` | E4 |
| 9 | supabase_db (local) | Data | ✅ PASS | `docker exec supabase_db_Antigravity psql -U postgres -c '\l'` | `supabase start` (Antigravity stack) | `supabase stop` | E8 |
| 10 | supabase_kong/auth/rest/realtime/storage/studio/inbucket/analytics/vector/pg_meta | Data/API | ✅ PASS | `docker ps` (healthy) | `supabase start` | `supabase stop` | E3 |
| 11 | **supabase_edge_runtime** | Data/API | 🔴 FAIL | `docker inspect ... .State` | `supabase start` / `docker start supabase_edge_runtime_Antigravity` | `docker stop supabase_edge_runtime_Antigravity` | E9 |
| 12 | Cloud Supabase (`wnigkahkamoizjpmpuxs`) | External | ✅ PASS | `curl $SUPABASE_URL/rest/v1/bot_status` | n/a (managed) | n/a | E6 |
| 13 | **bot_status heartbeat** | Trading | 🔴 FAIL | `curl .../bot_status?id=eq.1` | (revived by trading-bot) | n/a | E6 |
| 14 | tmux server | Automation | 🔴 FAIL | `tmux ls` | (auto via start_all.sh) | `tmux kill-server` | E5 |
| 15 | **agents** (`run_agents.py`, 10-node LangGraph) | Agent Pipeline | 🔴 FAIL | `tmux has-session -t agents` | `tmux new-session -d -s agents "cd ~/ut-bot-lumibot && source venv/bin/activate && python run_agents.py"` | `tmux kill-session -t agents` | E5,E10 |
| 16 | **trading-bot** (`main.py`) | Trading | 🔴 FAIL | `tmux has-session -t trading-bot` | `tmux new-session -d -s trading-bot "... python main.py"` | `tmux kill-session -t trading-bot` | E5 |
| 17 | **crypto-bot** (`run_crypto_bot.py`) | Trading | 🔴 FAIL | `tmux has-session -t crypto-bot` | `tmux new-session -d -s crypto-bot "... python run_crypto_bot.py"` | `tmux kill-session -t crypto-bot` | E5 |
| 18 | **sentiment** (`run_sentiment_scorer.py`) | Agent | 🔴 FAIL | `tmux has-session -t sentiment` | `tmux new-session -d -s sentiment "... python run_sentiment_scorer.py"` | `tmux kill-session -t sentiment` | E5 |
| 19 | **vectors** (`run_vector_store.py`) | Agent | 🔴 FAIL | `tmux has-session -t vectors` | `tmux new-session -d -s vectors "... python run_vector_store.py"` | `tmux kill-session -t vectors` | E5 |
| 20 | **options** (`run_option_data_worker.py`) | Trading | 🔴 FAIL | `tmux has-session -t options` | `tmux new-session -d -s options "... python run_option_data_worker.py"` | `tmux kill-session -t options` | E5 |
| 21 | **telegram-bot** (`run_telegram_bot.py`) | Notify | 🔴 FAIL | `tmux has-session -t telegram-bot` | `tmux new-session -d -s telegram-bot "... python run_telegram_bot.py"` | `tmux kill-session -t telegram-bot` | E5 |
| 22 | **watchdog** (`run_agent_watchdog.py`) | Automation | 🔴 FAIL | `tmux has-session -t watchdog` | `tmux new-session -d -s watchdog "... python run_agent_watchdog.py"` | `tmux kill-session -t watchdog` | E5 |
| 23 | Kill switch (`bot_status.target_status`) | Control | ✅ PASS (disengaged) | `curl .../bot_status?id=eq.1&select=target_status` | PATCH `target_status='running'` | PATCH `target_status='shutdown'` | E6,E10 |
| 24 | cron: `@reboot start_all.sh` | Automation | ✅ PASS | `crontab -l` | n/a | n/a | E5 |
| 25 | cron: pre-market check 13:45 UTC | Automation | ✅ PASS | `crontab -l` | n/a | n/a | E5 |
| 26 | cron: daily OHLCV seed 23:00 UTC | Automation | ✅ PASS | `crontab -l` | n/a | n/a | E5 |
| 27 | cron: 30-min watchdog | Automation | 🔴 FAIL (absent) | `crontab -l` | (would add `*/30 * * * * ...`) | n/a | E5 |
| 28 | cron/timer: 3 AM hardener | Automation | ⚠️ WARN (absent from cron) | `crontab -l; systemctl list-timers` | n/a | n/a | E5 |
| 29 | sentiment-scorer / vector-store (compose services) | Data | ⚠️ WARN (never created) | `docker ps -a` | `docker compose up -d sentiment-scorer vector-store` | `docker compose stop ...` | E9 |
| 30 | Netlify dashboard `3b6f54c8…` | External | ⏭️ SKIPPED | n/a (not locally inspectable) | n/a | n/a | — |

---

## C. Per-Component Detail with Captured Evidence

### E1 — Host storage / mount (PASS)
```
$ df -h
/dev/nvme0n1p2  915G   74G  795G   9% /
/dev/sda2       7.3T  154G  7.2T   3% /mnt/tick-storage
$ lsblk
sda    7.3T disk
└─sda2 7.3T part /mnt/tick-storage
$ mountpoint /mnt/tick-storage
/mnt/tick-storage is a mountpoint
$ grep tick-storage /etc/fstab
UUID=267ED1667ED12F75 /mnt/tick-storage ntfs-3g defaults,nofail,x-systemd.device-timeout=10,uid=1000,gid=1000,umask=022 0 0
```
✅ Real 7.3 TB drive, genuinely mounted, 7.2 TB free (3% used). fstab uses `nofail` (safe boot) + the audited UUID. Root disk healthy at 9%.

### E2 — `check_mount.sh` guard (PASS)
```
$ cat scripts/check_mount.sh
#!/bin/bash
MOUNT=/mnt/tick-storage
if ! mountpoint -q "$MOUNT"; then
  echo "ERROR: $MOUNT is not mounted. Refusing to start (would write to root disk)."
  exit 1
fi
echo "OK: $MOUNT is mounted."
$ grep -n check_mount scripts/start_all.sh
2:source "$(dirname "$0")/check_mount.sh"
```
✅ Guard correct and sourced as line 2 of `start_all.sh` → stack refuses to start if the drive is absent (the fix in commit `d357845`).

### E3 — Container roster & health (`docker ps -a`)
```
tick-collector                      python:3.11-slim   Up 14 minutes
news-collector                      python:3.11-slim   Up 14 minutes
ut-bot-lumibot-questdb-1            questdb/questdb     Up 14 minutes   :8812 :9000 :9009
ut-bot-lumibot-qdrant-1            qdrant/qdrant      Up 14 minutes   :6333
ut-bot-lumibot-nats-1              nats:latest        Up 14 minutes   :4222 :8222
supabase_studio/pg_meta/storage/rest/realtime/inbucket/auth/kong/vector/analytics/db   Up 14 minutes (healthy)
supabase_edge_runtime_Antigravity  edge-runtime       Exited (255) 9 days ago
```
Health-endpoint probes:
```
$ curl :9000/exec?query=SHOW TABLES   → {"dataset":[["ohlcv_1m"],["ticks"]]}
$ curl :6333/healthz                  → healthz check passed
$ curl :6333/collections              → {"collections":[{"name":"agent_memory"},{"name":"crypto_news"}]}
$ curl :8222/varz                     → {"version":"2.14.1", "port":4222, ...}
```
✅ All data services up and answering. Listening ports confirmed via `ss -tlnp`: 9000/9009/8812 (questdb), 6333 (qdrant), 4222/8222 (nats), 54321/54322 (supabase).

### E4 — Collectors (WARN)
**tick-collector** — live but very low throughput:
```
2026-06-02 04:16:29 [INFO] TickCollector: [THROUGHPUT] Received 0 ticks in 30s. Rate: 0.00 ticks/s. Total ticks: 14
```
Ticks ARE landing in QuestDB (see E7), so the pipe works; rate is near-zero (off-hours / sparse feed). ⚠️ low-throughput note.

**news-collector** — healthy, writing to **CLOUD** Supabase:
```
[NEWS] RSS Feed Cointelegraph poll complete. Discovered 2 new articles.
POST https://wnigkahkamoizjpmpuxs.supabase.co/rest/v1/news_articles "HTTP/1.1 201 Created"
[WARNING] [NEWS] Finnhub API key is placeholder. Skipping Finnhub polling.
```
⚠️ Finnhub source skipped (placeholder key). RSS path healthy.

### E5 — tmux / automation (FAIL + partial)
```
$ tmux ls
no server running on /tmp/tmux-1000/default
$ ps -eo pid,etime,cmd | grep -E 'run_agents|main.py|crypto_bot|telegram|watchdog|sentiment|vector'
(no matches — only containerized run_tick_collector.py / run_news_collector.py)
$ crontab -l
@reboot sleep 30 && cd ~/ut-bot-lumibot && bash scripts/start_all.sh >> ~/logs/startup.log 2>&1
45 13 * * 1-5 ~/ut-bot-lumibot/scripts/pre_market_check.sh
0 23 * * 1-5 cd ~/ut-bot-lumibot && source venv/bin/activate && python3 scripts/seed_historical.py --mode daily >> ~/logs/daily_update.log 2>&1
$ sudo -n crontab -l  → no crontab for root
```
🔴 **0/8 tmux sessions.** Expected 8: agents, trading-bot, crypto-bot, sentiment, vectors, options, telegram-bot, watchdog. Crontab is missing the 30-min watchdog and 3 AM hardener jobs (watchdog is designed to run as a tmux session — which is down). systemd timers list contains only OS timers, nothing app-specific.

**Crash-on-launch proof** — `start_all.sh`'s own embedded health check (run 20 s after launching the 8 sessions) reported, from `~/logs/startup.log`:
```
CRITICAL ISSUES (RED):
   ❌ bot_status heartbeat stale (272010s) while target=running
MINOR ISSUES (YELLOW):
   ⚠️  No tmux sessions running
   ⚠️  Latest regime detection is 75.7h old
  OVERALL STATUS: 🔴 RED
```
So the sessions were created and **all exited within ~20 s**. Dependencies are installed and entrypoint syntax is valid (see E10), so this is a **runtime crash on startup**, not a missing-dependency problem.

### E6 — Cloud heartbeat / kill switch (FAIL / disengaged)
```
$ curl $SUPABASE_URL/rest/v1/bot_status?id=eq.1
[{"status":"online","target_status":"running",
  "last_heartbeat":"2026-05-30T00:29:40Z","mode":"paper","symbol":"SPY",
  "uptime_seconds":139121,"session_id":"c4398034-..."}]
$ date -u  → 2026-06-02T04:20:57Z
$ curl .../news_articles -I (Prefer count) → content-range: 0-0/2090
```
🔴 Heartbeat **75.8 h stale** (last 2026-05-30T00:29Z). `target_status='running'` → **kill switch is DISENGAGED** (trading is *allowed*; it's simply not running). Cloud REST reachable; news_articles = 2090 rows and growing.

### E7 — Data freshness & mount-binding (PASS, except ohlcv_1m)
```
$ curl :9000 SELECT count(),max(timestamp) FROM ticks
  → [4861, "2026-06-02T04:18:54Z"]        (live, ~2 min before audit)
$ curl :9000 SELECT count(),max(timestamp) FROM ohlcv_1m
  → [0, null]                              ⚠️ EMPTY
$ qdrant agent_memory → points_count: 91 ;  crypto_news → points_count: 297
$ docker inspect (mounts)
  questdb: /mnt/tick-storage/questdb => /root/.questdb
  qdrant : /mnt/tick-storage/qdrant  => /qdrant/storage
  tick/news-collector: /home/k2/ut-bot-lumibot => /app   (code only)
$ find /mnt/tick-storage -newest
  /mnt/tick-storage/questdb/db/ticks~9/wal350/... (written 2026-06-01 21:15 MST)
```
✅ **Cross-check passed:** QuestDB & Qdrant data live on the mounted 7.3 TB drive; collectors only bind the code dir; tick data is actively writing to `/mnt/tick-storage`, NOT root. ⚠️ `ohlcv_1m` aggregate table is empty.

### E8 — Local Supabase tables (PASS infra, data empty)
```
$ docker exec supabase_db_Antigravity psql -U postgres -c "pg_stat_user_tables"
  regime_states      | 0
  trade_performance  | 0
  signal_performance | 0
```
✅ Local Postgres healthy and key tables exist; ⚠️ they are empty because **production data lives in CLOUD Supabase** — the local Antigravity stack is dev/secondary (matches ops topology).

### E9 — edge_runtime & uncreated compose services (FAIL / WARN)
```
$ docker inspect supabase_edge_runtime_Antigravity
  RestartPolicy=no  ExitCode=255  OOMKilled=false  Error=""
  FinishedAt=2026-05-24T00:00:38Z   (≈9 days down)
$ docker logs (tail)  → "Serving functions on ..." then nothing (clean last line, no traceback)
$ docker ps -a | grep -E 'sentiment-scorer|vector-store'  → NOT CREATED
```
🔴 edge_runtime stopped at midnight 2026-05-24, not OOM, no error captured, **`restart=no` → never recovers**. `start_all.sh` only `docker compose up -d`s 5 services, so the `sentiment-scorer`/`vector-store` *compose* services are never created (their tmux equivalents are the intended path — also down).

### E10 — Pipeline code & dependencies (informational)
```
$ grep add_node agents/orchestrator.py
  regime_detection_node, execution_filter_node, market_analysis_node, signal_node,
  debate_node, greeks_intercept, kelly_sizing, risk_node, research_node, report_node  (10 nodes)
$ venv/bin/pip list | grep -E langgraph/langchain/anthropic/lumibot/alpaca
  langgraph 1.2.1 · langchain 1.3.1 · anthropic 0.103.1 · lumibot 4.5.29 · alpaca-py 0.43.4
$ venv/bin/python -c "ast.parse(open('run_agents.py').read())" → syntax OK
```
Pipeline wiring + deps present; `run_agents.py` runs the orchestrator on a 900 s (15-min) cadence. Code is intact — the failure is at **runtime startup**, captured only inside the (now-gone) tmux panes.

### Resource snapshot (`docker stats --no-stream`)
QuestDB 1.08 GiB / 11.6% CPU (actively ingesting), Qdrant 710 MiB, all others nominal; host load 0.72, plenty of headroom (64 GiB RAM, 795 GiB root free).

---

## D. Findings — root cause & recommended fix

| ID | Sev | Finding | Root-cause hypothesis | Recommended fix (NOT executed) |
|----|-----|---------|------------------------|-------------------------------|
| F1 | 🔴 | All 8 tmux app sessions die within 20 s of launch → trading/agent/Telegram layer down | Runtime exception on startup (deps & syntax OK). Likely env/credential, broker-connection, or import-time error surfaced only inside tmux panes (lost on exit) | Launch ONE session in the foreground to capture the traceback, e.g. `source venv/bin/activate && python run_agents.py` (interactive, controlled window); fix the surfaced error; consider redirecting each tmux command to a per-session logfile so failures persist |
| F2 | 🔴 | Cloud `bot_status` heartbeat 75.8 h stale; regime detection 75.7 h old | Trading bot offline since 2026-05-30 00:29 UTC — same root cause as F1 | Resolve F1; verify heartbeat resumes (`status=online`, fresh `last_heartbeat`) |
| F3 | 🔴 | `supabase_edge_runtime` exited 255, down ~9 days, `restart=no` | Stopped at 2026-05-24 00:00 (not OOM, no error); no restart policy so it stayed down through the 04:02 stack restart | If local edge functions are needed: `docker start supabase_edge_runtime_Antigravity` (or `supabase start`) and set a restart policy. If unused (cloud is primary) — document as intentionally-off to silence the alarm |
| F4 | ⚠️ | No 30-min watchdog & no 3 AM hardener in cron; no root crontab | Watchdog only runs as a tmux session (currently dead → no self-healing); hardener (commit `5a015c1`) appears to have been a one-off, not scheduled | Add a cron-level watchdog independent of tmux (so it can resurrect dead sessions) and schedule the hardener if it's meant to be nightly |
| F5 | ⚠️ | `ohlcv_1m` QuestDB table empty (0 rows) | 1-min OHLCV aggregation likely produced by a worker that's part of the down tmux layer, or not wired to QuestDB | Re-check after F1 fix; confirm which process populates `ohlcv_1m` |
| F6 | ⚠️ | tick-collector throughput ~0.03 ticks/s | Off-hours / sparse Alpaca feed; data is still flowing (4861 rows) | Re-measure during market hours; verify `CRYPTO_SYMBOLS`/`INGEST_SYMBOLS` subscription breadth |
| F7 | ⚠️ | Finnhub key is placeholder → Finnhub news skipped | Credential not provisioned | Provision real `FINNHUB_API_KEY` or accept RSS-only and document |
| F8 | ⚠️ | `sentiment-scorer`/`vector-store` compose services never created | `start_all.sh` brings up only 5 of the compose services; the rest are run as tmux | Pick one path (compose OR tmux) to avoid drift; document the intended one |

---

## E. Independent-Control Matrix (can each be cycled alone?)

| Component | Cycle alone? | Dependencies / blast radius |
|-----------|--------------|------------------------------|
| QuestDB | ✅ Yes (`docker compose stop/up -d questdb`) | **Stopping breaks:** tick-collector ingest, ohlcv reads, health_check table list, any agent reading market data. tick-collector has `depends_on: questdb` (affects start ordering only). |
| Qdrant | ✅ Yes | **Stopping breaks:** vector-store, sentiment retrieval, agent_memory/crypto_news reads. |
| NATS | ✅ Yes | **Stopping breaks:** message bus between collectors and consumers; tick/news-collector + sentiment/vector `depends_on: nats`. |
| tick-collector | ✅ Yes | Needs questdb+nats up to be useful. Cycling it alone is safe. |
| news-collector | ✅ Yes | Needs nats; writes to cloud Supabase. Safe to cycle alone. |
| Local Supabase stack | ⚠️ Partial | Services are interdependent (kong→auth/rest/realtime; all→db). Cycle the whole stack via `supabase stop/start`; individual `docker stop` of `db` cascades to most others. `edge_runtime` CAN be cycled alone. |
| Cloud Supabase | n/a | Managed remotely; not cycled from this host. |
| tmux session `agents` | ✅ Yes | Independent process; consumes QuestDB/Qdrant/cloud Supabase + Anthropic API. Killing it stops the LangGraph pipeline only. |
| tmux `trading-bot` (main.py) | ✅ Yes | Owns the **heartbeat** + kill-switch poll; killing it stops heartbeats (bot_status goes stale) and trade execution. |
| tmux `crypto-bot` / `options` | ✅ Yes | Independent; depend on QuestDB + broker creds. |
| tmux `sentiment` / `vectors` | ✅ Yes | Depend on Qdrant (+NATS). Killing `vectors` stops embedding writes. |
| tmux `telegram-bot` | ✅ Yes | Independent; needs `TELEGRAM_BOT_TOKEN`. Killing it only stops command/notify interface. |
| tmux `watchdog` | ✅ Yes | Monitors/restarts others; killing it removes self-healing but harms nothing directly. |
| Kill switch | ✅ Yes (DB flag) | A single `target_status` value affects every process running the heartbeat loop (currently the trading bot). Independent of container lifecycle. |

> Note: `start_all.sh` is **all-or-nothing** (it `tmux kill-session`s all 8 then recreates them). For single-component cycling, use the per-session `tmux new-session`/`tmux kill-session` commands in the inventory table rather than re-running `start_all.sh`.

---

## F. Open Risks

1. **🔴 No running trading/agent layer for ~3 days** and reboot did not heal it (crash-on-launch). Highest-priority operational gap.
2. **🔴 No restart policy on `supabase_edge_runtime`** — silently absent for 9 days; any reliance on local edge functions is broken.
3. **⚠️ Self-healing depends on a tmux watchdog that is itself part of the dead tmux layer** — single point of failure. A cron- or systemd-level watchdog would survive an app-layer crash.
4. **⚠️ Crash diagnostics are lost** — tmux sessions launched without per-session log redirection, so the startup traceback (root cause of F1) is unrecoverable post-mortem. Add `>> ~/logs/<session>.log 2>&1` to each launch.
5. **⚠️ Kill-switch coverage** — only processes importing `strategies/heartbeat.py` honor `target_status`. Docker collectors and standalone workers do **not** respond to the remote shutdown flag; a true "stop everything" still needs container-level action.
6. **⚠️ Config drift** — `sentiment-scorer`/`vector-store` exist both as compose services (never started) and tmux sessions; `ohlcv_1m` empty; Finnhub key placeholder.
7. **⏭️ Not verifiable from host:** Netlify dashboard build/deploy state and cloud project internals (only cloud REST reachability confirmed).

### Cross-check of the recently-fixed failure mode — ✅ CLEAR
The drive is a genuine 7.3 TB mount (not a root-disk stub), `check_mount.sh` is present and sourced by `start_all.sh`, and QuestDB/Qdrant data + live ticks are confirmed writing to `/mnt/tick-storage` (not root). **No service is currently writing tick data to the root disk.**

---
*End of read-only audit. No state was modified. Report not committed.*
