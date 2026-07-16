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
- [ ] **P0-7 (HITL)** No human-approval gate on any order path; HITL queue has no reader/UI and is disabled → wire `get_approved_signals` into bots OR delete the module + its misleading "execution held" log. **DEFERRED by owner (2026-07-16) — decision pending.**
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
- [ ] **P0-15 (NEW)** SPY equity bot heartbeats but emits nothing: `signal_log`/`trade_performance` EMPTY. **ROOT-CAUSED 2026-07-16:** plumbing works — `component_heartbeat` shows `supabase-logger-bar_log` OK at 375 cycles (writes every iteration), but there is **no `supabase-logger-signal_log` component at all** → `signal_log` write (ut_bot.py:191, gated on `current_signal != 0`) has **never been attempted across ~375 iterations**. ∴ the UT Bot's `current_signal` is perpetually 0 — it never fires a buy/sell. Not a write/RLS bug; the **signal computation produces nothing**. Directly tied to **P0-8** (the live 14/3.0 4-branch implementation). Fix gated on the P0-8 decision.
- **RLS reads**: anon BLOCKED on all sensitive tables (signal_log, agent_signals, bot_status, trade_performance, signal_performance, regime_states, user_settings, risk_config, news_articles, portfolio_snapshots) — fleet #6 not borne out for reads. ⚠️ anon WRITE still untested.
- **P0-9 CONFIRMED**: `signal_performance.status` = 100% INSUFFICIENT_DATA (504/504).
- Fleet #9/#11 confirmed live: crypto agent writes `signal_type=NONE`, `timesfm_forecast` column populated by a "Linear Baseline" (polyfit), not TimesFM.

---

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
