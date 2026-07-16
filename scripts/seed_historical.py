#!/usr/bin/env python3
"""seed_historical.py — Seed REAL historical bars into the tick-storage Parquet
tree so the backtest resolver returns REAL_PARQUET instead of SyntheticDataError.
Sources: alpaca (default; equities ~2016+, crypto ~2021+) | yfinance (daily, SPY to 1993).

Daily bars are written to the path every reader in this repo globs:
    <root>/historical/equities/<SYM>/<SYM>_1D_<start>_<end>.parquet   (crypto -> historical/crypto/)
where <start>/<end> are the ACTUAL first/last bar dates in the file, not the
requested window. Readers glob `<SYM>_1D_*.parquet` and concatenate every match,
so exactly one 1D file per symbol may exist; stale ones are moved to <SYM>/_archive/.
Minute bars still go to historical/minute/<SYM>/<YEAR>.parquet — not yet on the
resolver's path (see MINUTE_SUBDIR note below).
Each file gets a .manifest.json sidecar. Columns: timestamp(UTC),open,high,low,close,volume.
"""
from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = "/mnt/tick-storage"
EQUITIES_SUBDIR = "historical/equities"
CRYPTO_SUBDIR = "historical/crypto"
# NOTE: minute bars are NOT yet on the resolver's path — readers expect
# equities/<SYM>/<SYM>_1m_<YYYY>_<MM>.parquet. Daily was the reported blocker.
MINUTE_SUBDIR = "historical/minute"
ARCHIVE_DIRNAME = "_archive"
CRYPTO = {"ETHUSD","BTCUSD","SOLUSD"}
ALPACA_KEY_ENVS = ["APCA_API_KEY_ID","ALPACA_API_KEY","ALPACA_API_KEY_ID"]
ALPACA_SEC_ENVS = ["APCA_API_SECRET_KEY","ALPACA_API_SECRET","ALPACA_SECRET_KEY"]
STD_COLS = ["timestamp","open","high","low","close","volume"]

def _norm_symbol(symbol, source):
    s = symbol.upper().replace("/","")
    if s in CRYPTO and source == "alpaca":  return f"{s[:-3]}/USD"
    if s in CRYPTO and source == "yfinance": return f"{s[:-3]}-USD"
    return s

def _is_crypto(symbol): return symbol.upper().replace("/","") in CRYPTO

def _creds():
    key = next((os.environ[e] for e in ALPACA_KEY_ENVS if os.environ.get(e)), None)
    sec = next((os.environ[e] for e in ALPACA_SEC_ENVS if os.environ.get(e)), None)
    if not key or not sec:
        raise SystemExit("ERROR: Alpaca creds not in env ("
                         f"{ALPACA_KEY_ENVS}/{ALPACA_SEC_ENVS}). Or use --source yfinance.")
    return key, sec

def _daily_dir(root: Path, canon: str) -> Path:
    """Directory the 1D resolver globs for this symbol."""
    return root / (CRYPTO_SUBDIR if _is_crypto(canon) else EQUITIES_SUBDIR) / canon

def _daily_name(canon: str, first: str, last: str) -> str:
    """<SYM>_1D_<start>_<end>.parquet, stamped with the ACTUAL bar range."""
    return f"{canon}_1D_{first}_{last}.parquet"

def _archive_stale_1d(dest_dir: Path, canon: str, keep: str, dry: bool) -> list[str]:
    """Move other <SYM>_1D_*.parquet aside — readers concat every glob match, so
    leaving two would silently blend sources. Archived, never deleted."""
    stale = sorted(p for p in dest_dir.glob(f"{canon}_1D_*.parquet") if p.name != keep)
    if not stale:
        return []
    moved = []
    for p in stale:
        if dry:
            print(f"  [dry-run] would archive {p.name} -> {ARCHIVE_DIRNAME}/")
        else:
            (dest_dir / ARCHIVE_DIRNAME).mkdir(parents=True, exist_ok=True)
            p.replace(dest_dir / ARCHIVE_DIRNAME / p.name)
            side = p.with_suffix(p.suffix + ".manifest.json")
            if side.exists():
                side.replace(dest_dir / ARCHIVE_DIRNAME / side.name)
            print(f"  archived {p.name} -> {ARCHIVE_DIRNAME}/ (superseded)")
        moved.append(p.name)
    return moved

def _preflight(root: Path):
    t = root / EQUITIES_SUBDIR
    try:
        t.mkdir(parents=True, exist_ok=True)
        p = t / "._writetest"; p.write_text("ok"); p.unlink()
    except PermissionError:
        raise SystemExit(f"ERROR: {root} not writable as {os.environ.get('USER','?')}. "
            "NTFS mounted as root. Fix /etc/fstab:\n  UUID=267ED1667ED12F75 /mnt/tick-storage "
            "ntfs-3g uid=1000,gid=1000,umask=022,nofail 0 0\nthen sudo mount -a")
    except OSError as e:
        raise SystemExit(f"ERROR: cannot write {root} ({e}). If read-only: sudo ntfsfix /dev/sdb2")

def _fetch_alpaca(symbol, timeframe, start, end):
    import pandas as pd
    from alpaca.data.timeframe import TimeFrame
    tf = TimeFrame.Day if timeframe=="daily" else TimeFrame.Minute
    if _is_crypto(symbol.replace("/","")):
        from alpaca.data.historical import CryptoHistoricalDataClient
        from alpaca.data.requests import CryptoBarsRequest
        c = CryptoHistoricalDataClient()
        bars = c.get_crypto_bars(CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=tf, start=start, end=end))
    else:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        k,s = _creds(); c = StockHistoricalDataClient(k,s)
        bars = c.get_stock_bars(StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, start=start, end=end))
    df = bars.df
    if df is None or df.empty: return pd.DataFrame(columns=STD_COLS)
    df = df.reset_index()
    tsc = "timestamp" if "timestamp" in df.columns else df.columns[1]
    df = df.rename(columns={tsc:"timestamp"})
    return df[["timestamp","open","high","low","close","volume"]]

def _fetch_yf(symbol, timeframe, start, end):
    import pandas as pd, yfinance as yf
    if timeframe=="minute":
        raise SystemExit("yfinance minute history ~30d only; use --source alpaca for minute.")
    d = yf.download(symbol, start=start.date().isoformat(), end=end.date().isoformat(),
                    interval="1d", auto_adjust=False, progress=False)
    if d is None or d.empty: return pd.DataFrame(columns=STD_COLS)
    d = d.reset_index()
    if isinstance(d.columns, pd.MultiIndex): d.columns = [c[0] for c in d.columns]
    d = d.rename(columns={"Date":"timestamp","Datetime":"timestamp","Open":"open",
                          "High":"high","Low":"low","Close":"close","Volume":"volume"})
    df = d[["timestamp","open","high","low","close","volume"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df

def _normalize(df):
    import pandas as pd
    if df.empty: return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.dropna(subset=["timestamp"]).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _write(df, out: Path, meta, dry):
    if dry: print(f"  [dry-run] would write {len(df):>6} rows -> {out}"); return
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, engine="pyarrow", index=False)
    out.with_suffix(out.suffix+".manifest.json").write_text(json.dumps(meta, indent=2, default=str))

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="+", default=["SPY","IWM","ETHUSD"])
    p.add_argument("--timeframe", choices=["daily","minute"], default="daily")
    p.add_argument("--source", choices=["alpaca","yfinance"], default="alpaca")
    p.add_argument("--start", default="2000-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--root", default=DEFAULT_ROOT)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    root = Path(a.root); _preflight(root)
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc) if a.end else datetime.now(timezone.utc)
    fetch = {"alpaca":_fetch_alpaca,"yfinance":_fetch_yf}[a.source]
    print(f"Seeding {a.timeframe} | source={a.source} | {start.date()}->{end.date()} | root={root}\n")
    rows_out=[]
    for canon in [s.upper().replace("/","") for s in a.symbols]:
        try:
            df = _normalize(fetch(_norm_symbol(canon,a.source), a.timeframe, start, end))
        except SystemExit: raise
        except Exception as e:
            print(f"  {canon:8s} FAILED: {type(e).__name__}: {e}"); rows_out.append((canon,a.source,0,"-","-")); continue
        if df.empty:
            print(f"  {canon:8s} no data"); rows_out.append((canon,a.source,0,"-","-")); continue
        c0,c1 = df['timestamp'].min().date(), df['timestamp'].max().date()
        meta={"source":a.source,"symbol":canon,"timeframe":a.timeframe,"rows":int(len(df)),
              "start":str(c0),"end":str(c1),"fetched_at":datetime.now(timezone.utc).isoformat()}
        if a.timeframe=="daily":
            dest = _daily_dir(root, canon); name = _daily_name(canon, str(c0), str(c1))
            _write(df, dest/name, meta, a.dry_run)
            _archive_stale_1d(dest, canon, name, a.dry_run)
        else:
            df["_yr"]=df["timestamp"].dt.year
            for yr,g in df.groupby("_yr"):
                _write(g.drop(columns="_yr"), root/MINUTE_SUBDIR/canon/f"{yr}.parquet", dict(meta,year=int(yr),rows=int(len(g))), a.dry_run)
        rows_out.append((canon,a.source,len(df),str(c0),str(c1)))
    print("\n"+"="*66)
    print(f"{'SYMBOL':8s}{'SOURCE':10s}{'ROWS':>8s}{'START':>13s}{'END':>13s}")
    for sym,src,r,s0,s1 in rows_out: print(f"{sym:8s}{src:10s}{r:>8d}{s0:>13s}{s1:>13s}")
    print("="*66)
    if a.source=="alpaca" and any(r[3]!="-" and r[3]>="2016" for r in rows_out):
        print("\nNOTE: Alpaca equities start ~2016. For SPY back to 1993 use --source yfinance.")
    print("\nNext: run STRICT -> python3 scripts/backtest_hmm_switching.py")

if __name__=="__main__": main()
