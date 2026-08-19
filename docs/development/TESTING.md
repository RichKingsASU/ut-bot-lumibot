# Reproducible Python testing

## Supported interpreter

Production (`Dockerfile`), CI (`.github/workflows/ci.yml`), and the supported test
interpreter use **CPython 3.11.x**. Other versions are not evidence for this gate.

## Dependency groups

| Manifest | Purpose |
|---|---|
| `requirements-core.txt` | Minimal trading runtime and safety imports |
| `requirements-backtest.txt` | Numeric and backtest tooling (includes core) |
| `requirements-agents.txt` | Lightweight agent tests (includes core) |
| `requirements-cloud.txt` | Deployed broker/database/GCP adapters |
| `requirements-test.txt` | Canonical complete hermetic test environment |
| `requirements-production.txt` | Canonical full production deployment, including optional large models |
| `requirements.txt` | Legacy bytes retained unchanged for PR transport compatibility; never install from this file |

Torch, Transformers, SentenceTransformers, TimesFM, and vector model runtimes are
not in the safety/test manifest. Unit tests must not load or download those models.

## Clean setup

```bash
python3.11 -m venv .venv-test
. .venv-test/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-test.txt
python -m pip check
python scripts/check_test_environment.py
```

No credentials or external services are needed to collect or execute the suite.
Do not enable system site packages.

`requirements-production.txt` is the canonical aggregate production manifest,
and `requirements-test.txt` is the canonical test manifest. The historical
`requirements.txt` is retained byte-for-byte only because the Codex PR transport
cannot serialize its malformed predecessor blob. No active tooling may install
from that legacy file.

References to `requirements.txt` under `docker/*/` and
`gemini-computer-use-agent/` are path-local subproject manifests, not the legacy
repository-root file. The remaining reference in `docs/implementation_plan.md`
is a historical change-scope checklist and is not an installation instruction.

## Gates

```bash
python -m compileall -q src strategies agents collectors backtests scripts
python -m pytest --collect-only -q
scripts/test-safety.sh                 # TRADING SAFETY GATE
python -m pytest -q backtests/tests/   # backtest gate
python -m pytest -q                    # complete intended unit suite
```

Run all checks with `scripts/test-all.sh`. The intended suite is explicitly rooted
by `pytest.ini`; operational scripts named `test_*.py` are not unit tests and may
perform network or credential checks when deliberately executed by operators.
Collection therefore performs no network calls and requires no secrets.

Large-model and real cloud/network integration checks belong in an extended,
sandboxed scheduled environment; they never replace the per-commit safety gate.

## Validated direct-dependency inventory

The manifests were derived from an AST scan of repository imports, then checked
against import paths reached by collection:

* **Core trading runtime:** Lumibot, NumPy, pandas, Pydantic, python-dotenv,
  HTTPX, Requests, pytz, python-dateutil, pandas-market-calendars, psutil,
  PyYAML, and rich.
* **Research/backtest:** SciPy, hmmlearn, scikit-learn, statsmodels, Matplotlib,
  Polars, PyArrow, and yfinance.
* **Agents/AI:** google-genai, Playwright, termcolor, and aiohttp. Torch,
  Transformers, SentenceTransformers, TimesFM, LangChain, and model/vector
  clients remain optional production/research dependencies.
* **Cloud/GCP and database/Supabase:** Supabase, alpaca-py, nats-py,
  qdrant-client, psycopg2, google-cloud-bigquery, and google-cloud-pubsub.
* **Test only:** pytest. It is intentionally absent from production manifests.

Platform-specific behavior is limited to the Linux `fcntl` execution lease; its
tests are part of the Linux CI gate. Direct requirements use bounded compatible
ranges rather than freezing transitive packages, so security resolver updates
remain possible while major-version drift is excluded.

## Import and side-effect policy

The Gemini agent uses the unambiguous `agent_config` module name. Previously its
tests prepended a directory and imported generic `config`, so an already-cached
root `config` module made results depend on collection order. Core package imports
must use package-qualified paths and retain direct-script compatibility.

Operational probes (`scripts/test_timesfm.py`, `scripts/test_trade_cycle.py`, and
root `test_supabase.py`) are intentionally outside pytest discovery: they load
models, call brokers, or call Supabase. They are operator integration probes, not
secret-independent unit tests. Production network/model initialization remains
behind methods or `main()` boundaries; unit collection must never invoke it.
