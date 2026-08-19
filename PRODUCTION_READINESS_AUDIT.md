# DISRUPTING ALPHA FDE PRODUCTION READINESS

> **This audit applies to the Disrupting Alpha algorithmic trading architecture. Django is not an architectural requirement.**

Repository: `https://github.com/RichKingsASU/ut-bot-lumibot.git`
Branch: `audit/disrupting-alpha-fde-readiness` (audit base was local branch `work`)
Commit: `96e157aa6399307c590ca56a3d05fd9cecbce929`
Audit Date: 2026-08-19 UTC

Overall Readiness: **41%**

Current Stage: **NOT READY**

Supervised Paper: **NO**
Extended Paper: **NO**
Micro Live: **NO**
Live Capital: **NO**

Open P0: **6**
Open P1: **11**

## 1. Scope, baseline, and evidence limits

This is a source-and-test audit, not a runtime certification. At audit start the working tree was clean, the only local branch was `work`, HEAD was the PR #85 documentation commit above, and no Git remote was configured. The latest 20 commits were recorded locally; the leading commits were `96e157a` (#85), `5d8d99a` (P0 closeout), `ad16c13` (UT Bot execution), and `7bfb87e` (Doppler-token cleanup). GitHub PR #86 could not be independently queried: both the GitHub page and API were rejected by the environment and there are no PR refs/remotes locally. Therefore **CLOSED / NOT MERGED is NOT RUNTIME-VERIFIED in this audit**; it is the supplied baseline assertion. The absence of Django on the audited tree *is* verified: no `manage.py`, Django settings/URL/WSGI/ASGI modules, or non-documentation Django imports were found.

Baseline commit sequence (newest first):

```text
96e157a docs: add FDE production readiness audit (#85)
5d8d99a Fix P0 trading safety closeout gaps
ad16c13 feat: complete YOLO execution task for UT Bot SPY
7bfb87e fix(secrets): untrack committed Doppler token, guard install-systemd.sh (#84)
4732d27 Feat/adc wif compatible credentials (#83)
5e22b39 chore: remove dead virtualenvs and move root docs into docs/ (#82)
aa889a4 feat(replication): resolve credentials via google.auth.default() for WIF (#81)
4074f33 feat(migration): bulk seed ohlcv_bars into BigQuery via load jobs (#80)
9a41489 fix(replication): use insert_rows_json correctly and await publish futures (#79)
2c30236 feat(migration): close Gate 0 with direct PostgreSQL introspection (#78)
1a3362d docs(migration): add automated Supabase -> GCP Phase 0 audit (#77)
f09b80a feat(replication): accept GOOGLE_APPLICATION_CREDENTIALS for GCP auth (#76)
c22e6f8 fix(replication): serialize Decimal/datetime rows before streaming (#75)
8183759 fix(compose): stop docker compose from starting a second trading bot (#74)
00c8393 fix(deployment): make da-gcp-replicator.service installable on k2 (#73)
1eefebc feat(replication): working entry point + false-pass guards (#72)
c8aefbd chore(gcp-daemon): sync deployment unit and dictionary after filesystem audit
f4ced4f Merge verified gcp-replication pipeline with staging receipts
916f194 Feature/gcp replication integration (#71)
034f624 Update tests for staging pipeline validation
```

Runtime host claims (systemd enabled state, cron, tmux, mounted storage, broker account, database row counts, credential validity, PR state) are explicitly not promoted to facts without host/API receipts.

## 2. Executive verdict

The repository contains meaningful safety work: the new broker adapter derives paper order routing from `ALPACA_IS_PAPER`, requires a second live opt-in, validates quotes, polls orders, and the new executor has broker reads, a local kill file, a process lock, market-calendar-aware cutoffs, and a flatten verification loop. These are promising controls, not a proven system.

The principal problem is **two competing money-moving implementations**. The documented service in `scripts/systemd/da-trading-bot.service` launches `main.py`/Lumibot, while `systemd/da-trading.service` launches `src/trading/executor.py`. They use separate brokers (`strategies/options_executor.py` and `src/trading/broker.py`) and only the latter owns the `fcntl` lock. Docker standalone/dev can launch `main.py` too. Thus the repository cannot prove exclusivity across all executors. The legacy strategy treats any truthy `buy_to_open` response as entry success and has a once-daily Lumibot cadence despite intraday EOD/exit duties. Its EOD path submits a close but does not prove broker-flat. The newer executor is safer but is not clearly canonical and also consumes the signal before successful fill.

Paper isolation is **PARTIAL**, not PASS. The two principal Python order adapters force paper when `ALPACA_IS_PAPER=true`, and the dashboard flatten defaults to paper. However configuration parsing treats every value other than the exact string `true` as live intent; legacy/read-only clients still consume raw `ALPACA_BASE_URL`; and executable endpoint tests could not run in the audit environment. No live credentials or broker calls were used.

Broker authority is **PARTIAL** in the new executor and **FAIL** system-wide. It queries broker positions/open orders every five seconds, but legacy `options_executor` retains module dictionaries, startup sync does not reconstruct pending lifecycle/entry metadata, partial fills are not quantity-reconciled end to end, and no event-sourced recovery proves the required restart scenarios.

Strategy profitability is unproven. The option harness has useful spread/slippage/commission and synthetic provenance controls, but live daily-candle timing does not match its intraday option harness or establish completed-bar/next-session semantics. Scientific validation lacks a unified immutable experiment registry, PBO, Deflated Sharpe, multiple-trial accounting, promotion gates, and paper-shadow drift records. **Execution safety can eventually pass while alpha remains unproven.**

## 3. Actual implemented architecture

```text
                     ┌──────── React/Vite dashboard + Netlify functions ────────┐
                     │ Supabase views/control + Alpaca read proxies + flatten   │
                     └──────────────────────────┬─────────────────────────────────┘
                                                │
Alpaca data REST/WebSocket ──► main.py/Lumibot UTBot ──► strategies/options_executor ──► Alpaca trading
             │                  │ heartbeat + health │
             │                  └─ Supabase telemetry / Telegram / kill poll
             │
             ├──────────────► src/trading/executor.py ─► src/trading/broker.py ─► Alpaca trading
             │                    local lock/risk/runtime-state
             ├──────────────► run_agents.py ─► deterministic + LLM agents ─► recommendation/debate/Telegram
             └──────────────► collectors ─► NATS ─► QuestDB / Qdrant / Supabase

Supabase PostgreSQL ─► replication daemon/Pub/Sub ─► BigQuery (analytics/migration path)
Local parquet + QuestDB + Alpaca ─► backtests/ and scripts/* backtest families
systemd + Docker Compose + legacy tmux scripts + cron evidence ─► competing runtime ownership
```

Implemented inventory includes `main.py`, `run_agents.py`, `run_crypto_bot.py`, two options execution stacks, UT Bot and crypto strategies, collectors, agent orchestrator, health/heartbeats/watchdogs, Supabase, replication/BigQuery/Pub/Sub, QuestDB/Qdrant/NATS, React/Netlify, systemd, Docker, tmux startup, cron inventory, and multiple backtest families. GCP is an analytics/migration dependency in source, not required for exits. Supabase is telemetry and control plane for much of the agent stack, but `main.py` still checks it at startup and its cloud kill mechanism is coupled to the orchestrator.

## 4. Money-moving and safety-control inventory

| Path | Entry/process | Capability and parameter source | Broker/control | Paper/live control | Finding |
|---|---|---|---|---|---|
| Legacy options | `main.py` → `UTBotStrategy` → `strategies/options_executor.py` | buy/close; signal, config qty, selected same-day contract/quote | raw Alpaca REST; local module state + broker sync | `_base_url()` forces paper when flag true | Money moving; no shared lock; POST/truthy result can be treated as success |
| New options | `systemd/da-trading.service` → `src/trading/executor.py` → `src/trading/broker.py` | buy/close/cancel; daily signal, env caps, quote-derived limits | raw Alpaca REST; broker polled every 5 s | paper flag + explicit live acknowledgement | Best path, but not canonical/runtime-validated |
| Lumibot broker | `main.py` → Lumibot `Trader` | framework broker activity plus custom options REST | Alpaca SDK config | `ALPACA_CONFIG.PAPER` | Potential second broker channel in same process; exact order authority not proven |
| Crypto | `run_crypto_bot.py` / `main_crypto.py` / adaptive strategy | `submit_order` for crypto | Lumibot/Alpaca configuration | shared environment | Separate money-moving process; not covered by options executor lock |
| Dashboard flatten | Netlify `alpaca-flatten.ts` | cancel all orders + close all positions | admin-key guard, cooldown, live typed confirmation | unset defaults paper; explicit false + `LIVE` confirmation | Destructive money path; submission is reported as success without flat reconciliation |
| Agent tools | `agents/tools/trading_tools.py` | cancel/flatten/kill declarations | approval decorator | URL helper | Stubs return not implemented; currently not money moving |
| Operator kill | Telegram `/stop`/`/resume`, Supabase `bot_control`, local kill file | toggles entry/termination depending process | Telegram/chat and database controls; local file only in new executor | account follows executor | Cloud kill in `main.py` terminates rather than deterministically flattening |
| Config/dashboard | env + settings UI | changes displayed mode/risk settings | environment or Supabase | UI not authoritative | Risk values can diverge from actual process values |

No replace path exists outside broker limit-price polling/PATCH in both option adapters. Cancel-all is broad account scope even when an underlying argument is supplied. This inventory is source-complete for searched submit/cancel/replace/close/flatten calls, but runtime-loaded plugins and untracked host scripts remain outside proof.

## 5. P0 findings

1. **P0 — duplicate executor cannot be excluded. [FIXED IN CODE; TESTED; NOT RUNTIME VALIDATED.]** `src/trading/executor.py` is canonical and acquires an Alpaca account-alias/paper-live `flock` before startup. Both options adapters deny mutations without current-PID authority; dashboard mutation is retired, Docker is explicit-profile only with the host lock mounted, and the installer no longer enables crypto. `tests/test_execution_lease.py` proves duplicate/manual denial, zero mutation HTTP calls, crash/stale-file recovery, strict modes, and read-only access. Edge systemd/Docker execution remains unvalidated here.
2. **P0 — legacy EOD close is not a flat state transition.** `UTBotStrategy` submits `sell_to_close` once and returns; its daily sleep cadence and static 15:55 clock are incompatible with robust intraday supervision. It does not cancel openings, retry, reconcile order states, or confirm flat. The new executor loop is closer but has no independent alert/persistence after ten failures.
3. **P0 — canonical deployment is ambiguous. [FIXED IN CODE; TESTED; NOT RUNTIME VALIDATED.]** Both maintained trading service definitions now invoke `src/trading/executor.py`; the canonical installer installs only `da-trading-bot`, legacy/crypto writers are removed from default startup, and any alternate process converges on the same account lease. Host unit enablement has not been inspected or changed from this environment.
4. **P0 — lifecycle/restart evidence is incomplete. [FIXED IN SOURCE; UNIT TESTED; PROCESS TESTED; EDGE RUNTIME NOT VALIDATED.]** Alpaca REST is authoritative for normalized order states, fills and positions; deterministic client IDs resolve lost responses and prevent duplicate logical entries; partial quantities and mismatch evidence survive versioned atomic cache reload. `tests/test_broker_reconciliation.py` covers pending entry/exit, partial/rejected/canceled/replaced states, query failure, contradictory local state, cloud independence, and a spawned-process restart. No edge/paper broker runtime receipt was available.
5. **P0 — invalid live mode strings fail toward live intent.** Exact-`true` parsing means malformed values choose the non-paper branch. The new broker's second acknowledgement prevents live routing, but the whole repository does not apply that guard consistently (Lumibot/config and other consumers remain).
6. **P0 — invalid market/quote data is not uniformly fail-closed.** The new signal/quote path has explicit validity, but legacy and agent code still maps missing values to `0`, `50`, neutral, empty collections, or defaults. Existing-position management also depends on signal evaluation and reconstructed local entry metadata.

## 6. P1 findings

1. Component health is fragmented: `main.py` heartbeat does not prove `run_agents.py` useful work, and global/dashboard heartbeats can remain green while a component is dead.
2. The kill switch is not one persistent, audited, locally authoritative state machine. Cloud failure can hide cloud kill; `main.py` terminates itself without broker-flat proof.
3. Daily P&L uses equity minus last equity (includes unrealized/change effects) and returns safe-looking zero alongside `valid=false`; some consumers ignore validity.
4. The new executor loses entry underlying/RSI metadata on restart; exit triggers are weakened until reconstructed.
5. Sentiment core distinguishes `OK/NO_DATA/STALE/ERROR`, but no `DISABLED` state exists and research/bull/bear/velocity paths still collapse missing values to zero/neutral.
6. Health endpoints expose process/readiness and broker reachability, not a single authoritative set of broker state validity, market freshness, working orders, executor lease, last useful output, and consumer acknowledgement.
7. Tests are non-hermetic: both mandated suites fail collection because core requirements are absent; broad collection also has a module-name collision.
8. Supabase partition maintenance has delayed-failure exposure: repository evidence only proves partitions through October 2026 and an hourly job at a past inspection, not future creation now.
9. Raw storage has overlapping writers/owners and no repository-backed capacity/retention proof for QuestDB/parquet/Docker caches.
10. Secrets validation is narrow and the live status/revocation of previously tracked credentials is not verifiable from source.
11. Broker/data stream availability, early-close flatten, alerts, and recovery have no supervised paper receipts.

## 7. Detailed control results

### Paper/live isolation — PARTIAL

Principal order adapters and Netlify flatten default to paper, and market data generally uses `data.alpaca.markets`. `ExecutionFilter.check_gap`, the new signal engine, and bars functions use data URLs. Several clock/contract discovery functions use `api.alpaca.markets`; these are read-only, but they weaken endpoint consistency. PASS is withheld because endpoint matrix tests did not execute, malformed mode values are unsafe semantics, and not every broker consumer uses the same resolver.

### Broker authority and lifecycle — FAIL system-wide

The new path polls Alpaca positions/orders and blocks entry on invalid state. It recognizes open orders and its broker polling handles `filled`, `partially_filled`, `rejected`, `canceled`, and `expired`; replace polling exists. There is no complete explicit transition model for `new`, `accepted`, `pending_new`, `pending_cancel`, `pending_replace`, `replaced`; no durable client-order id/idempotency ledger; and no restart correlation of fills to signals. The legacy cache (`_open_positions`, trade records, entry metadata) and Supabase records cannot be trusted over Alpaca. Broker truth must reconstruct all state before entries resume.

Scenario disposition: local-flat/broker-open **partial** on new executor; local-open/broker-flat **partial**; pending entry/exit restart **not verified**; partial fill restart **fail**; rejected/canceled **partial**; replace **partial**; final flat **partial only in new EOD helper**.

### Risk, kill, and EOD

The new supervisor enforces loss and trade count, while executor caps position size, blocks on broker/P&L invalidity, uses market calendar close, gates stale data, validates quotes, and owns a local kill file/lock. There is no complete independent gate for account-wide exposure, quote/data validity across legacy paths, duplicate executor, or absolute loss in all processes. States are not formalized as `BLOCK_ENTRY`, `MANAGE`, `FLATTEN`, `HALT`. Entry-quality checks must not block close orders; the new broker mostly separates them, legacy behavior needs scenario proof.

Kill scenarios: flat **blocks new entry on new path**; position/pending **cancel/close submitted but flat not persistently verified before loop continues**; cloud unavailable **local file still works only on new path**; restart **local file persists, cloud semantics not proven**. Operator authorization/audit depends on channel-specific controls.

### Market data, SPY gap, options quotes

`ExecutionFilter.check_gap` uses `ALPACA_DATA_URL`, not the paper trading host, and returns a failed filter when bars are unavailable. The new signal engine validates empty/stale daily and 5-minute bars and positive prices. Nonetheless its daily bar can be today's incomplete candle, and its 24-hour staleness test is not exchange-session aware. Options qualification in the new broker checks positive bid/ask, ask≥bid, quote age, maximum spread, active/tradable contract, type and same-day expiration; there is no consolidated executable test receipt. Some collectors/agents retain neutral defaults.

### Sentiment zero versus missing

The main agent context now uses nullable averages and status values `OK`, `NO_DATA`, `STALE`, `ERROR`; `NO_DATA/ERROR` can block configured asset classes and stale degrades. However `FINNHUB_API_KEY` still defaults to `placeholder_finnhub_api_key`, there is no explicit `DISABLED`, and downstream research, bull/bear and velocity code still substitutes `0.0`/neutral. A Telegram/debate reader can therefore see neutral-looking output without articles. Finnhub is optional to the deterministic options executor but a material input to the agent recommendation path; its outage must be explicit.

### Heartbeats, watchdogs, and readiness

`main.py` starts its own heartbeat and health server; `run_agents.py` has independent behavior. Therefore main-alive/agents-dead and agents-alive/main-dead can each leave a fresh partial signal. Watchdogs inspect process/tmux/container/API reachability and some signal age, but do not consistently prove useful work or output consumption. `strategies/health_server.py` readiness is essentially startup state and broker URL metadata. The newer runtime JSON has richer fields but is not the canonical HTTP readiness source. A container can be running with collector work stalled.

### Kelly and exposure

Kelly uses broker account equity, historical win/payout inputs, clamps fractional Kelly and a position-value hard cap. Orchestrator cautious flows and Telegram formatting are split across modules; no test proves displayed percent equals the final post-caution fraction and displayed dollars equals equity × that fraction. Classification: **NOT VERIFIED / P1**. Account equity/cash/buying power are broker-derived in some tools; exposure, daily P&L, drawdown and VaR are separately computed, can be stale, and include zero-on-error fallbacks. There is no single freshness-tagged account snapshot recomputed from broker positions.

## 8. Backtest and scientific validity

The `backtests/` harness prioritizes local parquet, Alpaca, then deterministic synthetic data; later QuestDB integration complicates the stated precedence. It models constructed contracts, DTE/strike, ask entry/bid exit, slippage, commissions, spread and Black-Scholes fallback, tags pricing `real|bs`, enforces some production risk, and emits reports/sweeps. Synthetic use is documented and strict provenance machinery exists. This is useful engineering evidence, not live-capital evidence.

**Signal timing parity: FAIL.** `UTBotStrategy` reads a daily frame and enters at/after 15:45 on the likely incomplete current daily candle; the newer executor does likewise. The options harness operates on configurable intraday bars, while `scripts/backtest_utbot.py` is an underlying daily model. No proof establishes completed daily candle → next-session execution, nor identical timestamp/market-calendar semantics.

Scientific inventory: some rolling/walk-forward scripts, regime work, parameter sweeps, deterministic seeds and provenance exist. No unified UT Bot OOS protocol, Monte Carlo distribution, PBO, Deflated Sharpe, multiple-trial ledger, immutable experiment registry, survivorship audit, promotion gate, or paper shadow exists. Look-ahead avoidance is asserted/tested in isolated families, not system-wide. Checked-in DMA reports are not proof of UT Bot option profitability. The historical UT Bot baseline must be regenerated with traceable data before quoting a profit factor.

Tournament readiness is low-to-moderate: reusable runners/metrics/provenance exist, but candidate identity, immutable configuration/data hashes, OOS scoring, stability/regime aggregation, shadow records and deterministic promotion authorization are absent. Time-machine readiness is low: market bars/ticks and some signals are stored, but complete agent prompts/model versions, debate inputs, risk snapshots, client order IDs, lifecycle events, quotes at decision, fills, exits, and P&L lineage are not joined by one correlation ID. Paper-drift readiness is low for the same reason.

AI agents recommend and orchestrate debate; exposed trading tools for cancel/flatten/kill are stubs with approval requirements. The deterministic executor makes orders. However `main.py` polls an agent-side cloud kill and agent/dashboard controls can terminate/flatten. No AI should gain direct ability to alter live mode, risk ceilings, kill deactivation, strategy promotion, or broker authority.

## 9. Data platform, storage, and secrets

| Component | Actual role | Trading dependency conclusion |
|---|---|---|
| Supabase bar/signal/session/trade/agent tables | telemetry, analytics, historical store | Must be noncritical for exits; startup logging/connectivity still creates coupling |
| Supabase `bot_control`/component heartbeat | control plane/health | Transitional; cloud failure must conservatively block entry without blocking exit |
| Supabase OHLCV/partman/cron | historical/transitional | Past evidence: 1.7M+ rows, ~70 RLS policies, monthly partitions through 2026-10, three cron jobs; current runtime size is unverified |
| QuestDB | hot ticks/ingestion/backtest source | Analytics/data dependency; outage must not masquerade as fresh data |
| Qdrant | agent/vector research | Noncritical; should degrade agents, never exits |
| NATS | collector event bus | Data pipeline dependency, not broker/risk authority |
| Parquet | warm deterministic historical/backtest data | Needs manifests, atomic writes, retention and capacity alerts |
| BigQuery/Pub/Sub | cold analytics and migration target | Replication has serialization, awaited publish, load-job, cursor work; never required for exits |

Replication source shows batching/cursors and `insert_rows_json`; bulk seed acknowledges OHLCV lacks the daemon's normal surrogate-ID cursor and uses a server-side cursor/load jobs. Idempotency/natural keys, Pub/Sub ack-after-durable-write, lag SLO and seed/stream cutover still need failure-injection receipts. `pg_partman` remains a delayed-failure risk unless a future partition beyond the current horizon is created and alerted upon.

Estimated repository model: tick rows can reach millions/day per liquid symbol; minute OHLCV is ~390 equity rows/session/symbol, while option chains/ticks are much larger. The repository has no runtime cardinality receipt, so storage growth cannot be responsibly quantified further. Recommended ownership: QuestDB hot (bounded retention), partitioned parquet warm (manifested/compacted), BigQuery/object storage cold; move high-volume tick/OHLCV and replication churn off Supabase before low-volume controls/telemetry.

`.gitignore`, examples, Doppler workflows and WIF changes show improvement, and a formerly tracked Doppler token was untracked. The audit did not print values. The CI scanner only detects two narrow Python assignment patterns and does not scan history, TypeScript, JSON, service-account keys, Telegram/Finnhub/Supabase tokens, or entropy. Active-key rotation cannot be inferred. Treat any previously exposed credential as P1 until provider-side revocation is evidenced (P0 if it can move live funds).

## 10. Observability scorecard

| Area | Score / 5 | Why |
|---|---:|---|
| Process monitoring | 3 | systemd restart and watchdogs exist; ownership conflicts |
| Data freshness | 2 | several checks, not end-to-end/useful-work proof |
| Broker health | 3 | account/position/order reads; reachability can be false green |
| Order lifecycle | 1 | no durable transition/correlation ledger |
| Risk state | 2 | richer runtime JSON is disconnected from canonical health |
| Market streams | 2 | reconnect/process checks without consumption watermark |
| Agents | 2 | component records exist; global heartbeat ambiguity |
| Collectors | 2 | container/process visibility, weak progress proof |
| Database | 2 | connectivity checks, limited saturation/partition horizon proof |
| Replication | 2 | cursor/logs but no lag/duplicate SLO receipt |
| Disk | 2 | storage guard/log limits exist; all paths not covered |
| Alerts | 2 | Telegram-dependent, no delivery/escalation acknowledgement |

## 11. Failure-scenario matrix

| Failure | Detected | Entry Blocked | Position Manageable | Recovery | Alert | Data Loss |
|---|---|---|---|---|---|---|
| Alpaca data outage | partial | new path yes; legacy partial | exits should bypass quote gate, untested | retry | log/partial Telegram | gaps likely |
| Alpaca broker outage | partial | new path yes | no until broker returns | loop retry, no durable workflow | partial | lifecycle telemetry possible |
| Supabase outage | startup/log detects | inconsistent cloud-kill semantics | broker path mostly yes | fire-and-forget retries vary | log | telemetry loss |
| GCP outage | replicator detects | should not affect | yes | bounded systemd retry | journal | lag/backlog uncertain |
| Finnhub outage | partial/status path | agent policy dependent | yes | collector retry | partial | news gap |
| WebSocket disconnect | process may log | not uniformly | broker REST exits possible | reconnect path | partial | ticks lost |
| stale bars | new path yes | new path yes | management degraded | next valid fetch | log | signal gap |
| stale option quote | new entry validator | new path yes | close should remain possible | refetch | log | no |
| disk full | storage guard partial | not universally | possibly impaired | operator cleanup | Telegram if guard alive | yes |
| QuestDB unavailable | process check | not uniformly | yes | Docker restart | partial | ticks lost/buffer uncertain |
| Qdrant unavailable | partial | should not control deterministic executor | yes | restart | partial | embeddings lost |
| agent dead | heartbeat ambiguity | deterministic executor unaffected | yes | systemd | false green possible | debates missed |
| main dead | systemd detects | process absent | no until restart/other executor | restart | watchdog partial | local events |
| watchdog dead | systemd may restart | no | unchanged | restart | no self-alert proof | no |
| partial fill | broker status partial | opening order gate | quantity/restart unsafe | polling only | logs | correlation loss |
| pending-order restart | open-order query | new path blocks duplicate | incomplete recovery | manual/broker polling | logs | metadata loss |
| EOD close rejection | new helper retries | yes | partial | ten retries | error log, alert unproven | state retained at broker |
| duplicate executor | account/mode kernel lease at broker boundary | yes (source tests) | only lease owner | kernel release/restart | structured critical events | edge runtime drill pending |

## 12. False-green matrix (highest financial risk first)

| Rank | Green indication | Actual degradation | Risk |
|---:|---|---|---|
| 1 | systemd says one trading unit active | second differently named executor/container/manual process also trades | duplicate/unintended order |
| 2 | close API returned success/Telegram says flattened | close merely submitted; position remains/partial/rejected | uncontrolled overnight position |
| 3 | main heartbeat fresh | agent orchestrator dead, or inverse | stale decision pipeline |
| 4 | HTTP health/readiness is 200 | broker state/data/lock/useful iteration invalid | entries or exits not actually safe |
| 5 | broker account endpoint reachable | order stream/market WebSocket stale | lifecycle blind spot |
| 6 | Docker container running | collector loop stalled/no output consumed | missing market/news data |
| 7 | sentiment shown as `0.0 neutral` | no articles, placeholder key, error, or stale data | false neutral trade input |
| 8 | bars request is HTTP 200 | empty/malformed/stale bars | invalid signal/default |
| 9 | entry log/POST accepted | not filled or partially filled | wrong exposure/accounting |
| 10 | replication daemon alive/cursor logged | lagging, duplicates, or unacked durable write | analytics/drift corruption |

## 13. Test and CI evidence

| Command | Collected | Passed | Failed | Skipped | Errors | Result |
|---|---:|---:|---:|---:|---:|---|
| `pytest -q` | collection interrupted | 0 | 0 | 0 | 14 | FAIL: missing numpy/pandas/requests/httpx/pytz plus Gemini `config` import collision |
| `python -m pytest backtests/tests/ -q` | collection interrupted | 0 | 0 | 0 | 6 | FAIL: missing numpy/pandas |

CI installs `requirements.txt`, syntax-checks only three Python files, runs `tests/` and backtests, checks narrow secret patterns, and runs strict synthetic-data guards. It does not test dashboard in the main workflow, executor exclusivity, endpoint matrix, restart/partial fills/flat confirmation, kill/EOD failure injection, migrations, broker contract mocks, or deployment manifests. Secret validation is push-to-main/manual rather than PR and depends on Doppler/network. Dependency locking/hashes are absent; tests include environment/network-sensitive scripts under broad pytest discovery.

## 14. Weighted production maturity score

| Area | Weight | Evidence score | Contribution |
|---|---:|---:|---:|
| Broker/order correctness | 15% | 40 | 6.00 |
| Trading safety/risk | 15% | 42 | 6.30 |
| Market-data integrity | 10% | 50 | 5.00 |
| Recovery/reconciliation | 10% | 28 | 2.80 |
| Strategy scientific validity | 10% | 30 | 3.00 |
| Backtest realism/parity | 10% | 45 | 4.50 |
| Observability | 10% | 38 | 3.80 |
| Edge/runtime reliability | 5% | 40 | 2.00 |
| Data durability/storage | 5% | 45 | 2.25 |
| Security/secrets | 5% | 55 | 2.75 |
| CI/testing | 3% | 30 | 0.90 |
| Operational documentation | 2% | 65 | 1.30 |
| **Total** | **100%** |  | **40.60 → 41%** |

The controlling score is **41%**. Present-but-unexecuted safety tests receive no maturity credit; this avoids conflating test existence with execution evidence.

## 15. Top evidence-based gaps

**Top risks:** duplicate executor; unverified flat; incomplete restart lifecycle; malformed mode semantics; divergent broker stacks; daily cadence for intraday duties; missing account-wide exposure authority; cloud/local kill divergence; invalid-data defaults; absent runtime receipts.

**Top silent failures:** partial fill treated as success; signal consumed before fill; close submission without flat; local exit metadata lost; empty bars; placeholder Finnhub; dropped collector output; stale websocket with REST healthy; replication lag; partition horizon exhaustion.

**Top scientific gaps:** timing parity; immutable experiment IDs; locked datasets/config hashes; unified OOS; walk-forward for actual UT option strategy; Monte Carlo; PBO/Deflated Sharpe; multiple-testing ledger; survivorship/selection bias audit; paper-shadow promotion evidence.

**Top operational gaps:** one canonical supervisor; account-scoped lock; broker recovery runbook with drills; EOD escalation; component readiness contract; dependency lock; disk capacity SLO; alert acknowledgement; credential rotation receipts; rollback/canary procedure.

## 16. Readiness decision

Choose exactly one: **NOT READY**. Phase 0 must prove one executor, paper endpoint invariants, broker-authoritative lifecycle/restart recovery, persistent kill behavior, and EOD broker-flat confirmation in executable tests and supervised paper drills. This is not a judgment that the code cannot trade; it is a judgment that safe behavior has not been defensibly demonstrated.

FDE PRODUCTION READINESS DECISION

Overall Score:
41%

Trading Safety:
D

Broker Correctness:
D

Market Data Integrity:
C

Backtest Validity:
D

Strategy Evidence:
D

Recovery:
F

Observability:
D

Edge Reliability:
D

Security:
C

Operational Maturity:
D

SUPERVISED PAPER:
NO-GO

EXTENDED PAPER:
NO-GO

MICRO LIVE:
NO-GO

UNSUPERVISED LIVE:
NO-GO

Highest-Risk Technical Failure:
Concurrent legacy/new executors can submit duplicate or conflicting orders without one account-scoped lock.

Highest-Risk Silent Failure:
A close/flatten submission no longer establishes flatness in the canonical executor. **FIXED IN SOURCE, UNIT TESTED, PROCESS TESTED, EDGE RUNTIME NOT VALIDATED**: the persistent kill/EOD workflow requires a fresh broker position quantity of zero and no prohibited opening orders before `KILLED_FLAT`; failures keep entry disabled.

Most Important Scientific Gap:
Live incomplete-daily-candle timing is not parity-validated against the option backtest and no immutable OOS protocol exists.

First Infrastructure Component Likely To Fail/Exhaust:
The hot edge data/storage path (QuestDB/parquet/Docker volume) because growth and retention lack runtime capacity evidence and comprehensive alerts.

Top 5 Actions:
1. Select one canonical executor and enforce one account-scoped lease across systemd, Docker, scripts, and dashboard control paths.
2. Implement and test a broker-authoritative durable order state machine, restart reconciliation, idempotent client order IDs, and partial-fill accounting.
3. Make kill/EOD a persistent workflow that cancels openings, retries closes, confirms broker-flat, and escalates before/after early closes.
4. Make paper/live parsing fail closed and execute an endpoint matrix for every money-moving path with live network calls mocked.
5. Lock dependencies and run deterministic safety suites plus supervised-paper failure drills before collecting strategy-validation evidence.
## P0-04 data-validity remediation — 2026-08-19

Source now defines explicit value/status/timestamp/age/source/reason semantics and a
central mandatory-input entry gate. Market bars, option quotes, sentiment aggregates,
risk values, agent decisions, regime failures, account equity, and SPY gap payloads no
longer use plausible zeros or neutral states for failures. Risk-reduction workflows
remain independent of enrichment validity. See `docs/architecture/DATA_VALIDITY.md`
for timing, status, provenance, and the dangerous-default inventory.

Operational acceptance remains partial until exercised in the deployed edge runtime.
Component useful-work heartbeat redesign is explicitly deferred to the next P0.
