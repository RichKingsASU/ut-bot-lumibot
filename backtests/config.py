"""
Backtest configuration.

Centralizes every tunable knob for the options backtest harness. Production
defaults are pulled from the repo's ``config.py`` so the backtest honors the
same risk/selection settings the live bot uses (``MAX_TRADES_PER_DAY``,
``MAX_POSITION_SIZE``, ``OPTION_STRIKE_STEP``, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional

# Pull production risk / option settings so the backtest matches live behavior.
# Import is defensive: the harness must run even if the repo's config import
# chain (dotenv, etc.) is unavailable in a bare environment.
try:  # pragma: no cover - trivial import guard
    import config as _prod_config

    _MAX_TRADES_PER_DAY = int(_prod_config.MAX_TRADES_PER_DAY)
    _MAX_POSITION_SIZE = int(_prod_config.MAX_POSITION_SIZE)
    _OPTION_STRIKE_STEP = float(_prod_config.OPTION_STRIKE_STEP)
    _OPTION_MAX_DTE_FALLBACK = int(_prod_config.OPTION_MAX_DTE_FALLBACK)
except Exception:  # pragma: no cover
    _MAX_TRADES_PER_DAY = 10
    _MAX_POSITION_SIZE = 5
    _OPTION_STRIKE_STEP = 1.0
    _OPTION_MAX_DTE_FALLBACK = 7


# Production signal constants (from strategies/ut_bot.py header + parameters).
UT_ATR_PERIOD = 10
UT_SENSITIVITY = 1.0
UT_RSI_PERIOD = 14
UT_RSI_STEP_THRESH = 5.0
UT_STOP_PCT = 0.005  # 0.5% adverse move on the underlying
UT_EOD_FLATTEN = "15:55"  # ET flatten time


@dataclass
class BacktestConfig:
    """All parameters for a single backtest run."""

    # ── Universe / window ──────────────────────────────────────────────
    symbol: str = "IWM"
    timeframe: str = "15m"           # "5m" | "15m"
    start: date = date(2024, 6, 1)
    end: date = date(2026, 6, 1)

    # ── Contract selection (reuses options_executor rules) ─────────────
    dte: int = 4                     # target days-to-expiry (3-5)
    strike_mode: str = "ATM"         # ATM | ITM1 | ITM2 | ITM3 | OTM1..
    strike_step: float = _OPTION_STRIKE_STEP

    # ── Signal (production ut_bot.py — off-limits math) ────────────────
    atr_period: int = UT_ATR_PERIOD
    sensitivity: float = UT_SENSITIVITY
    rsi_period: int = UT_RSI_PERIOD
    rsi_step_thresh: float = UT_RSI_STEP_THRESH
    stop_pct: float = UT_STOP_PCT
    eod_flatten_time: str = UT_EOD_FLATTEN

    # ── Scalp exits (new, CLI-configurable) ────────────────────────────
    time_stop_min: int = 20          # hard time stop
    profit_target: float = 0.50      # +50% on premium
    premium_stop: float = 0.40       # -40% on premium

    # ── Risk / sizing (production config.py) ───────────────────────────
    max_trades_per_day: int = _MAX_TRADES_PER_DAY
    max_position_size: int = _MAX_POSITION_SIZE
    contracts: int = 1               # contracts per trade (<= max_position_size)

    # ── Cost model ─────────────────────────────────────────────────────
    tick_size: float = 0.01          # option quote tick
    slippage_ticks: float = 1.0      # extra haircut beyond the spread
    spread_frac: float = 0.0075      # BS half-spread as fraction of mid
    commission_per_contract: float = 0.0

    # ── Black-Scholes fallback pricing ─────────────────────────────────
    risk_free_rate: float = 0.04
    base_iv: float = 0.20            # RVX-proxy annualized IV for IWM

    # ── Data plumbing ──────────────────────────────────────────────────
    data_store: str = "/mnt/tick-storage/historical/equities"
    cache_dir: str = "backtests/cache"
    results_dir: str = "backtests/results"
    allow_synthetic: bool = False     # last-resort synthetic underlying
    use_questdb: bool = False
    questdb_url: str = "http://localhost:9000"

    # ── Runtime-populated labels (not user input) ──────────────────────
    underlying_source: str = field(default="", compare=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d

    @property
    def contract_multiplier(self) -> int:
        return 100

    @property
    def option_type(self) -> str:
        # Direction is per-trade; this is only a default helper.
        return "call"
