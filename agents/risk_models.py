from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional
from datetime import datetime

MAX_POSITION_VALUE = 2500.00
MAX_PORTFOLIO_RISK_PCT = 0.05
MAX_DAILY_LOSS = 5000.00
STALE_BAR_SECONDS_MARKET = 60
STALE_BAR_SECONDS_AFTERHOURS = 3600

class PositionSizeModel(BaseModel):
    symbol: str
    asset_class: Literal['crypto', 'equities']
    proposed_position_value: float = Field(..., ge=0)
    account_equity: float = Field(..., gt=0)
    verdict: str

    @field_validator('proposed_position_value')
    @classmethod
    def enforce_max_position(cls, v):
        if v > MAX_POSITION_VALUE:
            raise ValueError(f"Position ${v:.2f} exceeds hard cap ${MAX_POSITION_VALUE:.2f}")
        return v

    @model_validator(mode='after')
    def enforce_portfolio_risk(self):
        pct = self.proposed_position_value / self.account_equity
        if pct > MAX_PORTFOLIO_RISK_PCT:
            raise ValueError(f"Position is {pct:.1%} of equity — exceeds {MAX_PORTFOLIO_RISK_PCT:.0%} limit")
        return self

class MarketDataFreshnessModel(BaseModel):
    symbol: str
    last_bar_timestamp: datetime
    current_time: datetime
    is_market_hours: bool

    @model_validator(mode='after')
    def enforce_freshness(self):
        age = (self.current_time - self.last_bar_timestamp).total_seconds()
        threshold = STALE_BAR_SECONDS_MARKET if self.is_market_hours else STALE_BAR_SECONDS_AFTERHOURS
        if age > threshold:
            raise ValueError(f"STALE DATA: {self.symbol} last bar is {int(age)}s old (threshold: {threshold}s)")
        return self

class DailyLossGuardModel(BaseModel):
    current_equity: float = Field(..., gt=0)
    start_of_day_equity: float = Field(..., gt=0)

    @model_validator(mode='after')
    def enforce_daily_loss(self):
        loss = self.start_of_day_equity - self.current_equity
        if loss > MAX_DAILY_LOSS:
            raise ValueError(f"DAILY LOSS LIMIT: Lost ${loss:.2f} today (limit: ${MAX_DAILY_LOSS:.2f})")
        return self
