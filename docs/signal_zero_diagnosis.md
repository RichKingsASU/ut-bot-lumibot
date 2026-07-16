# Diagnosis: UT Bot `current_signal=0` on all ~375 live iterations

**Scope:** Read-only diagnostic against `origin/main` (branch `debug/signal-zero`). No
protected code was modified. All numbers below were computed against **real production
SPY daily bars** fetched live from Alpaca (feed=`sip`, matching `ALPACA_FEED` in `.env`),
using the **exact, unmodified** signal formula copied verbatim from
`strategies/ut_bot.py` lines 126-164.

## TL;DR

The zero is **not a bug**. `current_signal=0` is the mathematically correct output of
the live 4-branch SMA-ATR formula (`atr_period=14`, `sensitivity=3.0`) on every single
calendar day the bot has actually been running (`2026-04-01`, `2026-07-09`,
`2026-07-10`, `2026-07-13`, `2026-07-15`, confirmed from `bar_log`'s distinct
`bar_time` values). None of those 5 days happens to be a trailing-stop crossover day.
The 375 iterations logged in `bar_log` all share **the exact same `bar_time`**
(`2026-07-15T04:00:00+00:00`) — because the strategy runs on `timeframe="1D"` bars but
polls every `sleeptime="1M"`, so all 375 checks are re-evaluating **the same single
daily bar** over and over (only its still-forming intraday close/volume changes between
checks). There is only ever ~1 meaningful signal evaluation per calendar day; 375
iterations is 375x redundant re-computation of that same evaluation, not 375
independent chances to fire.

## 1. The exact condition blocking the signal

Live code (`strategies/ut_bot.py:155-164`):

```python
df.loc[(df['close'] > df['trail_stop']) & (df['close'].shift() <= df['prev_trail_stop']), 'signal'] = 1
df.loc[(df['close'] < df['trail_stop']) & (df['close'].shift() >= df['prev_trail_stop']), 'signal'] = -1
```

A signal only fires **on the day of a crossover/crossunder** — the day price first
moves from the wrong side of the ratchet stop to the right side. Every day *after*
that, while the trend continues, `close` stays on the same side of `trail_stop` as the
day before, so the second (shifted) clause is always false and `signal` stays `0`. This
is by design for a trend-following stop-and-reverse system: it is supposed to be silent
for the vast majority of days.

Computed for the actual last bar of each live-run day (100-bar Alpaca lookback,
`atr_period=14`, `sensitivity=3.0`):

| Eval date (last bar) | close | trail_stop | prev_close | prev_trail_stop | signal |
|---|---|---|---|---|---|
| 2026-04-01 | 655.24 | 661.9346 | — | — | 0 |
| 2026-07-09 | 751.71 | 724.5536 | 745.40 | 724.5536 | 0 |
| 2026-07-10 | 754.95 | 726.7082 | 751.71 | 724.5536 | 0 |
| 2026-07-13 | 749.17 | 726.7082 | 754.95 | 726.7082 | 0 |
| 2026-07-15 | 754.81 | 728.9757 | 749.17 (07-13)/751.83 (07-14) | 726.7082 | 0 |

On 2026-07-15 specifically: `close(754.81) > trail_stop(728.98)` is TRUE (we are firmly
in an established uptrend), but `prev_close(751.83) <= prev_trail_stop(726.71)` is
FALSE — so the `signal=1` clause fails on its second half. We are **already inside**
the uptrend that began on the actual crossover day, **2026-06-15** (close 754.83,
trail_stop flipped from 724.55 to below price → `signal=1`). The bot was not running
on 2026-06-15 (not among the `bar_time`s ever logged), so it never caught that entry,
and every day since is correctly reported as "no new signal."

## 2. bar_log data — confirmed valid, non-null, correctly cased

- `bar_log` row shape uses lowercase `open/high/low/close/volume` fields matching
  `df['close']`, `df['high']`, etc. exactly as read in `ut_bot.py`.
- Last 30 rows of the running session (`session_id=20260714-205027-64ac95`) all show
  non-null `open=754.24, high=755.58, low≈750.20-750.24, close≈753.6-754.6,
  volume` climbing intraday — i.e., a single still-forming daily bar being logged
  repeatedly as its OHLCV update through the trading session.
- **All 375 rows for the current session have `bar_time = 2026-07-15T04:00:00+00:00`**
  (verified via PostgREST query grouped by `bar_time`) — one daily bar, 375 redundant
  writes.
- `signal_log` is confirmed **0 rows total** across all history (not just this
  session) via `Content-Range: */0` from a `count=exact` HEAD-style query — consistent
  with the bot having simply never been alive during any of the ~10 crossover days in
  the trailing year of SPY daily data.
- No column-name mismatch, no NaN propagation, no warmup starvation: the 100-bar
  lookback (`get_historical_prices(symbol, 100, "day")`) is far more than the 14-day
  ATR warmup needs, so `atr`/`loss`/`trail_stop` are all valid floats by the last row.

## 3. Manual computation on live params (14 / 3.0) — does it EVER fire?

**No, it is not structurally blocked.** Run over the trailing ~250 SPY trading days
(2025-06 through 2026-07-15) with the exact production formula and live params, it
fires **10 times**:

```
2025-10-10  signal=-1   2025-10-20  signal=1
2025-11-18  signal=-1   2025-11-28  signal=1
2026-01-20  signal=-1   2026-01-27  signal=1
2026-03-06  signal=-1   2026-04-08  signal=1
2026-06-05  signal=-1   2026-06-15  signal=1   <- most recent, bot wasn't running that day
```

That is roughly one signal every ~25 trading days (~4% of days) — sparse by design
(trend-following stop-and-reverse), not broken.

## 4. Manual computation with 10 / 1.0 on the same data

Using the exact **same production 4-branch SMA formula** but with backtest params
(`atr_period=10, sensitivity=1.0`): fires **30 times** over the same ~250-day window —
3x more often (tighter, more sensitive stop), but **on all 5 of the actual live-run
days it also computes 0**:

```
2026-04-01: trail_stop=643.778   SIGNAL(10/1.0)=0
2026-07-09: trail_stop=742.087   SIGNAL(10/1.0)=0
2026-07-10: trail_stop=745.572   SIGNAL(10/1.0)=0
2026-07-13: trail_stop=745.572   SIGNAL(10/1.0)=0
2026-07-15: trail_stop=747.696   SIGNAL(10/1.0)=0
```

The fully-independent 2-branch EWM variant from `backtests/signal.py`
(`calculate_ut_signals`, matching `scripts/backtest_utbot.py`) agrees qualitatively:
its last 5 buy/sell flags for the 07-15 window are also all `False`/`False`. **All
three formula/param combinations agree that today is a "no new signal" day** — this
rules out params or implementation-variant choice as the cause of today's specific
zero.

## 5. Warmup / lookback

Not a factor. `atr_period` warmup needs only 14 (or 10) rows; the strategy fetches 100
daily bars every iteration, so `atr`, `loss`, and `trail_stop` are fully valid
(non-NaN) well before the most recent bar in every case checked.

## 6. Column-name / NaN mismatches

None found. `bar_log` confirms `open/high/low/close/volume` arrive correctly, non-null,
matching the lowercase names `ut_bot.py` reads (`df['close']`, `df['high']`,
`df['low']`, `df['open']`). No silent-NaN path was found.

## Classification

**None of PARAMS / DATA / IMPLEMENTATION cleanly fits — this is an operational/
architecture issue:**

- **Not a data problem** — OHLCV values are valid, non-null, correctly named at every
  logged cycle.
- **Not a params problem** — 14/3.0 is not structurally blocked (fires ~10x/yr); 10/1.0
  produces the *same* zero on the exact days the bot was actually alive, so swapping
  params would not have changed today's outcome.
- **Not a signal-logic implementation bug** — three independently-computed variants
  (live 4-branch/14-3.0, live 4-branch/10-1.0, backtest 2-branch EWM/10-1.0) all agree
  0 is correct for 07-15.
- **The real issue:** (a) `sleeptime="1M"` polls a `timeframe="1D"` signal 375x/day for
  a computation that can only change once per day, producing a misleading appearance of
  "375 failed attempts"; and (b) the bot's actual uptime (only alive on 5 scattered
  calendar days per `bar_log`, with gaps of weeks/months between them, e.g.
  2026-04-01 → 2026-07-09) has, by chance, never coincided with one of the ~10
  crossover days/year — including missing the most recent one, 2026-06-15, entirely.
  `signal_log` being 0 rows across all of history is the direct consequence.

## Recommended fix

Align the polling cadence to the actual data cadence (e.g. run signal evaluation once
per new daily bar instead of every 1-minute cycle, or move to an intraday
`timeframe`/`sleeptime` pair that matches), and prioritize bot uptime/continuity so it
does not miss the rare (~4%-of-days) crossover events the strategy depends on — the
signal logic itself does not need to change.
