# Canonical Alpaca executor and account lease

## Decision

The sole production money-moving process is `src/trading/executor.py`, supervised
by `da-trading-bot.service`. It uses `src/trading/broker.py`; the
`RiskSupervisor` gates trading but does not confer broker authority. Authority
comes only from `ExecutionLease`.

The identity is `alpaca:<ALPACA_ACCOUNT_ALIAS>:<paper|live>`. The alias is a
required, non-secret operator identifier shared by every configuration using
that account. `ALPACA_IS_PAPER` must be exactly `true` or `false`; missing or
ambiguous values fail before acquisition. Paper and live use distinct locks.
Operators must not reuse an alias for different accounts or use different
aliases for the same account; deployment validation must compare the alias with
the account displayed by Alpaca.

Linux `flock(2)` owns `/run/disrupting-alpha/alpaca-<alias>-<mode>.lock` for the
life of the process. systemd creates the directory with mode 0750. Docker
development mounts that host directory, so its lock is not container-private.
A surviving file is diagnostic only: kernel ownership, not its existence or
PID text, grants authority.

Every submit, cancel, replace, and close operation in both options adapters
checks the in-process guard. It verifies that the lease belongs to the current
PID, preventing direct Python and fork inheritance bypasses. Read-only broker
queries remain available. Runtime state exposes `execution_lease_owned` and
the non-secret identity; entry permission is conjoined with ownership.

## Entry-point inventory

| Entry point | Submit | Cancel/replace | Close | Classification / owner |
|---|---:|---:|---:|---|
| `src/trading/executor.py` → `src/trading/broker.py` | Yes | Yes | Yes | **CANONICAL**, systemd `da-trading-bot` |
| `main.py` → `strategies/options_executor.py` | Yes | Replace | Yes | **DEPRECATED**; guarded; default launch removed |
| `run_crypto_bot.py` → Lumibot | Yes | Framework | Framework | **DANGEROUS DUPLICATE**; removed from installer/default boot |
| `scripts/test_trade_cycle.py` | Yes | Replace | Yes | **DANGEROUS MANUAL TEST**; adapter guard denies without lease |
| Netlify `alpaca-flatten` | No (formerly cancel/close) | No | No | **DISABLED**, authenticated HTTP 410 |
| `agents/tools/trading_tools.py` | No | Stub only | Stub only | **READ-ONLY** |
| `adapters/supabase_logger.py` | No | No | No | **READ-ONLY** account snapshot |

## Launch-path inventory

| Launcher | Command / environment | Disposition |
|---|---|---|
| `scripts/systemd/da-trading-bot.service` | venv Python `src/trading/executor.py`; `.env`; host `/run` | **Canonical production supervisor** |
| `systemd/da-trading.service` | Doppler then same executor | Alternate artifact; never install beside canonical unit; lease excludes overlap |
| old service / manual `python main.py` | legacy Lumibot writer | Deprecated and mutation-guarded |
| crypto units / `run_crypto_bot.py` | Lumibot using shared Alpaca environment | Not installed; never co-run on this account |
| bare `docker compose up -d` | support stack only | No writer by default |
| dev Compose `--profile trading-dev` | canonical executor; shared host lock | Explicit development only |
| `scripts/start_all.sh` / tmux | support services; trading lines commented | No writer |
| cron / `@reboot` | no active executor command found | No writer |
| dashboard | read-only orders; retired flatten mutation | No writer |
| `run_agents.py` | analysis; mutation tools are stubs | No writer |

## Operational rules

1. Configure a common `ALPACA_ACCOUNT_ALIAS` and explicit `ALPACA_IS_PAPER`.
2. Install only `da-trading-bot.service` for this account.
3. Never enable legacy trading or crypto units for the same account.
4. Duplicate, filesystem, or permission failure is fatal startup failure.
5. Normal exit, signals, exceptions, and crashes close the descriptor; the
   kernel releases authority even if the file remains.

This is a single-host lease. Multi-host execution is unsupported and outside
this remediation.

## Broker-authoritative lifecycle and recovery

Alpaca REST orders, fills, and positions override every local cache. Local JSON
is a versioned, atomic metadata/correlation cache only; an absent or stale cache
never proves flatness or a terminal order. Query failure is an unknown state,
not an empty result, and blocks entries while read/cancel/exit/flatten remain
available where Alpaca is reachable.

The canonical states are `NEW`, `ACCEPTED`, `PENDING_NEW`,
`PARTIALLY_FILLED`, `FILLED`, `PENDING_CANCEL`, `CANCELED`, `EXPIRED`,
`REJECTED`, `PENDING_REPLACE`, and `REPLACED`, plus explicit Alpaca terminal
states and `UNKNOWN_BROKER_STATE`. Unknown and unclassified working orders fail
closed. Requested, broker-filled, and remaining quantities are separate;
replacement quantity is never greater than broker-reported remaining quantity.
A submitted/filled close is not flat until the positions query returns quantity
zero.

Startup order is: acquire `ExecutionLease`; verify Alpaca account identity;
fetch positions; fetch recent/open orders and fills represented by those orders;
reconstruct correlations and metadata confidence; classify mismatches; then, and
only then, permit entry. The same REST reconciliation runs before entry, after
submission, on the five-second active executor cadence, and therefore after
reconnect and while positions/orders exist. Broker events may accelerate future
updates but can never replace startup/disconnect REST recovery.

Client IDs are at most 48 characters and use
`da-<strategy:10>-<YYYYMMDD>-<e|x|f>-<sha256:12>-<attempt:2>`. The digest binds
the full strategy, session, signal identity, and intent without disclosing the
signal. A timed-out POST is looked up by this exact ID; it is never retried with
a new ID. An unresolved outcome blocks entry. Recovered positions retain broker
quantity/average price; unavailable underlying price, RSI, or strategy version
is explicitly `UNKNOWN`/`DEGRADED_POSITION_STATE`, never invented.

### Canonical operation map

| Operation | Caller | Broker method | Lease required | State recorded |
|---|---|---|---:|---|
| Entry submit | executor/broker lifecycle | `POST /v2/orders` | Yes | deterministic client ID, broker order |
| Exit submit | executor | `POST /v2/orders` | Yes | broker order; position remains authoritative |
| Cancel | flatten helper | `DELETE /v2/orders` | Yes | next REST reconciliation |
| Replace/chase | broker adapter | `PATCH /v2/orders/{id}` | Yes | replacement IDs and remaining quantity |
| Flatten | executor verification loop | cancel + exit | Yes | broker position until quantity zero |
| Status/partial fills | reconciler | `GET /v2/orders` | No | requested/filled/remaining/status |
| Positions/startup | reconciler | `GET /v2/account`, `/v2/positions` | No | account identity and broker positions |

Structured reconciliation/order/position events are emitted without secrets,
and runtime health publishes validity, reconciliation timestamp, position and
order counts, errors, and entry block reason. Supabase and GCP are not called by
recovery. The cache format is version 1; incompatible legacy/unversioned data is
explicitly ignored in favor of broker reconstruction.
