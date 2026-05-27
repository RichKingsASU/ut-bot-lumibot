import os
import httpx
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')

class VaRRiskEngine:
    # CONSTANTS
    VAR_CONFIDENCE = 0.95
    VAR_LOOKBACK_DAYS = 30
    MAX_DAILY_VAR_PCT = 0.03      # 3% of equity — crypto positions have higher natural VaR
    DRAWDOWN_PAUSE_PCT = 0.10     # 10% from 14d high → PAUSE (paper trading with crypto is volatile)
    DRAWDOWN_STOP_PCT = 0.20      # 20% from 14d high → STOP (only at genuine crisis)
    MAX_POSITION_PCT = 0.80       # 80% — crypto bot holds 3 positions that naturally dominate
    MAX_CONCURRENT_POSITIONS = 10  # 3 crypto + SPY = 4 max currently, allow headroom
    CORRELATION_ALERT_THRESHOLD = 0.85

    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.alpaca_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_secret = os.getenv('ALPACA_API_SECRET')
        self.alpaca_base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        self.headers = {
            'APCA-API-KEY-ID': self.alpaca_key,
            'APCA-API-SECRET-KEY': self.alpaca_secret
        }

    async def get_portfolio_history(self, days: int = 30) -> list:
        url = f"{self.alpaca_base}/v2/account/portfolio/history"
        params = {
            "period": "1M",
            "timeframe": "1D"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    equity = data.get("equity", [])
                    return [float(e) for e in equity if e is not None]
        except Exception as e:
            pass
        return []

    async def get_portfolio_value(self) -> float:
        """Get current portfolio equity from Alpaca."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.alpaca_base}/v2/account", headers=self.headers)
                if resp.status_code == 200:
                    return float(resp.json().get('equity', 0.0))
        except Exception:
            pass
        return 0.0

    async def calculate_var(self) -> dict:
        raw_equities = await self.get_portfolio_history(self.VAR_LOOKBACK_DAYS)
        equities = [e for e in raw_equities if e is not None and e > 0]
        current_equity = 0.0
        var_pct = 0.0
        var_dollar = 0.0

        if len(equities) > 1:
            equity_arr = np.array(equities)
            returns = np.diff(equity_arr) / equity_arr[:-1]
        else:
            returns = np.array([])

        if len(equities) < 5 or len(returns) < 3:
            current_equity = await self.get_portfolio_value()
            if current_equity <= 0:
                current_equity = equities[-1] if equities else 1.0
            import logging
            logger = logging.getLogger("VaRRiskEngine")
            logger.warning(f"[VaR] Only {len(equities)} valid equity points in history — using safe defaults")
            return {
                "var_pct": 0.02,
                "var_dollar": current_equity * 0.02,
                "current_equity": current_equity,
                "breach": False,
                "confidence": self.VAR_CONFIDENCE,
                "lookback_days": 0,
                "insufficient_data": True,
                "note": "Insufficient history — using safe default"
            }
        
        current_equity = equities[-1]
        var_pct = np.percentile(returns, (1 - self.VAR_CONFIDENCE) * 100)
        var_dollar = abs(var_pct * current_equity)
        var_pct = abs(var_pct)

        return {
            "var_pct": float(var_pct),
            "var_dollar": float(var_dollar),
            "current_equity": float(current_equity),
            "breach": bool(var_pct > self.MAX_DAILY_VAR_PCT),
            "confidence": self.VAR_CONFIDENCE,
            "lookback_days": self.VAR_LOOKBACK_DAYS
        }

    async def check_drawdown(self) -> dict:
        raw_equities = await self.get_portfolio_history(self.VAR_LOOKBACK_DAYS)
        clean_equities = [e for e in raw_equities if e is not None and e > 0]
        peak_equity = 0.0
        current_equity = 0.0
        drawdown = 0.0
        action = 'OK'
        reason = 'Drawdown within acceptable limits'

        if len(clean_equities) < 5:
            current_equity = await self.get_portfolio_value()
            if current_equity <= 0:
                current_equity = clean_equities[-1] if clean_equities else 1.0
            return {
                "drawdown_pct": 0.0,
                "peak_equity": current_equity,
                "current_equity": current_equity,
                "action": "OK",
                "reason": "Insufficient history — safe default",
                "peak_window_days": 0,
                "insufficient_data": True
            }

        if clean_equities:
            # Use 14-day rolling peak instead of all-time peak
            recent_window = clean_equities[-14:] if len(clean_equities) >= 14 else clean_equities
            peak_equity = max(recent_window)
            current_equity = clean_equities[-1]
            if peak_equity > 0:
                drawdown = (current_equity - peak_equity) / peak_equity

            if drawdown < -self.DRAWDOWN_STOP_PCT:
                action = 'STOP'
                reason = f'Drawdown {drawdown:.1%} exceeds {self.DRAWDOWN_STOP_PCT:.0%} limit'
            elif drawdown < -self.DRAWDOWN_PAUSE_PCT:
                action = 'PAUSE'
                reason = f'Drawdown {drawdown:.1%} exceeds {self.DRAWDOWN_PAUSE_PCT:.0%} — pausing'

        return {
            "drawdown_pct": float(drawdown),
            "peak_equity": float(peak_equity),
            "current_equity": float(current_equity),
            "action": action,
            "reason": reason,
            "peak_window_days": min(14, len(clean_equities)),
            "note": "14-day rolling peak — paper trading mode"
        }

    async def check_position_concentration(self) -> dict:
        crypto_exposure = 0.0
        equity_exposure = 0.0
        position_count = 0
        alerts = []
        breach = False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                acc_resp = await client.get(f"{self.alpaca_base}/v2/account", headers=self.headers)
                pos_resp = await client.get(f"{self.alpaca_base}/v2/positions", headers=self.headers)

                if acc_resp.status_code == 200 and pos_resp.status_code == 200:
                    account = acc_resp.json()
                    positions = pos_resp.json()
                    total_equity = float(account.get('equity', 1.0))
                    if total_equity == 0: total_equity = 1.0

                    crypto_exposure = sum(
                        float(p['market_value']) for p in positions
                        if any(c in p['symbol'] for c in ['BTC', 'ETH', 'SOL', 'USD'])
                    ) / total_equity

                    equity_exposure = sum(
                        float(p['market_value']) for p in positions
                        if not any(c in p['symbol'] for c in ['BTC', 'ETH', 'SOL', 'USD'])
                    ) / total_equity

                    position_count = len(positions)

                    # Per-symbol concentration: alert only if SINGLE symbol > 50%
                    for p in positions:
                        single_pct = abs(float(p['market_value'])) / total_equity
                        if single_pct > 0.50:
                            alerts.append(
                                f'{p["symbol"]} is {single_pct:.1%} of portfolio'
                            )

                    if position_count > self.MAX_CONCURRENT_POSITIONS:
                        alerts.append(
                            f'{position_count} positions exceeds max '
                            f'{self.MAX_CONCURRENT_POSITIONS}'
                        )
        except Exception as e:
            pass
            
        if alerts:
            breach = True

        return {
            "position_count": position_count,
            "crypto_exposure_pct": float(crypto_exposure),
            "equity_exposure_pct": float(equity_exposure),
            "alerts": alerts,
            "breach": breach
        }

    async def full_risk_check(self) -> dict:
        import asyncio
        var_result, drawdown_result, concentration_result = await asyncio.gather(
            self.calculate_var(),
            self.check_drawdown(),
            self.check_position_concentration()
        )

        overall_action = 'OK'
        if drawdown_result['action'] == 'STOP':
            overall_action = 'STOP'
        elif drawdown_result['action'] == 'PAUSE':
            overall_action = 'PAUSE'
        elif var_result['breach']:
            overall_action = 'REDUCE'
        elif concentration_result['breach']:
            overall_action = 'ALERT'
            
        all_alerts = concentration_result['alerts'].copy()

        return {
            "overall_action": overall_action,
            "var": var_result,
            "drawdown": drawdown_result,
            "concentration": concentration_result,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "alerts": all_alerts
        }

    def format_telegram_alert(self, risk_result: dict) -> str:
        var_res = risk_result['var']
        dd_res = risk_result['drawdown']
        conc_res = risk_result['concentration']
        
        alerts_str = ", ".join(risk_result['alerts']) if risk_result['alerts'] else "None"
        
        return (
            f"🚨 VaR Risk Alert\n"
            f"Action: {risk_result['overall_action']}\n"
            f"Drawdown: {dd_res['drawdown_pct']:.1%} from peak\n"
            f"Daily VaR: {var_res['var_pct']:.1%} (${var_res['var_dollar']:,.0f})\n"
            f"Positions: {conc_res['position_count']}\n"
            f"Crypto: {conc_res['crypto_exposure_pct']:.1%} | Equity: {conc_res['equity_exposure_pct']:.1%}\n"
            f"Alerts: {alerts_str}"
        )
