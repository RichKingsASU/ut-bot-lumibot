# DIAGNOSIS — 2026-05-29

**Author:** Claude Code
**Branch:** `claude/jolly-fermi-MYqJf`
**Repo HEAD:** `1f50df4` (== `origin/main`)

---

## ⚠️ Environment limitation (read first)

This session is **not** running on the k2 edge server. It is running in an
**ephemeral cloud container** (hostname `vm`, path `/home/user/ut-bot-lumibot`)
that was freshly cloned from GitHub.

Consequences for this task:

| Resource | Available here? | Impact |
|---|---|---|
| `.env` secrets | ❌ No (`.env.example` only) | No Supabase/QuestDB/Alpaca/Telegram credentials |
| Supabase REST | ❌ Blocked (403 via proxy) | Cannot run the `agent_cycles` / `trade_performance` queries |
| QuestDB (`ticks`) | ❌ Not reachable | Cannot check tick/news freshness (2d) |
| Telegram API | ❌ Blocked (403) | Cannot capture a live report or send the completion notification |
| Live cycle | ❌ Cannot run | No Alpaca / no LLM key / no DB |

Therefore **Phase 2's live-data verification (2a row inspection, 2b cross-cycle
variance, 2c DB cross-check, 2d freshness) cannot be executed here.** What
follows is a **static source-level trace** of each claimed fix against the code
at HEAD. Items needing live data are marked **`LIVE-REQUIRED`** and must be
re-verified on k2.

---

## Phase 0 — Git state

- **Repo path:** `/home/user/ut-bot-lumibot`
- **Current branch:** `claude/jolly-fermi-MYqJf` — clean working tree.
- **Sync:** `HEAD == origin/main == 1f50df4`. `git log origin/main..HEAD` and
  `git log HEAD..origin/main` are both **empty** → fully in sync, nothing to
  fast-forward.
- **Stranded autonomous edits:** **None.** Working tree is clean. The
  Nightly-Hardener / Cycle-Watchdog stranded-edit scenario from the prompt does
  **not** apply to a fresh clone — those edits (if any) live on the k2 server's
  working copy, not here. No review branch was needed.
- All four referenced commits exist in history: `1f50df4`, `e5aed92`,
  `7e67fc7`, `1ef9122`.

---

## Phase 2 — Static verification (PASS = fix present & logically correct in source)

### 2a — Kelly crypto/equities isolation

| Check | Result | Evidence |
|---|---|---|
| Crypto pipeline passes a crypto symbol to KellySizer | **PASS (static)** | `orchestrator.py:391` — `symbol = signal.get("symbol", "ETH/USD" if asset == "crypto" else "SPY")`. The `SPY` default is reachable **only** when `asset == "equities"`. |
| Signal sets a real symbol | **PASS (static)** | `signal_agent.py` sets `"symbol": latest_row.get("symbol", "ETH/USD" if crypto else "SPY")` (commit `e5aed92`). |
| Debate node default symbol | **PASS (static)** | `orchestrator.py:197` — `default_symbol = 'ETH/USD' if asset_class == 'crypto' else 'SPY'`. |
| `get_historical_performance` isolates by asset_class | **PASS (static)** | `kelly_sizer.py:58-59` filters `asset_class=eq.{asset_class}`; `calculate_position_size(asset_class=asset)` is passed through from `kelly_sizing_node`. |

**Conclusion:** No SPY leak path remains in source for the crypto pipeline.
**`LIVE-REQUIRED`:** confirm `agent_cycles` crypto rows show ETH/BTC/SOL in the
Kelly fields (the original symptom could only ever be reproduced against live
rows).

### 2b — Debate score variance

| Check | Result | Evidence |
|---|---|---|
| Scores are computed, not hardcoded | **PASS (static)** | `bull_agent.py:59-139` and `bear_agent.py` build `score` additively from `avg_sentiment`, `overall_regime`, signal `action`/`buy_sig`/`sell_sig`, `sentiment_trend/velocity`, and greeks `trade_mode`. Optional Claude override extracts `Score: <n>` (`bull_agent.py:214-218`). |
| Inputs reach the agents | **PASS (static)** | `_debate_node_async` passes `market`, `signal`, `greeks`, `regime` into `bull/bear.analyze(...)` (`orchestrator.py:208-210`). |

**Important root-cause note:** the historical "always **Bull 0 / Bear 25 /
AVOID**" symptom is **what this code produces when `market_context` is empty /
all-default** (sentiment `0.0`, regime `''`, action `HOLD`). That is a
**stale-input / upstream-collector** failure mode, *not* a hardcoded debate.
The debate logic itself is dynamic. **`LIVE-REQUIRED`:** inspect 3+ consecutive
crypto + 3+ equities `agent_cycles` rows for variance — if still constant, the
fault is upstream (market_analyst inputs / data freshness 2d), not the debate
agents.

### 2c — The 7 Telegram fixes (source trace of commit `1f50df4`)

| # | Fix | Result | Evidence |
|---|---|---|---|
| 1 | Double Kelly reduction | **PASS (static)** | The duplicate `PROCEED_CAUTIOUSLY → position_value *= 0.5` block was **removed** from `_debate_node_async` (diff `1f50df4`). The 0.5 scale now exists in exactly one place, `kelly_sizing_node` (`orchestrator.py:400-405`). Graph order is `debate_node → greeks_intercept → kelly_sizing` (`orchestrator.py:630-633`), so the old debate-side reduction would in any case have been overwritten by the fresh `kelly_result`. (The separate VaR `REDUCE → *0.5` at `orchestrator.py:476` is an independent risk action, not a duplicate.) |
| 2 | `adjusted_kelly` display | **PASS (static)** | `orchestrator.py:722,726` — `c_frac = c_ks.get("adjusted_kelly", c_ks.get("kelly_fraction", 0.0))`. `adjusted_kelly` is computed at `kelly_sizer.py:201` and returned at `:267`. Report label changed to `adj. portfolio`. |
| 3 | VaR lookup | **PASS (static)** | Report reads `c_var_pct = crypto_result['var_result']['var']['var_pct']` (`orchestrator.py:730-736`), populated by the live `VaRRiskEngine.full_risk_check()` in `risk_node` (`:424,479`). The `0.01` default appears **only** in the exception fallback (`:483`) — expected degraded behaviour, not the default path. |
| 4 | Article count | **PASS (static)** | `base_agent.py` now returns `"article_count": len(scores)` (and `0` on every empty branch); `market_analyst.py:93` propagates it; report renders `({c_art} articles)` (`orchestrator.py:771`). |
| 5 | sentiment_velocity propagation | **PASS (static)** | `signal_agent.py:130-177` computes `sentiment_velocity`/`sentiment_trend` via `SentimentVelocity` and emits them on the signal; `_debate_node_async` (`orchestrator.py:200-201`) copies them into `market` unconditionally. Report shows `Velocity: {c_sr.get('sentiment_trend')}` from the signal. *(Note: `market_analyst.py:94-95` hardcodes `sentiment_velocity=0.0/STABLE`, but these are overridden by the signal's values in the debate node; harmless but see "Observations".)* |
| 6 | Reasoning truncation | **PASS (static)** | `_debate_line` now uses `reasoning[:300] + ("..." if len>300)` (`orchestrator.py:758`) instead of the old hard `reasoning[:120]` mid-sentence cut. |
| 7 | debate_node overwrite | **PASS (static)** | The block that overwrote `state['kelly_sizing']` from inside the debate node was removed (diff `1f50df4`); and the `if 'sentiment_trend' not in market` guards were replaced with unconditional assignment so signal values are not dropped. |

**`LIVE-REQUIRED`:** capture one real recent Telegram report on k2 and
cross-check each rendered field against the corresponding DB value.

### 2d — Data freshness (the likely real root cause)

**`LIVE-REQUIRED` — not executable here.** No QuestDB/Supabase access. The
queries in the prompt (`max(timestamp)` on `ticks`, `max(published_at)` on
`news_articles`, count of unscored recent articles) must be run on k2. Given
that 2b's constant-score symptom is a stale-input signature, **2d is the first
thing to check on k2** — a stalled tick/news collector will make 2a/2b/2c all
*look* broken downstream while the source code is correct.

---

## Summary

| Phase 2 item | Static (source) result | Live verification |
|---|---|---|
| 2a Kelly isolation | ✅ PASS | `LIVE-REQUIRED` |
| 2b Debate variance | ✅ PASS (logic dynamic) | `LIVE-REQUIRED` |
| 2c.1 Double Kelly | ✅ PASS | `LIVE-REQUIRED` |
| 2c.2 adjusted_kelly | ✅ PASS | `LIVE-REQUIRED` |
| 2c.3 VaR lookup | ✅ PASS | `LIVE-REQUIRED` |
| 2c.4 Article count | ✅ PASS | `LIVE-REQUIRED` |
| 2c.5 sentiment_velocity | ✅ PASS | `LIVE-REQUIRED` |
| 2c.6 Reasoning trunc | ✅ PASS | `LIVE-REQUIRED` |
| 2c.7 debate_node overwrite | ✅ PASS | `LIVE-REQUIRED` |
| 2d Data freshness | — | `LIVE-REQUIRED` (run first) |

**At the source level, every claimed fix is present and logically correct at
HEAD `1f50df4`. No code-level FAIL was found, therefore no surgical fix was
applied** (per the directive: do not touch anything that passes). All seven
relevant agent files pass `python -m py_compile` on Python 3.11.15.

## Observations (non-blocking, no change made)

- `market_analyst.py:94-95` hard-codes `sentiment_velocity=0.0` /
  `sentiment_trend="STABLE"` into `market_context`. It is currently masked
  because the debate node overrides these from the signal, and the report reads
  the signal's value — but it is a latent trap if any future consumer reads
  velocity straight from `market_context`. Flagging only; not fixed.

## Required next step (on k2)

Re-run Phase 2a–2d **on the k2 edge server** with real credentials. If any item
turns up FAIL there, that is a genuine regression to fix surgically — most
likely in the upstream collectors (data freshness, 2d) rather than in these
already-correct agent files.
