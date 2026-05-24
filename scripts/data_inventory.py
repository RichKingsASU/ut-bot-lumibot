#!/usr/bin/env python3
"""Data inventory — what's on disk vs what Alpaca can provide.

Scans the local Parquet archive for each symbol + timeframe, reports the
date range, row count, file size and any gaps, then (unless --no-probe)
queries Alpaca for the actually-available range and flags what still
needs to be seeded.

Usage:
  python scripts/data_inventory.py            # full report (probes Alpaca)
  python scripts/data_inventory.py --no-probe # offline, local-only
"""
from __future__ import annotations

import argparse
import shutil
from datetime import date, datetime, timezone

import pandas as pd
import pyarrow.parquet as pq

import seed_common as sc
from alpaca.data.timeframe import TimeFrame

TODAY = date.today()


# --------------------------------------------------------------------------- #
# Local scan
# --------------------------------------------------------------------------- #
def _ts_bounds(path) -> tuple[pd.Timestamp, pd.Timestamp]:
    col = pq.read_table(path, columns=["ts"])["ts"].to_pandas()
    col = pd.to_datetime(col)
    return col.min(), col.max()


def scan_local(symbol: str, is_crypto: bool, tf_label: str) -> dict:
    sym_dir = sc.symbol_dir(symbol, is_crypto)
    files = sorted(sym_dir.glob(f"{sc.fs_symbol(symbol)}_{tf_label}_*.parquet"))
    if not files:
        return {"files": 0, "rows": 0, "size_mb": 0.0, "min": None, "max": None, "gaps": []}

    rows = sum(pq.ParquetFile(f).metadata.num_rows for f in files)
    size_mb = sum(sc.file_size_mb(f) for f in files)
    min_ts, _ = _ts_bounds(files[0])
    _, max_ts = _ts_bounds(files[-1])

    gaps: list[str] = []
    if tf_label == sc.TF_MINUTE_LABEL and len(files) >= 1:
        # Month-level gap detection from filenames: {SYM}_1m_{YEAR}_{MONTH}.
        present = set()
        for f in files:
            y, m = f.stem.split("_")[-2:]
            present.add((int(y), int(m)))
        cur = (min_ts.year, min_ts.month)
        last = (max_ts.year, max_ts.month)
        while cur <= last:
            if cur not in present:
                gaps.append(f"{cur[0]}-{cur[1]:02d}")
            cur = (cur[0] + 1, 1) if cur[1] == 12 else (cur[0], cur[1] + 1)

    return {"files": len(files), "rows": rows, "size_mb": size_mb,
            "min": min_ts, "max": max_ts, "gaps": gaps}


# --------------------------------------------------------------------------- #
# Alpaca probe (cheap: daily bars over the full requested range)
# --------------------------------------------------------------------------- #
def probe_alpaca(symbol: str, is_crypto: bool, start: date) -> tuple[date, date] | None:
    try:
        client = sc.get_crypto_client() if is_crypto else sc.get_stock_client()
        s = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        e = datetime.now(timezone.utc)
        df = (sc.fetch_crypto_bars(client, symbol, TimeFrame.Day, s, e) if is_crypto
              else sc.fetch_stock_bars(client, symbol, TimeFrame.Day, s, e))
        if df.empty:
            return None
        ts = pd.to_datetime(df["ts"])
        return ts.min().date(), ts.max().date()
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _status(local: dict, avail: tuple[date, date] | None) -> str:
    if local["files"] == 0:
        return "MISSING — needs seed"
    if local["gaps"]:
        shown = ", ".join(local["gaps"][:3]) + (" …" if len(local["gaps"]) > 3 else "")
        return f"⚠️ GAP: {shown}"
    # Stale if local data ends well before what Alpaca can provide / today.
    target_end = avail[1] if avail else TODAY
    if local["max"] is not None and (target_end - local["max"].date()).days > 5:
        return f"⚠️ STALE: ends {local['max'].date()} (avail {target_end})"
    return "✅ COMPLETE"


def _fmt_row(label: str, local: dict, avail, totals: dict) -> str:
    totals["files"] += local["files"]
    totals["rows"] += local["rows"]
    totals["size_mb"] += local["size_mb"]
    status = _status(local, avail)
    if local["files"] == 0:
        return f"{label:14} {status}"
    rng = f"{local['min'].date()} → {local['max'].date()}"
    return (f"{label:14} {rng} | {local['rows']:>10,} rows | "
            f"{local['size_mb']:>7.1f}MB | {status}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Local vs Alpaca data inventory")
    ap.add_argument("--no-probe", action="store_true", help="Skip Alpaca availability probe")
    args = ap.parse_args()
    probe = not args.no_probe

    totals = {"files": 0, "rows": 0, "size_mb": 0.0}
    missing: list[str] = []

    plan = [
        ("EQUITIES", sc.EQUITY_SYMBOLS, False, sc.EQUITY_DAILY_START, sc.EQUITY_MINUTE_START),
        ("CRYPTO", sc.CRYPTO_SYMBOLS, True, sc.CRYPTO_DAILY_START, sc.CRYPTO_MINUTE_START),
    ]

    print("═" * 70)
    print("DISRUPTING ALPHA — DATA INVENTORY")
    print(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("═" * 70)

    for section, symbols, is_crypto, d_start, m_start in plan:
        print(f"\n{section}")
        print("─" * len(section))
        for sym in symbols:
            avail = probe_alpaca(sym, is_crypto, d_start) if probe else None
            for tf_label, tf_name in ((sc.TF_DAILY_LABEL, "Daily"), (sc.TF_MINUTE_LABEL, "1-min")):
                local = scan_local(sym, is_crypto, tf_label)
                print(_fmt_row(f"{sym} {tf_name}:", local, avail, totals))
                if local["files"] == 0:
                    missing.append(f"{sym} {tf_name}")
                elif local["gaps"]:
                    missing.append(f"{sym} {tf_name} (gaps: {len(local['gaps'])} months)")
            if probe:
                a = avail
                print(f"  ↳ Alpaca available: {a[0]} → {a[1]}" if a else "  ↳ Alpaca available: none")

    usage = shutil.disk_usage(sc.STORAGE_ROOT)
    used_gb = totals["size_mb"] / 1000
    free_tb = usage.free / 1e12

    print("\nSUMMARY")
    print("─" * 7)
    print(f"Total local files: {totals['files']}")
    print(f"Total local rows:  {totals['rows']:,}")
    print(f"Total storage:     {used_gb:.2f}GB / {free_tb:.1f}TB free")
    if missing:
        print(f"Missing / gaps:    {len(missing)} items")
        for m in missing:
            print(f"  • {m}")
        print("Recommended action: run  python scripts/seed_historical.py  for the items above")
    else:
        print("Missing data:      none — archive is complete")
        print("Recommended action: keep daily_updater.py scheduled via cron")


if __name__ == "__main__":
    main()
