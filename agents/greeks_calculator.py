import os
import logging
from datetime import datetime, timezone, date
from typing import Optional

import mibian
import numpy as np
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("GreeksCalculator")

# ── Constants ─────────────────────────────────────────────────────────────────
RISK_FREE_RATE = 5.0   # percent, as expected by mibian

# ── Supabase / env ────────────────────────────────────────────────────────────
SUPABASE_URL      = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY      = (
    os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
)

# Parquet historical data root
TICK_STORAGE_ROOT = os.getenv(
    "TICK_STORAGE_ROOT", "/mnt/tick-storage/historical/equities"
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _zeros_dict(expiry_days: float = 0.0) -> dict:
    """Return a safe zero-value Greeks dict."""
    return {
        "delta":       0.0,
        "gamma":       0.0,
        "theta":       0.0,
        "vega":        0.0,
        "iv":          0.0,
        "expiry_days": expiry_days,
    }


# ─────────────────────────────────────────────────────────────────────────────
class GreeksCalculator:
    """
    Computes Black-Scholes Greeks via *mibian*, IV Rank from Supabase, and
    Relative Volume (RVOL) from Parquet tick-storage files.
    """

    # ── Core Black-Scholes ────────────────────────────────────────────────────

    def calculate(
        self,
        underlying_price: float,
        strike: float,
        expiry_days: float,
        option_price: float,
        option_type: str,
        risk_free_rate: float = RISK_FREE_RATE,
    ) -> dict:
        """
        Calculate Black-Scholes Greeks for a single option contract.

        Parameters
        ----------
        underlying_price : float
        strike           : float
        expiry_days      : float    calendar days until expiry (min 0.01)
        option_price     : float    mid price of the option
        option_type      : str      'call' or 'put'
        risk_free_rate   : float    annualised %, default 5.0

        Returns
        -------
        dict with keys: delta, gamma, theta, vega, iv, expiry_days
        """
        expiry_days = max(expiry_days, 0.01)
        option_type = option_type.lower().strip()

        try:
            bs_input = [underlying_price, strike, risk_free_rate, expiry_days]

            # Pass 1 — derive implied volatility from the market price
            if option_type == "call":
                iv_calc = mibian.BS(bs_input, callPrice=option_price)
            else:
                iv_calc = mibian.BS(bs_input, putPrice=option_price)

            implied_vol = iv_calc.impliedVolatility
            if implied_vol is None:
                raise ValueError("mibian could not solve for IV")

            # Pass 2 — compute all Greeks at the solved volatility
            g = mibian.BS(bs_input, volatility=implied_vol)

            if option_type == "call":
                delta = g.callDelta
                theta = g.callTheta
            else:
                delta = g.putDelta
                theta = g.putTheta

            return {
                "delta":       float(delta),
                "gamma":       float(g.gamma),
                "theta":       float(theta),
                "vega":        float(g.vega),
                "iv":          float(implied_vol),
                "expiry_days": expiry_days,
            }
        except Exception as exc:
            logger.warning(
                "Greeks calculation failed (ul=%.2f, K=%.2f, days=%.2f, px=%.4f, type=%s): %s",
                underlying_price, strike, expiry_days, option_price, option_type, exc,
            )
            return _zeros_dict(expiry_days)

    # ── IV Rank ───────────────────────────────────────────────────────────────

    def calculate_iv_rank(
        self,
        symbol: str,
        current_iv: float,
        lookback_days: int = 30,
    ) -> float:
        """
        Query Supabase *greeks_snapshots* for the last *lookback_days* of IV data
        and return an IV Rank in [0, 100].

        Falls back to 50.0 (neutral) when fewer than 5 rows are available.
        """
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.warning("Supabase credentials not set — returning neutral IV rank")
            return 50.0

        url = f"{SUPABASE_URL}/rest/v1/greeks_snapshots"
        headers = {
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        params = {
            "select":      "iv",
            "symbol":      f"eq.{symbol}",
            "iv":          "not.is.null",
            "snapshot_at": f"gt.now()-interval '{lookback_days} days'",
            "limit":       1000,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                rows = resp.json()
        except Exception as exc:
            logger.error("Supabase IV rank query failed for %s: %s", symbol, exc)
            return 50.0

        ivs = []
        for row in rows:
            try:
                v = row.get("iv")
                if v is not None:
                    ivs.append(float(v))
            except (TypeError, ValueError):
                continue

        if len(ivs) < 5:
            logger.info(
                "Insufficient IV history for %s (%d rows) — returning neutral rank",
                symbol, len(ivs),
            )
            return 50.0

        min_iv = min(ivs)
        max_iv = max(ivs)
        if max_iv <= min_iv:
            return 50.0

        rank = (current_iv - min_iv) / (max_iv - min_iv) * 100.0
        return float(np.clip(rank, 0.0, 100.0))

    # ── Relative Volume ───────────────────────────────────────────────────────

    def calculate_rvol(
        self,
        symbol: str,
        current_volume: int,
    ) -> float:
        """
        Calculate Relative Volume vs. the 10-day average from Parquet files.

        Looks for ``*_1D_*.parquet`` files in:
            {TICK_STORAGE_ROOT}/{symbol}/

        Falls back to 1.0 (neutral) when no data is found.
        """
        import glob
        import pathlib

        symbol_dir = pathlib.Path(TICK_STORAGE_ROOT) / symbol
        pattern    = str(symbol_dir / "*_1D_*.parquet")
        files      = sorted(glob.glob(pattern))

        if not files:
            logger.info("No 1D parquet files found for %s — RVOL neutral", symbol)
            return 1.0

        try:
            import pandas as pd

            frames = [pd.read_parquet(f, columns=["volume"]) for f in files]
            combined = pd.concat(frames, ignore_index=True)

            if combined.empty or "volume" not in combined.columns:
                return 1.0

            avg_volume = float(combined["volume"].tail(10).mean())
            if avg_volume <= 0:
                return 1.0

            return float(current_volume) / avg_volume

        except Exception as exc:
            logger.warning("RVOL calculation failed for %s: %s", symbol, exc)
            return 1.0

    # ── Trade Mode ────────────────────────────────────────────────────────────

    def get_trade_mode(self, iv_rank: float) -> str:
        """
        Map IV Rank to a directional trade mode.

        < 25  → LONG_GAMMA      (cheap options, buy premium)
        > 75  → SHORT_PREMIUM   (expensive options, sell premium)
        else  → NEUTRAL
        """
        if iv_rank < 25:
            return "LONG_GAMMA"
        if iv_rank > 75:
            return "SHORT_PREMIUM"
        return "NEUTRAL"

    # ── Batch enrichment ──────────────────────────────────────────────────────

    def calculate_batch(
        self,
        contracts: list,
        underlying_price: float,
        symbol: str,
    ) -> list:
        """
        Enrich a list of option contract dicts with Greeks, IV Rank, and RVOL.

        Each input dict is expected to contain:
            strike, expiry (ISO date str), option_type, price, volume

        Returns a list of enriched dicts.
        """
        today = date.today()
        enriched: list[dict] = []

        for contract in contracts:
            try:
                expiry_str = contract.get("expiry", "")
                if expiry_str:
                    expiry_date = date.fromisoformat(expiry_str)
                    expiry_days = max((expiry_date - today).days, 0) + 0.01
                else:
                    expiry_days = 0.01

                greeks = self.calculate(
                    underlying_price=underlying_price,
                    strike=float(contract.get("strike", 0)),
                    expiry_days=expiry_days,
                    option_price=float(contract.get("price", 0)),
                    option_type=str(contract.get("option_type", "call")),
                )

                current_vol = int(contract.get("volume", 0))
                iv_rank = self.calculate_iv_rank(symbol, greeks["iv"])
                rvol    = self.calculate_rvol(symbol, current_vol)

                enriched.append({
                    # Identity
                    "symbol":      symbol,
                    "strike":      float(contract.get("strike", 0)),
                    "expiry":      expiry_str,
                    "option_type": str(contract.get("option_type", "")),
                    "volume":      current_vol,
                    # Greeks
                    **greeks,
                    # Derived metrics
                    "iv_rank":     iv_rank,
                    "rvol":        rvol,
                    "trade_mode":  self.get_trade_mode(iv_rank),
                })

            except Exception as exc:
                logger.error(
                    "Batch enrichment failed for contract %s: %s",
                    contract.get("symbol", "?"), exc,
                )
                continue

        return enriched
