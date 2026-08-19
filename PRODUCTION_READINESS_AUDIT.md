# Forrest Logistics FDE Production Readiness Audit

> **How close is this application to being safely deployable into production at Forrest Logistics?**
>
> **40% — FUNCTIONAL PROTOTYPE — NO-GO.** The repository contains a substantial paper-trading engine, risk controls, a Supabase-backed React dashboard, health endpoints, migrations, and operational scripts. It is not the approved Django/PostgreSQL 17/Bootstrap application described in the acceptance criteria; a clean audit environment cannot collect or execute the full test suite; no Selenium browser-to-database journey exists; production database state, migrations, broker behavior, restore, and rollback were not validated; and RBAC is not fit for multiple Forrest users. The shortest defensible path is to settle the target architecture, prove a reproducible Python 3.13/PostgreSQL 17 build, close live-trading and authorization blockers, run migrations and recovery drills in staging, add Selenium critical-path coverage, then complete documented UAT and operations handoff.

## 1. Scope, method, and immutable audit baseline

This was a source and local-environment audit. No packages were installed, no schema was changed, no external API was called, and no order was submitted. Only after evidence collection were these three audit artifacts added.

| Item | Evidence |
|---|---|
| Repository | `/workspace/ut-bot-lumibot` |
| Application | UT Bot / Disrupting Alpha algorithmic trading and monitoring system |
| Branch | `work` |
| Audited commit | `5d8d99ab67623aeca4eac6c354e619b224f4fe74` |
| Audit date | 2026-08-19 UTC |
| Initial tree | Clean; no modified or untracked files |
| Runtime observed | Python 3.14.4; `psql` and Docker unavailable |
| Review coverage | Repository inventory, history/status, source, SQL, environment templates, manifests, CI, deployment units, dashboard, tests, integrations, and operations documentation |

### Commands executed

```text
git branch --show-current; git rev-parse HEAD; git status --short; git log -8 --oneline
find . -maxdepth 3 -type f ...
rg -n -i "TODO|FIXME|HACK|TEMP|mock|fake|demo|prototype|bypass|hardcoded|localhost|..."
python manage.py makemigrations --check
python manage.py migrate --plan
python manage.py check
python manage.py check --deploy
pytest --collect-only -q
pytest -q
pytest -q tests/test_tools.py tests/test_gcp_replication.py backtests/tests/test_costs.py
python -m compileall -q -x '/\.agents/' .
env -i PATH="$PATH" HOME="$HOME" python preflight_check.py
cd dashboard && npm test -- --run
cd dashboard && npm run typecheck
cd dashboard && npm run build
docker compose config -q
```

Environment-caused failures remain failures of reproducible readiness: the repository does not provide a working, clean, locally executable audit path in the supplied environment. They are not interpreted as proof that application logic itself is defective where dependencies were simply absent.

## 2. Executive findings

### What is present and likely to work in a correctly provisioned paper environment

- The Python entry point validates required broker, Supabase, and admin configuration before starting; paper mode corrects a live-looking Alpaca base URL.
- The strategy includes freshness checks, EOD flattening, risk limits, broker reconciliation, a kill-switch poller, graceful process signals, structured JSON logging, Telegram notifications, and a health/readiness server.
- Supabase migrations cover trading, bars, strategies, telemetry, HITL, kill switch, RLS, and indexes. Later migrations attempt to replace broad anonymous reads with authenticated policies.
- The dashboard has Supabase password login, route/session gating, explicit loading/error states, and admin-key-protected Netlify functions.
- CI performs a limited Python install, syntax check, secret-pattern check, two Python test directories, and synthetic-data strict-mode assertions.
- systemd, Compose, incident response, deployment safety, and health-check material provide a useful operational starting point.

### What would fail or remain unproven today

- There is no `manage.py`, Django project, Django templates, Bootstrap frontend, psycopg declaration, or Django test/deploy configuration. All requested Django commands fail immediately.
- Python and container/CI runtimes are 3.14.4 and 3.11 rather than the approved Python 3.13.x; the frontend is React/Vite/Tailwind, and a separate Playwright subsystem is present despite Selenium being the approved browser automation.
- Full pytest collection stops on 14 import errors after reporting only 62 collected tests; therefore discovered/executed/pass totals for the complete suite cannot be established. A targeted 62-test command produced 6 pass, 52 fail, and 4 skip because PyYAML was unavailable.
- Dashboard tests cannot start (`vitest` missing); typecheck/build cannot resolve dependencies in the uninstalled tree. No screenshot or browser review was justified because no perceptible application change was made and the UI could not be built.
- PostgreSQL 17 was not available. Supabase migration application, current schema parity, constraints, concurrency, backup, and restore are not verified against a designated isolated test database.
- No Selenium tests exist. The separate Playwright computer-use agent is technology drift and is not application E2E proof.
- Compose cannot be validated locally because Docker is absent; images use mutable `latest` tags, Python 3.11, runtime `pip install`, root defaults, bind-mounted source, and host-specific `/mnt/tick-storage` paths.
- Production broker, Supabase, Netlify, GCP/BigQuery, QuestDB, Qdrant, NATS, Telegram, market data, and alert delivery were not exercised.

## 3. Approved technology stack verification

| Expected | Repository evidence | Result |
|---|---|---|
| Python 3.13.5+ within 3.13.x | CI/Docker/Compose use 3.11; audit host is 3.14.4 | **FAIL — P0 architecture decision** |
| Django | No Django dependency, settings, apps, URLs, templates, migrations, or `manage.py` | **FAIL** |
| PostgreSQL 17 + psycopg | Supabase PostgreSQL SQL exists, but no psycopg dependency or PG17 test proof | **FAIL / NOT VERIFIED** |
| Django templates + Bootstrap + JS/CSS | React 18, Vite, TypeScript, Tailwind, Framer Motion | **FAIL — drift** |
| Selenium on Python 3.13.x | No Selenium; separate Gemini agent uses Playwright | **FAIL — drift** |
| Controlled/read-only warehouse | GCP/BigQuery replication exists; no SQL Server warehouse path or proven least-privilege production role | **NOT VERIFIED** |

This is not a small implementation deviation: the repository is a different product architecture from the approved web stack. Forrest must either approve a formal exception with revised requirements or migrate the web/control plane before release.

## 4. Architecture and code quality

**Assessment: 45%.** Domains are separated into strategies, adapters, agents, collectors, backtests, replication, dashboard, and scripts, but responsibilities and launch paths overlap. There are multiple process supervisors and launchers (systemd, Compose, PM2, tmux scripts), divergent equity/crypto entry points, service code that reads environment variables independently, and runtime JSON configuration without transactional or audited management. Python dependencies are broad and mostly unpinned; the requirements file contains a malformed NUL/UTF-16-looking final dependency. Mutable container images and on-start dependency installation prevent deterministic rollback.

`main.py` catches a fatal trading-loop exception, alerts, performs cleanup, and then returns normally rather than explicitly exiting non-zero. This can turn a crash into an apparently successful process termination before `Restart=always` happens to compensate. The health server calls credential presence “broker connectivity,” reports a simplified websocket state, exposes operational state under wildcard CORS, and sets readiness before a demonstrated broker round trip.

Prototype/debt search found deterministic “mock” fallbacks, unimplemented tool methods, localhost defaults, host-specific paths, stale/duplicate launchers, broad exception swallowing, and documentation that itself records display-only controls and broken persistence. Existing audits are valuable evidence, not closure evidence.

## 5. Database and data integrity

**Assessment: 40%.** The primary operational data store is Supabase PostgreSQL rather than Django ORM/PostgreSQL configured through psycopg. SQL migrations create useful timestamped tables and indexes, and later migrations enable RLS. Risks remain:

- no clean PG17 migration rehearsal or schema diff was run;
- no Django model/constraint layer exists;
- migrations and root/dashboard schema snapshots coexist, making the authoritative schema unclear;
- an intermediate migration disables RLS on `signal_log`; correctness depends on every later migration applying successfully;
- several tables expose authenticated writes without demonstrated per-user/role ownership;
- trading/log writes are distributed REST calls, so cross-table updates lack a demonstrated transaction boundary;
- runtime JSON and local files (for example deduplication state) are outside database durability and locking;
- duplicate submission, partial fill, concurrent worker, restart, and idempotency proof is incomplete;
- data retention, deletion, privacy classification, and audit-history requirements are not defined;
- development/test/production database isolation was not proven;
- there is no executable backup/restore procedure, RPO, or RTO.

PostgreSQL compatibility is plausible because Supabase is PostgreSQL, but **PostgreSQL 17 compatibility is NOT VERIFIED**.

## 6. Authentication, authorization, and security

**Authentication/RBAC: 35%. Security: 38%.** Dashboard password authentication exists, but inventory documentation identifies one user and no MFA. RLS generally distinguishes `authenticated` from `service_role`, not Forrest business roles. An authenticated user can have broad writes to settings/strategies/HITL. The admin API key is stored in browser local storage and sent as a header; any XSS or local browser compromise exposes it. There is no demonstrated role administration, least-privilege mapping, separation of trader/operator/viewer/admin duties, deprovisioning, or authorization regression suite.

Positive controls include environment-based secrets, ignored `.env`, a config validator, RLS hardening migrations, service-role use on servers, loopback binding for the bot health port in Compose, log redaction logic, and a secret-validation workflow.

Material risks:

- live mode needs no independent deployment approval primitive beyond environment configuration;
- a weak admin key only logs a warning after the same key was declared required;
- wildcard CORS is applied by the Flask health service;
- several infrastructure ports are published on all interfaces;
- containers run as root and images/tags are not pinned by digest;
- CI secret scanning is narrow and does not scan history or common token formats;
- a repository risk register states a Supabase database password was previously shared and rotation remained deferred; rotation must be evidenced without exposing the value;
- dependency vulnerability/SBOM/license scans are absent;
- no Django deploy warnings exist because this is not Django. The requested `check --deploy` failed with missing `manage.py`, so CSRF, secure cookies, HSTS, `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` are not applicable to the current Flask/React design—not passes.

## 7. Business workflow matrix

Legend: **Y** source exists, **P** partial/unverified, **N** absent, **NV** not validated.

| Workflow | UI | Backend | Database | Validation | Auth | E2E | Production ready |
|---|---:|---:|---:|---:|---:|---:|---:|
| Supabase login/logout/session restore | Y | Supabase | Supabase Auth | P | Y | N | No |
| View market/portfolio/strategy data | Y | Netlify/Supabase | Y | P | Y | N | No |
| Configure dashboard/risk/options | Y | P | P | P | Admin key + auth | N | No; existing audit records non-persistence/display-only fields |
| Paper signal → option entry | P | Y | Y logs | P | service credentials | N | No; integration not run |
| Exit by RSI/stop/EOD | P | Y | Y logs | Y in source/tests | service credentials | N | No; broker persistence not run |
| Duplicate signal/restart reconciliation | P | Y | P/local state | P | service credentials | N | No; concurrency not proven |
| Kill switch / flatten | Y | Y | Y flag/log | P | admin key/approval paths | N | No; drill absent |
| HITL approve/reject | Y | Y | Y | P | any authenticated user in policy | N | No; RBAC blocker |
| Data collection/backfill | Y | Y | Supabase/QuestDB/Qdrant | P | vendor/service keys | N | No; failure recovery unproven |
| Health/readiness/incident diagnosis | Y | Y | component telemetry | P | mixed/public | N | No; checks overstate connectivity |
| User/role administration | Supabase-hosted only | External | External | NV | No app RBAC | N | No |
| Backup/restore/rollback | N | N | N | N | N/A | N | No |

For all workflows, refresh/restart persistence, invalid/missing data, duplicate submit, intelligible errors, permissions, and audit trail are **NOT VERIFIED end to end** unless explicitly noted.

## 8. UI/UX review

The React dashboard has extensive screens, navigation, charts, forms, loading/error/empty states, and responsive styling in source. It also has test files for Overview, Crypto, Settings, and Alpaca flatten. However the audit could not build or launch it without installing packages, so links, buttons, modals, pagination, filters, responsiveness, browser compatibility, accessibility, and real persistence are **NOT VERIFIED**. Existing repository documentation identifies display-only settings and writes that do not persist; these are workflow defects. No production UI screenshot was taken because the requested phase was an audit and the application could not be built from the supplied environment.

## 9. Testing maturity and results

| Metric | Result |
|---|---|
| Tests discovered | **At least 66**: pytest reported 62 collected before 14 collection errors; four dashboard test files also exist. Exact full total is not established. |
| Tests executed (full suite) | **0 complete-suite tests**; collection aborted |
| Passed (full suite) | **0 reportable** |
| Failed (full suite) | **14 collection errors** |
| Skipped (full suite) | Not reached |
| Targeted Python run | 62 selected: **6 passed, 52 failed, 4 skipped**; most failures were missing PyYAML in the audit environment |
| Dashboard | 0 executed; `vitest` absent |
| Coverage | **Unavailable; not measured** |
| Selenium | **0 tests; not implemented** |

Test categories present: backtest mechanics/costs/parity, tool unit tests, GCP replication/idempotency, signal direction/freshness, trading safety, a Gemini-agent unit suite, and dashboard component/function tests. Missing or inadequate: clean-install verification, PostgreSQL 17 database tests, migration up/down/dirty-state tests, authorization matrix tests, live/paper isolation, partial fills, broker timeout/retry, kill-switch drill, crash/restart/reconciliation, alert delivery, backup/restore, deployment smoke, accessibility/browser compatibility, and Selenium browser → application → PostgreSQL → refresh coverage.

## 10. Resilience, observability, deployment, and operations

Structured JSON logging, Telegram alerts, component heartbeat tables, `/health`, `/ready`, systemd restarts, Docker health checks, watchdogs, and incident documentation are meaningful foundations. Blind spots include no centralized error tracking, no defined SLO/SLI, no alert ownership/escalation, no proof alerts arrive, health checks that infer connectivity from credential presence, no trace/correlation standard across services, and unclear log retention/PII policy.

Deployment is host-coupled (`/home/k2`, `/mnt/tick-storage`), split across Netlify, Supabase, GCP, native systemd, Docker, and optional PM2/tmux. The README is materially behind the repository. No single versioned release manifest ties web, workers, migrations, and infrastructure together. There is no demonstrated one-command staging deployment, migration gate, canary, application/database rollback, or release evidence bundle. CI only runs on `main` push/PR and does not build dashboard/containers, validate Compose, exercise migrations, lint/typecheck all code, scan dependencies/images/IaC, or run E2E.

Backup/recovery is the lowest-maturity area: no versioned `pg_dump`/Supabase backup procedure, retention, encryption, restore drill, QuestDB/Qdrant/media coverage, RPO/RTO, migration rollback policy, or evidence of recovery.

## 11. External integration inventory

| Integration | Purpose | Auth | Failure handling | Test coverage | Production status |
|---|---|---|---|---|---|
| Alpaca REST/WebSocket/SIP/OPRA | Market data and order execution | API key/secret | retries/reconciliation/fail-closed elements | mocks/unit fragments | NOT VERIFIED; live blocker |
| Supabase Auth/PostgreSQL/Realtime/REST | identity, state, logs, control | anon, authenticated, service role, DSN | mixed; some errors logged/continued | SQL and unit fragments | NOT VERIFIED against production schema |
| Netlify Functions | dashboard backend/control proxy | admin API key + server secrets | HTTP status/error responses | one function test file present | build/deploy NOT VERIFIED |
| QuestDB | tick/time-series storage | no auth shown in Compose | health/watchdog | loader tests cannot collect | unsafe network exposure; NOT READY |
| NATS | messaging | no auth shown in Compose | reconnect loops | tool mocks | unsafe network exposure; NOT READY |
| Qdrant | vectors | no auth shown in Compose | reconnect/health checks | tool mocks | unsafe network exposure; NOT READY |
| Telegram | alerting/control bot | bot token/chat ID | often log/continue | no delivery drill | NOT VERIFIED |
| Anthropic/Hugging Face/models | agent/forecast/sentiment | API/token/model files | retries/fallbacks | limited | deterministic fallbacks can mask outage; NOT VERIFIED |
| GCP BigQuery | replication/analytics | ADC/WIF or service account | circuit breaker/idempotency code | 2 tests selected; environment-limited | least privilege and live path NOT VERIFIED |
| Reddit/vendor news | sentiment/news | client credentials | mixed | no integration proof | NOT VERIFIED |
| Gemini computer-use/Playwright | separate browser agent | Gemini credentials | HITL safety code | unit file cannot collect | technology drift; not app E2E |
| Email/Teams/SFTP/MercuryGate/Samsara/SQL Server | not found as implemented dependencies | N/A | N/A | N/A | NOT APPLICABLE / requirements clarification needed |

## 12. FDE operational review

| Discipline | Finding |
|---|---|
| Discovery | Trading purpose is clear; Forrest-specific users, controls, compliance, and acceptance criteria are not. |
| Requirements | Strategy behavior is documented; non-functional, RBAC, RPO/RTO, SLO, data retention, and approved-stack reconciliation are incomplete. |
| Architecture | Useful modular components, but target architecture conflicts with approved stack and deployment topology is fragmented. |
| Implementation | Significant paper-trading implementation; documented dead/display-only paths and overlapping launchers remain. |
| Integration | Many enterprise/vendor integrations exist; none received current production-like end-to-end validation. |
| Validation | Unit/backtest intent exists, but clean suite, DB integration, Selenium, recovery, and UAT evidence are absent. |
| Deployment | Several recipes exist; deployment is host-specific and not reproducible as a coherent release. |
| Adoption | Dashboard exists; user usability, role workflows, training, and UAT are unproven. |
| Operations | Health/watchdog/incident foundations exist; restore, alert drills, SLOs, ownership, and handoff are missing. |
| Feedback loop | GitHub workflow is inferable, but production triage/severity/SLA and user-feedback process are not defined. |
| Ownership | Application, infrastructure, data, integrations, security, and support accountable owners are not recorded. |

## 13. Prioritized findings

### P0 — production blockers (5)

1. **P0-01 — Target-stack conflict:** no Django/Bootstrap/psycopg/PG17/Selenium implementation; Python/React/Playwright drift requires architecture approval or migration.
2. **P0-02 — No reproducible green release:** full Python collection aborts, dashboard cannot test/build, and the supplied requirements are malformed/unpinned.
3. **P0-03 — Trading safety not proven end to end:** paper/live separation, order/partial-fill lifecycle, closeout, kill switch, reconciliation, and broker outage have no production-like acceptance evidence.
4. **P0-04 — Authorization inadequate:** no Forrest RBAC/least privilege/MFA evidence; broad authenticated policies and browser-held shared admin key cannot support safe multi-user production control.
5. **P0-05 — Database/recovery unvalidated:** authoritative PG17 schema, migration path, isolated test DB, backup, restore, and recovery drill are absent.

### P1 — must fix before production (10)

1. Rotate and attest previously disclosed database credentials and conduct repository-history secret scanning.
2. Pin Python/Node/package/image versions and produce deterministic lockfiles/SBOMs.
3. Remove public unauthenticated exposure of NATS, QuestDB, Qdrant, and monitoring ports; add network/auth controls.
4. Make containers non-root, immutable, least-privileged, and resource-limited in the actual runtime.
5. Replace shared browser local-storage admin secret with server-side session/claims authorization.
6. Add Selenium critical-path E2E against staging PostgreSQL and real server processes.
7. Correct health/readiness to perform dependency round trips and distinguish degraded/read-only/not-ready states.
8. Consolidate deployment topology/launchers and eliminate host-specific paths and duplicate-process risk.
9. Establish release/migration/rollback runbook, staging gate, UAT evidence, and operations sign-off.
10. Define monitoring, alert routing/on-call ownership, SLOs, log retention/redaction, and alert-delivery drills.

### P2 — should fix (7)

1. Refactor cross-service configuration into typed, validated environment profiles.
2. Clarify authoritative migrations and retire duplicate snapshots/backups from deployment paths.
3. Add transactional/idempotent handling for multi-table writes, duplicate submissions, and concurrent workers.
4. Resolve display-only/dead controls and explicitly label restart-required settings.
5. Expand CI across lint/typecheck, dashboard, containers, Compose, migrations, security, and coverage thresholds.
6. Document data classification, retention, deletion, audit history, and timezone conventions.
7. Consolidate structured correlation IDs and actionable operator diagnostics.

### P3 — enhancements (3)

1. Add performance/load/soak testing and capacity baselines.
2. Add automated canary and post-release synthetic monitoring after core gates pass.
3. Rationalize optional research/LLM/browser-agent modules into separately released services.

## 14. Scorecard

| Area | Weight | Score | Weighted score |
|---|---:|---:|---:|
| Architecture | 10% | 45% | 4.50 |
| Core Functionality | 15% | 55% | 8.25 |
| Database & Data Integrity | 10% | 40% | 4.00 |
| Security | 10% | 38% | 3.80 |
| Authentication / RBAC | 10% | 35% | 3.50 |
| Testing | 10% | 25% | 2.50 |
| UI / Workflow Parity | 5% | 50% | 2.50 |
| Deployment | 10% | 35% | 3.50 |
| Observability | 5% | 45% | 2.25 |
| Backup / Recovery | 5% | 10% | 0.50 |
| Documentation | 5% | 60% | 3.00 |
| Operational Supportability | 5% | 35% | 1.75 |
| **Total** | **100%** |  | **40.05% → 40%** |

Scores reflect implemented evidence plus validation evidence. Missing validation is not a pass.

## 15. Release gates

| Gate | Status | Evidence |
|---|---|---|
| 1 — Architecture | **FAIL** | Approved stack mismatch and fragmented topology |
| 2 — Database | **FAIL** | PG17 migration/current-state/restore not verified |
| 3 — Core Functionality | **PASS WITH CAVEATS** | Source implements paper flows/risk controls; no integration proof |
| 4 — Authentication/RBAC | **FAIL** | login exists; Forrest roles/MFA/least privilege absent |
| 5 — Security | **FAIL** | shared admin key, exposed services, unverified disclosed-secret rotation |
| 6 — Testing | **FAIL** | collection/build failures and no coverage |
| 7 — E2E Validation | **NOT IMPLEMENTED** | no Selenium tests |
| 8 — Deployment | **FAIL** | non-reproducible, host-specific, mutable artifacts |
| 9 — Backup/Recovery | **NOT IMPLEMENTED** | no executable/drilled procedure or RPO/RTO |
| 10 — Observability | **PASS WITH CAVEATS** | logs/health/alerts exist; correctness and delivery unverified |
| 11 — Documentation | **PASS WITH CAVEATS** | extensive but contradictory/stale and no unified release runbook |
| 12 — UAT | **NOT IMPLEMENTED** | no signed acceptance evidence |
| 13 — Operations Handoff | **NOT IMPLEMENTED** | no ownership/on-call/support/restore handoff |

## 16. Distance to production by work

```text
Completed: 40 / 100
Remaining: 60 / 100

Critical workstreams remaining:
1. Approve or migrate the architecture and establish a deterministic 3.13/PG17 release baseline.
2. Prove trading, data integrity, authentication/RBAC, and security controls in production-like staging.
3. Complete automated unit/integration/security/Selenium suites and execute UAT.
4. Rehearse deployment, migration, backup, restore, rollback, monitoring, and operations handoff.

Production readiness completion:       40 / 100
Core application completion:           55 / 100
Production hardening completion:       34 / 100
Testing completion:                    25 / 100
Deployment/operations completion:      28 / 100
```

# FDE PRODUCTION READINESS DECISION

```text
Application: UT Bot / Disrupting Alpha
Repository: /workspace/ut-bot-lumibot
Branch: work
Commit: 5d8d99ab67623aeca4eac6c354e619b224f4fe74
Audit Date: 2026-08-19 UTC

Overall Production Readiness: 40%
Current Stage: FUNCTIONAL PROTOTYPE
Production Deployment Today: NO-GO
UAT Ready: NO
Production Ready: NO
P0 Blockers: 5
P1 Issues: 10
P2 Issues: 7
P3 Enhancements: 3
```

The application has more implementation than a demo, but no defensible sign-off can be attached while architecture acceptance, clean builds/tests, PG17 integrity/recovery, RBAC, trading-safety E2E, UAT, and operations evidence remain open. Paper-only engineering validation may continue in an isolated non-production environment with real-money credentials unavailable.
