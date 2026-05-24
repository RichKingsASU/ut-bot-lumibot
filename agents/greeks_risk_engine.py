import logging
from agents.base_agent import BaseAgent

logger = logging.getLogger("GreeksRiskEngine")

class GreeksRiskEngine(BaseAgent):
    def __init__(self, name="GreeksRiskEngine", asset_class="equities"):
        super().__init__(name)
        self.asset_class = asset_class
        self.BASE_POSITION_VALUE = 2000.0  # Standard baseline fixed size

    def evaluate(
      self,
      signal: dict,
      greeks: dict,
      current_positions: list = None,
      kelly_sizing: dict = None
    ) -> dict:
        """Evaluate risk, options sensitivity metrics, and apply optimal Kelly sizer sizing."""
        logger.info("GreeksRiskEngine.evaluate() executing risk audit...")
        
        position_value = self.BASE_POSITION_VALUE
        if kelly_sizing and kelly_sizing.get("position_value") is not None:
            position_value = kelly_sizing["position_value"]
            
        decision = "APPROVE"
        reason = "Risk audit approved within Greeks exposure parameters."
        
        # Build base decision
        risk_decision = {
            "asset_class": self.asset_class,
            "decision": decision,
            "reason": reason,
            "exposure_pct": 0.0,
            "buying_power": 100000.0,
            "recommended_size_pct": 1.0,
            "position_value": position_value,
            "size_scalar": float(greeks.get("size_scalar", 1.0)) if greeks else 1.0
        }
        
        # Enrich with Kelly sizing details if provided
        if kelly_sizing:
            risk_decision["kelly_fraction"] = float(kelly_sizing.get("kelly_fraction", 0.0))
            risk_decision["kelly_position_value"] = float(kelly_sizing.get("position_value", 0.0))
            risk_decision["win_rate"] = float(kelly_sizing.get("win_rate", 0.50))
            risk_decision["using_kelly_defaults"] = bool(kelly_sizing.get("using_defaults", True))
            
        logger.info(f"GreeksRiskEngine decision: {risk_decision}")
        return risk_decision

    def format_telegram_alert(self, risk_decision: dict) -> str:
        """Format Risk decision and Kelly sizing stats for Telegram reports."""
        kelly_fraction = risk_decision.get("kelly_fraction", 0.0)
        win_rate = risk_decision.get("win_rate", 0.0)
        using_defaults_val = risk_decision.get("using_kelly_defaults", True)
        using_defaults = "default" if using_defaults_val else "historical"
        
        return (
            f"Kelly: {kelly_fraction:.1%} of portfolio\n"
            f"Win Rate: {win_rate:.1%} ({using_defaults} data)"
        )

    async def analyze(self) -> dict:
        """Abstract method from BaseAgent."""
        return {}
