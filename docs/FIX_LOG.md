# Project Fix & Audit Log

This document records the specific bug fixes and schema alignment corrections applied during this session.

## 🛠️ Applied Corrections

### 1. Unified Tool Layer (Python)
* **`get_regime_state` / `get_regime_history`**: Fixed queries executing against the non-existent `regime_state` table to target `regime_states`. Mapped returned keys (`detected_at` $\rightarrow$ `updated_at`, `regime_probability` $\rightarrow$ `confidence`) to maintain client compatibility.
* **`get_sentiment_scores`**: Updated query from the non-existent `sentiment_scores` table to retrieve `news_articles` and filter mentions in Python, calculating a rolling sentiment score.
* **`start_all.sh` / `morning_startup.sh` / `pre_market_check.sh`**: Changed all global `python3` invocations to use `venv/bin/python3` directly to ensure the virtualenv dependencies (`httpx`) load correctly in host terminal runs.

---

### 2. Frontend & Netlify Functions (TypeScript/React)
* **`get-system-health.ts` / `get-pipeline-status.ts`**: Corrected Supabase queries for the `regime_states` table. Replaced query select parameter `probability` with the PostgREST alias `probability:regime_probability` to prevent `400: column does not exist` query errors.
* **`CryptoView.tsx` / `OverviewView.tsx`**: Updated client-side regime state queries to use `probability:regime_probability` PostgREST aliasing.
* **`OverviewView.tsx` / `AccountHealthView.tsx`**: Updated client-side queries for `portfolio_snapshots` to request `portfolio_value:equity` to map the non-existent `portfolio_value` column to `equity`.
* **`EquitiesPerformanceView.tsx`**: Corrected `portfolio_snapshots` query by aliasing `created_at:snapshot_at` and updating the sorting configuration to order by `snapshot_at`.
* **`useMetrics.ts`**: Corrected the last snapshot query sorting behavior to order by `snapshot_at` instead of the non-existent `created_at` column.

---

## 🧪 Verification Logs

### 1. PostgREST Aliases Verification
Running simulated REST requests yielded `200 OK` responses:
```bash
# Regime Query with alias probability:regime_probability
200 [{'symbol': 'SPY', 'regime': 'VOLATILE', 'probability': 0.9986, 'detected_at': '2026-05-24T07:16:10.572591+00:00'}]

# Snapshots Query with alias portfolio_value:equity
200 [{'snapshot_at': '2026-05-24T04:12:33.818596+00:00', 'portfolio_value': 108054.69, 'equity': 108054.69}]

# Equities Curve Query with alias created_at:snapshot_at
200 [{'created_at': '2026-05-24T04:12:33.818596+00:00', 'equity': 108054.69}]
```

### 2. Python Unit Tests
```bash
$ venv/bin/pytest tests/test_tools.py -v
=================== 52 passed, 4 skipped, 1 warning in 4.94s ===================
```
