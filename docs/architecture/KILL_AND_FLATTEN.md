# Persistent kill and broker-confirmed flatten

## Safety contract

`KILL_REQUESTED` is not safe, and an accepted close order is not flat. The
canonical executor reports `KILLED_FLAT` only after fresh broker queries show
both zero position quantity and no working `ENTRY` or unclassified order.
Broker query failure remains unknown and entries remain disabled.

## State and ownership

The explicit states are `ENABLED`, `KILL_REQUESTED`, `ENTRY_BLOCKED`,
`CANCELING_OPEN_ORDERS`, `FLATTENING`, `VERIFYING_FLAT`, `KILLED_FLAT`, and
`KILL_FAILED`. Emergency kill outranks EOD flatten. The runtime interlock is
`/run/disrupting-alpha/trading-disabled`; the atomic durable checkpoint is
`/var/lib/disrupting-alpha/trading-disabled`. systemd creates both directories
as mode 0750; files are 0640 and owned by the service user/group. On reboot,
durable state rematerializes the runtime marker before safety work continues.

All cancels and flatten submissions execute in the canonical executor and
require the account `ExecutionLease`. Cloud state can request a local kill but
cannot clear it or mutate Alpaca. Telemetry failure is irrelevant to safety.

### Kill-path audit

| Source | Activate | Clear | Persistent | Scope | Flatten |
|---|---:|---:|---:|---|---:|
| canonical executor/local marker | Yes | executor-verified request | Yes | edge | Yes |
| operator scripts | Yes | request only | Yes | edge | No |
| Supabase/orchestrator poll | request only | No | cloud command is not authority | cloud to edge | No |
| dashboard Netlify endpoint | No (HTTP 410) | No | No | cloud | No |
| agent trading tools | No (stubs) | No | No | agent | No |
| legacy `main.py` watchdog | process halt request | No | cloud only | legacy | No |

The legacy/cloud meanings are intentionally not considered proof of safety.
Only their activation signal may be materialized into the canonical local state;
none is an enable or money-moving authority.

## Workflow and failure policy

Each bounded batch classifies broker orders, cancels only working opening or
unknown orders, and verifies each cancellation with an order query. A cancel/
fill race is handled by the next position query. Every flatten attempt uses the
current broker quantity. Emergency/EOD liquidation uses a broker-supported
market order to prioritize flatness, with deterministic `FLATTEN` client IDs.
After a bounded wait the executor re-queries orders and positions. Partial fills
repeat using only the remainder. Rejection or outage retries; exhaustion records
`KILL_FAILED`, keeps the interlock, and allows a later executor iteration to
start another bounded recovery batch.

## Market calendar and restart

The maintained NYSE calendar supplies actual session close in
`America/New_York`, including holidays and early closes. Thresholds subtract
`ENTRY_CUTOFF_MINUTES_BEFORE_CLOSE` (default 15) and
`FLATTEN_MINUTES_BEFORE_CLOSE` (default 5). No session or calendar failure
blocks entry; failure never substitutes 16:00. At flatten time every loop enters
the same verified workflow, including a restart after the threshold.

## Operator procedure

* `scripts/trading-stop.sh` atomically persists intent before creating the
  runtime interlock and deliberately does not claim flatness.
* `scripts/trading-status.sh` displays workflow state and pending enable intent.
* `scripts/trading-enable.sh` requires root/service-user permissions and a
  `KILLED_FLAT` checkpoint. It requests enable; only the lease-owning executor
  may re-query broker state, clear both layers, and emit the audit event.

Never delete state manually. `KILL_FAILED` requires incident escalation and
never enables entry. Edge/systemd and paper-broker validation remains a separate
deployment certification step; no live order is authorized by this procedure.
