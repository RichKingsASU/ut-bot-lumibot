# Remediation Execution Update — 2026-08-19

Work is proceeding on `refactor/production-django`. Current statuses and blockers are maintained in `docs/remediation/REMEDIATION_LEDGER.md`; the plan below remains authoritative and no P0 has been marked PASS without execution.

---

# Production Remediation Plan

This plan converts the findings in `PRODUCTION_READINESS_AUDIT.md` into release-gated engineering work. Tasks are ordered by dependency, not calendar duration. No task is complete until its validation artifact is attached to the release evidence bundle.

## Phase 1 — Production blockers

| ID | Priority | Description | Reason | Affected files/components | Recommended action | Validation method | Release gate |
|---|---|---|---|---|---|---|---|
| PR-001 | P0 | Resolve approved-stack conflict | Current system is React/Flask/Supabase/Python 3.11, not Django/Bootstrap/psycopg/Python 3.13 | whole repository, requirements, Docker, CI, dashboard | Architecture Decision Record signed by Forrest; either formally approve exception or define/execute migration with acceptance parity | ADR approval plus stack inventory CI assertion | 1 |
| PR-002 | P0 | Create deterministic clean build | Full tests/build cannot start; Python requirements are broad, unpinned, and malformed | `requirements*.txt`, dashboard lockfile, Dockerfiles, CI | standardize Python 3.13.x and Node; repair encoding; lock hashes/versions; separate runtime/dev/research dependencies | clean ephemeral build installs with no undeclared dependency and produces immutable artifacts | 1, 6, 8 |
| PR-003 | P0 | Establish authoritative PostgreSQL 17 schema | Supabase SQL is not proven on PG17 and schema sources diverge | `supabase/migrations`, `dashboard/supabase`, `schema_snapshot.sql`, adapters | nominate one migration chain; add clean/upgrade/dirty-state migration tests and schema drift check | migrate empty and production-shaped clone on PG17; compare schema; zero drift | 2 |
| PR-004 | P0 | Prove trading safety lifecycle | Real money could be exposed to stale/duplicate/partial orders or failed exits | `main.py`, `strategies/ut_bot.py`, `strategies/options_executor.py`, risk engines/watchdogs | define state machine and fail-closed invariants for paper/live, partial fills, cancel/replace, restart, outage, loss cap, EOD close, kill switch | staged broker sandbox scenarios with persisted evidence; independent reviewer sign-off | 3, 5, 7 |
| PR-005 | P0 | Implement Forrest identity and RBAC | One generic authenticated role/shared admin key is inadequate | dashboard auth/client, Netlify functions, Supabase RLS | define viewer/operator/trader/admin roles, MFA, server-side claims, least privilege, deprovisioning, break-glass audit | authorization matrix automated tests and manual privilege-escalation review | 4, 5 |
| PR-006 | P0 | Build backup/restore capability | No recovery evidence; data/state loss cannot be accepted | Supabase/Postgres, QuestDB, Qdrant, config/state files | define assets, encrypted backups, retention, PITR where needed, RPO/RTO, restore order, integrity checks | destructive staging restore drill meets approved RPO/RTO | 2, 9 |

## Phase 2 — Production hardening

| ID | Priority | Description | Reason | Affected files/components | Recommended action | Validation method | Release gate |
|---|---|---|---|---|---|---|---|
| PR-101 | P1 | Close secret incident and strengthen scanning | Risk register records prior DB credential disclosure | secret stores, Git history, workflows, migration risk register | rotate affected credentials, revoke old values, document attestation; add history-capable secret scanner | old credential rejected; scanner passes full history; owner attests rotation | 5 |
| PR-102 | P1 | Replace browser-held admin key | localStorage shared secret is exposed to XSS/local compromise | `dashboard/src/lib/apiClient.ts`, Settings, Netlify handlers | use authenticated server session/JWT claims and short-lived authorization; remove localStorage secret | browser storage inspection and XSS threat test show no privileged reusable secret | 4, 5 |
| PR-103 | P1 | Secure service network | Compose publishes unauthenticated data/messaging endpoints | `docker-compose*.yml`, nginx/network/firewall docs | bind privately, authenticate, encrypt where supported, segment networks, firewall host | external port scan blocked; authorized internal clients pass | 5, 8 |
| PR-104 | P1 | Harden containers | root, mutable tags, runtime installs and bind mounts undermine integrity | Dockerfiles, Compose | multi-stage immutable builds, non-root UID, read-only FS, capabilities drop, pinned digests, health/resource limits | image scan, runtime security assertions, restart/limit test | 5, 8 |
| PR-105 | P1 | Typed environment profiles | configuration is scattered and some unsafe values only warn | `config.py`, validator, workers, `.env.example`, Netlify config | explicit dev/test/UAT/prod schemas; fail closed on weak/mismatched live config; eliminate runtime ambiguity | table-driven config tests for missing/invalid/cross-environment cases | 1, 5, 8 |
| PR-106 | P1 | Correct readiness and failure semantics | presence of credentials is not connectivity; fatal loop can exit successfully | health server, `main.py`, watchers | dependency probes with bounded timeouts; degraded/not-ready status; non-zero fatal exit; avoid leaking internals | fault injection for broker/DB/ws/alert failures and orchestrator response | 3, 10 |
| PR-107 | P1 | Guarantee data write integrity | REST writes and local state allow partial/duplicate/concurrent inconsistency | adapters, execution, Supabase functions/migrations, local state | database constraints, idempotency keys, atomic RPC/transactions, optimistic locking, durable dedup state | concurrency/duplicate/crash tests verify exactly-once business outcomes | 2, 3 |
| PR-108 | P2 | Data governance | retention, PII, timezone, audit standards are undefined | schemas, logs, docs | classify fields, approve retention/deletion, UTC storage/display rules, immutable audit events | governance review plus automated retention/audit checks | 2, 5, 13 |

## Phase 3 — Test completion

| ID | Priority | Description | Reason | Affected files/components | Recommended action | Validation method | Release gate |
|---|---|---|---|---|---|---|---|
| PR-201 | P0 | Restore green test collection | audit collection has 14 errors and targeted suite mostly fails | pytest config, dependencies, test layout | isolate test roots, declare all dependencies, remove network-on-import, enforce hermetic fixtures | `pytest --collect-only -q` and `pytest -q` both pass in clean CI | 6 |
| PR-202 | P1 | Restore dashboard quality suite | Vitest/build/typecheck unavailable in audit tree | dashboard package/lock/config/tests | clean `npm ci`; run lint, typecheck, unit/component/function tests, production build | all commands green from clean checkout | 6 |
| PR-203 | P1 | Add Selenium application E2E | approved browser automation and browser→DB proof are absent | new Selenium suite, staging stack | cover login, permissions, dashboard data, settings, paper order lifecycle, HITL, kill switch, error/empty states, refresh persistence | Selenium on approved browsers against isolated PG17; DB assertions and screenshots/artifacts | 7 |
| PR-204 | P1 | Add integration/failure tests | critical dependency failures are not proven recoverable | broker, Supabase, NATS, QuestDB, Qdrant, Telegram, GCP | deterministic fakes plus staging contract tests for timeout, malformed response, outage, retry, duplicate, partial fill | fault matrix passes with correct logs/status/recovery | 3, 6, 10 |
| PR-205 | P2 | Establish coverage and mutation goals | no coverage measurement exists | Python/dashboard CI | measure meaningful branch coverage; set reviewed critical-module thresholds; consider mutation tests for risk rules | published reports meet approved thresholds with no excluded critical path | 6 |
| PR-206 | P2 | Add security regression tests | RBAC/RLS/input/dependency controls need continuous proof | RLS, APIs, dashboard, CI | role matrix, injection/XSS, method/schema validation, dependency/image/IaC scans | zero critical/high unaccepted findings; negative auth cases pass | 4, 5, 6 |

## Phase 4 — Deployment readiness

| ID | Priority | Description | Reason | Affected files/components | Recommended action | Validation method | Release gate |
|---|---|---|---|---|---|---|---|
| PR-301 | P1 | Define one release topology | systemd/Compose/Netlify/Supabase/GCP/tmux/PM2 paths overlap | deployment files, scripts, docs | document authoritative components and retire stale launchers; prevent duplicate bot instances with distributed lease | staging deployment and forced duplicate start prove single active executor | 1, 8 |
| PR-302 | P1 | Remove machine-specific assumptions | `/home/k2` and `/mnt/tick-storage` impede repeatability | systemd, Compose, scripts, env template | parameterize paths/users/storage; validate prerequisites without destructive action | deploy successfully on clean non-developer host | 8 |
| PR-303 | P1 | Implement safe release pipeline | current CI omits most deployable surfaces | GitHub/Harness workflows | build/sign artifacts once; scan; migration gate; deploy staging; smoke; manual approval; production rollout | rehearsal generates complete signed release evidence | 6, 8 |
| PR-304 | P1 | Define rollback | app and schema rollback are not coordinated | migrations, deployment/runbooks | forward-fix/rollback policy, compatible migration pattern, previous artifact, config rollback, abort thresholds | failed-release game day restores service/data consistency | 8, 9 |
| PR-305 | P1 | Operational monitoring and alerting | existing health/Telegram lacks SLO and ownership proof | logging, heartbeat, health, alerts | SLO/SLI, dashboards, on-call routes, severity/dedup, runbook links, retention/redaction | inject incidents; alert reaches named responder and runbook resolves them | 10, 13 |
| PR-306 | P2 | Supply SBOM and release manifest | deployed versions across services are not correlated | pipeline/artifacts | record commit, images/digests, packages, migrations, config version and model versions | operator can reconstruct and verify a release offline | 8, 11 |

## Phase 5 — UAT

| ID | Priority | Description | Reason | Affected files/components | Recommended action | Validation method | Release gate |
|---|---|---|---|---|---|---|---|
| PR-401 | P1 | Approve requirements and acceptance cases | Forrest workflows/NFRs are incomplete | product/FDE documentation | name stakeholders; approve workflow, risk, compliance, data, performance and accessibility acceptance criteria | requirements traceability review signed | 11, 12 |
| PR-402 | P1 | Execute role-based UAT | real-user adoption is unproven | staging dashboard and operations | viewer/operator/trader/admin execute normal/error/recovery scenarios with paper accounts | defects triaged; zero open P0/P1; stakeholder sign-off | 12 |
| PR-403 | P1 | Operations handoff | accountable ownership/support is absent | runbooks/training/on-call | name owners for app/infra/data/integrations/security/support; train restart, user admin, restore, kill switch, escalation | tabletop plus hands-on handoff checklist signed | 13 |

## Phase 6 — Production release

| ID | Priority | Description | Reason | Affected files/components | Recommended action | Validation method | Release gate |
|---|---|---|---|---|---|---|---|
| PR-501 | P1 | Controlled production rollout | trading blast radius requires progressive exposure | release pipeline, broker config, monitoring | deploy read-only/dashboard first, then paper; require explicit change approval before any live capability; cap initial exposure | preflight, smoke, reconciliation and abort criteria all pass | 3–13 |
| PR-502 | P1 | Release sign-off | evidence must drive GO | evidence bundle | FDE, product, security, data, operations and business owners review all gates and accepted caveats | signed checklist references immutable artifacts and results | 1–13 |

## Phase 7 — Post-production validation

| ID | Priority | Description | Reason | Affected files/components | Recommended action | Validation method | Release gate |
|---|---|---|---|---|---|---|---|
| PR-601 | P2 | Post-release smoke and reconciliation | deployment can drift from staging | all production components | automate read-only health/data/order/account reconciliation and manual first-operations watch | expected records/metrics/alerts reconcile with broker and DB | 3, 10 |
| PR-602 | P2 | Stabilization feedback loop | defects and enhancements need ownership | support tracker/runbooks | define intake, severity, response targets, root-cause and change-review process | sample incident traverses workflow with timestamps/owner | 13 |
| PR-603 | P3 | Capacity and canary improvement | improve confidence after baseline readiness | pipeline/monitoring | recurring load/soak, canary, synthetic user and recovery exercises | trend reports remain within approved SLO/error budgets | 8, 10 |

## Mandatory exit criteria

Production remains **NO-GO** until all P0 tasks and P1 tasks are either completed or explicitly risk-accepted by accountable Forrest owners, with no risk acceptance permitted for loss of trading control, exposed active secrets, irrecoverable data, authentication bypass, or failed core workflows. Gates 1–13 must be PASS or documented PASS WITH CAVEATS; UAT and operations handoff cannot be inferred from automated tests.
