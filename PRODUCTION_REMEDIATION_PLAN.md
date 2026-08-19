# Disrupting Alpha Production Remediation Plan

> **This audit applies to the Disrupting Alpha algorithmic trading architecture. Django is not an architectural requirement.**

**Audit base:** `96e157aa6399307c590ca56a3d05fd9cecbce929` · **Date:** 2026-08-19 UTC · **Starting verdict:** NOT READY / 41%.

This plan deliberately does not migrate frameworks, tune UT Bot, expand AI features, switch live services, or move databases during the audit. Every gate requires executable evidence; a merged implementation without a receipt does not close a finding.

## Phase 0 — P0 closure (trading safety only)

1. **Declare one canonical options executor.** Inventory enabled host units, cron, tmux, Compose profiles and manual wrappers. Disable/retire competing launch definitions only through a separately reviewed deployment change. Use one account+strategy scoped lease acquired before any broker client is constructed; make all alternate executors fail closed. Test two processes and two different launch mechanisms.
2. **Centralize fail-closed broker mode resolution.** Accept only typed `true|false`; malformed/unset production settings must choose paper or abort, never infer live. Live requires independent explicit acknowledgement and endpoint allow-list. Use the resolver for Lumibot, both REST adapters, dashboard flatten, scripts and tests. Mock every money-moving route and prove `ALPACA_IS_PAPER=true` never reaches `api.alpaca.markets` despite stale base URLs.
3. **Build a broker-authoritative lifecycle state machine.** Assign stable `client_order_id`/correlation IDs; persist intended quantity, filled quantity, remaining quantity, status and parent signal before submit. Model all Alpaca states (`new`, `accepted`, `pending_new`, `partially_filled`, `filled`, `canceled`, `expired`, `rejected`, `pending_cancel`, `pending_replace`, `replaced`). Retries must be idempotent.
4. **Reconcile before entry permission.** At startup and continuously fetch broker positions, all working/recent orders and fills. Resolve local-flat/broker-open, local-open/broker-flat, pending entry/exit and partial fill before entry. Unknown state means `BLOCK_ENTRY`, while deterministic existing-position exit remains available.
5. **Make kill and EOD persistent workflows.** Transition: disable entries → cancel opening orders → query broker → submit close for actual filled quantity → reconcile/retry → verify broker flat → emit acknowledged critical alert. Persist active kill across restart. Use Alpaca calendar/early closes. Failure must remain red and page an operator.
6. **Separate safety states.** Implement deterministic `BLOCK_ENTRY`, `MANAGE_EXISTING`, `EMERGENCY_FLATTEN`, and `FULL_HALT` semantics. Data/telemetry/AI/Supabase/GCP uncertainty blocks entries but must not block exits. Apply maximum size/trades/loss/absolute ceiling/exposure and duplicate lease independently of the strategy.
7. **Close invalid-data paths.** Typed market/quote snapshots carry status, event timestamp, receive timestamp, source and reason. Missing/empty/error/stale cannot become price zero, RSI 50, neutral sentiment or empty success. Emergency exits must not depend on entry quote quality.

**Exit evidence:** hermetic unit/contract tests plus supervised paper drills for every acceptance scenario; zero unknown order path; final broker-flat receipts; no open P0.

## Phase 1 — Paper execution validation

1. Run a supervised, bounded paper pilot only after Phase 0. Reconcile broker/local orders and positions at startup, each transition, shutdown and next startup.
2. Capture expected/actual contract, decision quote, order request, broker ID, every status/fill, exit request/status, fees and P&L under one immutable correlation ID.
3. Exercise normal entry/exit plus cancel, replace, reject, partial fill, network timeout after POST, restart, WebSocket disconnect, broker-data outage, broker-trading outage, Supabase outage and disk-pressure simulation.
4. Publish a canonical readiness endpoint exposing broker-state-valid, market-data-valid, entry-allowed/reason, kill state, positions, working orders, last broker/data/signal/useful-work/consumed-output timestamps, executor lease and risk supervisor state.
5. Replace process-only watchdog checks with progress SLOs and severity cadence (seconds for executor/working orders/EOD, minutes for streams/agents, longer for maintenance). Test alert delivery and acknowledgement.
6. Lock Python/Node dependencies, correct pytest discovery/import isolation, and make safety tests mandatory on PRs. Add dashboard function tests, deployment linting, history/entropy secret scanning and offline broker fixtures.

**Exit evidence:** minimum agreed supervised sessions including an early-close day or simulated calendar, no unreconciled order/position, documented incident drill results, and a signed execution-behavior report. Passing does **not** establish alpha.

## Phase 2 — Strategy scientific validation

1. Freeze exact live information timing. Decide completed daily candle/next-session or another explicit rule; reproduce it byte-for-byte in the backtester. Do not validate incomplete-candle live logic with completed-bar tests.
2. Create immutable experiment IDs binding Git SHA, strategy/parameters, universe, data manifest/hash, corporate-action policy, time zone/calendar, contract rules, quote source, cost model and random seed.
3. Run real-quote OOS and walk-forward evaluation for the actual UT Bot option expression. Separate synthetic/Black-Scholes mechanics from real-quote evidence.
4. Add parameter sensitivity, regime breakdown, Monte Carlo/path/bootstrap uncertainty, multiple-trial tracking, PBO and Deflated Sharpe where statistically applicable. Document survivorship and look-ahead controls.
5. Define profitability/promotability thresholds before results. Preserve losing/null experiments. Execution correctness and profitability receive separate approvals.

**Exit evidence:** reproducible real-data report, locked OOS results, uncertainty/multiple-testing treatment and independent review. No profitability claim is allowed from synthetic output.

## Phase 3 — Extended paper and drift

1. Add a paper-shadow record matching expected signal/contract/quote/fill/exit/P&L to actual values by correlation ID.
2. Run through varied volatility/liquidity/regime conditions and scheduled early closes. Measure missed signals, contract mismatch, quote age/spread, fill slippage, lifecycle latency, exit drift and P&L attribution.
3. Establish SLOs and promotion gates: broker reconciliation lag, market freshness, working-order age, EOD flat deadline, alert delivery, executor uptime/useful-work, data loss and drift tolerances.
4. Perform recovery drills: edge reboot with open/pending positions, corrupt local state, database outage, disk full, collector/agent/watchdog death and broker outage.

**Exit evidence:** extended paper window with no safety breach, explained drift, SLO history and incident runbooks exercised by someone other than the author.

## Phase 4 — Infrastructure simplification

1. Only after safety is stable, assign one owner per process: systemd for critical edge executors/watchdogs, Compose for bounded data services, no tmux/cron duplicate ownership.
2. Keep broker/risk/exit local and independent of Supabase/GCP/dashboard/Telegram/AI. Classify Supabase uses; move high-volume raw OHLCV/ticks first, retain low-volume control/telemetry only with explicit degraded semantics.
3. Use QuestDB for bounded hot data, manifested/compacted parquet for warm replay, BigQuery/object storage for cold analytics. Set retention, capacity, inode and restore SLOs. Bound Docker logs/caches.
4. Revalidate BigQuery/Pub/Sub idempotency, natural keys, ack-after-durable-write, cursor advancement, lag alerts and bulk-seed/stream cutover. Never make replication part of exits.
5. Prove `pg_partman` maintenance by observing future partition creation beyond the horizon; alert on horizon days, default-partition growth and cron failure before any migration.
6. Rotate/revoke historical secrets at providers, prefer WIF/short-lived identity, remove static service-account keys, and retain rotation receipts without secret values.

**Exit evidence:** architecture ownership map matches enabled host state; capacity/retention/restore and replication drills pass; exits work during total analytics/control-plane outage.

## Phase 5 — Micro-live readiness

1. Convene a separate go/no-go review; paper success is not automatic approval. Require Phase 0–4 evidence, strategy sign-off, security review, broker permission review and operator coverage.
2. Use a distinct live credential/project/account configuration, tiny hard broker-side/account-side notional, one strategy/symbol, no unattended scaling, and an explicit rollback/flatten drill.
3. Require two-person live-mode activation, immutable audit logging, launch-time endpoint/account fingerprint confirmation and continuous broker reconciliation.
4. Set loss/order/position ceilings below paper settings, staged canary hours, manual observation, and automatic entry block on any unknown state. Existing positions remain manageable.
5. Review every live fill and drift daily. Any duplicate, uncorrelated order, stale-data decision, missed EOD flat, reconciliation breach or unexplained alert stops the pilot.

**Exit evidence:** a new, explicit micro-live approval. This plan does not authorize live trading.

## Priority ledger

| Priority | Closure theme | Owner discipline | Proof required |
|---|---|---|---|
| P0 | unintended/duplicate order, loss of position control, invalid-data trade, paper→live route | trading + broker + SRE | deterministic tests and supervised broker receipts |
| P1 | recovery, monitoring, risk correctness, credentials, test reproducibility | SRE + QA + security | failure injection, alert/recovery receipts, CI green |
| P2 | scientific validity, drift, storage lifecycle, replication correctness | quant + data | immutable experiments, SLOs, reconciliation reports |
| P3 | performance and AI/product enhancements | product/research | only after higher priorities close |

AI feature expansion, strategy optimization, framework migration, live configuration changes, and database migration are explicitly sequenced behind P0/P1 closure.
