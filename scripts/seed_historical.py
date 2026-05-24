#!/usr/bin/env python3
"""Seed historical OHLCV data from Alpaca into Parquet on the 8TB drive.

Pulls ALL available history for the configured symbols and timeframes,
chunked to avoid API timeouts, and writes one Parquet file per
symbol+timeframe (daily) or per symbol+month (minute).

Coverage requested (Alpaca returns less where it has no history):
  Equities SPY/IWM/QQQ : daily from 2010, 1-minute from 2020 (monthly files)
  Crypto BTC/ETH/SOL   : daily from 2020, 1-minute from 2021 (monthly files)

Output layout:
  /mnt/tick-storage/historical/equities/{SYM}/{SYM}_1D_{START}_{END}.parquet
  /mnt/tick-storage/historical/equities/{SYM}/{SYM}_1m_{YEAR}_{MONTH}.parquet
  /mnt/tick-storage/historical/crypto/{SYM}/{SYM}_1D_{START}_{END}.parquet
  /mnt/tick-storage/historical/crypto/{SYM}/{SYM}_1m_{YEAR}_{MONTH}.parquet

Usage:
  python scripts/seed_historical.py                 # seed everything
  python scripts/seed_historical.py --asset crypto  # crypto only
  python scripts/seed_historical.py --symbols SPY    # one symbol
  python scripts/seed_historical.py --force          # ignore skip-if-fresh
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

import pandas as pd
from tqdm import tqdm

import seed_common as sc
from alpaca.data.timeframe import TimeFrame

log = sc.setup_logging("seed_historical")


# --------------------------------------------------------------------------- #
# Per-timeframe seeding
# --------------------------------------------------------------------------- #
def seed_daily(symbol: str, is_crypto: bool, start: date, force: bool, stats: dict) -> None:
    """Fetch the full daily history (yearly chunks) into one Parquet file."""
    end = date.today()
    sym_dir = sc.symbol_dir(symbol, is_crypto)
    sym_dir.mkdir(parents=True, exist_ok=True)
    target = sym_dir / f"{sc.fs_symbol(symbol)}_{sc.TF_DAILY_LABEL}_{start.isoformat()}_{end.isoformat()}.parquet"

    if target.exists() and sc.modified_today(target) and not force:
        log.info("⏭  skip (fresh today): %s", target.name)
        return

    client = sc.get_crypto_client() if is_crypto else sc.get_stock_client()
    frames = []
    for cs, ce in sc.year_chunks(start, end):
        try:
            df = (
                sc.fetch_crypto_bars(client, symbol, TimeFrame.Day, cs, ce)
                if is_crypto
                else sc.fetch_stock_bars(client, symbol, TimeFrame.Day, cs, ce)
            )
            if not df.empty:
                frames.append(df)
        except Exception as exc:  # noqa: BLE001
            log.error("daily fetch failed %s %s: %s", symbol, cs.year, exc)
            stats["failures"].append(f"{symbol} 1D {cs.year}: {exc}")

    if not frames:
        log.warning("no daily data returned for %s (start %s)", symbol, start)
        return

    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset="ts").sort_values("ts")
    # Remove any older daily snapshots for this symbol to avoid accumulation.
    for old in sym_dir.glob(f"{sc.fs_symbol(symbol)}_{sc.TF_DAILY_LABEL}_*.parquet"):
        if old != target:
            old.unlink()
    sc.write_parquet(out, target)
    _report_saved(symbol, sc.TF_DAILY_LABEL, out, target, stats)


def seed_minute(symbol: str, is_crypto: bool, start: date, force: bool, stats: dict) -> None:
    """Fetch 1-minute history, one Parquet file per calendar month."""
    end = date.today()
    sym_dir = sc.symbol_dir(symbol, is_crypto)
    sym_dir.mkdir(parents=True, exist_ok=True)
    client = sc.get_crypto_client() if is_crypto else sc.get_stock_client()

    months = list(sc.month_chunks(start, end))
    for year, month, cs, ce in tqdm(
        months, desc=f"{symbol} 1m", unit="mo", leave=False
    ):
        target = sym_dir / f"{sc.fs_symbol(symbol)}_{sc.TF_MINUTE_LABEL}_{year}_{month:02d}.parquet"

        # Past complete months are immutable — skip if already present.
        # The current month re-fetches unless written earlier today.
        complete = sc.month_is_complete(year, month)
        if target.exists() and not force:
            if complete or sc.modified_today(target):
                continue

        try:
            df = (
                sc.fetch_crypto_bars(client, symbol, TimeFrame.Minute, cs, ce)
                if is_crypto
                else sc.fetch_stock_bars(client, symbol, TimeFrame.Minute, cs, ce)
            )
        except Exception as exc:  # noqa: BLE001
            log.error("minute fetch failed %s %s-%02d: %s", symbol, year, month, exc)
            stats["failures"].append(f"{symbol} 1m {year}-{month:02d}: {exc}")
            continue

        if df.empty:
            continue
        sc.write_parquet(df, target)
        _report_saved(symbol, sc.TF_MINUTE_LABEL, df, target, stats, period=f"{year}-{month:02d}")


def _report_saved(symbol, tf_label, df, path, stats, period=None):
    rows = len(df)
    size = sc.file_size_mb(path)
    start_ts = pd.to_datetime(df["ts"].iloc[0]).date()
    end_ts = pd.to_datetime(df["ts"].iloc[-1]).date()
    label = f"{tf_label} {period}" if period else tf_label
    print(f"✅ Saved {symbol} {label} {start_ts} → {end_ts}: {rows:,} rows ({size:.1f}MB)")
    stats["files"] += 1
    stats["rows"] += rows


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Seed historical OHLCV from Alpaca -> Parquet")
    ap.add_argument("--asset", choices=["all", "equities", "crypto"], default="all")
    ap.add_argument("--symbols", nargs="*", help="Restrict to these symbols")
    ap.add_argument("--force", action="store_true", help="Re-download even if fresh")
    args = ap.parse_args()

    stats = {"files": 0, "rows": 0, "failures": []}
    start_clock = datetime.now(timezone.utc)

    equities = sc.EQUITY_SYMBOLS if args.asset in ("all", "equities") else []
    cryptos = sc.CRYPTO_SYMBOLS if args.asset in ("all", "crypto") else []
    if args.symbols:
        want = set(args.symbols)
        equities = [s for s in equities if s in want]
        cryptos = [s for s in cryptos if s in want]

    log.info("Seeding equities=%s crypto=%s force=%s", equities, cryptos, args.force)

    for sym in equities:
        log.info("=== %s (equity) ===", sym)
        seed_daily(sym, False, sc.EQUITY_DAILY_START, args.force, stats)
        seed_minute(sym, False, sc.EQUITY_MINUTE_START, args.force, stats)

    for sym in cryptos:
        log.info("=== %s (crypto) ===", sym)
        seed_daily(sym, True, sc.CRYPTO_DAILY_START, args.force, stats)
        seed_minute(sym, True, sc.CRYPTO_MINUTE_START, args.force, stats)

    total_gb = sc.dir_size_bytes(sc.HIST_ROOT) / 1_000_000_000
    elapsed = (datetime.now(timezone.utc) - start_clock).total_seconds() / 60

    print("\n" + "═" * 55)
    print("SEED COMPLETE")
    print("═" * 55)
    print(f"Files saved:   {stats['files']}")
    print(f"Rows:          {stats['rows']:,}")
    print(f"Storage:       {total_gb:.2f}GB on {sc.HIST_ROOT}")
    print(f"Elapsed:       {elapsed:.1f} min")
    if stats["failures"]:
        print(f"Failures:      {len(stats['failures'])}")
        for f in stats["failures"]:
            print(f"  ✗ {f}")
    else:
        print("Failures:      none")

    sc.send_telegram(
        "📊 Historical seed complete:\n"
        f"{stats['files']} files, {stats['rows']:,} rows\n"
        f"Storage: {total_gb:.1f}GB on /mnt/tick-storage\n"
        "Coverage: SPY/IWM/QQQ from 2010, BTC/ETH/SOL from 2020"
        + (f"\n⚠️ {len(stats['failures'])} failures (see logs)" if stats["failures"] else "")
    )


if __name__ == "__main__":
    main()
