import os
import httpx
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

logger = logging.getLogger("KellySizer")
load_dotenv()

class KellySizer:
  KELLY_FRACTION = 0.25    # Use 25% Kelly (conservative)
  MIN_TRADES_REQUIRED = 10 # Need at least 10 trades to calculate
  DEFAULT_WIN_RATE = 0.50  # Default until enough data
  DEFAULT_PAYOUT = 1.5     # Default avg win/loss ratio
  MAX_POSITION_PCT = 0.20  # Never more than 20% of portfolio
  MIN_POSITION_PCT = 0.02  # Never less than 2% of portfolio
  BASE_PORTFOLIO = 107879  # Starting portfolio value (update from Alpaca)

  def __init__(self):
    self.supabase_url = os.getenv('SUPABASE_URL')
    self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    self.alpaca_api_key = os.getenv('ALPACA_API_KEY')
    self.alpaca_api_secret = os.getenv('ALPACA_API_SECRET')
    self.alpaca_base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

  async def get_historical_performance(
    self,
    symbol: str,
    lookback_days: int = 30,
    asset_class: str = None
  ) -> dict:
    """Query trade_performance table for recent trades and calculate stats."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    
    # Try both Cloud and Local Supabase
    targets = []
    if self.supabase_url and self.supabase_key:
        targets.append((self.supabase_url, self.supabase_key, "CLOUD"))
    local_url = os.getenv("SUPABASE_LOCAL_URL")
    local_key = os.getenv("SUPABASE_LOCAL_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_LOCAL_ANON_KEY")
    if local_url and local_key:
        targets.append((local_url, local_key, "LOCAL"))
        
    rows = []
    for url, key, label in targets:
        target_url = f"{url}/rest/v1/trade_performance"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}"
        }
        params = {
            "symbol": f"eq.{symbol}",
            "created_at": f"gt.{cutoff}",
            "select": "*",
            "limit": 100
        }
        if asset_class:
            params["asset_class"] = f"eq.{asset_class}"
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(target_url, headers=headers, params=params)
                if resp.status_code == 200:
                    rows = resp.json()
                    logger.info(f"Retrieved {len(rows)} trades from {label} Supabase.")
                    break # Success, use these rows
                else:
                    logger.warning(f"Supabase {label} query returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to query {label} Supabase trade_performance: {e}")
            
    if not rows:
        logger.info(f"No trade history found for {symbol}. Using defaults.")
        return {
            "total_trades": 0,
            "win_rate": self.DEFAULT_WIN_RATE,
            "payout_ratio": self.DEFAULT_PAYOUT,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "data_sufficient": False
        }
        
    # Extract outcomes and pnl_pcts
    wins = []
    losses = []
    
    for row in rows:
        pnl_pct = float(row.get("pnl_pct", 0.0) or 0.0)
        is_win = row.get("win")
        # Parse boolean representation robustly
        win_bool = is_win in (True, 1, "true", "True", "1") if not isinstance(is_win, bool) else is_win
        
        if win_bool:
            wins.append(pnl_pct)
        else:
            losses.append(abs(pnl_pct))
            
    total_trades = len(rows)
    data_sufficient = total_trades >= self.MIN_TRADES_REQUIRED
    
    if data_sufficient:
        win_rate = len(wins) / total_trades
        avg_win_pct = sum(wins) / len(wins) if wins else 0.0
        avg_loss_pct = sum(losses) / len(losses) if losses else 0.0
        payout_ratio = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else self.DEFAULT_PAYOUT
    else:
        win_rate = self.DEFAULT_WIN_RATE
        payout_ratio = self.DEFAULT_PAYOUT
        avg_win_pct = sum(wins) / len(wins) if wins else 0.0
        avg_loss_pct = sum(losses) / len(losses) if losses else 0.0
        
    return {
      "total_trades": total_trades,
      "win_rate": win_rate,
      "payout_ratio": payout_ratio,
      "avg_win_pct": avg_win_pct,
      "avg_loss_pct": avg_loss_pct,
      "data_sufficient": data_sufficient
    }

  def calculate_kelly(
    self,
    win_rate: float,
    payout_ratio: float
  ) -> float:
    """Calculate the optimal fractional Kelly bet sizing percentage."""
    b = payout_ratio
    p = win_rate
    q = 1.0 - win_rate
    
    if b <= 0:
        f_star = 0.0
    else:
        f_star = (b * p - q) / b
        
    f_fractional = f_star * self.KELLY_FRACTION
    
    if f_fractional <= 0:
        return self.MIN_POSITION_PCT
    else:
        return max(self.MIN_POSITION_PCT, min(self.MAX_POSITION_PCT, f_fractional))

  async def get_portfolio_value(self) -> float:
    """Fetch current account equity from Alpaca or return default capital."""
    alpaca_headers = {
        "APCA-API-KEY-ID": self.alpaca_api_key or "",
        "APCA-API-SECRET-KEY": self.alpaca_api_secret or "",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{self.alpaca_base_url}/v2/account",
                headers=alpaca_headers
            )
            if resp.status_code == 200:
                data = resp.json()
                equity = float(data.get("equity", self.BASE_PORTFOLIO))
                logger.info(f"Alpaca dynamic equity parsed successfully: ${equity:,.2f}")
                return equity
            else:
                logger.warning(f"Alpaca equity fetch returned status {resp.status_code}. Using baseline capital.")
                return float(self.BASE_PORTFOLIO)
    except Exception as e:
        logger.error(f"Failed to fetch portfolio value from Alpaca: {e}")
        return float(self.BASE_PORTFOLIO)

  async def calculate_position_size(
    self,
    symbol: str,
    asset_class: str = 'equities',
    regime: str = 'QUIET',
    greeks_scalar: float = 1.0
  ) -> dict:
    """Calculate adjusted data-driven position sizing in absolute dollar terms."""
    # 1. Get historical performance for symbol
    perf = await self.get_historical_performance(symbol, asset_class=asset_class)
    
    # 2. Calculate Kelly fraction
    kelly_fraction = self.calculate_kelly(perf["win_rate"], perf["payout_ratio"])
    
    # 3. Get current portfolio value from Alpaca
    portfolio_value = await self.get_portfolio_value()
    
    # 4. Apply regime adjustment:
    #    BULL → kelly_fraction * 1.0 (no change)
    #    QUIET → kelly_fraction * 0.8 (reduce 20%)
    #    VOLATILE → kelly_fraction * 0.6 (reduce 40%)
    #    BEAR → kelly_fraction * 0.4 (reduce 60%)
    regime_adjustment = 1.0
    if regime == "BULL":
        regime_adjustment = 1.0
    elif regime == "QUIET":
        regime_adjustment = 0.8
    elif regime == "VOLATILE":
        regime_adjustment = 0.6
    elif regime == "BEAR":
        regime_adjustment = 0.4
        
    adjusted_kelly = kelly_fraction * regime_adjustment
    
    # 5. Apply Greeks scalar from GreeksRiskEngine
    # 6. Calculate final position value:
    #    position_value = portfolio_value * adjusted_kelly * greeks_scalar
    position_value = portfolio_value * adjusted_kelly * greeks_scalar
    
    return {
      "symbol": symbol,
      "kelly_fraction": kelly_fraction,
      "adjusted_kelly": adjusted_kelly,
      "regime_adjustment": regime_adjustment,
      "greeks_scalar": greeks_scalar,
      "portfolio_value": portfolio_value,
      "position_value": position_value,
      "position_value_str": f"${position_value:,.2f}",
      "win_rate": perf["win_rate"],
      "payout_ratio": perf["payout_ratio"],
      "data_sufficient": perf["data_sufficient"],
      "using_defaults": not perf["data_sufficient"]
    }

  async def record_trade_outcome(
    self,
    symbol: str,
    asset_class: str,
    signal_type: str,
    entry_price: float,
    exit_price: float,
    kelly_fraction: float,
    position_value: float,
    regime: str = None,
    iv_rank: float = None
  ) -> None:
    """Calculate trade PnL and write outcome row to trade_performance table."""
    pnl = float(exit_price) - float(entry_price)
    pnl_pct = pnl / float(entry_price) if float(entry_price) > 0 else 0.0
    win = pnl > 0
    
    # Write to local and cloud Supabase
    targets = []
    if self.supabase_url and self.supabase_key:
        targets.append((self.supabase_url, self.supabase_key, "CLOUD"))
    local_url = os.getenv("SUPABASE_LOCAL_URL")
    local_key = os.getenv("SUPABASE_LOCAL_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_LOCAL_ANON_KEY")
    if local_url and local_key:
        targets.append((local_url, local_key, "LOCAL"))
        
    payload = {
        "session_id": os.getenv("SESSION_ID", "standalone"),
        "symbol": symbol,
        "asset_class": asset_class,
        "signal_type": signal_type,
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "pnl": float(pnl),
        "pnl_pct": float(pnl_pct),
        "win": bool(win),
        "hold_bars": 0,
        "kelly_fraction": float(kelly_fraction),
        "position_value": float(position_value),
        "regime_at_entry": regime,
        "iv_rank_at_entry": iv_rank if iv_rank is not None else 0.0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    for url, key, label in targets:
        target_url = f"{url}/rest/v1/trade_performance"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(target_url, headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    logger.info(f"Recorded trade outcome for {symbol} to Supabase {label}.")
                else:
                    logger.error(f"Failed to record trade outcome to Supabase {label}: {resp.status_code} — {resp.text}")
        except Exception as e:
            logger.error(f"Failed to write trade outcome to Supabase {label}: {e}")
