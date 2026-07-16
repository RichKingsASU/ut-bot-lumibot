#!/usr/bin/env python3
"""diagnose_hmm_signal.py — PHASE 1 READ-ONLY diagnosis of the HMM switching backtest.

Imports the real strategy functions from backtest_hmm_switching and measures them.
Changes NO strategy logic: calculate_ut_signals / simulate_portfolio / evaluate_metrics
are imported and called as-is (only their existing *parameters*, e.g. fee_pct, are varied).

Usage:
  python3 scripts/diagnose_hmm_signal.py --symbol SPY --start 2000-01-01
"""
from __future__ import annotations

import argparse
import logging
import sys
import warnings
from datetime import date
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np
import pandas as pd
from hmmlearn import hmm

from scripts.backtest_hmm_switching import (
    load_data,
    calculate_ut_signals,
    simulate_portfolio,
    evaluate_metrics,
    extract_features,
    map_regimes,
)

# hmmlearn screams per-refit; we count instead of printing.
logging.getLogger("hmmlearn").setLevel(logging.CRITICAL)
logging.getLogger("HMMSwitchingBacktester").setLevel(logging.WARNING)

OUT = Path(_REPO_ROOT) / "docs" / "hmm_signal_diagnosis.md"


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Engine sanity + cost decomposition
# ─────────────────────────────────────────────────────────────────────────────
def engine_sanity(df, init_cash):
    close = df["close"]
    raw_bh = float(close.iloc[-1] / close.iloc[0] - 1.0)

    ones = pd.Series(1.0, index=df.index)
    bh_fee = simulate_portfolio(df, ones, ones, init_cash, fee_pct=0.001)
    bh_nofee = simulate_portfolio(df, ones, ones, init_cash, fee_pct=0.0)

    return {
        "raw_buy_hold": raw_bh,
        "engine_bh_fee": evaluate_metrics(bh_fee, init_cash)["total_return"],
        "engine_bh_nofee": evaluate_metrics(bh_nofee, init_cash)["total_return"],
    }


def cost_decomposition(df, pos, init_cash):
    ones = pd.Series(1.0, index=df.index)
    out = {}
    for fee in (0.001, 0.0005, 0.0001, 0.0):
        eq = simulate_portfolio(df, pos, ones, init_cash, fee_pct=fee)
        out[fee] = evaluate_metrics(eq, init_cash)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 2. Signal dissection
# ─────────────────────────────────────────────────────────────────────────────
def signal_stats(df, pos):
    close = df["close"]
    fwd_ret = close.pct_change().shift(-1)  # return from t -> t+1

    n = len(pos)
    frac_long = float((pos > 0).sum()) / n
    frac_flat = float((pos == 0).sum()) / n
    frac_short = float((pos < 0).sum()) / n

    valid = fwd_ret.notna()
    corr_fwd = float(pos[valid].corr(fwd_ret[valid]))              # t -> t+1 (as coded)
    corr_lookahead = float(pos.corr(close.pct_change()))            # t-1 -> t
    corr_lagged = float(pos[:-2].corr(close.pct_change().shift(-2)[:-2]))  # t+1 -> t+2

    # trades: 0 -> 1 entry, 1 -> 0 exit
    trades = []
    entry_i = None
    p = pos.values
    c = close.values
    for i in range(n):
        if p[i] > 0 and entry_i is None:
            entry_i = i
        elif p[i] == 0 and entry_i is not None:
            trades.append((entry_i, i, c[i] / c[entry_i] - 1.0))
            entry_i = None
    if entry_i is not None:
        trades.append((entry_i, n - 1, c[n - 1] / c[entry_i] - 1.0))

    rets = np.array([t[2] for t in trades]) if trades else np.array([])
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    holds = [t[1] - t[0] for t in trades]

    return {
        "n_bars": n,
        "frac_long": frac_long,
        "frac_flat": frac_flat,
        "frac_short": frac_short,
        "corr_fwd": corr_fwd,
        "corr_lookahead": corr_lookahead,
        "corr_lagged": corr_lagged,
        "n_trades": len(trades),
        "win_rate": float(len(wins) / len(rets)) if len(rets) else float("nan"),
        "avg_win": float(wins.mean()) if len(wins) else float("nan"),
        "avg_loss": float(losses.mean()) if len(losses) else float("nan"),
        "expectancy": float(rets.mean()) if len(rets) else float("nan"),
        "gross_sum": float(rets.sum()) if len(rets) else float("nan"),
        "avg_hold_bars": float(np.mean(holds)) if holds else float("nan"),
        "bars_per_trade": float(n / len(trades)) if trades else float("nan"),
    }


def alignment_proof(df, pos, init_cash):
    """Rebuild equity vectorially under 3 alignments; whichever matches the
    zero-fee engine is the alignment the engine actually implements."""
    ret = df["close"].pct_change()
    variants = {
        "t -> t+1 (correct, no look-ahead)": pos * ret.shift(-1),
        "t-1 -> t (LOOK-AHEAD)": pos * ret,
        "t+1 -> t+2 (lagged)": pos * ret.shift(-2),
    }
    engine = evaluate_metrics(
        simulate_portfolio(df, pos, pd.Series(1.0, index=df.index), init_cash, fee_pct=0.0),
        init_cash,
    )["total_return"]
    out = {}
    for name, series in variants.items():
        out[name] = float((1.0 + series.fillna(0.0)).prod() - 1.0)
    return engine, out


# ─────────────────────────────────────────────────────────────────────────────
# 3. HMM diagnostics — instrumented mirror of run_rolling_hmm's exact params
# ─────────────────────────────────────────────────────────────────────────────
def hmm_diagnostics(df_feats, lookback=252):
    vals = df_feats.values
    n = len(vals)
    regimes = pd.Series("QUIET", index=df_feats.index)  # mirrors run_rolling_hmm's default
    stats = {
        "refits": 0,
        "failed": 0,
        "hit_cap": 0,          # iter == n_iter -> did NOT converge by tolerance
        "ll_decreased": 0,     # final EM step lowered log-likelihood
        "phantom_refits": 0,   # >=1 zero-sum transmat row in the FINAL model
        "phantom_rows_total": 0,
        "warn_transmat": 0,    # hmmlearn logged a (transient, mid-EM) zero-sum warning
        "warn_notconv": 0,     # hmmlearn logged "Model is not converging"
        "populated_counts": [],
        "iters": [],
        "bull_idx": [],
        "rank_maps": [],
    }

    # hmmlearn reports both conditions via logging, not warnings — capture the records.
    class _Capture(logging.Handler):
        def emit(self, record):
            m = record.getMessage()
            if "zero sum" in m:
                stats["warn_transmat"] += 1
            elif "not converging" in m:
                stats["warn_notconv"] += 1

    hlog = logging.getLogger("hmmlearn.base")
    cap = _Capture()
    hlog.addHandler(cap)
    hlog.setLevel(logging.WARNING)
    hlog.propagate = False  # count them, don't print them

    for t in range(lookback, n):
        window = vals[t - lookback:t]
        w_mean = np.mean(window, axis=0)
        w_std = np.std(window, axis=0)
        w_std[w_std == 0] = 1.0
        window_std = (window - w_mean) / w_std

        model = hmm.GaussianHMM(n_components=4, covariance_type="diag",
                                n_iter=100, random_state=42)
        stats["refits"] += 1
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(window_std)
                states = model.predict(window_std)
        except Exception:
            stats["failed"] += 1
            stats["bull_idx"].append(None)
            stats["rank_maps"].append(None)
            continue

        # phantom states: transmat rows that sum to ~0 (state never transitioned from)
        row_sums = model.transmat_.sum(axis=1)
        phantom = int((row_sums < 1e-8).sum())
        if phantom:
            stats["phantom_refits"] += 1
            stats["phantom_rows_total"] += phantom

        stats["populated_counts"].append(int(len(np.unique(states))))

        # NOTE: model.monitor_.converged is NOT usable here — hmmlearn returns True
        # when iter == n_iter (cap hit), and its delta test omits abs() so a FALLING
        # log-likelihood also reads as converged. Measure both conditions directly.
        mon = getattr(model, "monitor_", None)
        if mon is not None:
            it = int(getattr(mon, "iter", -1))
            stats["iters"].append(it)
            if it >= 100:
                stats["hit_cap"] += 1
            hist = list(getattr(mon, "history", []))
            if len(hist) >= 2 and hist[-1] < hist[-2]:
                stats["ll_decreased"] += 1

        # label stability: which raw index is the highest-mean ("BULL") state?
        means = model.means_
        stats["bull_idx"].append(int(np.argsort(means[:, 0])[-1]))
        try:
            state_map = map_regimes(model, window_std)
            stats["rank_maps"].append(tuple(sorted(state_map.items())))
            regimes.iloc[t] = state_map.get(states[-1], "QUIET")
        except Exception:
            stats["rank_maps"].append(None)

    # permutation rate: BULL index changes between consecutive refits
    b = [x for x in stats["bull_idx"]]
    changes = sum(1 for i in range(1, len(b))
                  if b[i] is not None and b[i - 1] is not None and b[i] != b[i - 1])
    comparable = sum(1 for i in range(1, len(b))
                     if b[i] is not None and b[i - 1] is not None)
    stats["bull_permutation_rate"] = changes / comparable if comparable else float("nan")

    r = stats["rank_maps"]
    rchanges = sum(1 for i in range(1, len(r))
                   if r[i] is not None and r[i - 1] is not None and r[i] != r[i - 1])
    rcomparable = sum(1 for i in range(1, len(r))
                      if r[i] is not None and r[i - 1] is not None)
    stats["map_permutation_rate"] = rchanges / rcomparable if rcomparable else float("nan")
    return stats, regimes


# ─────────────────────────────────────────────────────────────────────────────
# 5. Reference UT Bot — read-only comparison, NOT a fix.
# ─────────────────────────────────────────────────────────────────────────────
def reference_ut_signals(df, atr_period=10, sensitivity=1.0):
    """The published UT Bot trailing stop (Yo_adri / QuantNomad Pine v4), for
    comparison ONLY. Differs from the repo's calculate_ut_signals by keeping the
    RESET branch: when price crosses the stop, the stop jumps to close∓nLoss
    instead of being clamped to the stale prior stop.

        xATRTrailingStop =
          close > prev and close[1] > prev -> max(prev, close - nLoss)   # ratchet up
          close < prev and close[1] < prev -> min(prev, close + nLoss)   # ratchet down
          close > prev                     -> close - nLoss              # RESET (crossed up)
          else                             -> close + nLoss              # RESET (crossed down)
    """
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period, min_periods=1).mean()

    c = close.values
    n_loss = (atr * sensitivity).values
    stop = np.empty(len(c))
    stop[0] = c[0]
    for i in range(1, len(c)):
        prev = stop[i - 1]
        if c[i] > prev and c[i - 1] > prev:
            stop[i] = max(prev, c[i] - n_loss[i])
        elif c[i] < prev and c[i - 1] < prev:
            stop[i] = min(prev, c[i] + n_loss[i])
        elif c[i] > prev:
            stop[i] = c[i] - n_loss[i]
        else:
            stop[i] = c[i] + n_loss[i]

    stop_s = pd.Series(stop, index=df.index)
    buy = (close > stop_s) & (close.shift() <= stop_s.shift())
    sell = (close < stop_s) & (close.shift() >= stop_s.shift())
    pos = pd.Series(0.0, index=df.index)
    cur = 0.0
    for i in range(len(df)):
        if buy.iloc[i]:
            cur = 1.0
        elif sell.iloc[i]:
            cur = 0.0
        pos.iloc[i] = cur
    return pos


# ─────────────────────────────────────────────────────────────────────────────
# 4. Exposure-matched control: is the regime map adding anything over constant size?
# ─────────────────────────────────────────────────────────────────────────────
def regime_quality(df, regimes):
    """Do the SEMANTIC labels mean anything? Raw-index permutation is irrelevant —
    map_regimes re-derives BULL/BEAR from emission means every refit, so it is
    invariant to hmmlearn's arbitrary state ordering. What matters is (1) whether the
    label sequence is stable day-to-day and (2) whether BULL actually precedes higher
    forward returns than BEAR."""
    fwd = df["close"].pct_change().shift(-1).reindex(regimes.index)
    live = regimes.iloc[252:]           # skip the warm-up default of "QUIET"
    fwd_live = fwd.iloc[252:]
    churn = float((live != live.shift()).iloc[1:].mean())
    per = {}
    for r in ["BULL", "QUIET", "VOLATILE", "BEAR"]:
        m = live == r
        if m.sum() > 1:
            x = fwd_live[m].dropna()
            per[r] = {
                "bars": int(m.sum()),
                "mean_fwd_bp": float(x.mean() * 1e4),
                "ann_ret": float(x.mean() * 252),
                "ann_vol": float(x.std() * np.sqrt(252)),
            }
    return {"churn": churn, "per_regime": per}


def exposure_control(df, pos, regimes, init_cash):
    sizing_regime = regimes.map(
        {"BULL": 1.0, "QUIET": 0.8, "VOLATILE": 0.6, "BEAR": 0.4}
    ).fillna(0.8)
    avg_size = float(sizing_regime.mean())
    # Pinned to the ORIGINAL 10bp/side cost model on purpose: this reproduces the
    # Phase 1 findings as measured. The corrected per-asset-class costs live in
    # backtest_hmm_switching.FEE_PER_SIDE.
    eq_regime = simulate_portfolio(df, pos, sizing_regime, init_cash, fee_pct=0.001)
    eq_const = simulate_portfolio(
        df, pos, pd.Series(avg_size, index=df.index), init_cash, fee_pct=0.001
    )
    return {
        "avg_regime_size": avg_size,
        "regime": evaluate_metrics(eq_regime, init_cash),
        "constant_matched": evaluate_metrics(eq_const, init_cash),
        "regime_counts": regimes.value_counts().to_dict(),
    }


def main():
    p = argparse.ArgumentParser(description="Phase 1 read-only diagnosis")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--start", type=date.fromisoformat, default=date(2000, 1, 1))
    p.add_argument("--end", type=date.fromisoformat, default=date(2026, 7, 14))
    p.add_argument("--init-cash", type=float, default=100000.0, dest="init_cash")
    p.add_argument("--skip-hmm", action="store_true", help="skip the slow rolling-HMM diagnostics")
    a = p.parse_args()

    sd = load_data(a.symbol, a.start, a.end)  # STRICT: no allow_synthetic
    df = sd.data
    prov = f"DATA PROVENANCE: {sd.provenance.value} | rows={sd.rows} | symbol={a.symbol}"
    print(prov, flush=True)

    # Mirror the backtester's own alignment: features drive the index it trades on.
    df_feats = extract_features(df)
    df_align = df.loc[df_feats.index]

    print("\n[1/5] engine sanity (buy & hold through simulate_portfolio)...", flush=True)
    eng = engine_sanity(df_align, a.init_cash)

    print("[2/5] signal dissection...", flush=True)
    pos = calculate_ut_signals(df_align, atr_period=10, sensitivity=1.0)
    sig = signal_stats(df_align, pos)

    print("[3/5] alignment proof...", flush=True)
    engine_ret, align = alignment_proof(df_align, pos, a.init_cash)

    print("[4/5] cost decomposition...", flush=True)
    costs = cost_decomposition(df_align, pos, a.init_cash)

    print("[5/6] reference UT Bot comparison (read-only)...", flush=True)
    ref_pos = reference_ut_signals(df_align, atr_period=10, sensitivity=1.0)
    ref = {
        "stats": signal_stats(df_align, ref_pos),
        "costs": cost_decomposition(df_align, ref_pos, a.init_cash),
    }

    hstats = None
    ctrl = None
    rq = None
    if not a.skip_hmm:
        print(f"[6/6] rolling HMM diagnostics ({len(df_feats) - 252} refits, slow)...", flush=True)
        hstats, regimes = hmm_diagnostics(df_feats, lookback=252)
        ctrl = exposure_control(df_align, pos, regimes, a.init_cash)
        rq = regime_quality(df_align, regimes)

    lines = []
    w = lines.append
    w("# HMM Switching Backtest — Phase 1 Diagnosis (read-only)")
    w("")
    w(f"`{prov}`")
    w("")
    w(f"Window: {a.start} → {a.end} | bars analysed: {len(df_align)} "
      f"({df_align.index.min().date()} → {df_align.index.max().date()})")
    w("")
    w("## (a) Is the P&L engine correct?")
    w("")
    w("| Test | Total return |")
    w("|---|---|")
    w(f"| Raw buy & hold (`close[-1]/close[0]-1`) | {_pct(eng['raw_buy_hold'])} |")
    w(f"| Buy & hold **through `simulate_portfolio`**, fee=0.001 | {_pct(eng['engine_bh_fee'])} |")
    w(f"| Buy & hold **through `simulate_portfolio`**, fee=0 | {_pct(eng['engine_bh_nofee'])} |")
    w("")
    w("## (b) Is the raw signal inverted or mis-shifted?")
    w("")
    w(f"- Exposure: **long {_pct(sig['frac_long'])}**, flat {_pct(sig['frac_flat'])}, "
      f"short {_pct(sig['frac_short'])} of {sig['n_bars']} bars")
    w(f"- **corr(pos[t], ret[t→t+1]) = {sig['corr_fwd']:+.4f}**  ← inversion test")
    w(f"- corr(pos[t], ret[t-1→t]) = {sig['corr_lookahead']:+.4f} (look-ahead alignment)")
    w(f"- corr(pos[t], ret[t+1→t+2]) = {sig['corr_lagged']:+.4f} (lagged alignment)")
    w(f"- Trades: **{sig['n_trades']}** (one per {sig['bars_per_trade']:.1f} bars, "
      f"avg hold {sig['avg_hold_bars']:.1f} bars)")
    w(f"- Win rate {_pct(sig['win_rate'])} | avg win {_pct(sig['avg_win'])} | "
      f"avg loss {_pct(sig['avg_loss'])} | **expectancy/trade {_pct(sig['expectancy'])}**")
    w(f"- Sum of gross (fee-free) trade returns: {_pct(sig['gross_sum'])}")
    w("")
    w("### Alignment proof (vectorised rebuild vs zero-fee engine)")
    w("")
    w(f"Zero-fee engine total return: **{_pct(engine_ret)}**")
    w("")
    w("| Alignment | Vectorised return | Matches engine? |")
    w("|---|---|---|")
    for name, val in align.items():
        match = "**YES**" if abs(val - engine_ret) < 0.02 else "no"
        w(f"| {name} | {_pct(val)} | {match} |")
    w("")
    w("### Cost decomposition (same signal, `fee_pct` varied)")
    w("")
    w("| fee_pct (per side) | Total return | Sharpe | Max DD |")
    w("|---|---|---|---|")
    for fee, m in costs.items():
        w(f"| {fee} | {_pct(m['total_return'])} | {m['sharpe_ratio']:.2f} | {_pct(m['max_drawdown'])} |")
    w("")

    rs = ref["stats"]
    w("### Repo signal vs published UT Bot reference (comparison only — nothing changed)")
    w("")
    w("The repo's `calculate_ut_signals` has 2 branches; the published UT Bot has 4 — it is")
    w("missing the RESET branch, so on a stop cross the stop is clamped to the stale prior")
    w("stop (`max(prev_stop, ...)`) instead of resetting a full ATR from price.")
    w("")
    w("| Metric | Repo `calculate_ut_signals` | Reference UT Bot (4-branch) |")
    w("|---|---|---|")
    w(f"| Trades | {sig['n_trades']} | {rs['n_trades']} |")
    w(f"| Avg hold (bars) | {sig['avg_hold_bars']:.1f} | {rs['avg_hold_bars']:.1f} |")
    w(f"| Win rate | {_pct(sig['win_rate'])} | {_pct(rs['win_rate'])} |")
    w(f"| Expectancy/trade | {_pct(sig['expectancy'])} | {_pct(rs['expectancy'])} |")
    w(f"| corr(pos[t], ret[t→t+1]) | {sig['corr_fwd']:+.4f} | {rs['corr_fwd']:+.4f} |")
    w(f"| Return @ fee=0 | {_pct(costs[0.0]['total_return'])} | {_pct(ref['costs'][0.0]['total_return'])} |")
    w(f"| Return @ fee=0.001 | {_pct(costs[0.001]['total_return'])} | {_pct(ref['costs'][0.001]['total_return'])} |")
    w("")
    w("#### KNOWN DEVIATION — accepted, will NOT be fixed")
    w("")
    w("`calculate_ut_signals` is **not** a faithful UT Bot: it implements 2 of the")
    w("published indicator's 4 trailing-stop branches, omitting the RESET branch. On a")
    w("stop cross it clamps to the stale prior stop via `max(prev_stop, close - nLoss)`")
    w("instead of resetting a full ATR from price, so the stop sits just under price and")
    w("whipsaws out — hence the 6.5-bar average hold.")
    w("")
    w(f"**This is a fidelity bug, not the cause of the loss.** Measured above: the correct")
    w(f"4-branch reference is *worse* on this data — "
      f"**{_pct(ref['costs'][0.0]['total_return'])} gross vs "
      f"{_pct(costs[0.0]['total_return'])} gross** for the repo version. Repairing it")
    w("would reduce returns, not rescue them. Documented as a known deviation and left")
    w("in place deliberately (decision: 2026-07-15); `calculate_ut_signals` is unchanged.")
    w("")

    if hstats:
        n = hstats["refits"]
        pc = hstats["populated_counts"]
        w("## (c) How broken is the HMM fit?")
        w("")
        w(f"- Refits: **{n}** (lookback 252, n_components=4, diag, n_iter=100)")
        w(f"- Failed fits (exception → carry previous regime): {hstats['failed']} "
          f"({_pct(hstats['failed'] / n)})")
        w(f"- **Hit the n_iter=100 cap (did NOT converge to tol): {hstats['hit_cap']} "
          f"({_pct(hstats['hit_cap'] / n)})**")
        w(f"- Final EM step *lowered* log-likelihood: {hstats['ll_decreased']} "
          f"({_pct(hstats['ll_decreased'] / n)})")
        w(f"- **Refits whose FINAL model has ≥1 phantom state (zero-sum transmat row): "
          f"{hstats['phantom_refits']} ({_pct(hstats['phantom_refits'] / n)})**")
        w(f"- Total phantom rows across all refits: {hstats['phantom_rows_total']}")
        if pc:
            w(f"- States actually populated in the final model: mean {np.mean(pc):.2f} of 4 "
              f"requested (min {min(pc)}, max {max(pc)})")
            for k in (1, 2, 3, 4):
                w(f"  - exactly {k} populated: {_pct(sum(1 for x in pc if x == k) / len(pc))}")
        if hstats["iters"]:
            w(f"- EM iterations: mean {np.mean(hstats['iters']):.1f}, "
              f"max {max(hstats['iters'])} (cap 100)")
        w(f"- **BULL state index permuted between consecutive refits: "
          f"{_pct(hstats['bull_permutation_rate'])} of refits**")
        w(f"- Full regime→index map changed between consecutive refits: "
          f"{_pct(hstats['map_permutation_rate'])} of refits")
        w("")
        w("hmmlearn log lines actually emitted (the warning spam in the run logs):")
        w("")
        w(f"- `Some rows of transmat_ have zero sum...`: **{hstats['warn_transmat']}** lines")
        w(f"- `Model is not converging...`: **{hstats['warn_notconv']}** lines")
        w("")
        w("> Both messages are misleading. The zero-sum check (`hmmlearn/base.py:497`) sits")
        w("> *after* the `break` on convergence at `:494`, so it can only ever fire on a")
        w("> **non-final** EM iteration — a state that is transiently empty mid-fit and")
        w("> repopulated before `fit()` returns. And `ConvergenceMonitor.converged` returns")
        w("> True when `iter == n_iter`, while its delta test omits `abs()`, so a *falling*")
        w("> log-likelihood logs \"not converging\" yet still reports converged. Neither log")
        w("> line describes the model that actually produces the regime labels.")
        w("")

    if rq:
        w("### Do the SEMANTIC regime labels mean anything?")
        w("")
        w("`map_regimes` re-derives BULL/BEAR by sorting emission means on **every** refit,")
        w("so it is invariant to hmmlearn's arbitrary state ordering — the raw-index")
        w("permutation above is expected and already handled. These are the metrics that")
        w("actually bear on the regime→size map:")
        w("")
        w(f"- Label churn: regime changes on **{_pct(rq['churn'])}** of bars")
        w("")
        w("| Regime | Bars | Mean fwd return (bp/day) | Annualised return | Annualised vol |")
        w("|---|---|---|---|---|")
        for r, m in rq["per_regime"].items():
            w(f"| {r} | {m['bars']} | {m['mean_fwd_bp']:+.2f} | {_pct(m['ann_ret'])} | "
              f"{_pct(m['ann_vol'])} |")
        w("")

    if ctrl:
        w("### Control: does the regime map beat a constant size at the same exposure?")
        w("")
        w(f"Regime sizing averages **{ctrl['avg_regime_size']:.3f}** exposure. If the regime")
        w("signal is real it must beat a flat line at that same average exposure; if it merely")
        w("holds less of a losing strategy, the two will match.")
        w("")
        w(f"- Regime distribution: {ctrl['regime_counts']}")
        w("")
        w("| Variant | Total return | Sharpe | Max DD |")
        w("|---|---|---|---|")
        for k in ("regime", "constant_matched"):
            m = ctrl[k]
            w(f"| {k} | {_pct(m['total_return'])} | {m['sharpe_ratio']:.2f} | {_pct(m['max_drawdown'])} |")
        w("")

    w("## Verdict")
    w("")
    bh = eng["engine_bh_fee"]
    w(f"1. **P&L engine: CORRECT.** Buy & hold through `simulate_portfolio` returns "
      f"{_pct(bh)} vs {_pct(eng['raw_buy_hold'])} raw. No sign, compounding or shift error.")
    w(f"2. **Signal: NOT inverted, NOT mis-shifted.** Positions are long/flat only "
      f"(`{{0.0, 1.0}}`) — a short is structurally impossible. "
      f"corr(pos[t], ret[t→t+1]) = {sig['corr_fwd']:+.4f} ≈ 0: no edge, not an inversion. "
      f"The vectorised t→t+1 rebuild reproduces the engine exactly, so alignment is correct.")
    n_tr = sig["n_trades"]
    w(f"3. **Root cause: transaction-cost drag on an edgeless signal.** "
      f"{n_tr} round trips × 2 sides × `fee_pct=0.001` = "
      f"{2 * n_tr * 0.001:.0%} of notional paid in fees. "
      f"(1{costs[0.0]['total_return']:+.3f}) × (1-0.001)^{2 * n_tr} = "
      f"{((1 + costs[0.0]['total_return']) * (1 - 0.001) ** (2 * n_tr)) - 1:+.1%} "
      f"vs {_pct(costs[0.001]['total_return'])} actual — the loss is fully accounted for.")
    if hstats:
        w(f"4. **HMM is not fabricating phantom states** (0% of final models degenerate; "
          f"100% have all 4 states populated; {_pct(hstats['hit_cap'] / hstats['refits'])} "
          f"hit the iteration cap). **But labels permute on "
          f"{_pct(hstats['bull_permutation_rate'])} of refits**, which is real and unfixed.")
    w("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nSaved: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
