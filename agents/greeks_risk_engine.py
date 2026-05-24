"""
agents/greeks_risk_engine.py
────────────────────────────
Full circuit-breaker risk engine for options Greeks.
Replaces the stub that always returned APPROVE.

Circuit-breaker rules
---------------------
  RVOL < 2.5          → BLOCK  (RVOL_LOW)
  Gamma > 0.08        → BLOCK  (GAMMA_CIRCUIT_BREAKER)
  Gamma > 0.05        → REDUCE (size_scalar scaled down)
  Delta exposure > $2500 → BLOCK  (DELTA_LIMIT)
"""

import logging
from agents.greeks_calculator import GreeksCalculator

logger = logging.getLogger("GreeksRiskEngine")

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_DELTA_EXPOSURE   = 2500.0
GAMMA_ALERT_THRESHOLD = 0.05
GAMMA_BLOCK_THRESHOLD = 0.08
RVOL_MIN_THRESHOLD   = 2.5
BASE_POSITION_VALUE  = 2500.0


# ─────────────────────────────────────────────────────────────────────────────
class GreeksRiskEngine:
    """
    Evaluates Greeks-based risk and returns an action decision dict.

    Does NOT subclass BaseAgent — it is a pure, synchronous service object
    consumed by GreeksAgent.
    """

    def evaluate(
        self,
        signal: dict,
        greeks: dict,
        current_positions: list = None,
        kelly_sizing: dict = None,
    ) -> dict:
        """
        Evaluate Greeks risk and return a structured decision.

        Parameters
        ----------
        signal            : dict  — trading signal (action, confidence, …)
        greeks            : dict  — enriched Greeks dict from GreeksCalculator
        current_positions : list  — optional list of open positions (reserved)
        kelly_sizing      : dict  — optional Kelly output with 'position_value'

        Returns
        -------
        dict with keys:
            action          "APPROVE" | "REDUCE" | "BLOCK"
            reason          str
            trigger         str
            size_scalar     float  0.0 – 1.0
            position_value  float
            trade_mode      str
            iv_rank         float
            gamma           float
            delta           float
            rvol            float
            alerts          list[str]
        """

        # ── STEP 1: Extract Greeks ─────────────────────────────────────────
        gamma            = float(greeks.get("gamma", 0.0))
        delta            = float(greeks.get("delta", 0.0))
        iv_rank          = float(greeks.get("iv_rank", 50.0))
        rvol             = float(greeks.get("rvol", 1.0))
        underlying_price = float(greeks.get("underlying_price", 0.0))
        alerts: list[str] = []

        action      = "APPROVE"
        reason      = None
        trigger     = None
        size_scalar = 1.0

        # ── STEP 2: RVOL filter ────────────────────────────────────────────
        if rvol < RVOL_MIN_THRESHOLD:
            logger.warning(
                "RVOL_LOW: %.2f < %.2f — BLOCK", rvol, RVOL_MIN_THRESHOLD
            )
            return self._build_result(
                action="BLOCK",
                reason=f"Insufficient volume — RVOL {rvol:.2f}x below minimum {RVOL_MIN_THRESHOLD:.1f}x",
                trigger="RVOL_LOW",
                size_scalar=0.0,
                position_value=0.0,
                trade_mode=self._calc().get_trade_mode(iv_rank),
                iv_rank=iv_rank,
                gamma=gamma,
                delta=delta,
                rvol=rvol,
                alerts=alerts,
            )

        # ── STEP 3: Gamma circuit breaker ──────────────────────────────────
        if gamma > GAMMA_BLOCK_THRESHOLD:
            logger.warning(
                "GAMMA_CIRCUIT_BREAKER: %.4f > %.4f — BLOCK",
                gamma, GAMMA_BLOCK_THRESHOLD,
            )
            return self._build_result(
                action="BLOCK",
                reason=(
                    f"Gamma {gamma:.4f} exceeds block threshold "
                    f"{GAMMA_BLOCK_THRESHOLD}"
                ),
                trigger="GAMMA_CIRCUIT_BREAKER",
                size_scalar=0.0,
                position_value=0.0,
                trade_mode=self._calc().get_trade_mode(iv_rank),
                iv_rank=iv_rank,
                gamma=gamma,
                delta=delta,
                rvol=rvol,
                alerts=alerts,
            )

        if gamma > GAMMA_ALERT_THRESHOLD:
            action      = "REDUCE"
            size_scalar = max(0.1, 1.0 - (gamma / GAMMA_BLOCK_THRESHOLD))
            alerts.append(
                f"⚠️ High Gamma {gamma:.4f} — position reduced to "
                f"{size_scalar * 100:.0f}%"
            )
            logger.info(
                "GAMMA_ALERT: %.4f > %.4f — REDUCE to %.0f%%",
                gamma, GAMMA_ALERT_THRESHOLD, size_scalar * 100,
            )
        else:
            action      = "APPROVE"
            size_scalar = 1.0

        # ── STEP 4: Delta exposure check ───────────────────────────────────
        # delta_exposure = dollar sensitivity of ONE contract position
        # = |delta| × underlying_price  (×100 is a portfolio multiplier, applied upstream)
        if underlying_price > 0:
            delta_exposure = abs(delta * underlying_price)
            if delta_exposure > MAX_DELTA_EXPOSURE:
                logger.warning(
                    "DELTA_LIMIT: $%.0f > $%.0f — BLOCK",
                    delta_exposure, MAX_DELTA_EXPOSURE,
                )
                return self._build_result(
                    action="BLOCK",
                    reason=(
                        f"Delta exposure ${delta_exposure:.0f} exceeds "
                        f"${MAX_DELTA_EXPOSURE:.0f} limit"
                    ),
                    trigger="DELTA_LIMIT",
                    size_scalar=0.0,
                    position_value=0.0,
                    trade_mode=self._calc().get_trade_mode(iv_rank),
                    iv_rank=iv_rank,
                    gamma=gamma,
                    delta=delta,
                    rvol=rvol,
                    alerts=alerts,
                )

        # ── STEP 5: IV Rank trade mode ─────────────────────────────────────
        trade_mode = self._calc().get_trade_mode(iv_rank)

        if iv_rank < 25:
            alerts.append(f"🎯 IV Rank {iv_rank:.0f} — LONG GAMMA mode")
        elif iv_rank > 75:
            alerts.append(f"💰 IV Rank {iv_rank:.0f} — SHORT PREMIUM mode")

        # ── STEP 6: Kelly override ─────────────────────────────────────────
        if kelly_sizing and kelly_sizing.get("position_value"):
            position_value = float(kelly_sizing["position_value"]) * size_scalar
        else:
            position_value = BASE_POSITION_VALUE * size_scalar

        # ── STEP 7: Return result ──────────────────────────────────────────
        return self._build_result(
            action=action,
            reason=reason or "Risk within acceptable limits",
            trigger=trigger or "NONE",
            size_scalar=size_scalar,
            position_value=position_value,
            trade_mode=trade_mode,
            iv_rank=iv_rank,
            gamma=gamma,
            delta=delta,
            rvol=rvol,
            alerts=alerts,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_result(
        action: str,
        reason: str,
        trigger: str,
        size_scalar: float,
        position_value: float,
        trade_mode: str,
        iv_rank: float,
        gamma: float,
        delta: float,
        rvol: float,
        alerts: list,
    ) -> dict:
        return {
            "action":         action,
            "reason":         reason,
            "trigger":        trigger,
            "size_scalar":    size_scalar,
            "position_value": position_value,
            "trade_mode":     trade_mode,
            "iv_rank":        iv_rank,
            "gamma":          gamma,
            "delta":          delta,
            "rvol":           rvol,
            "alerts":         alerts,
        }

    @staticmethod
    def _calc() -> GreeksCalculator:
        """Return a lightweight GreeksCalculator (used only for get_trade_mode)."""
        return GreeksCalculator()

    # ── Telegram helpers ──────────────────────────────────────────────────────

    def should_alert_telegram(self, risk_decision: dict) -> bool:
        """Return True when the decision warrants a Telegram notification."""
        if risk_decision.get("action") == "BLOCK":
            return True
        if risk_decision.get("trigger") == "GAMMA_CIRCUIT_BREAKER":
            return True
        iv_rank = risk_decision.get("iv_rank", 50.0)
        if iv_rank < 25 or iv_rank > 75:
            return True
        if risk_decision.get("rvol", 1.0) > 5.0:
            return True
        return False

    def format_telegram_alert(
        self,
        risk_decision: dict,
        symbol: str,
    ) -> str:
        """Format a Greeks risk alert for Telegram."""
        action         = risk_decision.get("action", "?")
        trigger        = risk_decision.get("trigger", "NONE")
        gamma          = risk_decision.get("gamma", 0.0)
        delta          = risk_decision.get("delta", 0.0)
        iv_rank        = risk_decision.get("iv_rank", 50.0)
        rvol           = risk_decision.get("rvol", 1.0)
        trade_mode     = risk_decision.get("trade_mode", "NEUTRAL")
        position_value = risk_decision.get("position_value", 0.0)
        size_scalar    = risk_decision.get("size_scalar", 0.0)

        return (
            f"🚨 Greeks Alert: {symbol}\n"
            f"Action: {action} | Trigger: {trigger}\n"
            f"Gamma: {gamma:.4f} | Delta: {delta:.4f}\n"
            f"IV Rank: {iv_rank:.0f} | RVOL: {rvol:.1f}x\n"
            f"Mode: {trade_mode}\n"
            f"Position: ${position_value:.0f} ({size_scalar * 100:.0f}% of base)"
        )
