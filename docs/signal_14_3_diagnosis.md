# Diagnosis: equities UT Bot `current_signal=0` at params **ATR=14 / sensitivity=3.0**

**Branch:** `debug/signal-14-3-investigation` · **Mode:** read-only diagnosis, no code changes, no restarts.
**Date:** 2026-07-16 (computed live during the RTH session, ~09:40 MST).
**Signal formula:** copied verbatim from `strategies/ut_bot.py:127-166` (4-branch SMA-ATR). No protected file modified.

---

## Root-cause verdict (one sentence)

**TIMEFRAME_MISMATCH (compounded by operational uptime), not a params/data/implementation fault:** the signal is computed correctly on **daily** bars, but the bot polls it every **1 minute**, so "hundreds of cycles with signal=0" is really ~1 real evaluation per day re-logged ~375×/day — and today (2026-07-16) is a genuine *no-crossover* day (SPY closes **751.97**, ~**23 pts / 3.1% above** the trailing stop **728.98**), so `signal=0` is the mathematically correct output.

**At current params (14/3.0), the signal will first fire when** the daily close crosses the trailing stop — concretely a **SELL (−1)** on the first day SPY closes below ~**729** (the stop ratchets upward as price rises), or a **BUY (+1)** only after such a drop then reclaims the ratcheted stop. **Estimated time:** not today; **days-to-weeks**, on the next >~3% daily-close pullback. Historically 14/3.0 fires **~once/month** (12× in the last 13 months; most recent **2026-06-15**, when the bot was offline).

---

## Step 1 — Prior diagnosis (`docs/signal_zero_diagnosis.md`) summary

The earlier read-only diagnosis (branch `debug/signal-zero`) already concluded **signal=0 is not a bug**. It established, using the exact `ut_bot.py` formula against live SPY daily bars, that: (a) the strategy runs `timeframe="1D"` but `sleeptime="1M"`, so all ~375 daily iterations re-evaluate the **same single daily bar** (`bar_time=2026-07-15T04:00:00Z`), giving the illusion of "375 failed attempts"; (b) 14/3.0 is **not structurally blocked** — it fires ~10×/yr, last on 2026-06-15, a day the bot was not alive; (c) on all 5 scattered calendar days the bot actually ran, **10/1.0 also computes 0**, so params aren't the cause; (d) no NaN/warmup/column-name problem — 100 daily bars fetched each cycle, ATR valid. It classified the real cause as **operational/architecture** (cadence mismatch + poor uptime never coinciding with a ~monthly crossover) and recommended aligning poll cadence to the daily bar and prioritizing uptime — signal logic unchanged. **14/3.0 was specifically tested** there; this document re-confirms it with fresh 2026-07-16 data and adds an explicit sensitivity sweep.

---

## Step 2 — Live log inspection (`journalctl -u da-trading-bot`)

The bot is healthy and evaluating every minute; every cycle logs a valid price and RSI with `Signal: 0.0`. Representative verbatim lines (2026-07-16 MST):

```
09:31:01 [UTBotStrategy] Price: 751.93 | Signal: 0.0 | Dir: None | RSI: 64.4 | Position: False
09:33:01 [UTBotStrategy] Price: 752.50 | Signal: 0.0 | Dir: None | RSI: 65.0 | Position: False
09:37:01 [UTBotStrategy] Price: 752.09 | Signal: 0.0 | Dir: None | RSI: 64.5 | Position: False
09:39:01 [UTBotStrategy] Price: 752.23 | Signal: 0.0 | Dir: None | RSI: 64.7 | Position: False
[STRATEGY] Strategy Initialized. Symbol: SPY, P&L: $0.00, Trades: 0/10
[SUPABASE] Portfolio snapshot logged successfully. Equity: $96275.97
```

- **Signal value logged:** `0.0` on every cycle (no `1.0`/`-1.0`).
- **RSI:** real, ~64–65 → indicators are computing on valid data (**not** NaN, **not** warmup-starved).
- **ATR/SMA/trail_stop:** not logged per-cycle (only Price/Signal/Dir/RSI/Position); computed and verified independently below.
- **Errors/exceptions:** **NONE** in the last 100 lines. No "warming up" / "insufficient data" / stale-bar messages.
- **Cadence:** iteration ends each minute with "next check in time is …09:3X:00" — confirms `sleeptime≈1M` polling.

**LOG_ERRORS_FOUND: none.**

---

## Step 3 — Bar-data availability

- **QuestDB `ohlcv_1m` is EMPTY** — `SELECT symbol,count() … GROUP BY symbol` → `[]` (0 rows); `min/max(ts)` → `None`. **SPY_BARS_IN_QUESTDB: NO_DATA** (0). IWM also absent.
- Only two QuestDB tables exist: `ohlcv_1m` (empty) and `ticks` (**57,559 rows, crypto only** — `BTCUSD/ETHUSD/SOLUSD`). There is **no equities OHLCV in QuestDB at all**.
- **This does not affect the equities signal.** `ut_bot.py:114` sources bars via `self.get_historical_prices("SPY", 100, "day")` → **Alpaca daily bars through lumibot**, *not* QuestDB. The signal path has valid data (confirmed by the live RSI and the computation below). The empty `ohlcv_1m` is a separate data-pipeline gap (equities OHLCV not being written to QuestDB) that matters only for consumers that read `ohlcv_1m` — the live UT Bot signal is not one of them.
- For the sensitivity analysis I therefore used **live Alpaca SPY daily bars (feed=SIP, 282 bars, 2025-06-02 → 2026-07-16)** — the same source the bot uses. No synthetic bars.

---

## Step 4 — Signal-logic trace (`strategies/ut_bot.py`, read-only)

| # | Question | Answer with evidence |
|---|----------|----------------------|
| a | Where/how is ATR calculated? | `ut_bot.py:127-130`. True range = max(H−L, \|H−prevC\|, \|L−prevC\|); **`atr = tr.rolling(window=atr_period).mean()`** → **SMA method (not EWM)**, `atr_period=14`. |
| b | Trailing stop? | `ut_bot.py:132-152`. `loss = sensitivity*atr`; a Python `for`-loop implementing the classic UT Bot ratchet. |
| c | Exact 4 branches → what makes signal=1? | Stop loop `:141-151`: (1) `close>prev_stop & prev_close>prev_stop` → `max(prev_stop, close−loss)`; (2) `close<prev_stop & prev_close<prev_stop` → `min(prev_stop, close+loss)`; (3) `close>prev_stop` → `close−loss`; (4) else → `close+loss`. Signal `:154-166`: **`signal=1` iff `close>trail_stop` AND `prev_close<=prev_trail_stop`** (a crossover); `signal=-1` iff `close<trail_stop` AND `prev_close>=prev_trail_stop` (crossunder). A one-day transition is required — steady trend days are always 0. |
| d | Band width at 3.0 vs SPY vol? | Current **ATR(14)=8.21**, so band `loss = 3.0×8.21 = 24.63` pts. At close 751.97 the stop sits at **728.98 → 3.1% below price**. Not "so wide price never crosses it" — it's crossed ~monthly — but it means only a ≥~3% daily-close reversal triggers a flip. |
| e | Warmup with period=14? | On **daily** bars: needs 14 *daily* bars. The bot fetches **100 daily** bars every cycle (`:114`), so ATR/stop are valid floats far before the last bar. **Not** 14 minutes and **not** a warmup issue (live RSI≈64 confirms). |
| f | 1m / 15m / daily? Today's bar complete? | **Daily** (`"day"`, `:114`). Polled every ~1 min. Today's daily bar is **still open** during RTH — each poll re-reads the same forming 2026-07-16 bar, which is why signal can't change intraday. |

---

## Step 5 — Sensitivity analysis (live SPY daily bars, exact formula)

Current bar **2026-07-16**: close **751.97**, **ATR(14)=8.209** (same for all sensitivities).

| sensitivity | band `loss` (pts) | trail_stop | dist close−stop | **today's signal** | signals in last 60 bars | last signal |
|---|---|---|---|---|---|---|
| 1.0 | 8.21 | 746.20 | 5.77 (0.8%) | **0** | 6 | 2026-06-30 (+1) |
| 2.0 | 16.42 | 737.59 | 14.38 (1.9%) | **0** | 6 | 2026-07-10 (+1) |
| **3.0 (live)** | **24.63** | **728.98** | **22.99 (3.1%)** | **0** | 2 | **2026-06-15 (+1)** |

**Would today fire at *any* sensitivity?** Sweep of the last bar: `0.25→−1`, and `0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0 → 0`. Only an absurdly tight 0.25× band flips it (noise). **No reasonable sensitivity produces a signal on today's bar** — because today is not a crossover day; price is firmly mid-uptrend above the stop at every setting.

**Full 14/3.0 signal history (2025-06 → 2026-07-16), 12 fires (~1/month):**
```
2025-08-01 -1   2025-08-12 +1   2025-10-10 -1   2025-10-20 +1
2025-11-18 -1   2025-11-28 +1   2026-01-20 -1   2026-01-27 +1
2026-03-06 -1   2026-04-08 +1   2026-06-05 -1   2026-06-15 +1  ← most recent (bot offline)
```
Last 8 daily bars @14/3.0 — stop ratcheting up, price staying above it (hence 0):
```
2026-07-09 close=751.71 stop=724.55  sig=0
2026-07-10 close=754.95 stop=726.71  sig=0
2026-07-13 close=749.17 stop=726.71  sig=0
2026-07-14 close=751.83 stop=726.71  sig=0
2026-07-15 close=754.81 stop=728.98  sig=0
2026-07-16 close=751.97 stop=728.98  sig=0   ← today
```

Interpretation: at 3.0 the last transition was the **+1 on 2026-06-15**; we have been continuously long-side since, so the shifted second clause of the `signal=1` test is false every day → correct 0. Lowering sensitivity does **not** make *today* fire; it only tightens the stop (so a future pullback flips sooner) and would have caught later re-entries (07-10 at 1.0/2.0). This matches the prior finding that params are not the blocker.

---

## Step 6 — Root-cause classification

- **WARMUP** — ❌ 100 daily bars fetched; ATR(14) valid; RSI≈64 live.
- **SENSITIVITY_TOO_HIGH** — ❌ 3.0 is not structurally blocked (fires ~monthly); no reasonable sensitivity fires *today*; on the actual run-days even 10/1.0 = 0 (prior doc).
- **DATA_GAP** — ❌ *for the signal path* (Alpaca daily bars valid). ✅ *separately*, QuestDB `ohlcv_1m` is empty for equities — a real pipeline gap, but the live signal doesn't read it.
- **TIMEFRAME_MISMATCH** — ✅ **primary.** A daily-bar signal polled every minute manufactures the "hundreds of zero cycles" symptom; there is only ~1 real evaluation per day.
- **IMPLEMENTATION_BUG** — ❌ formula verified against three variants (prior doc) and reproduced here; 0 is correct.
- **OTHER (operational)** — ✅ **contributing.** The bot's uptime (only ~5 scattered live days) never coincided with a ~monthly crossover — it missed the last one (2026-06-15) entirely, so `signal_log` has 0 rows across all history.

---

## Step 7 — Recommendation (recommend only — no change made)

**Minimal correct fix — operational, not params:** align the evaluation cadence to the data cadence (evaluate once per **new daily bar** instead of every 1-minute poll) **and** keep the bot continuously up so it is alive on the rare (~4%-of-days) crossover events — **the signal logic does not need to change.** No param edit makes the signal fire today (today is simply not a crossover). 

Secondary, *optional and only if faster/more-frequent signals are actually desired* (a strategy change, requires a backtest — ties to open item **P0-8**, do **not** ship unbacktested): either switch to an intraday `timeframe`/`sleeptime` pair (e.g. 15m) so crossovers occur more often, or lower `sensitivity` toward ~1.5–2.0 to tighten the stop. Neither is a bug fix; both alter strategy behavior.

Also worth a separate ticket (does not block the equities signal): **populate `ohlcv_1m` for equities in QuestDB** — it is currently empty (crypto ticks only).

---

### Final answers
- **ROOT_CAUSE:** TIMEFRAME_MISMATCH (+ operational uptime); not params/data/impl.
- **WILL_FIRE_WHEN:** next daily close that crosses the stop — a SELL (−1) on the first close below ~729 (currently ~3.1% under spot), or a BUY (+1) only after such a drop then reclaims the ratcheted stop; ~monthly historically; not today.
- **RECOMMENDATION:** fix cadence (evaluate per daily bar) + ensure continuous uptime; leave signal logic and params unchanged (any param/timeframe change needs a backtest per P0-8).
- **LOG_ERRORS_FOUND:** none.
- **SPY_BARS_IN_QUESTDB:** NO_DATA (0 rows in `ohlcv_1m`; signal instead uses live Alpaca daily bars).
