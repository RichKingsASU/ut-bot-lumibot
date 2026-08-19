# FDE Remediation Ledger

Evidence status as of 2026-08-19 on `refactor/production-django`. A test file, configuration, or script without execution is not a pass.

| ID | Pri | Status | Evidence / blocker |
|---|---|---|---|
| PR-001 approved stack | P0 | IN PROGRESS | Django/PostgreSQL/templates foundation committed; clean dependency install and PG17 execution blocked by package policy/tool availability; legacy retained for parity only |
| PR-002 deterministic build | P0 | OPEN | exact approved dependencies pinned, but clean install returned HTTP 403; Python host is 3.14, not 3.13 |
| PR-003 authoritative PG17 schema | P0 | IN PROGRESS | Django migrations/models exist; no PG17 migration rehearsal |
| PR-004 trading safety | P0 | IN PROGRESS | idempotency, default-safe kill switch, limits, HITL state and tests implemented; broker/failure/restart scenarios unexecuted |
| PR-005 RBAC | P0 | IN PROGRESS | explicit groups, server-side permissions, negative tests; tests unexecuted and provisioning/MFA require validation |
| PR-006 backup/restore | P0 | OPEN | guarded scripts/runbook exist; host lacks PostgreSQL tools, so restore evidence is absent |
| PR-201 green collection | P0 | OPEN | legacy baseline has 14 collection errors; approved Django tests could not install/run |
| PR-101 secrets incident | P1 | OPEN | credential rotation requires accountable external owner evidence |
| PR-102 browser admin key | P1 | IN PROGRESS | approved Django path uses server sessions; legacy UI retirement not complete |
| PR-103/104 network/containers | P1 | IN PROGRESS | internal PG network, loopback web, non-root/read-only/cap-drop config; Docker unavailable for execution |
| PR-105/106 config/readiness | P1 | IN PROGRESS | fail-closed production settings and DB readiness probe implemented; fault test outstanding |
| PR-107 write integrity | P1 | IN PROGRESS | database transactions/constraints/idempotency implemented; PG concurrency test outstanding |
| PR-202 dashboard suite | P1 | OPEN | legacy npm registry 403; Django static/template validation not executed |
| PR-203 Selenium | P1 | IN PROGRESS | login/RBAC/kill-switch journeys created; browser→PG execution absent |
| PR-204 failure tests | P1 | OPEN | full broker/network/restart matrix outstanding |
| PR-301–305 deployment/operations | P1 | IN PROGRESS | production compose/CI/runbooks exist; staging rehearsal/monitoring ownership absent |
| PR-401–403 UAT/handoff | P1 | OPEN | plan exists; no stakeholder signatures or operations drill |
| PR-501/502 release | P1 | BLOCKED | all P0 evidence gates and sign-offs required |
