# Legacy Environment Baseline

Captured **2026-08-19 UTC** before architectural changes on source commit `96e157aa6399307c590ca56a3d05fd9cecbce929` (the audit prompt's `ffb1b3d...` object is not present in this clone). Refactor branch: `refactor/production-django`; initial tree: clean.

## Host toolchain

| Component | Observed version | Required/declared state |
|---|---|---|
| OS | Ubuntu 24.04.4 LTS | Not pinned |
| Python | 3.14.4 | Docker/CI use 3.11; approved target is 3.13.x |
| pip | 26.1 | Not pinned |
| Node | 24.15.0 | Not pinned |
| npm | 11.4.2 | lockfile version 3 |
| Docker | Unavailable (`command not found`) | Compose 3.8 files exist |
| PostgreSQL/psql | Unavailable (`command not found`) | Legacy production path uses Supabase; version unverified |

The observed Python environment contained: `iniconfig==2.3.0`, `packaging==26.0`, `pip==26.1`, `pluggy==1.6.0`, `Pygments==2.19.2`, and `pytest==9.0.3`, plus editable/container support packages reported by `pip freeze`. It did **not** contain the application dependencies declared by `requirements.txt`. The root requirements use broad lower bounds and contain a malformed UTF-16 fragment for `pandas_market_calendars`; therefore they are not a reproducible lock. The dashboard has `package-lock.json`, but installation was blocked by registry policy on `netlify-cli@17.38.1`.

## Dependency manifests

- Python runtime/research: `requirements.txt`, `requirements-research.txt`, four collector-specific files under `docker/`, and `gemini-computer-use-agent/requirements.txt`.
- Node dashboard: `dashboard/package.json`, `dashboard/package-lock.json`, and `dashboard/deno.lock`.
- Other tooling: `Execution/motion/package.json`; `.agents` tooling is repository-development metadata, not an application dependency.

Exact resolution must be obtained from a clean approved Python 3.13 environment and retained as a lock/constraints artifact. No legacy versions were altered during this capture.

## Required legacy environment variables

The checked-in examples declare: `ADMIN_API_KEY`, Alpaca credentials/endpoints/feed/paper flag, Anthropic keys, strategy/risk limits, Databento credentials, Google credentials, ingestion symbols/timeframes, Reddit credentials, Supabase URL/DSN/anon/service-role keys, symbols, and Vite dashboard settings. See `.env.example` and `dashboard/.env.example` for the complete names and safe examples. Secrets belong in an external secret store and `.env` is ignored.

## Legacy startup commands

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py          # equities
python main_crypto.py   # crypto
cd dashboard && npm install && npm run dev
# Optional service topology:
docker compose up -d
```

The repository also has systemd, Harness, Netlify, PM2, and shell startup paths; the authoritative production topology was not defined.

## Legacy test commands

```bash
pytest --collect-only -q
pytest -q
cd dashboard
npm install
npm test -- --run
npm run typecheck
npm run build
```

Additional discovered validation includes `.github/workflows/ci.yml`, `.github/workflows/validate-secrets.yml`, Harness pipelines, backtest scripts, and `preflight_check.py`.
