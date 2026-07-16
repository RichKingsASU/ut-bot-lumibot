"""
agents/greeks_agent.py
──────────────────────
Async Greeks scanning agent.

For each watched symbol the agent:
  1. Reads the live option chain from OptionDataWorker's in-memory cache.
  2. Calculates full Greeks via GreeksCalculator.calculate_batch().
  3. Runs circuit-breaker evaluation via GreeksRiskEngine.evaluate().
  4. Scores each opportunity with score_opportunity().
  5. Persists the ATM contract snapshot to Supabase (greeks_snapshots).
  6. Publishes the enriched Greeks to NATS subject greeks.{symbol}.
  7. Fires a Telegram alert when GreeksRiskEngine.should_alert_telegram() is True.

Returns a greeks_summary dict on every call to analyze().
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from agents.base_agent import BaseAgent
from agents.greeks_calculator import GreeksCalculator
from agents.greeks_risk_engine import GreeksRiskEngine, GAMMA_ALERT_THRESHOLD

load_dotenv()

logger = logging.getLogger("GreeksAgent")

# ── Env ───────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
SUPABASE_URL       = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY       = (
    os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
)
NATS_URL           = os.getenv("NATS_URL", "nats://localhost:4222")

# ── NATS shared connection ────────────────────────────────────────────────────
_nc = None


async def _get_nats():
    """Lazily connect to NATS and return the connection (or None on failure)."""
    global _nc
    if _nc is not None and not _nc.is_closed:
        return _nc
    try:
        import nats
        _nc = await nats.connect(
            NATS_URL,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )
        logger.info("GreeksAgent connected to NATS at %s", NATS_URL)
    except Exception as exc:
        logger.error("NATS connect failed: %s", exc)
        _nc = None
    return _nc


async def _nats_publish(subject: str, data: dict) -> None:
    """Best-effort NATS publish."""
    nc = await _get_nats()
    if nc is None:
        return
    try:
        await nc.publish(subject, json.dumps(data).encode("utf-8"))
    except Exception as exc:
        logger.error("NATS publish to %s failed: %s", subject, exc)


# ── Telegram helper ───────────────────────────────────────────────────────────

async def _send_telegram(message: str) -> None:
    """Fire a Telegram message (best-effort)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram credentials not set — skipping alert")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
class GreeksAgent(BaseAgent):
    """
    Async agent that scans the Greeks for a list of symbols, applies circuit-
    breaker risk rules, scores trading opportunities, and publishes results.
    """

    def __init__(self, name: str, asset_class: str = "equities"):
        super().__init__(name)
        self.asset_class  = asset_class
        self.calculator   = GreeksCalculator()
        self.risk_engine  = GreeksRiskEngine()

        if asset_class == "equities":
            self.symbols = [
                "SPY", "QQQ", "IWM",
                "NVDA", "TSLA", "AAPL",
                "MSFT", "META", "GOOGL",
            ]
        else:
            self.symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]

    # ── Main entry point ──────────────────────────────────────────────────────

    async def analyze(self) -> dict:
        """
        Scan all watched symbols and return a greeks_summary dict.

        greeks_summary keys
        -------------------
        symbols_scanned           int
        high_gamma_alerts         list[str]
        iv_rank_alerts            list[str]
        circuit_breakers_triggered list[str]
        top_opportunities         list[dict]  — sorted by score descending
        scan_timestamp            str         — ISO 8601 UTC
        """
        from collectors.option_data_worker import get_cached_greeks  # local import avoids circular

        symbols_scanned            = 0
        high_gamma_alerts          = []
        iv_rank_alerts             = []
        circuit_breakers_triggered = []
        opportunities              = []

        for symbol in self.symbols:
            try:
                # 1 ── Fetch cached chain ───────────────────────────────────
                cache_entry = get_cached_greeks(symbol)
                if cache_entry is None:
                    logger.warning(
                        "No cached chain for %s — worker may not have scanned yet",
                        symbol,
                    )
                    continue

                contracts        = cache_entry.get("contracts", [])
                underlying_price = float(cache_entry.get("underlying_price", 0.0))

                if not contracts:
                    logger.info("Empty contract list for %s — skipping", symbol)
                    continue

                symbols_scanned += 1

                # 2 ── Calculate Greeks for all contracts ───────────────────
                enriched = self.calculator.calculate_batch(
                    contracts=contracts,
                    underlying_price=underlying_price,
                    symbol=symbol,
                )
                if not enriched:
                    continue

                # 3 ── Find best ATM contract ───────────────────────────────
                atm = self._find_atm(enriched, underlying_price)
                if atm is None:
                    continue

                # Attach underlying price so risk engine can compute delta exposure
                atm_greeks = {**atm, "underlying_price": underlying_price}

                # 4 ── Risk evaluation ──────────────────────────────────────
                risk_decision = self.risk_engine.evaluate(
                    signal={"symbol": symbol},
                    greeks=atm_greeks,
                )

                action  = risk_decision.get("action", "APPROVE")
                trigger = risk_decision.get("trigger", "NONE")
                iv_rank = risk_decision.get("iv_rank", 50.0)
                gamma   = risk_decision.get("gamma", 0.0)

                # Collect alert categories
                if trigger == "GAMMA_CIRCUIT_BREAKER" or action == "BLOCK":
                    circuit_breakers_triggered.append(
                        f"{symbol}: {trigger} ({action})"
                    )
                if gamma > GAMMA_ALERT_THRESHOLD:
                    high_gamma_alerts.append(f"{symbol}: gamma={gamma:.4f}")
                if iv_rank < 25 or iv_rank > 75:
                    iv_rank_alerts.append(
                        f"{symbol}: iv_rank={iv_rank:.0f} "
                        f"({'LONG_GAMMA' if iv_rank < 25 else 'SHORT_PREMIUM'})"
                    )

                # 5 ── Telegram alert ───────────────────────────────────────
                if self.risk_engine.should_alert_telegram(risk_decision):
                    alert_msg = self.risk_engine.format_telegram_alert(
                        risk_decision, symbol
                    )
                    await _send_telegram(alert_msg)

                # 6 ── Persist snapshot to Supabase ────────────────────────
                await self._persist_snapshot(symbol, atm, risk_decision)

                # 7 ── Publish to NATS ──────────────────────────────────────
                await _nats_publish(
                    f"greeks.{symbol}",
                    {
                        "symbol":       symbol,
                        "greeks":       atm_greeks,
                        "risk":         risk_decision,
                        "timestamp":    datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Score and collect opportunity
                score = self.score_opportunity(symbol, atm_greeks, risk_decision)
                opportunities.append(
                    {
                        "symbol":        symbol,
                        "score":         score,
                        "action":        action,
                        "trade_mode":    risk_decision.get("trade_mode", "NEUTRAL"),
                        "iv_rank":       iv_rank,
                        "gamma":         gamma,
                        "rvol":          risk_decision.get("rvol", 1.0),
                        "position_value": risk_decision.get("position_value", 0.0),
                    }
                )

            except Exception as exc:
                logger.error("GreeksAgent error on %s: %s", symbol, exc, exc_info=True)
                continue

        top_opportunities = sorted(
            opportunities, key=lambda x: x["score"], reverse=True
        )

        summary = {
            "symbols_scanned":            symbols_scanned,
            "high_gamma_alerts":          high_gamma_alerts,
            "iv_rank_alerts":             iv_rank_alerts,
            "circuit_breakers_triggered": circuit_breakers_triggered,
            "top_opportunities":          top_opportunities,
            "scan_timestamp":             datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "Greeks scan complete — %d scanned, %d opportunities, "
            "%d circuit breakers",
            symbols_scanned,
            len(top_opportunities),
            len(circuit_breakers_triggered),
        )
        return summary

    # ── Opportunity scorer ────────────────────────────────────────────────────

    def score_opportunity(
        self,
        symbol: str,
        greeks: dict,
        risk_decision: dict,
    ) -> float:
        """
        Score an option opportunity on a 0–100 scale.

        Component weights
        -----------------
        RVOL component     30  pts  (capped at RVOL=5)
        IV Rank component  30  pts  (distance from 50 → extremes are high-scoring)
        Gamma component    20  pts  (capped at GAMMA_ALERT_THRESHOLD)
        Volume component   20  pts  (capped at 10 000 contracts)
        """
        rvol   = float(greeks.get("rvol",   1.0))
        iv_rank = float(greeks.get("iv_rank", 50.0))
        gamma  = float(greeks.get("gamma",  0.0))
        volume = int(greeks.get("volume",   0))

        score = 0.0
        score += min(rvol / 5.0, 1.0) * 30
        score += abs(iv_rank - 50.0) / 50.0 * 30
        score += min(gamma / GAMMA_ALERT_THRESHOLD, 1.0) * 20
        score += min(volume / 10_000, 1.0) * 20
        return round(score, 2)

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _find_atm(enriched: list, underlying_price: float) -> dict | None:
        """
        Return the contract whose strike is closest to the underlying price.
        Prefers calls when two contracts are equidistant.
        """
        if not enriched:
            return None
        if underlying_price <= 0:
            return enriched[0]
        return min(
            enriched,
            key=lambda c: (
                abs(float(c.get("strike", 0)) - underlying_price),
                0 if str(c.get("option_type", "")).lower() == "call" else 1,
            ),
        )

    async def _persist_snapshot(
        self,
        symbol: str,
        greeks: dict,
        risk_decision: dict,
    ) -> None:
        """
        Upsert the ATM contract Greeks snapshot into Supabase greeks_snapshots.
        Silently logs on failure — does not propagate.
        """
        if not SUPABASE_URL or not SUPABASE_KEY:
            return

        row = {
            "symbol":        symbol,
            "strike":        greeks.get("strike"),
            "expiry":        greeks.get("expiry"),
            "option_type":   greeks.get("option_type"),
            "delta":         greeks.get("delta"),
            "gamma":         greeks.get("gamma"),
            "theta":         greeks.get("theta"),
            "vega":          greeks.get("vega"),
            "iv":            greeks.get("iv"),
            "iv_rank":       greeks.get("iv_rank"),
            "rvol":          greeks.get("rvol"),
            "volume":        greeks.get("volume"),
            "trade_mode":    risk_decision.get("trade_mode"),
            "snapshot_at":   datetime.now(timezone.utc).isoformat(),
        }

        from common.safe_write import safe_write_async
        ok = await safe_write_async(
            "greeks_snapshots", row, "greeks-agent",
            method="post",
        )
        if ok:
            logger.debug("Snapshot persisted for %s", symbol)
