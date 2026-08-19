# Legacy Test Baseline

Captured **2026-08-19 UTC** on `96e157aa6399307c590ca56a3d05fd9cecbce929`, before refactoring. Failures are deliberately retained as evidence.

| Command | Result | Counts / evidence | Classification |
|---|---|---|---|
| `pytest --collect-only -q` | FAIL (exit 2) | 62 tests discovered; 14 collection errors | **ENVIRONMENT ISSUE**: undeclared/uninstalled runtime packages; malformed, unlocked requirements prevent deterministic install |
| `pytest -q` | FAIL (exit 2) | 0 executed; 14 collection errors; 0 passed/failed/skipped | **TEST INFRASTRUCTURE ISSUE**: global discovery includes scripts, Gemini subproject, integrations, and tests with import-time optional dependencies |
| `cd dashboard && npm install` | FAIL (exit 1) | registry returned HTTP 403 for `netlify-cli@17.38.1` | **ENVIRONMENT ISSUE**: package denied by registry/security policy |
| `cd dashboard && npm test -- --run` | FAIL (exit 127) | 0 executed; `vitest` absent after failed install | **ENVIRONMENT ISSUE** |
| `cd dashboard && npm run typecheck` | FAIL (exit 2) | Type declarations/packages unavailable; JSX and jest-dom errors | **ENVIRONMENT ISSUE**; application errors cannot be excluded until clean install |
| `cd dashboard && npm run build` | FAIL (exit 127) | `designmd` absent after failed install | **ENVIRONMENT ISSUE** |

## Required summary

```text
Tests discovered: 62 Python tests before collection aborted; dashboard tests statically discovered but not collected
Tests executed: 0 Python; 0 dashboard
Passed: 0
Failed: 0 test assertions (all failures occurred before execution)
Skipped: 0 reported
Collection errors: 14 Python; dashboard runner unavailable
```

The collection errors referenced missing `httpx`, `pytz`, `pandas`, and other imports across backtests, scripts, Gemini automation, Supabase checks, and trading tests. This baseline is **FAIL** and PR-002/PR-201 remain open. It must not be interpreted as an application-quality result.
