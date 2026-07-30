# Repository Review and Audit — 2026-07-30

## Executive verdict

**Status: RED — not approved for live trading or an Internet-exposed production deployment.**

The repository has meaningful safety work (paper/live endpoint correction, strict synthetic-data
checks, privileged-function authentication helpers, unit tests, operational runbooks), but the
review found two critical trust-boundary problems, a non-reproducible dashboard install, an
environment-dependent Python test, incomplete CI coverage, and substantial maintainability debt.
The existing `PRODUCTION_READINESS.md` verdict remains correct.

This is a source-tree audit of commit `9f6dd86` on branch `work`. It does **not** attest to the live
Alpaca, Supabase, Netlify, NATS, QuestDB, Qdrant, Docker, systemd, or host state. No credentials were
used and no orders, database mutations, deployments, or external-service calls were made.

## Scope and method

Reviewed 671 tracked files across the Python trading/agent/collector/backtest layers, React/Netlify
dashboard, SQL migrations, container definitions, GitHub Actions, configuration, tests, and
operational documentation. Checks performed:

- repository and dependency-manifest inventory;
- full Python byte-compilation;
- complete Pytest run (including `tests/` and `backtests/tests/`);
- Ruff static analysis;
- dashboard clean-install attempt, then test/typecheck/build gate attempt;
- Docker Compose static configuration attempt;
- targeted review for credentials, authorization boundaries, unsafe subprocesses, permissive CORS,
  fail-open behavior, unpinned dependencies/images, mutable runtime installs, and test/CI gaps.

### Verification snapshot

| Check | Result |
|---|---|
| `python -m compileall ...` | PASS |
| `pytest -q` | **FAIL:** 1 failed, 84 passed, 4 skipped |
| `ruff check ...` | **FAIL:** 316 findings (162 automatically fixable) |
| `npm ci` (`dashboard/`) | **FAIL:** lockfile contains an extraneous platform-specific Rollup package |
| dashboard test/typecheck/build | BLOCKED because clean install failed (`vitest` unavailable) |
| `docker compose config -q` | NOT RUN: Docker CLI absent in the audit environment |

## Prioritized findings

### CRITICAL-1 — privileged Netlify background functions do not authenticate requests

Several HTTP handlers create a Supabase client with `SUPABASE_SERVICE_ROLE_KEY` and perform writes or
expensive Alpaca ingestion without calling the repository's admin-auth helper. Examples include
`seed-bars-background.ts`, `seed-options-background.ts`, `ingest-options-chain.ts`,
`ingest-options.ts`, `run-backtest.ts`, and related seed/ingestion handlers. In
`seed-bars-background.ts`, caller-controlled `symbol`, `timeframe`, and `days` flow directly into a
potentially long-running, service-role-backed ingestion job.

**Impact:** if these functions are routable, an unauthenticated caller can trigger privileged database
writes, consume paid upstream API quota and compute, create unbounded jobs, and pollute market-data
tables. Scheduled-function intent does not make a public HTTP route private.

**Remediation:** require the existing fail-closed `requireAdmin` helper (or signed, replay-resistant scheduler credentials)
at the first line of every privileged handler; reject unsupported methods; validate symbols,
timeframes, date ranges, and body sizes against allowlists; add rate limits/idempotency keys; and add
negative tests proving missing/incorrect credentials produce 401/503 without touching Supabase or
Alpaca. Inventory every file under `dashboard/netlify/functions`, rather than fixing only the examples.

### CRITICAL-2 — the administrator shared secret is persisted as user-editable metadata and browser storage

The application copies `user.user_metadata.ADMIN_API_KEY` into two `localStorage` keys on session load
and auth changes. The settings/system-health flow also writes the key into user metadata. Supabase
`user_metadata` is intended for user-controlled profile data, not secrets or authorization claims;
`localStorage` makes the credential readable by any same-origin script and persistent after the
session ends.

**Impact:** compromise of any authenticated account, browser extension, injected script, or XSS can
recover a global bearer secret that authorizes high-impact backend operations. Placing the same shared
secret in every administrator's profile also makes rotation and attribution poor.

**Remediation:** remove the shared admin key from user metadata and `localStorage`. Authorize Netlify
functions using the Supabase access token, validate it server-side, and enforce an immutable
server-owned role/allowlist (`app_metadata` or a database membership table). For step-up operations,
use short-lived, scoped server-issued capabilities and HttpOnly/Secure/SameSite cookies. Rotate the
current admin key after migration.

### HIGH-1 — authentication can be bypassed from a production URL

When there is no session, `App.tsx` accepts either persistent `DEV_BYPASS_AUTH=true` or any URL whose
query string contains `dev=true`, then constructs a mock authenticated session. This is shipped in the
normal production bundle and is not guarded by `import.meta.env.DEV`.

**Impact:** anyone can enter the authenticated dashboard shell. Correctly protected Netlify endpoints
still require the admin key, but any client-side-only controls and any Supabase reads allowed to the
anonymous client remain exposed. It also creates a dangerous false impression that UI authentication
protects operations.

**Remediation:** delete the bypass from production code, or compile it only in an explicit local-only
entry point guarded by `import.meta.env.DEV`; add a production-build test asserting the bypass string
is absent.

### HIGH-2 — dashboard dependency installation is not reproducible

`npm ci` fails on Linux x64 because the lockfile records nested Rollup platform artifacts as
`extraneous` rather than optional; npm attempts to install the Android ARM package and exits with
`EBADPLATFORM`. Consequently, dashboard tests, TypeScript checking, and the production build cannot be
executed from a clean checkout.

**Remediation:** regenerate `dashboard/package-lock.json` from `dashboard/package.json` with a current,
supported npm version in a clean directory; verify platform packages are optional; pin Node/npm via
`engines` and CI; and require `npm ci`, `npm test`, `npm run typecheck`, and `npm run build` in CI.

### HIGH-3 — Python tests perform network/model initialization and fail in a clean environment

`tests/test_ic_direction.py` constructs `SignalDecayMonitor`, whose `BaseAgent` initializer eagerly
loads `SentenceTransformer("all-MiniLM-L6-v2")`. The test attempted a Hugging Face download and failed
with an HTTP proxy 403. A unit test for IC direction should not depend on network access, a model hub,
Qdrant availability, or a multi-hundred-megabyte model.

**Remediation:** inject the embedding model/client into `BaseAgent`, lazy-load only at the point of use,
and provide a deterministic fake in unit tests. Run tests with offline/network-disabled settings in CI
to enforce hermeticity. Keep a separately marked integration test for real model loading.

### HIGH-4 — CI does not validate most of the deployable system

The workflow compiles only three Python files and runs Python tests. It does not run full compilation,
Ruff/type checking, dashboard install/tests/typecheck/build, migration linting, Compose validation,
container builds, or dependency-vulnerability scanning. Its secret scan recognizes only two exact
Python assignment patterns and misses TypeScript, shell, JSON, dotenv files, tokens, private keys, and
history.

**Remediation:** split CI into Python, dashboard, SQL, container, and security jobs; pin tool versions;
run the same clean-install commands used for deployment; add Gitleaks/TruffleHog history scanning and
dependency audits; and protect the default branch with all gates required.

### HIGH-5 — production artifacts are mutable and unpinned

Python requirements use only lower bounds (including entirely unbounded `timesfm`, `vectorbt`, and
`pyfolio-reloaded`). Compose uses `latest` for QuestDB, NATS, and Qdrant. Four services bind-mount the
working tree and run `pip install` during every container start.

**Impact:** identical commits can resolve to different code, cold starts depend on package-index
availability, upstream releases can break or compromise production without a repository change, and
rollback/reconstruction is unreliable.

**Remediation:** generate a hashed Python lock with constraints, pin images by immutable digest, build
collector images once in CI, copy code into read-only images, run as a non-root user, and deploy a
versioned image digest.

### MEDIUM-1 — static-analysis baseline is absent

Ruff reports 316 errors, including bare `except`, import redefinitions, unused variables/imports, and
style patterns that obscure control flow. Not every finding is a defect, but the volume prevents Ruff
from acting as a regression gate and highlights duplicated/dead code in core agents.

**Remediation:** auto-fix the safe subset in isolated commits, manually resolve behavior-sensitive
findings, adopt a narrow initial ruleset, and ratchet it stricter without blanket per-file ignores.

### MEDIUM-2 — container attack surface and availability controls need hardening

Compose publishes NATS monitoring/messaging, QuestDB SQL/HTTP/ILP, and Qdrant directly on all host
interfaces; contains no explicit authentication/TLS configuration; supplies the full `.env` to broad
services; and lacks health checks for data services and collectors. `depends_on` expresses start order,
not readiness.

**Remediation:** bind management ports to loopback or a private network, enable service authentication
and TLS, provide least-privilege per-service secrets, add health checks with readiness conditions,
drop Linux capabilities, set `no-new-privileges`, use read-only filesystems where possible, and define
CPU/memory/PID limits supported by the actual Compose deployment mode.

### MEDIUM-3 — configuration validation is inconsistent at its final security gate

`validate_production_env` calls missing `ADMIN_API_KEY` fatal in the critical-variable check, but later
only warns when it is weak (shorter than 16 characters) and still returns success. A weak global admin
credential is a deployment-blocking condition, not an informational warning.

**Remediation:** replace `sys.exit`-driven validation with a typed validation result/exception, fail
closed for weak secrets, validate entropy rather than length alone, and unit-test every paper/live and
missing/invalid combination.

### MEDIUM-4 — operational documentation is contradictory and time-sensitive

The repository retains an older `FULL_STACK_AUDIT.md` claiming 100% completion and pilot readiness,
while newer audits correctly say RED/not ready. Multiple historical handoffs and reports look
authoritative but describe different hosts, branches, dates, and live states.

**Remediation:** add a single indexed audit landing page with scope, commit, environment, supersession,
and expiry metadata; mark historical reports prominently as superseded; never treat a source-only audit
as evidence of current external-service health.

## Positive controls observed

- `config_validator.py` corrects a paper-mode/live-endpoint mismatch to the paper endpoint and rejects
  the inverse mismatch.
- CI explicitly checks that three backtest/simulation paths reject synthetic data in strict mode.
- The main Compose trading service has bounded JSON logs and a health check.
- Privileged function auth utilities and negative tests already exist for some sensitive endpoints,
  providing a pattern that can be extended to all handlers.
- The repository contains incident response, deployment safety, remediation, and production-readiness
  documents rather than presenting backtest results as sufficient production evidence.

## Remediation sequence / release gates

1. **Immediate stop-ship:** keep live trading disabled; restrict or disable unauthenticated Netlify
   handlers; remove the production auth bypass; rotate the admin shared secret.
2. **Identity redesign:** replace browser-held shared-admin-secret authorization with verified user
   sessions and server-owned roles; add endpoint-level authorization tests.
3. **Restore reproducibility:** regenerate the dashboard lockfile, lock Python dependencies and images,
   and remove runtime package installation.
4. **Make tests hermetic:** inject/lazy-load ML dependencies, make the complete Python suite pass with
   network disabled, then add dashboard and migration/container gates.
5. **Harden runtime:** private networking, service auth/TLS, least-privilege secrets, non-root/read-only
   containers, readiness checks, resource limits, backup/restore and kill-switch drills.
6. **Evidence before pilot:** perform paper-only end-to-end tests for stale data, duplicate orders,
   restart/reconciliation, broker outage, partial fills, kill switch, loss limits, and recovery. Record
   immutable logs and account identity.
7. **Live release criterion:** no Critical/High findings open; all required CI gates green from a clean
   checkout; external infrastructure independently audited; rollback and incident drills passed; and a
   human operator explicitly approves a bounded canary.

## Residual limitations

- No live service, host, cloud configuration, database policy, account identity, position, balance,
  market-data freshness, backup, alert-delivery, or kill-switch behavior was verified.
- Docker configuration could not be normalized because the Docker CLI is absent.
- Dashboard code could not be compiled after the clean install failed; additional TypeScript/build-time
  issues may therefore remain.
- This review used targeted manual security analysis and Ruff, not a full SAST/DAST, SBOM, dependency
  CVE, license, Git-history secret, penetration, quantitative-model, or financial-controls audit.
