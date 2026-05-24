import asyncio
import json
import logging
import os
import httpx
from datetime import datetime, timezone
from agents.base_agent import BaseAgent

logger = logging.getLogger("RiskAgent")


class RiskAgent(BaseAgent):
    def __init__(self, name="RiskAgent", qdrant_host="localhost", qdrant_port=6333, nats_url=None):
        super().__init__(name, qdrant_host, qdrant_port)

        is_docker = os.path.exists("/.dockerenv")
        default_nats = "nats://nats:4222" if is_docker else "nats://localhost:4222"
        self.nats_url = nats_url or os.getenv("NATS_URL") or default_nats

    async def analyze(self, signal_recommendation: dict) -> dict:
        """Evaluate risk for a given signal_recommendation and return a risk_decision dict.

        Args:
            signal_recommendation: dict produced by SignalAgent.analyze(), expected to contain:
                - action: str
                - confidence: "HIGH"|"MEDIUM"|"LOW"
                - sentiment_score: float
                - technical_signal: str
                - reasoning: str

        Returns:
            {
                decision: "APPROVE"|"REDUCE"|"BLOCK",
                reason: str,
                exposure_pct: float,
                buying_power: float,
                recommended_size_pct: float
            }
        """
        logger.info("RiskAgent.analyze() started.")

        alpaca_headers = {
            "APCA-API-KEY-ID": self.alpaca_api_key or "",
            "APCA-API-SECRET-KEY": self.alpaca_api_secret or "",
        }
        base_url = self.alpaca_base_url

        # ── Step 1: GET /v2/account ────────────────────────────────────────────
        equity = 0.0
        buying_power = 0.0
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{base_url}/v2/account",
                    headers=alpaca_headers
                )
                resp.raise_for_status()
                account_data = resp.json()
                equity = float(account_data.get("equity", 0.0))
                buying_power = float(account_data.get("buying_power", 0.0))
                logger.info(f"Account → equity={equity:.2f}, buying_power={buying_power:.2f}")
        except Exception as e:
            logger.error(f"Failed to fetch Alpaca account: {e}")

        # ── Step 2: GET /v2/positions ──────────────────────────────────────────
        total_market_value = 0.0
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{base_url}/v2/positions",
                    headers=alpaca_headers
                )
                resp.raise_for_status()
                positions = resp.json()
                if isinstance(positions, list):
                    for pos in positions:
                        mv = pos.get("market_value")
                        if mv is not None:
                            total_market_value += float(mv)
            logger.info(f"Total market value across positions: {total_market_value:.2f}")
        except Exception as e:
            logger.error(f"Failed to fetch Alpaca positions: {e}")

        # ── Step 3: Calculate exposure_pct ────────────────────────────────────
        if equity > 0:
            exposure_pct = total_market_value / equity
        else:
            exposure_pct = 0.0

        logger.info(f"Exposure: {exposure_pct:.4f} ({exposure_pct * 100:.2f}%)")

        # ── Step 4: Apply risk rules ───────────────────────────────────────────
        confidence = str(signal_recommendation.get("confidence", "MEDIUM")).upper()

        if exposure_pct > 0.80:
            decision = "BLOCK"
            reason = "Overexposed"
            recommended_size_pct = 0.0
        elif buying_power < 1000.0:
            decision = "BLOCK"
            reason = "Insufficient capital"
            recommended_size_pct = 0.0
        elif confidence == "LOW":
            decision = "REDUCE"
            reason = f"Low confidence signal ({signal_recommendation.get('technical_signal', 'N/A')}); reducing position size."
            recommended_size_pct = 0.5
        else:
            decision = "APPROVE"
            reason = (
                f"Risk within acceptable limits — exposure={exposure_pct:.2%}, "
                f"buying_power={buying_power:.2f}, confidence={confidence}."
            )
            recommended_size_pct = 1.0

        risk_decision = {
            "decision": decision,
            "reason": reason,
            "exposure_pct": round(exposure_pct, 6),
            "buying_power": round(buying_power, 2),
            "recommended_size_pct": recommended_size_pct,
        }

        logger.info(f"Risk decision → {risk_decision}")

        # ── Step 5: Publish to NATS agents.risk_decision ──────────────────────
        try:
            import nats
            nc = await nats.connect(self.nats_url)
            await nc.publish(
                "agents.risk_decision",
                json.dumps(risk_decision).encode("utf-8")
            )
            await nc.close()
            logger.info("Published risk_decision to NATS 'agents.risk_decision'.")
        except Exception as e:
            logger.error(f"Failed to publish risk_decision to NATS: {e}")

        return risk_decision
