# Disrupting Alpha Production Acceptance Matrix

> **This audit applies to the Disrupting Alpha algorithmic trading architecture. Django is not an architectural requirement.**

**Audit base:** `96e157aa6399307c590ca56a3d05fd9cecbce929` · **Date:** 2026-08-19 UTC · **Controlling verdict:** NOT READY / 41%.
“Tested” means executed evidence in this audit, not merely a test file. “Runtime validated” requires broker/edge receipts; source inspection is insufficient.

| Capability | Implemented | Tested | Runtime Validated | Safe | Evidence | Remaining Work |
|---|---|---|---|---|---|---|
| Paper isolation | Partial | No (collection blocked) | No | No | principal adapters force paper; second live opt-in in new broker | strict parser and endpoint matrix across all paths |
| Signal | Yes | No | No | Partial | daily UT calculation and new typed snapshot | prove exchange-session freshness and exact decision timing |
| Market data | Yes | No | No | Partial | data host used broadly; stale/empty checks in new engine | eliminate default substitutions; stream consumption watermark |
| SPY gap filter | Yes | No | No | Partial | `ExecutionFilter` uses data URL and blocks missing bars | mock response/error/stale/empty tests through Telegram decision |
| Sentiment | Partial | No | No | No | nullable/status path exists; legacy zero defaults and no DISABLED | end-to-end status schema and policy tests |
| Risk supervisor | Partial | No | No | No | loss/trade/size/data/cutoff gates split across stacks | one independent gate and formal safety states |
| Kelly sizing | Yes | No | No | No | cap and equity logic exists | assert final percent/dollars/quantity and cautious reduction display |
| Order submission | Yes | Yes (`test_broker_reconciliation.py`) | No | Partial | canonical REST boundary uses deterministic client IDs and lost-response lookup | edge paper drill |
| Accepted versus filled | Yes | Yes (`test_broker_reconciliation.py`) | No | Partial | explicit normalized lifecycle; unknown status fails closed | edge paper drill |
| Partial fill | Yes | Yes (`test_broker_reconciliation.py`) | No | Partial | broker requested/filled/remaining quantities and remaining-only replace | edge paper drill |
| Cancel | Yes | No | No | No | account-wide DELETE in adapters/dashboard | scope/audit, confirm terminal state, recovery |
| Replace | Partial | No | No | No | limit repricing PATCH loops | pending_replace/replaced/rejection/idempotency tests |
| Reconciliation | Yes | Yes (`test_broker_reconciliation.py`) | No | Partial | account/position/recent-order startup reconstruction; query failures are unknown | edge paper drill |
| Kill switch | Source Pass | Yes | Yes | No | durable/runtime state machine; broker-confirmed and cross-process tests | edge runtime not validated |
| EOD flatten | Source Pass | Yes | Yes | No | same verified engine; normal/early-close calendar tests | edge runtime not validated |
| Broker-flat verification | Source Pass | Yes | Yes | No | zero broker quantity plus no prohibited opening orders | paper edge drill required |
| Market calendar | Source Pass | Yes | N/A | No | NYSE session/holiday/early-close fail-closed tests | edge timezone validation required |
| Restart kill recovery | Source Pass | Yes | Yes | No | durable state reload across new Python processes | machine reboot not executed |
| Restart recovery | Yes | Yes (unit + spawned-process test) | No | Partial | pending entry/exit, partial fill and durable cache reload scenarios | edge paper drill |
| Duplicate prevention | Yes | Yes (`test_execution_lease.py`, `test_broker_reconciliation.py`) | No | Partial | account lease plus deterministic consumed-signal/client-ID boundary | edge systemd/Docker runtime drill |
| Account/exposure | Partial | No | No | No | broker account/positions available; separate fallbacks | unified freshness-tagged snapshot and account-wide exposure |
| Option quote validity | Partial | No | No | Partial | new adapter validates bid/ask/spread/age/contract | prove emergency exits bypass entry checks |
| Health/readiness | Partial | No | No | No | legacy health + richer runtime JSON disconnected | canonical component/state readiness API |
| Heartbeats | Yes | No | No | No | main and agents heartbeat independently | useful-work and consumed-output watermarks per component |
| Watchdog | Partial | No | No | No | process/tmux/Docker/Alpaca/signal checks | severity cadence, progress checks and watchdog self-monitoring |
| Supabase outage | Partial | No | No | No | logging often catches errors; cloud kill/control coupled | failure injection; exits independent; entry policy explicit |
| GCP outage | Yes (degradation) | No | No | Partial | out-of-process bounded replicator | prove no exit dependency and lag/backlog recovery |
| QuestDB/Qdrant/NATS outage | Partial | No | No | No | Docker restart/dependencies | progress/loss/backpressure tests; deterministic entry policy |
| Backtesting | Yes | No (6 collection errors) | No | No | option economics/provenance/reports exist | hermetic dependencies and real-data acceptance run |
| Live/backtest parity | Partial | No | No | No | signal parity test exists but did not collect | align completed/incomplete candle and execution timestamps |
| OOS validation | Fragmented | No | No | No | isolated rolling/walk-forward scripts | locked UT Bot option OOS protocol |
| Walk-forward | Fragmented | No | No | No | forecasting/HMM scripts | unified candidate scoring and leakage controls |
| Monte Carlo/PBO/DSR | No | No | No | No | none found as promotion evidence | implement after execution safety |
| Experiment registry | No | No | No | No | reports/results lack immutable global IDs | config/code/data hashes and multiple-trial ledger |
| Paper drift | No | No | No | No | no correlated expected-vs-actual schema | signal/contract/quote/order/fill/exit/P&L correlation |
| AI safety boundary | Partial | Partial (approval stub tests not run here) | No | Partial | trading tools are stubs; deterministic executor orders | prevent agent risk/live/kill authority; audit permissions |
| Storage durability | Partial | No | No | No | parquet/QuestDB/BigQuery/Supabase layers and storage guard | owners, retention, capacity SLO, restore drills |
| Secrets | Partial | No | No | No | ignore/examples/Doppler/WIF and narrow CI scan | history-wide scan and provider revocation receipts |
| CI | Partial | N/A | No | No | Python 3.11 workflow/test jobs | lock deps; dashboard, safety integration, deployments, secret PR scan |
| Incident recovery | Partial | No | No | No | docs/scripts exist | supervised drills with broker convergence receipts |

## Stage gates

| Gate | Required objective evidence | Status |
|---|---|---|
| Supervised execution-validation paper | all P0 closed; one executor; endpoint/lifecycle/kill/EOD/restart tests; operator present | **NO-GO** |
| Strategy-validation paper | prior gate plus timing parity and immutable real-data experiment | **NO-GO** |
| Extended paper | 20+ sessions including early close/outage drills; zero unreconciled orders; drift report | **NO-GO** |
| Micro-live review | prior gates, security/recovery sign-off, bounded capital/blast radius, rollback drill | **NO-GO** |
| Unsupervised live | statistically adequate drift/strategy evidence and operational SLO history | **NO-GO** |

## Non-negotiable acceptance scenarios

Each must produce broker request/response fixtures, correlated state transitions, alert receipt, and final broker truth: local flat/broker open; local open/broker flat; pending entry restart; partial fill restart; pending exit restart; rejected/canceled/expired/replaced; duplicate process start; malformed paper/live settings; kill flat/open/pending/cloud-down/restart; EOD early close/rejection; stale/empty/error bars; stale/invalid quote; disk full; and Supabase/GCP/QuestDB/Qdrant/NATS outages.
## P0-04 — decision-data validity (2026-08-19)

| Acceptance criterion | Source evidence | Status |
|---|---|---|
| Missing, stale, malformed and failed inputs cannot authorize entry | `src/trading/data_validity.py`, `src/trading/decision_inputs.py` | PASS (source) |
| Empty market response is not a zero gap | `src/trading/market_gap.py`, `tests/test_market_gap.py` | PASS |
| Zero sentiment differs from zero scored articles | `tests/test_data_validity.py` | PASS |
| Invalid quote blocks entry without gating exits | `tests/test_data_validity.py` | PASS |
| Lease, reconciliation and kill/flatten regression | Existing P0 suites | PARTIAL: SIGINT lease-release test fails in this runtime; other cases pass |
| Edge deployment/runtime observation | Requires deployed credentials and live session | NOT VERIFIED |
