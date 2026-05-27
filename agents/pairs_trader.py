import numpy as np
import pandas as pd
import glob
import logging
import httpx
import os
from datetime import datetime, timezone
from pathlib import Path
from agents.base_agent import BaseAgent

logger = logging.getLogger("PairsTrader")

PAIRS = [
    ('SPY', 'QQQ'),
    ('SPY', 'IWM'),
]

class PairsTrader(BaseAgent):
    def __init__(self, name='PairsTrader'):
        super().__init__(name)
        self.hist_root = Path('/mnt/tick-storage/historical/equities')
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    def load_daily_close(self, symbol: str) -> pd.Series:
        symbol_dir = self.hist_root / symbol
        files = list(symbol_dir.glob(f"{symbol}_1D_*.parquet"))
        if not files:
            raise FileNotFoundError(f"No 1D parquet files for {symbol}")
        
        # Load the most recent file
        latest_file = sorted(files)[-1]
        df = pd.read_parquet(latest_file)
        df = df.sort_values('ts').reset_index(drop=True)
        series = df.set_index('ts')['close']
        return series.last('252D')

    def calculate_spread(self, s1: pd.Series, s2: pd.Series) -> dict:
        try:
            from statsmodels.tsa.stattools import coint
        except ImportError:
            logger.error("statsmodels is not installed. Please install it.")
            raise

        # Align series
        df = pd.concat([s1, s2], axis=1).dropna()
        s1 = df.iloc[:, 0]
        s2 = df.iloc[:, 1]

        # 1. Test cointegration
        score, pvalue, _ = coint(s1, s2)

        # 2. Calculate hedge ratio via OLS
        from numpy.linalg import lstsq
        A = np.column_stack([s2, np.ones(len(s2))])
        hedge_ratio, intercept = lstsq(A, s1, rcond=None)[0]

        # 3. Calculate spread
        spread = s1 - hedge_ratio * s2 - intercept

        # 4. Z-score
        zscore = (spread - spread.mean()) / spread.std()

        # 5. Current signal
        current_z = float(zscore.iloc[-1])
        if current_z > 2.0:
            signal = 'SHORT_SPREAD'
        elif current_z < -2.0:
            signal = 'LONG_SPREAD'
        elif abs(current_z) < 0.5:
            signal = 'EXIT'
        else:
            signal = 'HOLD'

        return {
            'cointegrated': bool(pvalue < 0.10),
            'pvalue': float(pvalue),
            'hedge_ratio': float(hedge_ratio),
            'current_zscore': float(current_z),
            'signal': signal,
            'spread_mean': float(spread.mean()),
            'spread_std': float(spread.std())
        }

    def calculate_half_life(self, spread: pd.Series) -> float:
        delta_spread = spread.diff().dropna()
        lag_spread = spread.shift(1).dropna()
        # Align them
        df = pd.concat([lag_spread, delta_spread], axis=1).dropna()
        if len(df) == 0:
            return 1.0
        
        model = np.polyfit(df.iloc[:, 0], df.iloc[:, 1], 1)
        half_life = -np.log(2) / model[0] if model[0] != 0 else 1.0
        return float(max(1.0, abs(half_life)))

    async def analyze(self) -> dict:
        opportunities = []
        for sym1, sym2 in PAIRS:
            try:
                s1 = self.load_daily_close(sym1)
                s2 = self.load_daily_close(sym2)
                result = self.calculate_spread(s1, s2)
                
                logger.info(f'[Pairs] Loaded {sym1}: {len(s1)} bars')
                logger.info(f'[Pairs] {sym1}/{sym2} p-value: {result["pvalue"]:.4f}')
                logger.info(f'[Pairs] {sym1}/{sym2} z-score: {result["current_zscore"]:.2f}')
                
                # Align series to calculate half life
                df = pd.concat([s1, s2], axis=1).dropna()
                spread = df.iloc[:, 0] - result['hedge_ratio'] * df.iloc[:, 1]
                half_life = self.calculate_half_life(spread)
                
                result['sym1'] = sym1
                result['sym2'] = sym2
                result['pair'] = f'{sym1}/{sym2}'
                result['half_life'] = half_life
                
                if result['cointegrated']:
                    opportunities.append(result)
            except Exception as e:
                logger.error(f'Pairs error {sym1}/{sym2}: {e}')

        active_signals = [
            o for o in opportunities
            if o['signal'] in ['LONG_SPREAD', 'SHORT_SPREAD']
        ]

        # Write active signals to Supabase agent_signals
        if self.supabase_url and self.supabase_key:
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json"
            }
            url = f"{self.supabase_url}/rest/v1/agent_signals"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                for sig in active_signals:
                    conf = 'HIGH' if abs(sig['current_zscore']) > 2.5 else 'MEDIUM'
                    payload = {
                        "symbol": sig['pair'],
                        "action": sig['signal'],
                        "confidence": conf,
                        "reasoning": f"Z-score {sig['current_zscore']:.2f}, half-life {sig['half_life']:.0f}d, p-value {sig['pvalue']:.3f}",
                        "asset_class": "pairs",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "agent_name": self.name
                    }
                    try:
                        await client.post(url, headers=headers, json=payload)
                    except Exception as e:
                        logger.error(f"Failed to write pair signal to Supabase: {e}")

        return {
            'pairs_analyzed': len(opportunities),
            'active_signals': len(active_signals),
            'opportunities': opportunities,
            'top_opportunity': opportunities[0] if opportunities else None
        }
