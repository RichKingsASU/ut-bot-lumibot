# Remediation Acceptance Update — 2026-08-19

Django models/templates, PostgreSQL production settings, psycopg, server-side RBAC, trading-safety primitives, Selenium journeys, and recovery procedures now exist on the refactor branch. They remain **not production validated** because dependency installation was denied (HTTP 403), Docker/PostgreSQL tools are unavailable, and UAT is unsigned. Current readiness is **48%, NO-GO**. Detailed status: `docs/remediation/REMEDIATION_LEDGER.md`.

---

# Production Acceptance Matrix

Statuses are evidence-based as of commit `5d8d99ab67623aeca4eac6c354e619b224f4fe74` on 2026-08-19 UTC. **Partial** means source exists but production-like proof does not. **Not verified** is never equivalent to pass.

| Requirement | Implemented | Tested | Validated | Production Ready | Evidence | Remaining Work |
|---|---|---|---|---|---|---|
| Approved Python 3.13.x | No | No | Host was 3.14; CI/images are 3.11 | No | Dockerfile, Compose, CI | Pin 3.13.x and clean-build all services |
| Django backend | No | No | Django commands fail: no `manage.py` | No | requirements/root inventory | Architecture exception or Django migration |
| Django templates + Bootstrap | No | No | React/Vite/Tailwind present | No | dashboard package/source | Architecture exception or frontend migration |
| PostgreSQL 17 + psycopg | Partial | No | Supabase SQL exists; PG17/psycopg absent | No | Supabase migrations; requirements | PG17 rehearsal, psycopg/approved access, schema parity |
| Selenium E2E | No | No | no Selenium files | No | repository search | Implement browser→server→PG→refresh suite |
| Dependency reproducibility | No | No | full collection/build cannot start | No | unpinned/malformed requirements; missing node modules | lock/hashes, split dependencies, clean CI |
| Architecture separation | Partial | Partial | modular apps but overlapping launchers/config | No | agents/adapters/strategies/collectors/deployment | ADR, consolidate boundaries/topology |
| Paper/live environment isolation | Partial | Partial | validator source only; staging not exercised | No | `config_validator.py` | independent live approval and sandbox tests |
| Signal freshness validation | Yes | Partial | source/tests exist but full suite fails | No | strategy and freshness tests | green hermetic tests + broker E2E |
| Position sizing/loss/trade caps | Yes | Partial | risk modules/tests present | No | config, Kelly/risk modules | boundary/concurrency/live-state verification |
| Order entry | Yes | Partial | no current broker integration run | No | options executor | sandbox entry/idempotency/timeout tests |
| Partial fill/cancel/replace | Partial | No | not verified | No | executor/broker paths | explicit state machine and broker scenarios |
| RSI/stop/EOD exits | Yes | Partial | source/backtest intent | No | UT strategy/backtest engine | Selenium/broker persistence and restart proof |
| Kill switch/flatten | Yes | Partial | code/function test intent; no drill | No | orchestrator, Netlify flatten, watchdog | staged and operational drill with reconciliation |
| Restart/broker reconciliation | Partial | Partial | startup sync exists, end-to-end unverified | No | `main.py`, options executor | crash at every order state; prove convergence |
| Duplicate submission prevention | Partial | Partial | local/durable semantics unclear | No | dedup/state code and P0 closeout doc | DB idempotency and concurrent worker tests |
| Supabase database schema | Yes | Partial | migration application/current state not run | No | migration chain | authoritative chain and drift gate |
| Keys/FKs/check/unique constraints | Partial | No | static SQL only | No | migration SQL | model each invariant; migration/database tests |
| Atomic multi-record writes | No/Partial | No | REST writes not proven transactional | No | adapters/common writes | transactional RPC/idempotent outbox |
| RLS enabled | Yes | Partial | later hardening SQL exists | No | 20260710/20260716 migrations | live schema inspection and negative tests |
| Data retention/deletion | No | No | requirements absent | No | no approved policy found | classify and automate policy |
| Audit trail | Partial | No | trading/system audit tables exist | No | migrations/loggers | immutable actor/action/config audit verification |
| Timezone handling | Partial | Partial | ET/UTC logic present | No | strategy/backtest scripts | DST/database/display test matrix |
| Dashboard login/logout | Yes | Partial | component source; UI tests not runnable | No | `App.tsx`, Login/TopBar | clean tests and Selenium session flows |
| MFA | No evidence | No | not verified | No | auth inventory | enable/enforce per policy and test recovery |
| Forrest RBAC | No | No | generic authenticated/service roles | No | RLS policies | role claims, least privilege, role admin |
| Privileged API authorization | Partial | Partial | shared admin header checks exist | No | Netlify functions/api client | server-side claims, negative/authz tests |
| User provisioning/deprovisioning | No app process | No | not verified | No | Supabase-hosted auth only | owner/runbook/automation/audit |
| Secrets externalized | Partial | Partial | env/Doppler patterns exist | No | env example/workflows/docs | rotation evidence, history scan, scoped identities |
| Previously disclosed DB credential revoked | Unknown | No | risk register says deferred | No | migration risk register | rotate/revoke/attest without publishing secret |
| TLS/HTTPS | Partial | No | Netlify/vendor assumed; internal services exposed | No | deployment config | end-to-end TLS/network validation |
| CSRF/Django cookie/HSTS controls | N/A current architecture | No | Django absent | No against approved stack | missing `manage.py` | decide architecture; assess equivalent controls |
| CORS restriction | No | No | Flask health uses `*` | No | health server | explicit origins and tests |
| XSS/input/schema validation | Partial | Partial | React escaping and some handlers; no systematic proof | No | dashboard/functions | CSP, schema validation, security suite |
| SQL injection resistance | Partial | No | client/REST patterns; scripts/query construction mixed | No | adapters/scripts/functions | parameterization audit and injection tests |
| Dependency/image vulnerability control | No | No | not in CI | No | workflows | SCA/container scan, patch SLA, SBOM |
| Structured application logs | Yes | Partial | compile/source inspection | Partial | JSON logger/redaction | correlation, retention, sink and redaction tests |
| Health endpoint | Yes | Partial | source only; overstates connectivity | No | health server | dependency round trips and fault tests |
| Readiness endpoint | Partial | No | credentials treated as connectivity | No | health server | correct dependency semantics and orchestration test |
| Metrics/performance monitoring | Partial | No | CPU/memory/component telemetry only | No | health/heartbeat/dashboard | SLI/SLO, latency/error/queue/order metrics |
| Alerts | Yes | Partial | Telegram code; delivery not drilled | No | adapters/watchdogs | routing, escalation, dedup, delivery drills |
| Error tracking/on-call | No/Partial | No | logs/Telegram only; no named ownership | No | operations docs | accountable rota, severity/SLA, runbooks |
| Docker deployment | Partial | No | Docker unavailable; config not validated | No | Dockerfile/Compose | immutable non-root build and staging rehearsal |
| systemd deployment | Partial | No | host-specific paths | No | systemd units/scripts | parameterize and test on clean host |
| Netlify deployment | Partial | No | configuration/docs exist, current deploy unknown | No | netlify config/docs | preview/staging/prod pipeline and smoke |
| Static frontend build | Partial | No | build cannot resolve packages | No | dashboard package | `npm ci`, typecheck, tests, production build |
| CI install/test | Partial | No for whole system | narrow CI; audit failures | No | GitHub workflows | full clean matrix and protected gates |
| Migration deployment gate | No | No | not present | No | workflows | backup/precheck/migrate/postcheck/abort pipeline |
| Application rollback | Partial docs | No | not rehearsed | No | incident response | immutable previous artifact and game day |
| Migration rollback/forward fix | No | No | not defined | No | migrations/docs | compatibility policy and drill |
| PostgreSQL backup | No executable evidence | No | not verified | No | docs search | encrypted automated backup and monitoring |
| PostgreSQL restore | No | No | no drill | No | docs search | destructive staging restore with integrity checks |
| QuestDB/Qdrant/state backup | No | No | not defined | No | Compose volumes/local files | asset inventory, backup/restore/retention |
| RPO/RTO | No | No | not defined | No | docs search | business approval and measured recovery |
| Unit/model/business tests | Partial | No green suite | collection aborts | No | pytest results | hermetic dependencies and complete green suite |
| Database integration tests | No/Partial | No | no designated PG17 DB | No | test inventory | isolated PG17 fixtures and migration tests |
| Authentication/authorization tests | Partial | No complete proof | no role matrix | No | component/function tests | exhaustive role/negative suite |
| Security tests | Partial | No | narrow regex scanner only | No | CI | history secrets, SAST/SCA/image/IaC/DAST |
| Coverage reporting | No | No | unavailable | No | no coverage result | publish reviewed thresholds |
| Selenium critical workflows | No | No | absent | No | repository search | implement and gate |
| Browser compatibility/accessibility | No evidence | No | UI not launched | No | dashboard source only | approved browser/a11y test matrix |
| Empty/error/loading states | Yes in source | No current execution | not browser-validated | No | dashboard components | component + Selenium validation |
| Dead/display-only control removal | No | No | existing audit records defects | No | Settings audit | wire persistence or remove/label controls |
| Alpaca integration | Yes | Partial | production-like path not run | No | main/streamer/executor | sandbox contracts, outage/partial-fill scenarios |
| Supabase integration | Yes | Partial | production schema/connectivity not run | No | adapters/migrations/dashboard | staging schema/RLS/realtime/load verification |
| QuestDB/NATS/Qdrant integrations | Yes | Mock/partial | local services unavailable | No | collectors/tools/Compose | auth/network/failure/retention integration tests |
| GCP BigQuery replication | Yes | Partial | limited mock tests; real path unverified | No | replication and tests | WIF least privilege, staging replay/reconcile |
| Telegram integration | Yes | No delivery proof | not verified | No | alert modules | expiry/outage/routing drill |
| LLM/model fallbacks | Yes | Partial | deterministic fallback may mask degraded service | No | agent modules | explicit degraded mode, provenance and alert tests |
| Incident response | Partial | No drill | documentation exists | Partial | incident response/deployment safety docs | tabletop and technical exercises |
| Deployment runbook | Partial | No clean-host proof | fragmented/stale | No | README/docs/scripts | unified versioned release runbook |
| Troubleshooting/user/role support docs | Partial | No handoff | ownership absent | No | training/operations docs | role runbooks and support training |
| Named operational ownership | No | No | not found | No | repository docs | assign app/infra/data/integration/security/support owners |
| UAT | No | No | no signed evidence | No | none | traceable role-based UAT |
| Production sign-off | No | No | 5 P0 and 10 P1 open | No | readiness audit | close gates 1–13 and sign immutable evidence bundle |

## Acceptance rule

A row can become **Production Ready = Yes** only when implementation, automated test where applicable, production-like validation, owner, and rollback/recovery evidence are all present. Vendor-managed capability is not automatically accepted: configuration, least privilege, failure behavior, and Forrest operating procedure still require evidence.
