"""
Quote provider abstraction.

Yields a bid/ask/mid for a given contract at a given timestamp. Two backends,
tried in order of fidelity:

  1. :class:`AlpacaOptionQuoteProvider` — REAL historical premium via Alpaca
     ``OptionHistoricalDataClient`` (bars/quotes). Preferred; captures theta and
     IV changes automatically. Requires credentials + network egress.
  2. :class:`BlackScholesQuoteProvider` — reconstructs premium from the
     underlying + IV estimate when real data is missing. Labeled ``bs``.

The engine calls :meth:`get_quote` and records the returned ``priced_via`` on
every trade so fallback-priced fills are auditable.

bid/ask/mid convention mirrors ``options_executor.get_option_quote``:
``mid = round((bid + ask) / 2, 2)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from .contracts import Contract
from .pricing import bs_price, iv_estimate


@dataclass
class Quote:
    bid: float
    ask: float
    priced_via: str  # "real" | "bs"

    @property
    def mid(self) -> float:
        # options_executor.get_option_quote convention.
        return round((self.bid + self.ask) / 2, 2)

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)


class BlackScholesQuoteProvider:
    """Synthesize a bid/ask around a Black-Scholes mid.

    half_spread = max(tick, spread_frac * mid); bid/ask straddle the BS mid.
    """

    def __init__(self, cfg):
        self.cfg = cfg

    def get_quote(self, contract: Contract, underlying_price: float,
                  ts: datetime) -> Optional[Quote]:
        t_years = max((contract.expiry - ts.date()).days, 0) / 365.0
        # Include the intraday fraction so theta decays within the day too.
        intraday_frac = (
            (16 * 60 - (ts.hour * 60 + ts.minute)) / (6.5 * 60) if t_years >= 0 else 0
        )
        t_years = max(t_years + max(0.0, intraday_frac) / 365.0, 0.0)

        iv = iv_estimate(self.cfg.base_iv, underlying_price, contract.strike, t_years)
        mid = bs_price(
            S=underlying_price,
            K=contract.strike,
            t_years=t_years,
            iv=iv,
            r=self.cfg.risk_free_rate,
            option_type=contract.option_type,
        )
        if mid <= 0:
            # Expired / far OTM worthless — model a nominal 1-tick bid at most.
            return Quote(bid=0.0, ask=self.cfg.tick_size, priced_via="bs")

        half = max(self.cfg.tick_size, self.cfg.spread_frac * mid)
        bid = max(0.0, round(mid - half, 2))
        ask = round(mid + half, 2)
        return Quote(bid=bid, ask=ask, priced_via="bs")


class AlpacaOptionQuoteProvider:
    """Real historical option quotes via Alpaca OptionHistoricalDataClient.

    Falls back to the wrapped BS provider for any (contract, ts) that Alpaca
    has no data for, so a run is never blocked by a single missing bar.
    """

    def __init__(self, cfg, api_key: str, api_secret: str, fallback: BlackScholesQuoteProvider):
        from alpaca.data.historical import OptionHistoricalDataClient

        self.cfg = cfg
        self.fallback = fallback
        self._client = OptionHistoricalDataClient(api_key, api_secret)
        self._cache: dict = {}

    def get_quote(self, contract: Contract, underlying_price: float,
                  ts: datetime) -> Optional[Quote]:
        try:
            bar = self._load_bar(contract.symbol, ts)
        except Exception:
            bar = None
        if bar is None:
            return self.fallback.get_quote(contract, underlying_price, ts)

        # Alpaca option bars are trade bars; synthesize a bid/ask around the
        # close using the same half-spread model as the BS provider so the two
        # sources are comparable. Real quote feed can be wired in the same way.
        mid = float(bar["close"])
        half = max(self.cfg.tick_size, self.cfg.spread_frac * mid)
        return Quote(
            bid=max(0.0, round(mid - half, 2)),
            ask=round(mid + half, 2),
            priced_via="real",
        )

    def _load_bar(self, symbol: str, ts: datetime):  # pragma: no cover - network
        from alpaca.data.requests import OptionBarsRequest
        from alpaca.data.timeframe import TimeFrame

        key = (symbol, ts.date())
        if key not in self._cache:
            req = OptionBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=datetime(ts.year, ts.month, ts.day),
            )
            bars = self._client.get_option_bars(req).df
            self._cache[key] = bars
        bars = self._cache[key]
        if bars is None or len(bars) == 0:
            return None
        # nearest bar at/just before ts
        try:
            sub = bars.xs(symbol, level="symbol")
        except Exception:
            sub = bars
        sub = sub[sub.index <= ts]
        if len(sub) == 0:
            return None
        return sub.iloc[-1]


def build_quote_provider(cfg, api_key: Optional[str], api_secret: Optional[str]):
    """Choose the best available provider. Returns (provider, source_label)."""
    bs = BlackScholesQuoteProvider(cfg)
    if api_key and api_secret:
        try:
            prov = AlpacaOptionQuoteProvider(cfg, api_key, api_secret, bs)
            return prov, "alpaca-real+bs-fallback"
        except Exception:
            pass
    return bs, "black-scholes"
