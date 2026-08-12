# Disrupting Alpha Settings Console Audit

> Evidence-based functional and safety audit of the Settings Console and its
> path into the running Alpaca trading bot.
>
> **Branch:** `claude/disrupting-alpha-settings-audit-r3fln6`
> **Commit audited:** `f7bf1d9ea365670cd983d701c807a6dc2e09d704`
> **Date:** 2026-07-16
> **Method:** Static code tracing + subagent cross-verification. **No live browser
> session, no Supabase connection, no Alpaca call, no order placed.** All runtime
> persistence claims are code-proven, not observed — see §3.

---

## 1. Executive Summary

The "Settings Console" (`/settings`, `SettingsView.tsx`) is **largely non-functional as a
control surface for the running bot.** It is a mostly-cosmetic form:

- The **paper/live toggle does not control anything.** It sets a local React state
  variable (`useState(true)`), is never persisted, and only changes the Base-URL string
  used by the *Test Connection* button. The actual bot's paper/live mode is decided
  entirely by **environment variables** (`ALPACA_IS_PAPER`, `ALPACA_BASE_URL`) read once
  at process start. The UI can display any mode while the bot trades in the opposite one.
- The mode **badge** next to the toggle reads a Supabase row (`user_settings.paper_mode`)
  that **no code ever writes**, so it is permanently `unknown` ("...").
- The **"Save Defaults" button has no `onClick`** — it does nothing.
- Broker API-key / secret / Base-URL / Database-token fields **have no save path at all**;
  they exist only to feed the Test Connection buttons.
- The only Settings field that attempts to persist (Telegram config) writes to a table whose
  RLS blocks the anonymous browser client, and whose `key` column is not unique, so writes
  either silently fail or accumulate duplicate rows.
- The rich **`ContractConfigSection`** component and the **`options-config` save endpoint**
  are **orphaned** — never imported/called by the app.
- The **emergency "flatten" endpoint** (`alpaca-flatten`) **defaults to the LIVE Alpaca
  account** when `ALPACA_IS_PAPER` is unset and **fails open** when `ADMIN_API_KEY` is unset,
  meaning it can liquidate a live account without authentication under a plausible misconfig.

There are **at least three independent, un-synchronized representations of "trading mode"**
(local UI toggle, unwritten Supabase row, env vars) and **two independent env switches**
(`ALPACA_IS_PAPER` vs `ALPACA_BASE_URL`) that can disagree. This is the central defect.

---

## 2. Immediate Safety Warning

🚨 **The Settings Console must not be trusted as an indicator of, or control over, the live
trading environment.** Specifically:

1. **The UI paper/live selector is decorative.** Switching it Paper↔Live changes nothing in
   the runtime. Operators could believe they are in Paper while the bot is Live (or vice
   versa). — `SettingsView.tsx:246,476-488`
2. **`alpaca-flatten` fails to LIVE.** If `ALPACA_IS_PAPER` is unset in the Netlify
   environment, the emergency flatten targets `https://api.alpaca.markets` (real money) and
   liquidates all positions + cancels all orders. — `alpaca-flatten.ts:28-31,48,52`
3. **Auth fails open.** All `alpaca-*` functions skip their admin check when `ADMIN_API_KEY`
   is not set; `alpaca-flatten`'s check passes for a header-less request in that case. —
   `alpaca-flatten.ts:22`, `alpaca-orders.ts:5-9`, `lib/auth.ts:12-13`
4. **`alpaca-account` is an open credential/URL proxy.** Any unauthenticated caller can send
   `{apiKey, apiSecret, baseUrl}` in the body and have the function relay them to Alpaca. —
   `alpaca-account.ts:10-28`

Do not enable live trading until §25 stop-ship items are fixed.

---

## 3. Audit Scope and Limitations

**In scope:** the `/settings` Settings Console (`SettingsView.tsx`), its supporting hooks
(`useTradingMode`, `useRiskConfig`, `useAlpacaAccount`), the Netlify functions that back it,
the Supabase `user_settings`/`risk_config`/`bot_status` persistence, and the Python bot's
Alpaca/paper-live/credentials/kill-switch runtime path.

**Limitations (honest):**
- **No running application.** This environment has no live Supabase project, Netlify runtime,
  or Alpaca account, and no browser. Every claim below is **code-proven** (traced through
  source) or **static-config-proven**, not **observed** in a browser or DB. Items that would
  require a live system to confirm are marked **UNVERIFIED** with the missing evidence named.
- **`.env` values were not read** (only variable names, masked). Actual deployed values of
  `ALPACA_IS_PAPER`, `ADMIN_API_KEY`, etc. are unknown, so several safety outcomes are
  *conditional on deployment configuration* — which is itself a finding (the code fails open).
- No live trades, cancels, or position closes were performed.

---

## 4. Environment Inspected

| Item | Value |
| --- | --- |
| Working dir | `/home/user/ut-bot-lumibot` |
| Branch | `claude/disrupting-alpha-settings-audit-r3fln6` |
| Commit | `f7bf1d9ea365670cd983d701c807a6dc2e09d704` |
| Remote | `RichKingsASU/ut-bot-lumibot` |
| Frontend | Vite + React + TypeScript (`dashboard/`), Supabase JS client |
| Backend | Netlify Functions (`dashboard/netlify/functions/`) — no Supabase Edge Functions |
| Bot runtime | Python + Lumibot (`main.py`, `main_crypto.py`, `run_crypto_bot.py`), PM2 (`ecosystem.config.js`), Docker |
| Database | Supabase (Postgres) |
| Broker | Alpaca (Lumibot broker + alpaca-py + raw REST) |
| Secrets model | Environment variables (`.env` / Netlify env). No secret vault. |

Environment variable **names** present (values masked): `ALPACA_IS_PAPER`, `ALPACA_API_KEY`,
`ALPACA_API_SECRET`, `ALPACA_BASE_URL`, `ALPACA_DATA_URL`, `ADMIN_API_KEY`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`,
`VITE_ADMIN_API_KEY`, `MAX_DAILY_LOSS`, `MAX_POSITION_SIZE`, `MAX_TRADES_PER_DAY`, …

---

## 5. Architecture Summary

```
                     ┌─────────────────────────────────────────────┐
   Browser (anon) ── │ SettingsView.tsx  (/settings)               │
                     │  • Alpaca key/secret  → local state only    │
                     │  • Paper/Live toggle  → local state only    │──┐ (never persisted)
                     │  • Base URL (readonly, derived from toggle) │  │
                     │  • Telegram config    → supabase upsert     │  │
                     │  • Strategy defaults  → local state, Save=noop│ │
                     └───────────────┬─────────────────────────────┘  │
                                     │ Test Connection (POST creds)     │
                                     ▼                                  │
             ┌───────────────────────────────────┐                     │
             │ Netlify Functions                 │                     │
             │  alpaca-account (open proxy)      │  env: ALPACA_*      │
             │  alpaca-orders/positions (RO)     │──────────────┐      │
             │  alpaca-flatten (LIVE default!)   │              │      │
             │  options-config (orphaned save)   │              │      │
             └───────────────┬───────────────────┘              │      │
                             │ service_role                     │      │
                             ▼                                  ▼      ▼
                   ┌──────────────────┐            ┌──────────────────────────┐
                   │ Supabase         │            │ Alpaca REST              │
                   │  user_settings   │            │  paper-api / api         │
                   │  bot_status      │◄───────┐   └──────────────────────────┘
                   │  risk_config     │        │
                   └──────────────────┘        │ heartbeat reads target_status
                             ▲                  │
                             │ writes logs      │
   ┌─────────────────────────┴──────────────────┴───────────────────────────┐
   │ Python Bot (main.py / Lumibot)                                          │
   │   config.py: ALPACA_CONFIG["PAPER"] = ALPACA_IS_PAPER=="true"           │  ◄── REAL
   │   ALPACA_BASE_URL (options_executor.py)                                 │      SOURCE
   │   Reads mode/creds ONLY from env — NEVER from user_settings.paper_mode  │      OF TRUTH
   └─────────────────────────────────────────────────────────────────────────┘
```

The dashboard's write path and the bot's read path **do not meet** for trading mode or
credentials.

---

## 6. Settings Console Inventory

Route: `/settings` → `SettingsView` (lazy-loaded at `App.tsx:37,172`). Four accordion
sections, all in `SettingsView.tsx`:

| Section | Content | Persists? |
| --- | --- | --- |
| **Broker Configuration** | Alpaca API key, Secret key, Base URL (readonly), Test Connection, Paper/Live toggle + badge | **No** (test-only) |
| **Database Configuration** | Supabase endpoint (readonly), Database token, Test Connection | **No** (test-only) |
| **Notifications** | Telegram token + chat id (Save/Test), Email toggle, Push toggle, Quiet hours start/end | Telegram: attempts Supabase (blocked by RLS for anon). Rest: **local only** |
| **Strategy Defaults** | Default symbol, Timeframe, ATR period, Sensitivity, Auto-start toggle, **Save Defaults** | **No** — Save button has no handler |

**Not in the Console (but exist in the codebase):** `ContractConfigSection.tsx` (options
expiration/strike UI — orphaned, never imported), `RiskManagerView.tsx` (kill switch + risk
limits — separate `/risk` page), `useRiskConfig` (`risk_config` table).

---

## 7. Visible Fields and Controls

| Section | Label | Component/File:line | Type | Default | Value source | Save path | Persistence | Runtime consumer | Classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Broker | Alpaca API Key | `SettingsView.tsx:429` | password | `''` | local state | none | none | none (test only) | **DISPLAY-ONLY / BROKEN** |
| Broker | Alpaca Secret Key | `:430` | password | `''` | local state | none | none | none | **DISPLAY-ONLY / BROKEN** |
| Broker | Base URL | `:434-439` | text (readOnly) | derived from `paperMode` | local state | none | none | none | **DISPLAY-ONLY** |
| Broker | Test Connection | `:442-456` | button | — | `handleTestAlpaca` | n/a | n/a | Alpaca `/v2/account` | **WORKING (test only)** |
| Broker | Paper/Live toggle | `:476-488` | toggle | `paperMode=true` | local state | none | none | **none** | **DISPLAY-ONLY / BROKEN** |
| Broker | Mode badge | `:457-475` via `useTradingMode` | badge | `unknown` | `user_settings.paper_mode` (unwritten) | n/a | n/a | n/a | **BROKEN (always "...")** |
| Database | Database endpoint | `:581-582` | text (readOnly) | hard-coded URL | hard-coded | none | none | none | **DISPLAY-ONLY** |
| Database | Database token | `:584` | password | `''` | local state | none | none | none | **DISPLAY-ONLY** |
| Database | Test Connection | `:586-596` | button | — | `handleTestDb` | n/a | n/a | Supabase select | **WORKING (test only)** |
| Notifications | Telegram Bot Token | `:631-637` | password | loaded from Supabase | `user_settings.telegram_config` | `handleSaveTelegram` | Supabase (RLS-blocked for anon) | `telegram_bot.py` reads env, not this | **BROKEN (see §12)** |
| Notifications | Telegram Chat ID | `:641-647` | text | loaded from Supabase | same | same | same | same | **BROKEN** |
| Notifications | Save Telegram Config | `:651-653` | button | — | `handleSaveTelegram` | upsert | see §12 | — | **BROKEN (silent-fail risk)** |
| Notifications | Send Test Message | `:654-664` | button | — | `handleTestTelegram` | n/a | n/a | Telegram API (from browser) | **WORKING (test only)** |
| Notifications | Email Notifications | `:680-683` | toggle | `false` | local state | none | none | none | **DISPLAY-ONLY** |
| Notifications | Push Notifications | `:684-687` | toggle | `true` | local state | none | none | none | **DISPLAY-ONLY** |
| Notifications | Quiet Hours Start | `:689-692` | time | `22:00` | local state | none | none | none | **DISPLAY-ONLY** |
| Notifications | Quiet Hours End | `:693-696` | time | `07:00` | local state | none | none | none | **DISPLAY-ONLY** |
| Strategy | Default Symbol | `:713-716` | text | `IWM` | local state | none | none | none | **DISPLAY-ONLY** |
| Strategy | Default Timeframe | `:717-726` | select | `15m` | local state | none | none | none | **DISPLAY-ONLY** |
| Strategy | ATR Period | `:727-730` | number | `14` | local state | none | none | none | **DISPLAY-ONLY** |
| Strategy | Sensitivity | `:731-734` | number | `2.0` | local state | none | none | none | **DISPLAY-ONLY** |
| Strategy | Auto-start on deploy | `:736-739` | toggle | `false` | local state | none | none | none | **DISPLAY-ONLY** |
| Strategy | **Save Defaults** | `:740-742` | button | — | **no `onClick`** | none | none | none | **BROKEN (no-op)** |

**Fake/placeholder interactivity:** the "Save Defaults" button (`:740`) renders a Save icon
and label but wires no handler — clicking it does nothing (not even a toast). The
Email/Push/Quiet/Strategy fields are fully editable but discarded on unmount.

---

## 8. Hidden and Code-Only Settings

| Setting | Where | Wired to UI? | Reaches bot? |
| --- | --- | --- | --- |
| Options `expiration_mode`, `strike_mode`, `strike_step`, `expiration_days_out`, `max_dte_fallback` | `ContractConfigSection.tsx`, saved via `options-config.ts:132` → `user_settings.options_config` | **No** (component never imported; no caller of `action=save`) | Partially — bot reads options params from `runtime_config.json` via `config.py:_get`, **which nothing writes**; falls back to env/defaults |
| Risk config (`max_position_pct`, `max_daily_loss`, `kelly_fraction`, stops, …) | `useRiskConfig.ts` → `risk_config` table | Used by RiskManager, not Settings | **UNVERIFIED** — needs check whether bot reads `risk_config` (bot reads limits from `config.py`/env: `MAX_DAILY_LOSS`, `MAX_POSITION_SIZE`) |
| `trading_enabled` kill switch | `RiskManagerView.tsx:61-72` → `user_settings` `id=1` | On `/risk` page | **No** — bot does not read it; write also targets a non-existent schema (§12) |
| `ALPACA_LIVE_URL` | `agents/tools/trading_tools.py:44` | No | Env only |
| Runtime overrides (`runtime_config.json`) | `config.py:11-32` | No writer anywhere in repo | Read by bot but file is never produced |

---

## 9. Frontend Save and Load Trace

**Load (`SettingsView.tsx:272-290`):**
- Reads `localStorage['alpaca_last_verified']` (display string only).
- Reads `user_settings.telegram_config` from Supabase → populates Telegram fields.
- **Does NOT load** Alpaca key/secret, paper mode, DB token, or any Strategy Default. Those
  start at their hard-coded initial state every mount.

**Save handlers:**
- `handleSaveTelegram` (`:292-301`) — `supabase.from('user_settings').upsert({key:'telegram_config', value: JSON.stringify(...)})`. Sets a 3-second "Saved"/"Failed" chip from the returned `error`. **Not awaited before the chip is set? It is awaited**, but the chip logic only distinguishes `error` truthiness; an RLS denial that returns `error` shows "Failed", but note the upsert also cannot conflict-match on `key` (§12).
- Broker, Database, Strategy sections have **no save handler**.
- **`Save Defaults` button — no handler at all.**

**Anti-patterns found:**
- Paper/Live toggle mutates local state only (`setPaperMode`, `:486`) — value never leaves
  the component. — matches "Fields rendered but omitted from save payload."
- `paperMode` local boolean and `useTradingMode()` badge are two different sources → the
  toggle and the badge can display different things.
- Blank Alpaca secret field on every load — if a save path existed it would risk overwriting
  stored secrets with blanks (it does not exist today, but the pattern is set up for it).
- `console.log` of connection attempts including base URL (`:340,358`) — no secrets, but noisy.

---

## 10. Network Activity Results

Static trace (no browser available — see §3). Per action:

| Button | Handler | Request | Persists? |
| --- | --- | --- | --- |
| Broker → Test Connection | `handleTestAlpaca` `:316-383` | `POST /.netlify/functions/alpaca-account` with `{apiKey, apiSecret, baseUrl}` + `x-admin-api-key: VITE_ADMIN_API_KEY` | **No.** Read-only account fetch; nothing saved. |
| Broker → Paper/Live toggle | inline `:476-488` | **No network request** | No. Local state only. |
| Database → Test Connection | `handleTestDb` `:303-314` | `supabase.from('user_settings').select('id').limit(1)` | No |
| Notifications → Save Telegram | `handleSaveTelegram` | `supabase upsert user_settings` | Attempts — see §12 |
| Notifications → Send Test Message | `handleTestTelegram` `:385-401` | `POST api.telegram.org/bot<token>/sendMessage` **directly from the browser** | No (exposes token to browser network log; no error surfaced to user — empty `catch`) |
| Strategy → Save Defaults | — | **No network request** (no handler) | No |

> For the paper/live toggle and Save Defaults: **No network request is generated when the
> button is clicked.** The value changes only in React component state and is lost on unmount.

---

## 11. Backend and API Findings

Netlify functions in `dashboard/netlify/functions/`. There is **no settings-writer backend
for paper/live mode or Alpaca credentials** — the only `user_settings` writer is
`options-config.ts` (key `options_config`), which the UI never calls.

| Function | Method | Creds source | Paper/Live logic | Auth | Trade capability |
| --- | --- | --- | --- | --- | --- |
| `alpaca-account.ts` | GET/POST | env `ALPACA_*`, **or request body** | `isPaper = baseUrl.includes('paper-api')` (`:71`) | **Bypassed** if body has creds (`:26`); skipped if `ADMIN_API_KEY` unset | Read-only `/v2/account` |
| `alpaca-orders.ts` | GET | env | `ALPACA_BASE_URL` default paper (`:11`) | `if (adminKey && …)` — fails open if env unset (`:5-9`) | Read-only `/v2/orders` |
| `alpaca-positions.ts` | GET | env | `ALPACA_BASE_URL` default paper | fails open if env unset | Read-only `/v2/positions` |
| `alpaca-flatten.ts` | POST | env | **`ALPACA_IS_PAPER === 'true'` → default LIVE** (`:28-31`) | `adminKey !== env` — passes for header-less request when env unset (`:22`) | **DELETE all orders + all positions** (`:48,52`) + bot shutdown |
| `options-config.ts` | GET/POST | env | n/a | `X-Admin-API-Key` (`:355-363`) | data only; writes `user_settings.options_config` |
| `bot-state.ts` | GET | env `ALPACA_DATA_URL` | n/a | admin, fails open | read-only |
| `ingest-bars.ts` | GET | env | live host for clock | admin **or** `User-Agent` contains "Netlify" (`:30`) — trivially bypassable | data write only |

**Shared helper** `lib/auth.ts:9-17` `isAuthorized()` returns `true` when `ADMIN_API_KEY` is
unset ("default to authorized for local dev convenience"). The alpaca-* functions inline the
same fail-open pattern.

Key backend defects:
- **No endpoint persists trading mode or credentials.** Confirmed by searching all functions.
- **`alpaca-account` open proxy** (`:10-28`): unauthenticated body-cred bypass.
- **`alpaca-flatten` live-default + fail-open** (`:22,28`): the single highest financial risk.

---

## 12. Supabase and Persistence Findings

**`user_settings` live shape** (`dashboard/supabase/schema_current_state.sql:245-253`):
```sql
CREATE TABLE IF NOT EXISTS user_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT,            -- NULLABLE, NOT UNIQUE, NOT INDEXED
  value JSONB,
  updated_at TIMESTAMPTZ
);
```
A conflicting definition exists in `migrations_bak/20260325000000_8_screen_upgrade.sql:19-24`
(`user_id`, `settings` columns). There are also **two migration trees** (repo-root
`supabase/migrations/` and `dashboard/supabase/migrations/`) carrying duplicate remediation
files.

Critical persistence defects:
1. **`key` is not unique** → `supabase.upsert({key, value})` with no `onConflict` defaults to
   the PK (`id`), which callers never supply → **every "save" inserts a new duplicate row**
   instead of updating (matches the "2 rows" note at `schema_current_state.sql:245`). Affects
   Telegram config, alerts_enabled, options_config. — **BROKEN persistence.**
2. **RLS blocks the anonymous browser client.** `supabase/migrations/20260710000000_supabase_audit_remediation.sql:21-47,158-164`
   enables RLS and grants read/write **only** to `authenticated`/`service_role`; anon write
   grants are revoked. The frontend uses the **anon key** (`supabaseClient.ts:3-11`). Unless
   the user is signed in as `authenticated`, **all `user_settings` reads/writes from the
   browser silently fail** — including the Telegram save and the `useTradingMode` /
   `paper_mode` read (so the badge is doubly guaranteed to be `unknown`).
3. **`RiskManagerView.tsx:36-83`** reads/writes `user_settings` as `id=1` with columns
   `trading_enabled`, `max_daily_loss`, `max_position_pct`, `account_equity` — **none of
   which exist** in the live schema, and `id` is a UUID PK, not integer `1`. These calls
   **error** against the real table → the kill switch and risk-limit saves do not persist.
4. **`paper_mode` is never written or seeded** anywhere in the repo (`INSERT INTO
   user_settings` = 0 matches; no seed row). The toggle only sets local state.
5. **Telegram bot token stored plaintext** in `user_settings.value` (`SettingsView.tsx:296-297`).
6. **No Alpaca secrets are stored in Supabase** — credentials live only in env vars. (Good.)

**Runtime consumption:** the Python bot **never reads `user_settings`** for mode, credentials,
or kill state (verified across `*.py`; only `strategies/health_server.py` *echoes* the
env-derived `PAPER` value). So even a *successful* Supabase settings write would not reach the
bot.

---

## 13. Alpaca Paper/Live Configuration Trace

```
UI toggle (paperMode, useState(true))         SettingsView.tsx:246
  └─ onClick → setPaperMode(!paperMode)        :476-488   ── local state only, dead end
  └─ drives Base-URL display + Test payload    :319,437   ── not persisted

Mode BADGE (separate source!)
  └─ useTradingMode()                          useTradingMode.ts:30-53
       └─ supabase user_settings key=paper_mode (READ)   :36-40
            └─ NO WRITER anywhere → always 'unknown'

RUNTIME (the real thing)
  Lumibot equities/crypto broker
    └─ config.py:64  ALPACA_CONFIG["PAPER"] = os.getenv("ALPACA_IS_PAPER","true").lower()=="true"
        └─ main.py:60 / main_crypto.py:47 / run_crypto_bot.py:65  Alpaca(ALPACA_CONFIG)
  Options order REST (the actual order path)
    └─ strategies/options_executor.py:141-142  _base_url() = os.getenv("ALPACA_BASE_URL","paper-api…")
  Portfolio snapshot client
    └─ adapters/supabase_logger.py:357  is_paper = os.getenv("ALPACA_IS_PAPER"…)=="true"
  Emergency flatten (Netlify)
    └─ alpaca-flatten.ts:28  isPaper = process.env.ALPACA_IS_PAPER === 'true'  (unset ⇒ LIVE)
```

**Answers to the Phase 9 questions:**
1. **Source of truth for trading mode:** environment variables — `ALPACA_IS_PAPER` (Lumibot
   broker, portfolio client, flatten) and `ALPACA_BASE_URL` (options REST). Read once at start.
2. **More than one source of truth?** Yes — `ALPACA_IS_PAPER` and `ALPACA_BASE_URL` are
   independent and can disagree; plus the UI toggle and the Supabase badge are two more
   (disconnected) representations. **Four representations, none synchronized.**
3. **Does the UI update the source of truth?** No.
4. **Does the running worker reload it?** No — env is read at process start only.
5. **Restart required?** Yes — mode change requires editing env and restarting the process.
6. **Can UI show Paper while runtime is Live?** **Yes.**
7. **Can UI show Live while runtime is Paper?** **Yes.**
8. **Does selecting Live change the endpoint?** No (only the readonly display string + test call).
9. **Does selecting Live change credentials?** No — one env credential pair is used regardless.
10. **Selector functional / broken / decorative?** **Decorative.**

---

## 14. ALPACA_IS_PAPER Investigation

| Variable | File:line | Definition/usage | Default | Time | Side | Controls UI | Controls endpoint | Controls creds | Overridden by | Live/dead |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ALPACA_IS_PAPER` | `config.py:64` | `os.getenv("ALPACA_IS_PAPER","true").lower()=="true"` | `true`/paper | runtime start | backend (Python) | no | **yes (Lumibot broker)** | no | not overridden | live |
| `ALPACA_IS_PAPER` | `adapters/supabase_logger.py:357` | same parse | paper | runtime | backend | no | yes (snapshot client) | no | — | live |
| `ALPACA_IS_PAPER` | `preflight_check.py:36`, `strategies/heartbeat.py:43` | same parse | paper | runtime | backend | no | selects URL / status label | no | — | live |
| `ALPACA_IS_PAPER` | `alpaca-flatten.ts:28` | `=== 'true'` | **unset ⇒ LIVE** | runtime | backend (Netlify) | no | **yes (flatten target)** | no | — | live |
| `ALPACA_BASE_URL` | `config.py:70`, `options_executor.py:142`, `alpaca-orders/positions/account.ts` | `os.getenv(...,"paper-api…")` | paper | runtime | both | no | **yes (REST/options)** | no | — | live |
| `TRADING_MODE` | `Dockerfile:22` + backtest scripts | `ENV TRADING_MODE=paper`; scripts check `=="research"` | paper | build/runtime | backend | no | **no** (research-data flag only) | no | — | live (unrelated to broker) |

**Boolean-parsing safety:**
- Python path uses `os.getenv("ALPACA_IS_PAPER","true").lower() == "true"` **everywhere** —
  **safe** (no `bool("false")===true` bug), defaults to paper. Any non-`true` value (e.g.
  `"1"`, `"yes"`) is treated as **live** — a minor footgun but explicit.
- Netlify `alpaca-flatten.ts:28` uses `=== 'true'` with **default-live semantics**: unset ⇒
  `false` ⇒ live. This is the dangerous parse — it fails to live, opposite of the Python default.

**Conclusion:**
```
The actual paper/live mode is controlled by:
  ALPACA_IS_PAPER (Lumibot broker, portfolio client, Netlify flatten) and
  ALPACA_BASE_URL (options-order REST path) — environment variables read at process start.

The Settings Console does NOT control it because:
  the toggle only mutates local React state; there is no save endpoint, no persistence,
  and the Python bot never reads Supabase for mode. The mode badge reads a Supabase row
  (user_settings.paper_mode) that no code ever writes, and which RLS blocks the anon
  browser from reading anyway.
```

---

## 15. Alpaca Credential Management

| Credential | UI Field | Backend Field | Storage | Runtime Variable | Runtime Consumer | Separate by Mode | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Paper API key | `alpacaKey` `SettingsView.tsx:429` (not persisted) | `process.env.ALPACA_API_KEY` | **env only** | `ALPACA_API_KEY` | Lumibot/REST/Netlify | **No** — one pair for both modes | BROKEN (UI cannot save) |
| Paper secret | `alpacaSecret` `:430` (not persisted) | `process.env.ALPACA_API_SECRET` | env only | `ALPACA_API_SECRET` | same | No | BROKEN |
| Live API key | (same field) | (same env) | env only | `ALPACA_API_KEY` | same | **No — reused** | MISSING separation |
| Live secret | (same field) | (same env) | env only | `ALPACA_API_SECRET` | same | No — reused | MISSING separation |

Details:
- **Masked** in UI via `MaskedInput` (`:215-238`), with eye-toggle reveal. Fields start blank.
- **Not sent to the frontend** — the backend never returns Alpaca secrets to the browser.
  (`alpaca-account` echoes only Alpaca's account JSON.)
- **Full secret IS sent from the browser to `alpaca-account`** on Test Connection
  (`:348-352`), and `alpaca-account` will relay **any** body-supplied creds to Alpaca without
  auth (`alpaca-account.ts:26`) — an open proxy, though it only leaks what the caller already
  typed.
- **No separate paper/live credential sets.** One `ALPACA_API_KEY`/`ALPACA_API_SECRET` pair is
  used for whichever endpoint is selected → switching to live reuses the same keys against the
  live host (only works if those keys are live keys; otherwise fails — no isolation guarantee).
- **Test Connection exists** (`:442`), but **no pre-save credential validation** (there is no
  save).
- **Not encrypted at rest** concern is N/A for Alpaca (env only), but the **Telegram token is
  plaintext** in Supabase.
- **Admin API key is exposed to the browser**: `VITE_ADMIN_API_KEY` is compiled into the
  client bundle (`useAlpacaAccount.ts:32,47,61`, `SettingsView.tsx:341`) and mirrored to
  `localStorage['ADMIN_API_KEY']` (`App.tsx`) — anyone with the deployed JS can read it, which
  undermines the admin gate on every Netlify function.

Example masking format used in this report: `PK**************7A` (no full credential is printed).

---

## 16. Alpaca Client Initialization

| Site | File:line | SDK | Key/secret | Base URL / paper source | Lifetime |
| --- | --- | --- | --- | --- | --- |
| Lumibot broker (equities) | `main.py:60` | `lumibot.brokers.Alpaca` | `ALPACA_CONFIG` env | `ALPACA_CONFIG["PAPER"]` (`config.py:64`) | once at worker start (singleton for session) |
| Lumibot broker (crypto) | `main_crypto.py:47`, `run_crypto_bot.py:65` | Lumibot Alpaca | env | `ALPACA_CONFIG["PAPER"]` | once at start |
| Options order REST | `strategies/options_executor.py:130-142` | raw REST | env headers | `ALPACA_BASE_URL` | per call |
| Portfolio snapshot | `adapters/supabase_logger.py:353-363` | alpaca-py `TradingClient` | env | `ALPACA_IS_PAPER` | per snapshot |
| Data stream | `adapters/alpaca_streamer.py:28` | alpaca-py `StockDataStream` | env | data feed (no paper flag) | per stream |
| Legacy REST | `run_agents.py:204-213` | `alpaca_trade_api` | env | `ALPACA_BASE_URL` | per query |
| Netlify account/orders/positions/flatten | `alpaca-*.ts` | fetch/axios | env (+ body for account) | `ALPACA_BASE_URL` (or `ALPACA_IS_PAPER` for flatten) | per request |

**Recreation after a settings change:** none. The Lumibot broker is built once at process
start from env; there is no client rebuild, singleton invalidation, or worker restart wired to
any settings change. A mode change is only effective after an **env edit + process restart**.

---

## 17. Running Bot Configuration

Entry points: `main.py` (equities, Lumibot), `main_crypto.py` / `run_crypto_bot.py` (crypto),
plus agents/collectors run via `run_*.py`, orchestrated by PM2 (`ecosystem.config.js`) or
Docker (`Dockerfile` CMD `python main.py`; `docker-compose.yml` `env_file: .env`).

Config loader: `config.py` (`load_dotenv()` at `:8`), validated by `config_validator.py`
(called at `main.py:38-40`).

Trace of settings into runtime:

| Setting | Runtime source | Loaded | Consumed by |
| --- | --- | --- | --- |
| Paper/live mode | `ALPACA_IS_PAPER` / `ALPACA_BASE_URL` env | once at start | broker + options REST |
| API key / secret | `ALPACA_API_KEY/SECRET` env | once | all clients |
| Endpoint | env | once | clients |
| Max daily loss | `config.py:37` `MAX_DAILY_LOSS` env (or `runtime_config.json`) | start + `reload()` | risk logic |
| Max position / trades | `config.py:38-39` env | start | risk logic |
| Options expiration/strike | `config.py:78-82` via `_get()` (`runtime_config.json` → env → default) | start + `reload()` | options executor |
| Kill / shutdown | `bot_status.target_status` Supabase | polled by heartbeat every interval | `strategies/heartbeat.py:126-134` (process exit) |

**How the bot learns a setting changed:** for mode/creds/limits — it does **not** (env is
static; `runtime_config.json` has no writer). For remote shutdown — the heartbeat thread polls
`bot_status.target_status` and exits on `"shutdown"` (`heartbeat.py:93-107,126-134`). **This is
the only live control channel from the dashboard to the bot,** and it is triggered by
`alpaca-flatten` (`setBotTargetStatus('shutdown')`, `alpaca-flatten.ts:56`).

**Fail-closed?** Partially. `config_validator.py` `sys.exit(1)` on missing creds/keys and on
`PAPER=false && base_url contains paper-api` (`:32-36`). But `PAPER=true && base_url = live`
is only a **warning that claims to "fix" but does not** (`:37-41`) — options REST would then
route live while Lumibot is paper. Not fully fail-closed.

**Is the active config visible / acknowledged?** The bot writes heartbeat/status to Supabase,
and `health_server.py` echoes `paper_mode`. But there is **no proof-of-consumption** surface:
the dashboard cannot show that the worker acknowledged a settings change (because it never
sends one).

---

## 18. Runtime Synchronization

- **No settings-change event bus, pub/sub, realtime channel, or queue** connects the Settings
  Console to the bot for mode/credentials/limits.
- The only sync is one-directional emergency shutdown via `bot_status.target_status` polling.
- `config.reload()` exists (`config.py:44-57`) to re-read `runtime_config.json`, but **nothing
  writes that file and nothing calls `reload()` on a settings change** (only options/risk keys
  would flow through it anyway).
- **Stale-config risk is total** for mode/creds/limits: the bot runs on whatever env it started
  with until manually restarted. The UI cannot detect or display this drift.

---

## 19. Safety-Control Inventory

| Control | Status |
| --- | --- |
| Explicit paper/live selector | **Present but BROKEN/decorative** (`SettingsView.tsx:476`) |
| Separate paper & live credentials | **MISSING** (one env pair reused) |
| Live-mode warning banner | Present (`:529-548`) — but tied to non-persisted local toggle |
| Typed live-mode confirmation | **MISSING** (only a `window.confirm`, `:478-485`) |
| Second confirmation step | Partial `window.confirm` on toggle and on live test |
| Role-based live permission | **MISSING** |
| Active Alpaca endpoint display | Display-only (readonly base URL, from local toggle, not runtime) |
| Active account display | Present only after Test Connection (`:504-519`) |
| Test Connection button | **Present & working** (test only) |
| Last successful connection | Present via `localStorage['alpaca_last_verified']` (`:273,369`) — local, not authoritative |
| Credential rotation | **MISSING** |
| Global kill switch | **Two:** (a) RiskManager `trading_enabled` toggle — **BROKEN** (wrong schema, not consumed); (b) flatten→`bot_status` shutdown — **WORKING** but live-default + fail-open |
| Disable-all-trading | Via (b) shutdown only |
| Cancel-open-orders | `alpaca-flatten` — **WORKING but dangerous** |
| Close-all-positions | `alpaca-flatten` — **WORKING but dangerous** |
| Max order notional | **MISSING** in UI (bot has `MAX_POSITION_SIZE` env) |
| Max position size | Env `MAX_POSITION_SIZE`; RiskManager UI write **BROKEN** |
| Max daily loss | Env `MAX_DAILY_LOSS` + `ABSOLUTE_DAILY_LOSS_LIMIT=5000` floor; RiskManager UI write **BROKEN** |
| Max drawdown | `risk_config` table (UNVERIFIED consumption) |
| Max trades/day | Env `MAX_TRADES_PER_DAY` |
| Symbol allow/blocklist | **MISSING** |
| Trading-hours / extended-hours | **MISSING** in Settings |
| Short / options / crypto toggles | **MISSING** in Settings |
| Strategy/agent enable-disable | **MISSING** in Settings |
| Signal-only / dry-run / human-approval | HITL queue exists in agents; not surfaced in Settings — **UNVERIFIED** |
| Settings audit history / last-modified-by | **MISSING** |
| Worker sync status / restart-required indicator | **MISSING** |
| Config version / rollback | **MISSING** |
| Production banner / runtime health | Health views exist elsewhere; Settings has none |

---

## 20. Automated Test Results

**Frontend (`dashboard/`, vitest):** only two tests exist — `OverviewView.test.tsx`,
`CryptoView.test.tsx`. **No test covers** `SettingsView`, `useTradingMode`, paper/live,
credential handling, or persistence. (Not executed here — no deps installed; would need
`npm install && npm test`. Marked UNVERIFIED for pass/fail.)

**Backend/Netlify:** no tests for `alpaca-*` functions or `options-config`.

**Python:** `tests/test_ic_direction.py`, `test_ut_bot_freshness.py`, `test_tools.py` — none
cover paper/live selection, credential isolation, or the kill switch. `preflight_check.py` and
`config_validator.py` provide startup guards but are not unit-tested for the divergent-mode
cases.

**Coverage gaps (critical):** no test asserts that (a) the UI selector reaches runtime, (b)
paper vs live selects the correct client, (c) blank secrets don't overwrite, (d) flatten
cannot target live without confirmation, (e) UI mode == runtime mode.

No test uses live credentials or hits live endpoints in the reviewed files.

---

## 21. Complete Settings Status Matrix

| Category | Setting | UI | Editable | Loads | Save Req | Persists | Survives Refresh | Runtime Uses | Restart Req | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Broker | Alpaca API key | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | env only | — | **BROKEN** | `SettingsView.tsx:429,244` |
| Broker | Alpaca secret | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | env only | — | **BROKEN** | `:430,245` |
| Broker | Base URL | ✓ | ✗ | derived | ✗ | ✗ | ✗ | env only | — | **DISPLAY-ONLY** | `:434-439` |
| Broker | **Paper/Live mode** | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | **✗ (env)** | yes | **BROKEN/decorative** | `:246,476-488` |
| Broker | Mode badge | ✓ | — | ✗(unwritten) | — | — | — | — | — | **BROKEN (always ...)** | `useTradingMode.ts:36-40` |
| Broker | Test Connection | ✓ | — | — | POST | — | — | Alpaca | — | **WORKING (test)** | `:342` |
| Database | Endpoint | ✓ | ✗ | hard-coded | ✗ | ✗ | ✗ | none | — | **DISPLAY-ONLY** | `:582` |
| Database | Token | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | none | — | **DISPLAY-ONLY** | `:584` |
| Database | Test Connection | ✓ | — | — | select | — | — | Supabase | — | **WORKING (test)** | `:306` |
| Notifications | Telegram token/chat | ✓ | ✓ | ✓* | upsert | ✗† | ✗† | env (`telegram_bot.py`) | — | **BROKEN** | `:279-298` |
| Notifications | Email/Push toggles | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | none | — | **DISPLAY-ONLY** | `:680-687` |
| Notifications | Quiet hours | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | none | — | **DISPLAY-ONLY** | `:689-696` |
| Strategy | Symbol/TF/ATR/Sens | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | none | — | **DISPLAY-ONLY** | `:713-734` |
| Strategy | Auto-start | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | none | — | **DISPLAY-ONLY** | `:736-739` |
| Strategy | **Save Defaults** | ✓ | — | — | **none** | ✗ | ✗ | none | — | **BROKEN (no-op)** | `:740-742` |
| Options | Expiration/strike | ✗(orphan) | ✓ | ✓ | POST‡ | dup-row‡ | — | runtime_config (unwritten) | — | **BROKEN** | `ContractConfigSection.tsx`, `options-config.ts:132` |
| Risk | Kill switch `trading_enabled` | ✓(/risk) | ✓ | err | upsert | ✗(bad schema) | ✗ | ✗ | — | **BROKEN** | `RiskManagerView.tsx:61-83` |
| Risk | Max daily loss / pos % | ✓(/risk) | ✓ | err | upsert | ✗(bad schema) | ✗ | env only | — | **BROKEN** | `RiskManagerView.tsx:74-89` |
| Safety | Emergency flatten | ✓ | — | — | POST | — | — | Alpaca + `bot_status` | — | **WORKING but UNSAFE** | `alpaca-flatten.ts` |

\* Load works only if signed-in `authenticated` (RLS). † Write hits non-unique `key` +
RLS-blocked for anon → duplicate rows or silent failure. ‡ Endpoint exists but no UI caller.

**Category summary:**

| Category | Status | Working | Broken | Missing | Safety Impact | Required Fix |
| --- | --- | --- | --- | --- | --- | --- |
| Trading mode | **BROKEN** | test only | selector, badge | live confirm, persistence | **Critical** — UI≠runtime | Make selector authoritative + worker sync, or make it read-only truth |
| Paper creds | BROKEN | — | save path | separation | High | Env-only is OK; add validation + separation |
| Live creds | MISSING | — | — | separate keys | High | Separate live key set + gating |
| Connection status | Partial | test | last-verified auth | live/last-fail history | Medium | Server-side status |
| Broker account data | Working | on test | — | persistent display | Low | — |
| Trading enablement | BROKEN | — | kill toggle | consumption | High | Wire kill switch to bot |
| Strategy settings | DISPLAY-ONLY | — | Save no-op | persistence | Medium | Add save + consumption |
| Agent settings | MISSING | — | — | all | Medium | Add |
| Risk settings | BROKEN | — | schema mismatch | UI→bot path | High | Fix schema + consumption |
| Order settings | MISSING | — | — | max notional etc. | High | Add |
| Market-data settings | Partial | env | — | UI | Low | — |
| Notification settings | BROKEN | test | telegram save | email/push wiring | Medium | Fix persistence |
| Runtime settings | MISSING | — | runtime_config unwritten | writer + reload | High | Add writer + reload trigger |
| Security settings | BROKEN | — | fail-open auth, browser admin key | RLS/anon, encryption | **Critical** | Fail-closed + server secrets |
| General app settings | DISPLAY-ONLY | — | — | persistence | Low | — |

---

## 22. Product Performance Scores

**Counts** (visible Settings-Console controls + directly related settings):
- Total visible settings/controls: **~24**
- Fully working (renders→loads→saves→persists→runtime→behavior): **0**
- Working as *test-only* actions (not persisted settings): 4 (Alpaca test, DB test, Telegram test, flatten)
- Broken: **9** (key, secret, paper toggle, badge, telegram save, Save Defaults no-op, kill switch, risk limits, options config)
- Display-only: **11**
- Missing required: separate live creds, live confirmation, worker sync, order caps, audit history (**5+**)
- Unverified: risk_config consumption, live browser persistence, test-suite pass/fail
- % fully functional: **0%**
- % that persist to intended storage: **~4%** (only options_config path writes, and it duplicates rows + is orphaned)
- % reaching runtime: **0%** (no Settings-Console value reaches the bot)
- Conflicting sources of truth for mode: **4** (UI toggle, Supabase badge, `ALPACA_IS_PAPER`, `ALPACA_BASE_URL`)
- Silent failures: **≥5** (telegram RLS, risk schema, paper toggle, Save Defaults, options save duplicates)
- Safety-critical findings: **6** (see §24)

| Dimension | Score | Rationale |
| --- | --- | --- |
| **Functional Completeness** | **12 / 100** | UI is complete visually, but 0 settings save+load+reach runtime. Only test buttons work. |
| **Reliability** | **10 / 100** | No persistence for most fields; duplicate-row upserts; RLS-blocked anon writes; env-only + no reload = total staleness; 4 unsynced sources of truth. |
| **Trading Safety** | **8 / 100** | Decorative paper/live selector; no credential isolation; flatten fails to live + fails open; kill switch broken; only partial fail-closed. |
| **Security** | **18 / 100** | Admin key shipped to browser; fail-open auth; open cred proxy; plaintext telegram token; trivially-bypassable ingest auth. RLS + env-only Alpaca creds are the few positives. |
| **Observability** | **20 / 100** | Heartbeat/status to Supabase and health echo exist, but no settings-change acknowledgement, no worker-sync display, no audit history, no last-modified-by. |
| **User Experience** | **35 / 100** | Clean layout, masking, confirm dialogs, warning banners. Undermined by no-op Save, non-persisting fields, and a badge stuck on "...". |

---

## 23. Product Performance Scores — (see §22)

_(Merged into §22 above per the scoring rubric.)_

---

## 24. Security and Trading-Safety Risks (Defects)

| ID | Title | Sev | Category | File:line | Root cause | Fix |
| --- | --- | --- | --- | --- | --- | --- |
| DA-01 | Paper/Live selector is decorative — UI can disagree with runtime | **Critical** | safety/runtime | `SettingsView.tsx:246,476-488`; `config.py:64` | Toggle = local state; bot reads env only; no persistence/sync | Persist mode to a single authoritative store the worker reads; show worker-acknowledged mode; hard-block on divergence |
| DA-02 | `alpaca-flatten` defaults to LIVE + fails open on auth | **Critical** | security/safety | `alpaca-flatten.ts:22,28-31,48,52` | `ALPACA_IS_PAPER === 'true'` unset⇒live; `adminKey !== env` passes when env unset | Default to paper; require explicit mode; fail closed (reject if `ADMIN_API_KEY` unset); require typed confirmation |
| DA-03 | `alpaca-account` open credential/base-URL proxy | **High** | security | `alpaca-account.ts:10-28` | Auth bypassed when body carries creds | Require auth regardless; whitelist base URLs; never accept arbitrary baseUrl |
| DA-04 | Admin API key shipped to browser bundle + localStorage | **High** | security | `useAlpacaAccount.ts:32`, `SettingsView.tsx:341`, `App.tsx` | `VITE_ADMIN_API_KEY` compiled client-side | Move privileged calls behind server session; never expose admin key to client |
| DA-05 | Two env mode-switches can diverge; validator only warns one way | **High** | safety | `config_validator.py:32-41`; `options_executor.py:142` | `ALPACA_IS_PAPER` (Lumibot) vs `ALPACA_BASE_URL` (options) independent; paper+liveURL not blocked | Single derived source; hard-fail both divergence directions |
| DA-06 | Fail-open admin auth across `alpaca-*` when `ADMIN_API_KEY` unset | **High** | security | `lib/auth.ts:12-13`, `alpaca-orders.ts:5-9` | "default authorized for local dev" | Fail closed in production; require the env var |
| DA-07 | `user_settings.key` not unique → upserts duplicate rows | High | database | `schema_current_state.sql:245-253` | Missing unique constraint / `onConflict` | Add `UNIQUE(key)`; pass `onConflict:'key'` |
| DA-08 | RLS blocks anon browser writes → Settings silently fail | High | database/UX | `20260710000000_supabase_audit_remediation.sql:21-47`; `supabaseClient.ts:3-11` | Anon key + authenticated-only policies | Route writes through authenticated session or server function; surface failures |
| DA-09 | RiskManager kill switch/limits write non-existent columns | High | safety/database | `RiskManagerView.tsx:36-83` | Uses `id=1` + `trading_enabled/max_*` columns absent from live schema | Fix to `(key,value)` model; wire `trading_enabled` into bot |
| DA-10 | Kill switch not consumed by bot | High | safety | `RiskManagerView.tsx`; no Python reader | Bot never reads `trading_enabled` | Have bot poll a control row (like `bot_status.target_status`) and halt |
| DA-11 | `paper_mode` badge never written → permanently "unknown" | Medium | UX/safety | `useTradingMode.ts:36-40`; no writer | No producer + RLS | Write mode server-side; badge from worker-acknowledged state |
| DA-12 | `runtime_config.json` read but never written | Medium | runtime | `config.py:11-32` | No producer | Add writer + `reload()` trigger, or remove the dead path |
| DA-13 | Telegram bot token stored plaintext in Supabase | Medium | security | `SettingsView.tsx:296-297` | No encryption | Store server-side/secret manager; restrict RLS |
| DA-14 | `ingest-bars` auth bypass via `User-Agent: Netlify` | Medium | security | `ingest-bars.ts:30` | UA-string trust | Use signed/service auth, not UA |
| DA-15 | "Save Defaults" button is a no-op | Medium | UX | `SettingsView.tsx:740-742` | No handler | Implement save + consumption, or remove |
| DA-16 | Orphaned options-config UI + endpoint | Low | dead code | `ContractConfigSection.tsx`; `options-config.ts` | Never wired | Wire into Settings or remove |
| DA-17 | Non-`true` `ALPACA_IS_PAPER` values silently mean live (Python) | Low | safety | `config.py:64` | strict `=="true"` | Validate allowed values; reject ambiguous input |

---

## 25. Prioritized Remediation Plan

### Priority 0 — Stop-Ship (must fix before any live trading)
| Issue | Change | Files |
| --- | --- | --- |
| DA-02 | `alpaca-flatten`: default paper, fail closed on missing `ADMIN_API_KEY`, require typed "LIVE" confirmation token | `alpaca-flatten.ts` |
| DA-01 | Establish a single authoritative trading-mode store the worker reads; make the UI selector write it and display worker-acknowledged mode; refuse to render "Paper" unless the worker confirms paper | `SettingsView.tsx`, new control table + Python reader |
| DA-03 | Remove body-cred auth bypass; require auth; whitelist base URLs | `alpaca-account.ts` |
| DA-04 | Stop shipping the admin key to the browser; move privileged calls server-side | frontend hooks, `App.tsx` |
| DA-05 | Derive `ALPACA_BASE_URL` from a single mode flag; hard-fail on any paper/live divergence | `config.py`, `config_validator.py`, `options_executor.py` |
| DA-06 | Fail closed when `ADMIN_API_KEY` is unset in production | `lib/auth.ts`, all `alpaca-*` |

### Priority 1 — Core Functionality
| Issue | Change | Files |
| --- | --- | --- |
| DA-07 | Add `UNIQUE(key)` + `onConflict:'key'` | migration, `SettingsView.tsx`, `AlertsView.tsx`, `options-config.ts` |
| DA-08 | Route settings writes through an authenticated session or server function; surface errors | frontend + Netlify |
| DA-09/DA-10 | Fix RiskManager to `(key,value)`; wire `trading_enabled` kill switch into the bot's poll loop | `RiskManagerView.tsx`, `strategies/heartbeat.py` |
| DA-15 | Implement or remove "Save Defaults" | `SettingsView.tsx` |
| DA-12 | Add a writer + `reload()` trigger for `runtime_config.json`, or delete the dead path | `config.py`, new sync |

### Priority 2 — Reliability & Observability
| Issue | Change |
| --- | --- |
| DA-11 | Server-side mode writer; badge from worker-acknowledged state |
| DA-13 | Move Telegram token to a secret store; tighten RLS |
| — | Add worker-sync / restart-required indicators; settings audit history (last-modified-by/at); connection-history persistence |

### Priority 3 — UX
| Issue | Change |
| --- | --- |
| DA-16 | Wire or delete orphaned options UI |
| DA-17 | Validate allowed `ALPACA_IS_PAPER` values |
| — | Clarify which fields persist vs are test-only; add "restart required" banner on mode change |

---

## 26. Recommended Automated Tests

**Frontend:** every Settings field renders; saved Telegram value loads; Save invokes the
correct mutation with expected payload; secret fields never expose stored secrets; blank
secret preserves stored value; success only after confirmed persistence; live-mode requires
typed confirmation; badge reflects worker-acknowledged mode.

**Backend:** unauthorized caller cannot change broker settings; `alpaca-flatten` rejects when
`ADMIN_API_KEY` unset; `alpaca-account` requires auth even with body creds; base URL is
whitelisted; unknown payload fields rejected; audit record created.

**Integration:** UI Save writes expected row (single, no duplicates); refresh reloads it;
worker receives updated config; paper mode selects paper client and paper creds; live mode
selects live; runtime and UI cannot diverge silently; env-var precedence explicit.

**Safety:** missing/invalid creds disable trading; inconsistent mode+creds fail closed; kill
switch blocks order submission; live endpoint unusable without confirmation; UI cannot show
Paper while runtime is Live; settings update requires worker acknowledgement; failed sync
raises a visible alert.

---

## 27. Final Production-Readiness Verdict

The Settings Console does not control the live trading environment, cannot be trusted to
reflect it, and contains multiple fail-to-live / fail-open safety defects. Paper/live mode is
env-driven and static; the UI selector is decorative; the emergency flatten can hit a live
account without authentication under a plausible misconfiguration. Persistence is broken at
the schema and RLS levels, and no Settings-Console value reaches the running bot.

The Python bot **defaults to paper** (`ALPACA_IS_PAPER` unset ⇒ paper) and has a startup
validator, so a correctly-configured deployment *can* run paper safely at the bot level — but
the **console cannot be relied on to prove or change that**, and the Netlify flatten path
defaults the opposite way.

---

## Phase 24 — Final Questions (answered plainly)

1. **Is the Settings Console currently functional?** No — as a control surface it is largely non-functional; only Test buttons work.
2. **How many visible settings fully work?** **0** (end-to-end: load→save→persist→runtime→behavior).
3. **How many are broken?** ~9 (key, secret, paper toggle, badge, telegram save, Save-Defaults no-op, kill switch, risk limits, options config).
4. **How many are display-only?** ~11.
5. **How many required settings are missing?** ≥5 (separate live creds, live confirmation, worker sync, order caps, audit history).
6. **Do settings save successfully?** Almost none. Telegram/alerts/options writes hit a non-unique `key` (duplicate rows) and are RLS-blocked for the anon browser; most fields have no save path.
7. **Do settings reload after refresh?** Only Telegram (and only if signed-in `authenticated`). Everything else resets to defaults.
8. **Do settings reach the running trading bot?** No. The bot reads env (and an unwritten `runtime_config.json`); it never reads `user_settings`.
9. **Actual source of truth for paper/live?** Env vars — `ALPACA_IS_PAPER` (Lumibot broker, portfolio client, flatten) and `ALPACA_BASE_URL` (options REST), read once at process start.
10. **Does the UI selector control that source of truth?** No.
11. **Does Paper→Live change the Alpaca endpoint?** No (only the readonly display + the test call).
12. **Does it change the credential set?** No — one env pair is reused.
13. **Does it require a worker restart?** Yes — mode changes require an env edit + restart.
14. **Does `ALPACA_IS_PAPER` override the UI?** It is authoritative for the bot; the UI never competes with it. The UI badge's `user_settings.paper_mode` is independent and unwritten.
15. **Are paper and live API keys managed separately?** No.
16. **Are Alpaca secrets stored securely?** They are in env vars only (not in Supabase) — acceptable — but the admin key is shipped to the browser and the Telegram token is plaintext.
17. **Can the frontend retrieve full Alpaca secrets?** No — the backend never returns them. (It will relay body-supplied creds to Alpaca, but that only echoes what the caller typed.)
18. **Can the UI show Paper while the bot trades Live?** **Yes.**
19. **Can the UI show Live while the bot stays Paper?** **Yes.**
20. **Could the system accidentally submit a live order?** The dashboard has no order-placement endpoint, so not from the console. The **bot** submits live orders whenever `ALPACA_IS_PAPER`/`ALPACA_BASE_URL` point live — and `alpaca-flatten` can place live cancels/liquidations under misconfig. So: **yes, via env misconfiguration or the flatten path.**
21. **Is there a functioning kill switch?** Partially — the flatten→`bot_status.target_status='shutdown'` path works (but is unsafe/fail-open); the RiskManager `trading_enabled` toggle is broken and not consumed.
22. **Does the bot fail closed when config is invalid?** Partially — it `sys.exit(1)` on missing creds and on `PAPER=false`+paperURL, but only warns on `PAPER=true`+liveURL, so options can route live silently.
23. **Five most urgent fixes:** (1) make `alpaca-flatten` default paper + fail closed [DA-02]; (2) make the paper/live selector authoritative + worker-acknowledged [DA-01]; (3) close the `alpaca-account` proxy and fail-open auth [DA-03/DA-06]; (4) stop shipping the admin key to the browser [DA-04]; (5) unify the two env mode-switches and hard-fail divergence [DA-05].
24. **Is the system safe for paper trading?** At the bot level, with a correct env (`ALPACA_IS_PAPER=true`, paper `ALPACA_BASE_URL`), yes — but the console can neither prove nor guarantee it, and the flatten path defaults live. Safe **only** with disciplined env management and the security fixes.
25. **Is the system safe for live trading?** No.

---

## Phase 25 — Final Verdict

```
NOT READY FOR TRADING
```

The UI paper/live selector is **not** the runtime source of truth — `ALPACA_IS_PAPER` and a
hard-coded/env `ALPACA_BASE_URL` are. The UI can disagree with the running trading environment
(a critical stop-ship condition), settings persist nowhere the bot consumes, and the emergency
flatten path defaults to the live account with fail-open authentication. These must be
remediated (§25 Priority 0) before even paper deployment can be trusted through this console.
