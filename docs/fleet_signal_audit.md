# Live Fleet Signal Audit

**Date:** 2026-07-15
**Branch:** `audit/fleet-signal-dependencies`
**Mode:** READ-ONLY. No agent code, config, or schedule was modified.
**Question:** How much of the running fleet depends on what `docs/hmm_signal_diagnosis.md` just falsified?

---

## Executive summary

The literal answer to the audit question is **less than feared** — and that is the least
reassuring finding in this document.

The falsified components (UT Bot daily signal, HMM regime map) turn out to be **largely
disconnected from the code that actually places orders**. The regime map drives a proposed size
that no automated order reads. The orchestrator's entire risk pipeline — debate, Kelly, VaR,
HITL — runs in a different process from the trading bots and cannot stop a trade. So the
anti-predictive HMM is not sizing live positions.

But the same tracing that produced that good news produced this: **the live SPY bot trades
parameters that have never been backtested, using a signal implementation that no backtest
tests, with no human approval gate, and a decay monitor that is structurally incapable of ever
flagging it.** The fleet is not exposed to the falsified research because the fleet is barely
connected to the research at all.

Three findings are ranked CRITICAL below. The most urgent is not the HMM.

**A note on what "edgeless" covers.** The diagnosis proved a 2-branch EWM-ATR signal at
`10 / 1.0` is edgeless. Production runs a **4-branch SMA-ATR signal at `14 / 3.0`** (§1.2).
That is not the same signal at the same parameters. This audit therefore does **not** conclude
the live signal is edgeless — it concludes the live signal is **unmeasured**. That is a
different, and arguably worse, position to be in.

---

## 1. Signal inventory

### 1.1 Signals that can move money

Only two files place orders. Everything else in the fleet is advisory.

| Signal | Producer | Symbol | Timeframe | Logic |
|---|---|---|---|---|
| UT Bot ATR crossover | `strategies/ut_bot.py:126-164` | SPY | Daily bars, 1-min poll (`ut_bot.py:67`) | SMA-ATR trailing stop, **4-branch**; `+1` on close crossing above stop, `-1` below. Buys CALL/PUT (`ut_bot.py:256`) |
| UT Bot exits | `ut_bot.py:271-294` | SPY | same | RSI step-back ≥5.0, 0.5% adverse move, EOD flatten 15:55 ET (`ut_bot.py:96-101`) |
| ADX trend regime | `strategies/adaptive_trend_mr_eth.py:94-97,157-181` | ETH/USD | 15m | ADX>25 → EMA 9/21 cross + DI confirm; ATR 2.5x trail |
| Bollinger mean-reversion | `adaptive_trend_mr_eth.py:183-204` | ETH/USD | 15m | ADX≤25 → BB(20,2) touch + RSI<30/>70 |

Running processes (verified via `ps` + `systemctl`; unit files at `/etc/systemd/system/da-*.service`
are **host-only, not in this repo**):

| Unit | ExecStart | PID | Places orders? |
|---|---|---|---|
| `da-trading-bot.service` | `main.py` | 10774 | **Yes** — SPY options |
| `da-crypto-bot.service` | `run_crypto_bot.py` | 10773 | **Yes** — ETH/USD |
| `da-agents.service` | `run_agents.py` | 10772 | **No** — advisory only |

### 1.2 CRITICAL: the live signal is not the backtested signal, at two independent levels

**Level 1 — parameters.** `main.py:63-66` constructs the strategy with an explicit override:

```python
strategy = UTBotStrategy(
    broker=broker,
    parameters={
        "atr_period": 14,
        "sensitivity": 3.0,
    }
)
```

Every other source of truth in the repo says `10 / 1.0`:

- `strategies/ut_bot.py:54-55` — class default `atr_period: 10`, `sensitivity: 1.0`, each annotated `# per spec`
- `strategies/ut_bot.py:11` — the file's own constraint block: `ATR_PERIOD=10, ATR_MULT=1.0`
- `backtests/config.py:34-35` — `UT_ATR_PERIOD=10`, `UT_SENSITIVITY=1.0`

A sensitivity of 3.0 versus 1.0 is a **3× wider trailing stop**. That is not a tuning nuance; it
is a materially different strategy with a different trade count, hold time, and turnover profile.
Note that `ut_bot.py:11` declares the signal "OFF-LIMITS for edits" — the parameters were then
overridden from the outside, leaving the constraint technically intact and practically void.

**Level 2 — implementation.** There are **five** definitions of `calculate_ut_signals`, and the
live bot uses none of them:

| Definition | ATR | Branches |
|---|---|---|
| `scripts/backtest_utbot.py:36` | EWM | 2 |
| `scripts/backtest_questdb_spot.py:56` | EWM | 2 |
| `scripts/backtest_regime.py:24` | EWM | 2 |
| `scripts/backtest_hmm_switching.py:204` | EWM | 2 |
| `backtests/signal.py:109` | EWM | 2 (verbatim copy of `backtest_utbot.py`, test-only) |

Live is a **sixth, inlined implementation** at `strategies/ut_bot.py:126-164` — SMA ATR,
4-branch. The only faithful 4-branch reproduction is `backtests/signal.py:28`
`compute_ut_signal`, used solely by `backtests/engine.py:89`; `backtests/signal.py:9-16`
documents the split explicitly.

**Why this matters for the research programme.** `scripts/diagnose_hmm_signal.py:450-452` notes
the 2-branch version "is missing the RESET branch… clamps to the stale prior stop," and
`:466-477` records this as a **deliberately accepted deviation, decision dated 2026-07-15**, on
the grounds that the correct 4-branch version backtests *worse*. But 4-branch is what production
runs. The accepted-deviation rationale therefore argues for keeping a backtest that does not
match live — the deviation was accepted in the wrong direction. **The edgeless-signal finding
is a finding about a signal that does not trade.**

### 1.3 Advisory-only signals (feed Telegram/Supabase; never an order)

HMM regime (`regime_detector.py:15-29`), sentiment fusion (`signal_agent.py:113-159`), sentiment
velocity (`sentiment_velocity.py:10`), "TimesFM" forecast (`timesfm_forecaster.py:201-210`),
Kronos (`orchestrator.py:898,968`), GEX (`gex_calculator.py:63`), 200-day MA
(`ma_regime_filter.py`), PEAD (`pead_signal.py`), bull/bear/judge debate
(`orchestrator.py:344-371`), session filter (`session_filter.py`), macro filter
(`macro_filter.py:52`), soft daily stop (`orchestrator.py:79-119`), VaR
(`var_risk_engine.py:10`), greeks circuit breaker (`greeks_risk_engine.py`).

Two of these deserve flagging on truth-in-labelling grounds:

- **`timesfm_forecaster.py` does not run TimesFM.** `_load_model` (`:25`) is never called;
  `forecast()` hardcodes `method_used = 'linear_regression'` (`:201`) and does `np.polyfit(x, closes, 1)`
  (`:208`) — a straight line through ≤512 daily closes, extrapolated 12 bars, with `confidence`
  hardcoded 0.5. Downstream labelling is honest (`signal_agent.py:206` says "Linear Baseline"),
  but the module name, `TIMESFM_MODEL = 'google/timesfm-1.0-200m'` (`:16`), and the
  `timesfm_forecast`/`timesfm_pct` columns written to Supabase (`orchestrator.py:792-793`) all
  imply a foundation model. Consequently the Kronos-vs-TimesFM "agreement" metric in the Telegram
  report (`orchestrator.py:1116-1129`) is Kronos versus a trendline.
- **`pairs_trader.py:18`** (cointegration on SPY/QQQ, SPY/IWM) is not imported by the
  orchestrator. Its only consumer is `scripts/run_pairs_analysis.py:9`, which is in no cron and no
  systemd unit. **Dead code / manual-only.**

### 1.4 The crypto bot's signals never reach the agent fleet

The only path from a strategy to the fleet is `signal_log`: `ut_bot.py:194` → `db.log_signal`
(`adapters/supabase_logger.py:155`) → `signal_agent.py:50` reads the last 5 rows.
`adaptive_trend_mr_eth.py` **never calls `log_signal`**. So `signal_agent.py:47-48`'s crypto
filter (`symbol like.%USD%`) returns nothing → `buy_sig=sell_sig=False` (`:61-63`) → the crypto
SignalAgent's `technical_signal` is permanently `"NONE"`. *(Code-derived; not confirmed against
the live table — see §7.)*

---

## 2. HMM dependency map

### 2.1 What the diagnosis established

Per `docs/hmm_signal_diagnosis.md:114-117`: **BULL → −2.8% annualised forward return**,
**BEAR → +7.9%**. Label churn 41.9% of bars (`:110`); the BULL state index permutes between
refits on 69.7% of refits and the full map changes on 90.0% (`:87-88`).

### 2.2 Consumers, by what they actually do

**A. Influences position size**

| Consumer | Evidence | Effect |
|---|---|---|
| `agents/kelly_sizer.py:193-203` | direct multiplier | BULL 1.0 / QUIET 0.8 / VOLATILE 0.6 / BEAR 0.4 |
| `agents/orchestrator.py:580,585-590` | feeds `overall_regime` into `calculate_position_size(regime=...)` | uses the **majority vote across 6 symbols** (`regime_detector.py:211-214`), not the per-symbol regime |
| `agents/bull_agent.py:76-77,107-121` | `if regime == 'BULL': base_bull += 15.0` (equities); +30/+20/+15/+5/+10 (crypto) | moves bull score |
| `agents/bear_agent.py:76-79,109-123` | `if regime == 'BEAR': base_bear += 15.0`, VOLATILE +10.0 | moves bear score |
| `agents/judge_agent.py:72-104,129-131` | `net_score = bull_score - bear_score` → verdict → `position_value * size_pct` | indirect regime→size |
| `agents/orchestrator.py:602-607` | `PROCEED_CAUTIOUSLY` → `orig_val * 0.5` | second, compounding regime→size channel |

The sizer's exact arithmetic (`kelly_sizer.py:275`):

```
position_value = portfolio_value * adjusted_kelly * greeks_scalar * ic_scalar
where adjusted_kelly = clamp(((b*p - q)/b) * 0.25, 0.02, 0.20) * regime_adjustment
```

**The map is precisely inverted relative to measured reality: it multiplies BULL (−2.8% ann) by
1.0 and BEAR (+7.9% ann) by 0.4.** It sizes up into the losing state and down into the winning
one. `scripts/backtest_hmm_switching.py:52-53` already says so in a code comment.

**Compounding:** an equities BEAR hits size twice — `regime_adjustment = 0.4` in the sizer, *and*
+15 to bear score pushing `net_score` toward `PROCEED_CAUTIOUSLY` (×0.5) or `AVOID`.

**The default is not neutral.** `regime='QUIET'` is the default (`kelly_sizer.py:174`) and QUIET
→ **0.8**. Every error/no-data fallback returns `'QUIET'` (`regime_detector.py:170,175,209`), so
the failure path silently takes a 20% haircut. There is no neutral path except a literal `BULL`.

**B. Gates trades.** `orchestrator.py:363-371` — `if verdict in ['AVOID','STRONG_AVOID']:
signal['action'] = 'HOLD'`. Regime feeds that verdict via bull/bear scores. Hard block.

**C. Display only.** `dashboard/.../PositionSizingView.tsx:34-46,71-79` — **a duplicate
reimplementation** of the same 1.0/0.8/0.6/0.4 map (`regimeScalar`), plus hardcoded disclosure
text at `:256`. Display-only, but a second copy that must move in lockstep with any fix. Also:
`OverviewView.tsx:154-168`, `CryptoView.tsx:67-69`, `AgentPipelinePage.tsx:384-405`, netlify
`get-pipeline-status.ts:102-111`, `get-system-health.ts:102-110`, `telegram_bot.py:101-121`,
`orchestrator.py:1102-1109`, `run_regime_detector.py:25-33`, `scripts/morning_startup.sh:43-60`.

**D. Logging/tooling only.** `orchestrator.py:759,783-802`; `kelly_sizer.py:347`
(`regime_at_entry` — but both live callers pass `regime=None` (`adaptive_trend_mr_eth.py:278`) or
an executor-local value (`options_executor.py:700,773`), so the column is largely unpopulated);
`scripts/health_check.py:291-327`; `scripts/ground_truth.py:161-262`;
`agents/tools/trading_tools.py:236-278`; `agents/market_analyst.py:110-114`.

**E. Not the HMM — do not confuse.** `ma_regime_filter.py` (200-day MA; independently touches
size at `:101-111`), `research_agent.py:98-102` (sentiment-derived BULL/BEAR/NEUTRAL — NEUTRAL
exists only here), `gex_regime` (`orchestrator.py:335,592-600`).

**F. Dead branch.** `run_agents.py:109` tests `overall_regime == "BULL_NORMAL"` — a value the
detector cannot emit (labels are BULL/BEAR/VOLATILE/QUIET, `regime_detector.py:19`; the SQL CHECK
at `20260524_009_regime_states.sql:7` forbids it). Always falls through to `MEAN_REVERSION`.
Report-text only, so low blast radius, but that line has never done what it appears to do.

### 2.3 The regime volatility estimate has no live consumer

`regime_detector.py:149` emits `'volatility': float(features[-1, 1])` — note this is the
**z-scored** feature (standardised at `:103-107`), not an annualised vol. It is written to the
table (`:188`) and exposed via `trading_tools.py:267`, but **nothing multiplies anything by it**.
The redundancy finding (corr 0.906 with 20d realised vol) is therefore live-inert. Vol targeting
exists only in backtest code (`scripts/backtest_hmm_switching.py:341-349`).

### 2.4 Does the anti-predictive map reach a real order? No.

This is the load-bearing nuance of the entire audit, so it is stated precisely:

- **Options (live, `ut_bot.py`):** qty is **fixed** — `qty = self.parameters.get("max_contracts", 1)`
  (`ut_bot.py:247`), capped by `config.MAX_POSITION_SIZE` (`:250-253`), passed straight to
  `buy_to_open` (`:256`). **KellySizer is never called on this path.**
- **Crypto (live, `adaptive_trend_mr_eth.py`):** sizes off a **static** `kelly_cap = 0.25`
  parameter (`:36,:62`) — `kelly_qty = (equity * self.kelly_cap) / price` (`:231`). It imports
  `KellySizer` only at `:261-263` to call `record_trade_outcome` *after* a fill, passing
  `regime=None` (`:278`).
- **Where regime sizing does land:** the `agent_signals` table (`orchestrator.py:801-802`), the
  HITL queue's `proposed_size_usd` (`hitl_queue.py:19,69`), `greeks_risk_engine.py:176-177`,
  Telegram reports, and the dashboard.

**Conclusion: the anti-predictive regime map drives a human-facing proposed size, a hard
AVOID→HOLD block on advisory signals, and risk-engine display numbers — but not the quantity on
any automated order.** Fixing the map is a correctness and truth-in-reporting matter, not an
active bleed.

---

## 3. Cost assumptions in live code

**There is no 10bp-style global constant anywhere in a live path.** Every `0.001` / `0.0001` in
the repo is in backtest, diagnostic, or test code. I grepped `strategies/`, `adapters/`,
`agents/risk_models.py`, `agents/risk_agent.py`, `agents/kelly_sizer.py`, `config.py`, `main*.py`
for `fee|slip|commission|spread|bps|cost` — zero hits that are cost assumptions. (The `0.001` at
`execution_filter.py:120,122` is a gap-direction threshold, not a fee.) `config.py` and
`.env.example` carry no fee or slippage setting.

**The live problem is the inverse of the backtest problem: the live sizing path models no cost at
all.** `kelly_sizer.py:275` computes `position_value` gross of everything. The Kelly
`payout_ratio` derives from realised `pnl_pct` (`kelly_sizer.py:91,106-108`) computed as raw
`(exit_price - entry_price)/entry_price` (`:321-322`) — **fills only, no commission term**.

What the live path actually pays, implicitly:

- Entry: `options_executor.py:541-545` — `"type": "limit", "limit_price": str(ask_price)` where
  `ask_price = quote["ask"]` (`:533`). **Crosses the full spread.**
- Exit: `options_executor.py:713-719` submits at `bid_price`. **Crosses the full spread again.**
- Plus `_execute_order_with_chase` (`:565`).
- The only qualitative acknowledgement in live code: `execution_filter.py:54` —
  `reason = 'Opening 30min — high spread, avoid'`.

Because the executor buys at ask and sells at bid, the spread is embedded in the fills, so Kelly
stats are net-of-spread **by accident**. They are never net-of-commission.

Backtest-side, for contrast: `backtests/costs.py:33-48,77-82` explicitly mirrors the executor's
spread-crossing, but `backtests/config.py:79` sets `commission_per_contract = 0.0` — while
`backtests/tests/test_costs.py:57` uses ~$0.65/contract as its test value. **If real commission
is nonzero, both the backtest edge and the live Kelly payout ratio are biased optimistic.**

Un-remediated backtest fee errors of the same class the HMM work fixed:
`scripts/backtest_utbot.py:81-82` — `fees=0.001, slippage=0.001` (10bp + 10bp on an equity
signal). `scripts/backtest_hmm_switching.py:404-415` is the good pattern: `fee_pct` is
keyword-only with no default, deliberately.

---

## 4. Decision authority

### 4.1 CRITICAL: no HITL gate exists on any execution path

**100% of order-creating call sites bypass HITL.** Full live chain, in-process, no gate:

`main.py:60-63` (starts `UTBotStrategy`) → `main.py:99` (`trader.run_all()`) → `ut_bot.py:237`
(signal fires) → `ut_bot.py:256` (`buy_to_open`) → `options_executor.py:543-551` (payload) →
`options_executor.py:554` (`_place_order`) → `options_executor.py:345-350`
(`requests.post(f"{_base_url()}/v2/orders", ...)`).

`strategies/ut_bot.py` imports nothing HITL-related (`ut_bot.py:14-39`). This process is running
now (PID 10774).

| Order-submission site | HITL-gated? |
|---|---|
| `options_executor.py:554` (buy-to-open, live) | **No** |
| `options_executor.py:721` (sell-to-close, live) | **No** |
| `options_executor.py:391` (chase re-price PATCH) | **No** |
| `adaptive_trend_mr_eth.py:239` (`submit_order`, ETH, PID 10773) | **No** |
| `adaptive_trend_mr_eth.py:224` (`sell_all()` trail stop) | **No** |
| `scripts/test_trade_cycle.py:99,133` | **No** — manual script, places real orders |
| `dashboard/netlify/functions/alpaca-flatten.ts:49,53` | No, but admin-key gated (`:22`) + 30s cooldown (`:15`); risk-reducing only |

The only gates on the live path are automated caps: `MAX_TRADES_PER_DAY` (`ut_bot.py:241`),
`MAX_POSITION_SIZE` (`:252`, caps rather than blocks), an already-open-position check
(`options_executor.py:505`), and a post-rejection cooldown (`:513`).

### 4.2 The HITL queue is write-only, disabled, and has no UI

`agents/hitl_queue.py` defines three functions:

- `submit_for_approval` (`:14`) — one caller: `orchestrator.py:762`
- `get_approved_signals` (`:42`) — **zero callers repo-wide** (verified by grep across `.py`/`.ts`/`.tsx`)
- `mark_executed` (`:54`) — **zero callers repo-wide**

Nothing polls the queue, so an approved row can never become an order; `executed`/`executed_at`
(`20260602_013_hitl_queue.sql:18-19`) are never written. The one submit site is gated on
`HITL_ENABLED == 'true'`, defaulting `'false'` (`orchestrator.py:750`), and the host `.env` has
`HITL_ENABLED=false` — so even the write is dead today.

`hitl_queue.py:74` directs the operator to `disruptingalpha.com/admin/hitl`. That route does not
exist: `dashboard/src/App.tsx:147-172` defines `/admin/health` and `/admin/pipeline` but no
`/admin/hitl`; the catch-all at `:173` silently redirects to `/`. Grep for `hitl` across
`dashboard/` returns nothing. **No code in this repo can set `approved = true`** — and nothing
would read it if it did.

### 4.3 The "execution held" log line describes a control that never existed

`orchestrator.py:763` logs `"submitted for human approval — execution held"`. Nothing is held.
`run_agents.py` (PID 10772) is a **separate process** from the trading bots (PIDs 10774, 10773)
and contains no order-submission code — it never had execution authority to withhold. `ut_bot.py`
never reads `agent_signals`, `risk_decision`, or `execution_approved`. **The orchestrator's entire
debate/Kelly/VaR/HITL pipeline (`orchestrator.py:196-230,744-765`) is advisory and structurally
disconnected from the bots that trade.**

### 4.4 CRITICAL: `ALPACA_IS_PAPER` does not govern the live order path

Two variables, not coupled:

- `ALPACA_IS_PAPER` → `ALPACA_CONFIG["PAPER"]` (`config.py:64`) → consumed only by the Lumibot
  `Alpaca` broker (`main.py:60`) and cosmetic labels (`main.py:71`, `heartbeat.py:43-44`).
- `ALPACA_BASE_URL` (`config.py:70`) → consumed by `options_executor._base_url()`
  (`options_executor.py:141-142`), which is what **actually places the options orders**.

`_base_url()` reads `ALPACA_BASE_URL` **only — it never consults `ALPACA_IS_PAPER`.** The flag
that reads as the safety switch does not govern the live order path.

The validator covers this asymmetrically (`config_validator.py:32-41`):

- `IS_PAPER=false` + paper URL → fatal `sys.exit(1)` (`:36`). Correct.
- `IS_PAPER=true` + **live URL** → logs `"Fixing..."` and **does nothing** (`:39-41`).

The comment at `:41` — `"This is handled in config.py"` — is **false**. `config.py:70` is a bare
`os.getenv` and performs no clamping (verified). So `ALPACA_IS_PAPER=true` with a live
`ALPACA_BASE_URL` sends **real orders to the live account**, behind a log line reading
`"Trading Mode: PAPER (Verified)"` (`:38`).

**Current host state is genuinely paper** (`.env`: `ALPACA_BASE_URL=https://paper-api.alpaca.markets`,
`ALPACA_IS_PAPER=true`, `TRADING_MODE=PAPER`). The exposure is that the paper→live transition is
one env var away from being silently wrong in the dangerous direction. `TRADING_MODE` is unused
by the trading path (only `scripts/run_options_backtest.py:75`, `backtest_hmm_switching.py:527`).

---

## 5. Risk ranking

Ranked by damage if this runs as-is on paper→live. **Recommendations only — nothing was implemented.**

| # | Severity | Finding | Evidence | Recommended action |
|---|---|---|---|---|
| 1 | **CRITICAL** | Paper/live safety flag doesn't gate the live order path; validator's guard is a no-op whose comment claims otherwise | `options_executor.py:141-142`, `config_validator.py:39-41`, `config.py:70` | Make `_base_url()` derive from `ALPACA_IS_PAPER`, or make the validator `sys.exit(1)` on the paper+live-URL case. **Fix before any live cutover.** |
| 2 | **CRITICAL** | No human approval gate on any order path; HITL queue has no reader, no UI, and is disabled | `hitl_queue.py:42,54` (zero callers), `orchestrator.py:750,763`, §4.1 table | Decide explicitly: either wire `get_approved_signals` into the bots' entry path, or **delete the HITL module and its "execution held" log** so nobody believes a gate exists. The current state is worse than either. |
| 3 | **CRITICAL** | Live bot trades unbacktested params (`14/3.0`) on an implementation no backtest covers (4-branch SMA vs 2-branch EWM) | `main.py:63-66` vs `ut_bot.py:11,54-55` and `backtests/config.py:34-35`; §1.2 | Reconcile before any further research. Either backtest `14/3.0` on the 4-branch (`backtests/engine.py:89`), or revert `main.py` to `10/1.0`. Revisit the accepted deviation at `diagnose_hmm_signal.py:466-477` — it was accepted in the wrong direction. |
| 4 | **HIGH** | SignalDecayMonitor cannot ever compute IC for the live strategy; fails **open** to full size | `ut_bot.py:198` vs `options_executor.py:695,768`; join at `signal_decay_monitor.py:149`; `kelly_sizer.py:252-254`; §6 | Normalise `signal_type` vocabulary at both writers. Change `INSUFFICIENT_DATA` to fail **closed** (or alert), not to `ic_scalar = 1.0`. Fix the test fixtures (`tests/test_ic_direction.py:44,49`). |
| 5 | **HIGH** | Kelly `payout_ratio` carries no commission term; backtest assumes `commission_per_contract = 0.0` | `kelly_sizer.py:321-322`, `backtests/config.py:79` vs `test_costs.py:57` | Add a commission term to both. Until then treat every Kelly-derived size and backtest edge as optimistic. |
| 6 | **HIGH** | Supabase RLS disabled with `anon` read/write on `signal_log` — the sole path from bot to fleet | `AUDIT.md` (18 P0 findings) | Enable RLS. An unauthenticated writer can currently inject technical signals the fleet reports on. |
| 7 | **MEDIUM** | Anti-predictive regime map (BULL×1.0 / BEAR×0.4) drives proposed size, debate scores, and an AVOID→HOLD block — but **not** automated order qty | `kelly_sizer.py:193-203`, `orchestrator.py:363-371`, §2.4 | Set `regime_adjustment = 1.0` unconditionally (or remove the param). Must change in lockstep with the dashboard's duplicate copy at `PositionSizingView.tsx:42-46,72,79,256`. Not an active bleed — correctness/reporting. |
| 8 | **MEDIUM** | QUIET (the fallback and most common label) silently applies a 0.8 haircut; no neutral path | `kelly_sizer.py:174,193-203`, `regime_detector.py:170,175,209` | Subsumed by #7. |
| 9 | **MEDIUM** | `timesfm_forecaster` runs `np.polyfit`, not TimesFM; writes `timesfm_*` columns and feeds a Kronos "agreement" metric | `timesfm_forecaster.py:16,25,201,208`; `orchestrator.py:792-793,1116-1129` | Rename module/columns to `linear_baseline_*`, or load the model. Reporting integrity. |
| 10 | **MEDIUM** | `scripts/backtest_utbot.py` still applies 10bp fee + 10bp slippage to an equity signal | `backtest_utbot.py:81-82` | Apply the `fee_for_symbol()` pattern from `backtest_hmm_switching.py:65-67`. |
| 11 | **LOW** | Crypto strategy never writes `signal_log`; crypto SignalAgent's technical signal is permanently `"NONE"` | `adaptive_trend_mr_eth.py` (no `log_signal`), `signal_agent.py:47-63` | Add logging or remove the crypto technical branch. Confirm against the live table first. |
| 12 | **LOW** | Dead/stale launchers: `main_crypto.py` (unreferenced third copy), `ecosystem.config.js:5` (pm2 not installed) | — | Delete. Divergence risk — `main_crypto.py` lacks `run_crypto_bot.py:58`'s alerts and broker sync. |
| 13 | **LOW** | `run_agents.py:109` branches on `"BULL_NORMAL"`, an impossible label | `regime_detector.py:19`, `20260524_009_regime_states.sql:7` | Fix or delete. Report text only. |
| 14 | **LOW** | `pairs_trader.py` unreferenced by the orchestrator; no schedule | `scripts/run_pairs_analysis.py:9` only | Wire up or delete. |
| 15 | **LOW** | Telegram chat ID `8641189809` hardcoded in ~6 places; all severities to one chat; delivery failures swallowed | `hitl_queue.py:8`, `signal_decay_monitor.py:236`, `run_agents.py:68`, `orchestrator.py:42,70,529,637` | Read from `TELEGRAM_CHAT_ID`; add severity routing. A dropped DEAD alert is currently silent. |

**Nothing in this table was implemented.** Items 1–3 are the ones that would change what the
fleet does tomorrow.

---

## 6. Staleness check — is the decay monitor wired to what's trading?

**No. It is wired to the right tables, but the join key can never match.**

`signal_decay_monitor.py:149` joins `signal_log` to `trade_performance` on equality of
`signal_type`:

```python
matching_outcomes = [o for o in outcomes if o.get('signal_type') == sig_type]
if not matching_outcomes:
    continue
```

The two writers use different vocabularies for that column:

- `signal_log` ← `strategies/ut_bot.py:198`: `signal_type="UT_BUY" if current_signal == 1 else "UT_SELL"`
- `trade_performance` ← `strategies/options_executor.py:695` and `:768`: `signal_type="ut_bot"`

`"UT_BUY" != "ut_bot"`, so `matching_outcomes` is **always empty** → every signal hits `continue`
→ `matched_pairs` stays `[]` → `len < MIN_TRADES` → returns `None` (`:171-173`) →
`classify_status` returns `INSUFFICIENT_DATA` (`:193-195`). Symbols match fine (both `"SPY"`), so
`signal_type` is the sole blocker.

**For the live SPY strategy the monitor is structurally pinned at INSUFFICIENT_DATA regardless of
how badly it performs.**

**Why nobody noticed:** `tests/test_ic_direction.py:44,49` sets `signal_type: "ut_bot"` on *both*
the synthetic signals and the outcomes — a vocabulary production's `signal_log` never writes. The
test passes; production never matches. It is the only test of the matcher.

**The failure is fail-open.** `kelly_sizer.py:252-254`: `INSUFFICIENT_DATA` or `ic_score is None`
→ `ic_scalar = 1.0` — full size, no reduction. The permanent INSUFFICIENT_DATA state reads as "no
adjustment" forever. (Moot for equities today, since `ut_bot.py:247` sizes from `max_contracts`
and never calls KellySizer — but it is live for anything that does.)

**Would it catch the edgeless condition the backtest found? No — three independent ways:**

1. It never gets that far (the join above).
2. **Even with the join fixed**, `classify_status:205` is `if ic >= IC_DEAD_THRESHOLD` with
   `IC_DEAD_THRESHOLD = 0.0` (`:16`) — so an IC of exactly 0.0, textbook zero edge, returns
   **DEGRADING, not DEAD**. Only a *negative* IC is ever DEAD. **Zero edge is by construction the
   best case a dead signal can present**, which is exactly the condition the diagnosis found
   (corr −0.0385 ≈ 0).
3. A degenerate constant signal gives `spearmanr` → NaN, mapped to `0.0` at `:180-181` →
   DEGRADING. A signal with no variance scores as merely "weak".

**And the verdict actuates nothing.** DEAD sends a Telegram message (`:315-322`) and writes a
row. `ut_bot.py` never reads `signal_performance`. The `"DISABLE strategy"` text (`:210`) is
advice to a human, not an actuator.

Also noted: the brief's recalled concern about thin 30-trade Spearman windows is **not** what the
config says — `signal_decay_monitor.py:17-18` is a rolling **30-day** lookback with
`MIN_TRADES = 10`. Ten trades is thinner still. `FORWARD_BARS = 5` (`:19`) is declared and never
used — the monitor measures realised trade P&L, not forward returns, so it is not an IC in the
predictive sense the name implies. Scheduling is fragile too: the 20:00 ET check sits *after*
`run_cycle()` and both handlers `continue` (`run_agents.py:294,298`), so a cycle error in the
20:00–20:15 window skips that day silently; the `minute < 15` window (`:303`) can also double-fire.

---

## 7. What was out of view

Stated explicitly rather than guessed:

- **I did not query the live databases.** Every DB claim here is derived from code. Two are worth
  confirming empirically and would take minutes: (a) `signal_performance.status` — expect 100%
  INSUFFICIENT_DATA; (b) `signal_log.signal_type` vs `trade_performance.signal_type` — expect
  `UT_BUY`/`UT_SELL` vs `ut_bot`. Also unconfirmed: whether `regime_states` has data at all, given
  the env-var bug noted at `regime_detector.py:158-163` that silently skipped writes historically.
- **Systemd unit files** (`/etc/systemd/system/da-*.service`) are host-only, not in this repo. I
  read them via `systemctl`, not from version control.
- **Runtime env may differ from `.env`.** I read `.env`, not `/proc/<pid>/environ`. The paper-mode
  conclusion in §4.4 rests on the file.
- **`disruptingalpha.com` may serve a HITL page from outside this repo.** I verified it is absent
  from `dashboard/src`. This does not change the finding: even a working UI has no consumer, since
  `get_approved_signals` has no callers.
- **Alpaca account-level controls** (options level, buying-power caps) are broker-side and could
  constrain damage independently of this code. Not assessable from the repo.
- **Cron timing.** `crontab -l` shows `45 5 * * 1-5 scripts/pre_market_check.sh`, whose comment
  (`pre_market_check.sh:2`) claims 8:45 AM ET. Whether 05:45 host-local is 08:45 ET depends on host
  TZ, which I did not verify.
- **Evidentiary basis is uncommitted.** `docs/hmm_signal_diagnosis.md` and
  `scripts/diagnose_hmm_signal.py` are untracked, and `scripts/backtest_hmm_switching.py` /
  `scripts/seed_historical.py` are modified-uncommitted, as of this audit. This document cites
  files not yet in version control. Per the brief's "commit ONLY docs/fleet_signal_audit.md," they
  were left untouched.

---

## 8. Bottom line

The fleet's safety architecture is **present as components and absent as a circuit**. HITL,
SignalDecayMonitor, the debate's AVOID block, the VaR engine, the paper-mode flag — each exists,
each logs convincingly, and **none of them can stop a trade**. The two bots that place orders
hold unconditional authority and read none of it.

The HMM and UT Bot findings that motivated this audit turn out to be mostly quarantined inside
the advisory half of that split. That is luck, not design — and the same split means the research
programme has been measuring a signal the fleet does not trade, at parameters it does not use.

**If one thing changes before a live cutover, make it #1** (paper/live flag). **If two, add #3**
(reconcile live params with what's actually backtested) — because until #3 is resolved, no
backtest in this repo, including the ones Tracks 1 and 2 are about to run, describes the thing
that is trading.
