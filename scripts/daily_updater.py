#!/usr/bin/env python3
"""Incremental daily updater — keeps the Parquet archive current.

For every seeded symbol + timeframe it finds the last stored bar, pulls
everything newer from Alpaca, writes a dated snapshot under
daily_updates/{YYYY-MM-DD}/, and merges the new bars back into the
canonical historical store so the archive stays current.

Cron (run daily at 6:00 PM ET, ~30 min after the equities close):
  # 0 18 * * 1-5 cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python scripts/daily_updater.py

Crypto trades 24/7, so it is updated on the same run regardless of weekday.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd

import seed_common as sc
from alpaca.data.timeframe import TimeFrame

log = sc.setup_logging("daily_updater")


# --------------------------------------------------------------------------- #
# Locate latest local bar
# --------------------------------------------------------------------------- #
def _daily_file(symbol: str, is_crypto: bool):
    files = sorted(sc.symbol_dir(symbol, is_crypto).glob(
        f"{sc.fs_symbol(symbol)}_{sc.TF_DAILY_LABEL}_*.parquet"))
    return files[-1] if files else None


def _minute_files(symbol: str, is_crypto: bool):
    return sorted(sc.symbol_dir(symbol, is_crypto).glob(
        f"{sc.fs_symbol(symbol)}_{sc.TF_MINUTE_LABEL}_*.parquet"))


def _latest_ts(path) -> pd.Timestamp | None:
    if path is None or not path.exists():
        return None
    df = sc.read_parquet(path)
    if df.empty:
        return None
    return pd.to_datetime(df["ts"]).max()


# --------------------------------------------------------------------------- #
# Merge helpers
# --------------------------------------------------------------------------- #
def _merge_into(path, new_df: pd.DataFrame) -> int:
    """Append new_df into an existing/empty Parquet file, deduped by ts.

    Returns the number of genuinely new rows added.
    """
    if path.exists():
        existing = sc.read_parquet(path)
        before = len(existing)
        combined = (
            pd.concat([existing, new_df], ignore_index=True)
            .drop_duplicates(subset="ts")
            .sort_values("ts")
            .reset_index(drop=True)
        )
        added = len(combined) - before
    else:
        combined = new_df.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)
        added = len(combined)
    sc.write_parquet(combined, path)
    return added


def _merge_minute(symbol: str, is_crypto: bool, new_df: pd.DataFrame) -> int:
    """Distribute new minute bars into per-month canonical files."""
    added = 0
    ts = pd.to_datetime(new_df["ts"])
    for (year, month), grp in new_df.groupby([ts.dt.year, ts.dt.month]):
        target = sc.symbol_dir(symbol, is_crypto) / (
            f"{sc.fs_symbol(symbol)}_{sc.TF_MINUTE_LABEL}_{year}_{month:02d}.parquet")
        added += _merge_into(target, grp.reset_index(drop=True))
    return added


def _merge_daily(symbol: str, is_crypto: bool, new_df: pd.DataFrame, current) -> int:
    """Append new daily bars and re-stamp the file's end date to today."""
    sym_dir = sc.symbol_dir(symbol, is_crypto)
    if current is not None and current.exists():
        existing = sc.read_parquet(current)
    else:
        existing = pd.DataFrame(columns=sc.COLUMNS)
    before = len(existing)
    combined = (
        pd.concat([existing, new_df], ignore_index=True)
        .drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True))
    added = len(combined) - before
    if combined.empty:
        return 0
    start_d = pd.to_datetime(combined["ts"].iloc[0]).date()
    end_d = pd.to_datetime(combined["ts"].iloc[-1]).date()
    target = sym_dir / f"{sc.fs_symbol(symbol)}_{sc.TF_DAILY_LABEL}_{start_d}_{end_d}.parquet"
    for old in sym_dir.glob(f"{sc.fs_symbol(symbol)}_{sc.TF_DAILY_LABEL}_*.parquet"):
        if old != target:
            old.unlink()
    sc.write_parquet(combined, target)
    return added


# --------------------------------------------------------------------------- #
# Gap detection
# --------------------------------------------------------------------------- #
def _gap(symbol: str, tf_label: str, last_ts: pd.Timestamp, first_new: pd.Timestamp) -> str | None:
    """Flag a suspicious gap between the last stored bar and the first new one."""
    delta_days = (first_new.normalize() - last_ts.normalize()).days
    # Daily equities: a >4 calendar-day jump exceeds a normal weekend+holiday.
    # Minute / crypto: treat a >2 day jump as a gap worth reporting.
    threshold = 4 if tf_label == sc.TF_DAILY_LABEL else 2
    if delta_days > threshold:
        return f"{symbol} {tf_label}: {delta_days}d gap ({last_ts.date()} → {first_new.date()})"
    return None


# --------------------------------------------------------------------------- #
# Per-symbol update
# --------------------------------------------------------------------------- #
def update_symbol(symbol: str, is_crypto: bool, snapshot_dir, stats: dict) -> None:
    client = sc.get_crypto_client() if is_crypto else sc.get_stock_client()
    now = datetime.now(timezone.utc)

    plans = [
        (sc.TF_DAILY_LABEL, TimeFrame.Day, _daily_file(symbol, is_crypto), timedelta(days=1)),
        (sc.TF_MINUTE_LABEL, TimeFrame.Minute, (lambda f: f[-1] if f else None)(_minute_files(symbol, is_crypto)), timedelta(minutes=1)),
    ]

    for tf_label, tf, latest_file, step in plans:
        last_ts = _latest_ts(latest_file)
        if last_ts is None:
            log.info("⏭  %s %s: not seeded yet — run seed_historical.py", symbol, tf_label)
            stats["not_seeded"].append(f"{symbol} {tf_label}")
            continue

        start_dt = (last_ts + step).to_pydatetime()
        if start_dt >= now:
            log.info("✓ %s %s already current (last %s)", symbol, tf_label, last_ts)
            continue

        try:
            if is_crypto:
                new_df = sc.fetch_crypto_bars(client, symbol, tf, start_dt, now)
            else:
                new_df = sc.fetch_stock_bars(client, symbol, tf, start_dt, now)
        except Exception as exc:  # noqa: BLE001
            log.error("fetch failed %s %s: %s", symbol, tf_label, exc)
            stats["failures"].append(f"{symbol} {tf_label}: {exc}")
            continue

        if new_df.empty:
            log.info("· %s %s: no new bars", symbol, tf_label)
            continue

        first_new = pd.to_datetime(new_df["ts"]).min()
        gap = _gap(symbol, tf_label, last_ts, first_new)
        if gap:
            stats["gaps"].append(gap)

        # 1) dated snapshot of just-fetched bars
        snap = snapshot_dir / f"{sc.fs_symbol(symbol)}_{tf_label}_{date.today()}.parquet"
        sc.write_parquet(new_df, snap)

        # 2) merge into canonical store
        if tf_label == sc.TF_DAILY_LABEL:
            added = _merge_daily(symbol, is_crypto, new_df, latest_file)
        else:
            added = _merge_minute(symbol, is_crypto, new_df)

        log.info("✅ %s %s: +%d new bars (snapshot %s)", symbol, tf_label, added, snap.name)
        stats["new_bars"] += added
        stats["updated"].add(symbol)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    today = date.today().isoformat()
    snapshot_dir = sc.DAILY_UPDATES_ROOT / today
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    stats = {"updated": set(), "new_bars": 0, "gaps": [], "failures": [], "not_seeded": []}

    for sym in sc.EQUITY_SYMBOLS:
        update_symbol(sym, False, snapshot_dir, stats)
    for sym in sc.CRYPTO_SYMBOLS:
        update_symbol(sym, True, snapshot_dir, stats)

    updated = sorted(stats["updated"])
    gaps_txt = "; ".join(stats["gaps"]) if stats["gaps"] else "none"

    print("\n" + "═" * 55)
    print(f"DAILY UPDATE COMPLETE — {today}")
    print("═" * 55)
    print(f"Updated symbols: {', '.join(updated) if updated else 'none'}")
    print(f"New bars:        {stats['new_bars']:,}")
    print(f"Gaps:            {gaps_txt}")
    if stats["not_seeded"]:
        print(f"Not seeded:      {', '.join(stats['not_seeded'])}")
    if stats["failures"]:
        print(f"Failures:        {len(stats['failures'])}")
        for f in stats["failures"]:
            print(f"  ✗ {f}")

    sc.send_telegram(
        f"📅 Daily update complete: {today}\n"
        f"Updated: {', '.join(updated) if updated else 'none'}\n"
        f"New bars: {stats['new_bars']:,}\n"
        f"Any gaps: {gaps_txt}"
        + (f"\n⚠️ {len(stats['failures'])} failures" if stats["failures"] else "")
    )


if __name__ == "__main__":
    main()
