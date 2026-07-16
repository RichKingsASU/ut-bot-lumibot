# Production Readiness Checklist

**Status: 🔴 NOT READY FOR LIVE TRADING**
**Compiled: 2026-07-16** — synthesized from all audit/handoff docs in this repo.

The binding verdict comes from `DISRUPTING_ALPHA_SETTINGS_AUDIT.md` (2026-07-16):
*"NOT READY FOR TRADING… Do not enable live trading until the §25 stop-ship items are fixed."*
Older "ready for pilot" claims (`FULL_STACK_AUDIT.md`, 2026-05-14) are scoped to supervised **paper** trading and predate the RED live-QA pass (`qa_audit_report.md`, 2026-06-02).

Source docs: `DISRUPTING_ALPHA_SETTINGS_AUDIT.md`, `docs/fleet_signal_audit.md`, `AUDIT.md`,
`REMEDIATION.md`, `qa_audit_report.md`, `FULL_STACK_AUDIT.md`, `HARDENING_CHANGELOG.md`,
`DEPLOYMENT_SAFETY.md`, `INCIDENT_RESPONSE.md`, `docs/USER_ACTION_REQUIRED.md`,
`docs/SUPABASE_AUDIT.md`, `docs/MCP_CONNECTION_AUDIT.md`, `docs/provenance_reality_report.md`,
`HANDOFF_V2_PHASE5_5.md`, `HANDOFF_V2_PHASE6.md`.

---

## ✅ DONE / verified

### Research & intelligence stack (Phases 5.5–6)
- [x] HMM regime detector, Kelly position sizer, signal-decay monitor built (`agents/`), unit tests pass
- [x] QuestDB HF backtester + rolling-HMM overlays + decay/recovery sim — 3 milestones complete, tests pass
- [x] Backtest safety lock — synthetic data fails closed by default (`SyntheticDataError` unless `--allow-synthetic`)
- [x] 4 backtest suites pass on real data (`test_costs`, `test_golden_trade`, `test_questdb_loader`, `test_signal_parity`)

### Hardening (May 2026)
- [x] Absolute daily-loss safeguard (`ABSOLUTE_DAILY_LOSS_LIMIT`, $5k fail-closed default)
- [x] Remote kill-switch (DB-driven), operator command center, 30s flatten cooldown
- [x] WebSocket streaming (<100ms), N+1 query fixes, live dashboards off mock data
- [x] Admin-key enforcement on Netlify functions; RLS revoked on `system_alerts`/`system_audit`

### Fleet safety
- [x] **Paper/live gate fixed** (`e72c643`) — base URL derives from `ALPACA_IS_PAPER`; validator overrides env
- [x] IC sign-convention fix (`db4f22a`) — **partial only** (join + fail-safe still open, see P0-9)

---

## 🔴 P0 — STOP-SHIP blockers (must fix before ANY live trading)

### Settings / broker safety (audit §25)
- [x] **DA-02** `alpaca-flatten` defaults to LIVE + fails open → **FIXED** (branch `harden/p0-broker-safety`): now defaults paper (`resolveIsPaper`), fail-closed auth (`requireAdmin`), live flatten requires typed `{"confirm":"LIVE"}`. *Pending: deploy + test.*
- [ ] **DA-01** Paper/Live UI selector decorative; UI can disagree with runtime → single authoritative mode store the worker reads *(frontend — not in this batch)*
- [x] **DA-03** `alpaca-account` open credential/base-URL proxy → **FIXED**: requires admin auth even with body creds; base URL whitelisted to the two Alpaca endpoints. *Pending: deploy + test.*
- [ ] **DA-04** Admin API key shipped to browser bundle + localStorage (`VITE_ADMIN_API_KEY`) → move privileged calls server-side *(frontend/deploy — not in this batch)*
- [x] **DA-05** `ALPACA_IS_PAPER` vs `ALPACA_BASE_URL` divergence → **Already addressed** in `config_validator.py` (e72c643): live+paper-url → FATAL exit; paper+live-url → overrides to paper endpoint. Both directions now fail-safe.
- [x] **DA-06** Admin auth fails open when `ADMIN_API_KEY` unset → **FIXED**: `requireAdmin` fails closed (503) in deployed contexts; applied to flatten/account/orders/positions.

### Fleet criticals (audit 2026-07-15, OPEN)
- [ ] **P0-7 (HITL)** No human-approval gate on any order path; HITL queue has no reader/UI and is disabled → wire `get_approved_signals` into bots OR delete the module + its misleading "execution held" log. **BACKLOG (owner, 2026-07-16): theoretical while the equity bot is inert; becomes ACTIVE the moment the signal fires. Must-implement before any live-trading consideration — not now, not forgettable.**
- [ ] **P0-8 (params)** Live bot trades unbacktested `14/3.0` on 4-branch SMA that no backtest covers → backtest `14/3.0` on 4-branch, or revert `main.py` to `10/1.0`. **DEFERRED by owner (2026-07-16) — decision pending.**
- [x] **P0-9 (decay)** → **FIXED** (branch `harden/p0-broker-safety`), two parts: (A) `signal_decay_monitor.py` now normalizes `signal_type` to a family token so the IC join can match (`UT_BUY`/`ut_bot`→`ut`) — ⚠️ heuristic, validate against real values once tables have data; (B) `kelly_sizer.py` now **fails closed** on INSUFFICIENT_DATA/None IC — `ic_scalar` = `IC_INSUFFICIENT_DATA_SCALAR` (default 0.5, env-tunable to 0.0 for hard-halt) instead of 1.0. Decay unit tests pass (3/3). *Decision knob for you: 0.5 haircut vs 0.0 hard-halt.*
- [ ] **P0-10 (Kelly)** `payout_ratio` missing commission term → add commission to Kelly + backtest

### Supabase security (staged, NOT applied to prod)
- [ ] **P0-11** RLS-enable migration `20260710000000_supabase_audit_remediation.sql` + grant revocations + SECURITY INVOKER views are staged on a branch but **never `db push`-ed to prod** → verify live state (docs conflict), then apply
  - ⚠️ CONFLICT: `SUPABASE_AUDIT.md`/`MCP_CONNECTION_AUDIT.md` claim "RLS active"; `AUDIT.md` (18 P0s) + fleet #6 say RLS **disabled, anon read/write on `signal_log`**. Resolve against the live DB, not the docs.

### Operational reliability (live QA 2026-06-02 — RE-VERIFIED 2026-07-16: layer is UP)
> Live check 2026-07-16 09:17Z: `bot_status=online`, heartbeat current, `mode=paper`,
> uptime ~32.4h. The June "down 3 days" RED is STALE. Deprioritized — but the SPOF
> root cause below is unproven, and the bot produces no signals (see P0-15).
- [~] **P0-12** tmux sessions crashing → NOT currently reproducing (32h uptime). Verify root cause still latent.
- [~] **P0-13** `supabase_edge_runtime` restart policy → re-verify current state
- [ ] **P0-14** Self-healing depends on tmux watchdog (SPOF); no cron watchdog → still worth installing

### Live-data findings (verified 2026-07-16 via service-role read)
- [ ] **P0-15 (NEW)** SPY equity bot emits nothing: `signal_log`/`trade_performance` EMPTY. **DIAGNOSED 2026-07-16 (branch `debug/signal-zero`, `docs/signal_zero_diagnosis.md`): NOT a code bug — signal=0 is correct.** (1) Strategy polls every 1 min (`sleeptime="1M"`) but trades daily bars (`timeframe="1D"`), so all "375 iterations" re-evaluate the SAME daily bar (~1 real eval/day). (2) UT buy needs a crossover (`close>stop` AND `prev_close<=prev_stop`); on the ~5 scattered days the bot ran, price was already mid-uptrend → no transition. 14/3.0 CAN fire (~10×/yr; last 2026-06-15, bot was offline); 10/1.0 also computes 0 on the actual run-days. Not params/data/impl. **Real cause = operational: cadence mismatch + poor uptime (bot alive only ~5 days, never online during a crossover).** Fix: align poll cadence to daily bar + ensure continuous uptime; signal logic unchanged. → **Downgrades P0-8 urgency** (strategy isn't defective).
- **RLS reads**: anon BLOCKED on all sensitive tables (signal_log, agent_signals, bot_status, trade_performance, signal_performance, regime_states, user_settings, risk_config, news_articles, portfolio_snapshots) — fleet #6 not borne out for reads. ⚠️ anon WRITE still untested.
- **P0-9 CONFIRMED**: `signal_performance.status` = 100% INSUFFICIENT_DATA (504/504).
- Fleet #9/#11 confirmed live: crypto agent writes `signal_type=NONE`, `timesfm_forecast` column populated by a "Linear Baseline" (polyfit), not TimesFM.

### Post-merge verification (2026-07-16, after PRs #49/#50/#51 merged to main)
- ✅ **Netlify hardening LIVE + `ADMIN_API_KEY` set**: deployed `alpaca-account` returns **HTTP 401** (fail-closed working), not 503, on both `disruptingalpha.com` and `.netlify.app`. DA-02/03/06 confirmed deployed.
- 🔴 **RR-worst — WRONG ALPACA ACCOUNT** *(original finding)*: earlier this day the referenced creds (`PKGSLL62…`) authenticated to account **`PA3W7I3UVDS2`**, NOT the required **`PA3ZBZQM5K7H`**. That account held **3 open crypto positions** (BTC/ETH/SOL). `user_settings` has no `alpaca_account_id` recorded (only a `paper_mode` row).
- ✅ **RESOLVED (2026-07-16 ~06:23 MST)** — verified read-only, no credential edit was needed:
  - The live `/home/k2/ut-bot-lumibot/.env` (the **only** `.env` in the repo; the `EnvironmentFile` for all four `da-*` systemd units) authenticates to **`PA3ZBZQM5K7H`** — the required account. Confirmed via `account.account_number` (the earlier check used `account.id`, which is a **UUID**, not the `PA…` number — that comparison never matched). Equity **$96,275.97, all cash, 0 open positions**. Bots verified on it post-restart (logs: "Trading Mode: PAPER (Verified)", portfolio snapshot equity $96,275.97, no errors).
  - The `PKGS…` → `PA3W7I3UVDS2` credentials now exist **only** in the June `.env.bak.*` backups; the live `.env` (mtime 2026-06-04) was already the correct `PKBR…` creds. No swap performed today.
  - ⚠️ **Left intact, out of scope:** the **3 crypto positions (~$72k)** remain **open on the wrong account `PA3W7I3UVDS2`** (reachable only via the backup creds; equity $97,764.49 / cash $26,073.61). Deliberately not closed — pending a separate decision.
  - Bots were cleanly stopped 06:04 MST (deliberate `systemctl stop`, graceful SIGTERM — not a crash, not the watchdog) and restarted 06:23 MST on the verified-correct account.
- Note: local `.env` has `ALPACA_BASE_URL` **blank** (runtime derives it from `ALPACA_IS_PAPER=true`).

---

## 🔴 Additional P0/CRITICAL from full forensic risk register (`reports/risk-register-20260716.md`, 2026-07-16)
> This later forensic audit (5 CRITICAL / 15 HIGH / 5 MEDIUM) surfaced items not in the earlier synthesis. Not yet fixed.
- [x] **RR-worst — RESOLVED (2026-07-16)** Live `.env` (all `da-*` units) authenticates to the **required `PA3ZBZQM5K7H`**; verified via `account_number`, bots restarted and confirmed on it. Wrong-account (`PA3W7I3UVDS2`) positions left open pending separate decision. See Post-merge verification section above. *(Fix the identity check to compare `account.account_number`, not `account.id` — the latter is a UUID.)*
- [ ] **RR A-02 (CRITICAL)** `kelly_sizer.get_portfolio_value()` silently substitutes hardcoded `BASE_PORTFOLIO=107879` on Alpaca fetch failure → wrong position dollars on any broker/API outage (fail-open, no degraded heartbeat/halt). `kelly_sizer.py:20,146-168`.
- [ ] **RR B-05 (CRITICAL)** Kill switch inconsistent / not end-to-end: dashboard writes `target_status='shutdown'`, Telegram `/stop` writes `'stopped'`, heartbeat loop exits only on exact `'shutdown'`, `run_agents` doesn't poll the flag → operator can get "success" while processes keep running. (Contradicts the "kill switch works" hardening claim.)
- [ ] **RR B-06 (CRITICAL)** Orders have no `client_order_id`/idempotency key; `open_position` set only after confirmed fill → disconnect-after-acceptance can duplicate orders; partial fills treated as "not filled." `options_executor.py`.
- [ ] **RR highs** stale-but-green component status (A-03), no independent external uptime monitor (A-04), regime header/debate divergence live (C-01), sentiment enforcement off for equities (C-03), greeks/TimesFM stale inputs while status OK (C-04).
- Note: risk register rates IC/decay sequencing (B-03) and UT-bot daily-bar freshness (B-04) as **PASS** — reconcile B-03's "Kelly checks status" view with the fail-open I fixed in P0-9 (it defaulted to `1.0`, which is what changed).

## 🧪 MUST-TEST before production (no automated safety tests exist today — audit §20)

### Safety / kill-switch
- [ ] Missing/invalid creds → trading disabled (fail closed)
- [ ] Inconsistent mode + creds → fail closed
- [ ] Kill switch actually blocks order submission (verify bot consumes `trading_enabled` — DA-09/10)
- [ ] `alpaca-flatten` rejects when `ADMIN_API_KEY` unset; requires typed "LIVE" confirmation
- [ ] Live endpoints unusable without explicit confirmation

### Paper/Live integrity
- [ ] Worker receives updated config; paper mode selects paper client+creds, live selects live
- [ ] UI can never show "Paper" while runtime is Live (no silent divergence)
- [ ] `PAPER=true` + live URL is rejected (currently only warns — §17)

### Settings persistence
- [ ] Save writes a single non-duplicate row (needs `UNIQUE(key)` — DA-07); refresh reloads
- [ ] Secret fields never expose stored secrets; blank secret preserves stored value

### Live-data confirmations (query the real DB — fleet audit §7 could not)
- [ ] Is `signal_performance.status` 100% INSUFFICIENT_DATA? (confirms P0-9)
- [ ] `signal_log.signal_type` vs `trade_performance.signal_type` mismatch (`UT_BUY` vs `ut_bot`)?
- [ ] Does `regime_states` actually contain data?

### Deploy checklist (`DEPLOYMENT_SAFETY.md` — all currently unchecked)
- [ ] `flake8 .` / `npm run lint`
- [ ] `mypy .`
- [ ] `pytest`
- [ ] Env validation — `ALPACA_IS_PAPER` set correctly
- [ ] Secret scan — no keys committed
- [ ] `docker-compose config`

### Post-fix reproduction (Phase 6)
- [ ] `pytest backtests/tests/test_questdb_loader.py test_hmm_switching.py test_decay_recovery.py -v`
- [ ] Re-run options / HMM / decay backtests with `--no-synthetic`

---

## 👤 Human-only actions (only the operator can do these)
- [ ] Set & weekly-rotate `ADMIN_API_KEY`; set `MAX_DAILY_LOSS` for the real account size
- [ ] Populate Netlify env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ALPACA_*`, `ADMIN_API_KEY`)
- [ ] Apply staged Supabase migration to prod (`supabase db push`) after review
- [ ] Rotate service-role key; restart tmux/host workers
- [ ] Remember: paper→live requires an env edit + process restart — the UI cannot be trusted to switch mode
- [ ] Start host worker processes (`run_agents.py`, `run_crypto_bot.py`, `main.py`) — no systemd units exist yet

---

## ⚠️ Strategic caution (not a checklist item — a decision input)
- Phase 6 rolling-HMM SPY backtests are **net-losing across all three configs (−51% to −65%)**. Even once safety is fixed, the strategy edge itself is unproven live. Do a supervised paper run before any live cutover.

## Doc conflicts to resolve against the live system
- [ ] RLS status on `signal_log` (SUPABASE_AUDIT/MCP say active; AUDIT/fleet say disabled)
- [ ] Whether Harness CI exists (`MCP_CONNECTION_AUDIT` says no; `provenance_audit_map` references `.harness/pipeline.yaml`)

---

## Suggested sequence
1. Verify live DB/RLS state + whether the trading layer is currently up (read-only)
2. Fix the 6 P0 settings stop-ships + wire the kill switch
3. Resolve HITL (P0-7) and the live-vs-backtested param mismatch (P0-8)
4. Write the safety test suite (all "MUST-TEST" items above)
5. Supervised paper run, then reassess before any live cutover
