# Component health and watchdog architecture (P0-05)

## Safety invariant and model

Health means a component completed expected useful work inside its freshness window. A PID, systemd unit, tmux session, running container, HTTP response, connected WebSocket, or fresh timer heartbeat is supporting evidence only and can never independently produce `HEALTHY`.

`ComponentHealth` distinguishes `STARTING`, `HEALTHY`, `DEGRADED`, `STALE`, `FAILED`, `DISABLED`, and `UNKNOWN`. It records component/tier, PID, process UUID, start time, heartbeat, work start/completion, success/failure, output ID, counters, cadence, maximum staleness, reason, and non-secret metadata. Records default to `/run/disrupting-alpha/health` (`DA_HEALTH_DIR` overrides it), with a 0750 directory, 0640 files, same-directory temporary write, `fsync`, and atomic replacement. Telemetry failure warns but never crashes trading safety.

Evaluation checks current instance identity, PID existence, heartbeat age, then useful-work age. A fresh heartbeat with stale work is `STALE`. An old process UUID or dead PID is `FAILED`.

## Verified runtime inventory

| Component | Tier | Expected useful work | Cadence / freshness | Health evidence |
|---|---:|---|---|---|
| canonical executor, risk, kill (`src/trading/executor.py`) | 0 | lease-owned reconciliation, iteration, position management | 5s / 15s | completed local iteration plus runtime kill/lease state |
| broker reconciliation | 0 | account, positions, and orders reconstructed | every iteration | reconciliation result and separate capability metadata |
| required equity market input | 0 | valid snapshot/bar while NYSE expects data | strategy cadence | P0-04 validity plus completed executor iteration |
| crypto market input (`run_crypto_bot.py`) | 0 | valid messages/bars continuously | 24/7 | continuous work expectation; edge instrumentation not validated |
| agent orchestrator (`run_agents.py`) | 1 | complete market→signal→agents→risk→decision cycle | 15m / 25m | independent cycle UUID, start, completion/failure |
| news collector | 2 default | one provider request completes; zero new articles is valid | 10m / 4h | provider/fetch/article-count evidence |
| Telegram/dashboard | 2 | report/delivery | minutes | optional evidence |
| GCP/BigQuery replication, QuestDB archival/research | 3 | acknowledged batch/cursor | job-specific minutes | container/job logs; local instrumentation follow-up |
| broad watchdog | 2 | audit starts and completes | 30m / 40m | local run/completion/exit/alert evidence |

Risk, reconciliation, kill and flatten are functions within the canonical executor, not falsely modeled as independent daemons. Executor health exposes lease ownership/identity, broker capabilities, reconciliation, kill/flatten, and broker-flat evidence.

## Aggregation, sessions, and entry gating

Required Tier-0 failure produces `CRITICAL`; required Tier-1 failure produces `NOT_READY`; optional Tier-2/3 failure produces `DEGRADED` without blocking safe core management; all-current produces `TRADING_READY`. The aggregate JSON contains `status`, `entry_allowed`, reasons, and per-component heartbeat/useful-work ages and is safe for a local health API/operator rendering.

The executor evaluates required local records each five-second iteration (`DA_REQUIRED_COMPONENTS`, default `run_agents`). Failure emits `ENTRY_BLOCKED_COMPONENT_HEALTH` and blocks **new entry only**. Reconciliation, position management, kill, exit and broker-confirmed flatten continue. Successful resumed work emits `COMPONENT_RECOVERED` and restores readiness without restart.

Equity callers use the existing NYSE calendar (open, closed, holiday, early close) to set whether market output is expected. Market closure suppresses only missing-bar staleness; executor/broker/lease/kill remain monitored. Crypto is always `work_expected=True`.

Operator and Telegram decision reports must place aggregate `SYSTEM STATUS`, `ENTRY: BLOCKED`, and reasons before any normal decision wording.

## Historical watchdog check audit

| Existing check | Proves | Does not prove / former false-green |
|---|---|---|
| recent signal row | a signal was persisted | current orchestrator or complete pipeline |
| global `main.py` heartbeat | main heartbeat thread ran | `run_agents.py` ran |
| systemd/tmux state | supervisor/session exists | child workload or useful work is alive |
| Docker exited list | listed container did not exit | running app is progressing |
| Alpaca account/equity | account endpoint answered | positions/orders/data capabilities work |
| Supabase component beat | remote write occurred | current instance completed work |
| sentiment rows | articles exist/scored | collector request completed recently |

The local useful-work check overlays these checks: infrastructure state may downgrade but never upgrade functional health. The 30-minute cron remains a broad audit, not Tier-0 protection. Tier 0 is gated locally every 5–15 seconds; Tier 1 uses 30–120 seconds or its natural cycle; optional/background audits use minutes.

The watchdog never submits, closes, cancels, or flattens orders and never blindly restarts the money-moving executor. Systemd owns restart policy; lease acquisition and broker reconciliation remain authoritative after restart. The watchdog alerts and records its own proof of execution; no recursive watchdog is added.

## Events and certification boundary

Events include `COMPONENT_STARTED`, `COMPONENT_HEARTBEAT` (DEBUG), `COMPONENT_WORK_STARTED`, `COMPONENT_WORK_SUCCEEDED`, `COMPONENT_WORK_FAILED`, `COMPONENT_STALE`, `COMPONENT_RECOVERED`, `PIPELINE_CYCLE_STARTED`, `PIPELINE_CYCLE_COMPLETED`, `PIPELINE_CYCLE_FAILED`, `WATCHDOG_FALSE_GREEN_DETECTED`, and `ENTRY_BLOCKED_COMPONENT_HEALTH`.

Unit certification covers fresh-main/dead-agents, alive/no-cycle, tmux-child-dead, running-container/stalled-app, connected/no-data, stale news, partial broker capability, fresh-heartbeat/stale-work, dead/old instance, optional failure, failed intermediate stage, recovery, equity close, and crypto continuous semantics. Real edge systemd/Docker/tmux/cron and provider cadence validation is **not verified**.
