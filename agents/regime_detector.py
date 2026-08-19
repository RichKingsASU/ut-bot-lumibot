import numpy as np
import pandas as pd
import polars as pl
import os
import glob
import logging
import httpx
from hmmlearn.hmm import GaussianHMM
from dotenv import load_dotenv
from agents.base_agent import BaseAgent
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RegimeDetector(BaseAgent):
    N_STATES = 4
    LOOKBACK_BARS = 252
    MIN_BARS = 60
    REGIME_LABELS = {0: 'QUIET', 1: 'BULL', 2: 'VOLATILE', 3: 'BEAR'}

    def __init__(self, name: str, asset_class: str = 'equities'):
        super().__init__(name)
        self.asset_class = asset_class
        self.models = {}
        self.symbols = (
            ['SPY', 'QQQ', 'IWM', 'NVDA', 'TSLA', 'AAPL']
            if asset_class == 'equities'
            else ['BTC/USD', 'ETH/USD', 'SOL/USD']
        )

    def _load_bars(self, symbol: str) -> pd.DataFrame:
        if self.asset_class == 'equities':
            path = f"/mnt/tick-storage/historical/equities/{symbol}/"
            pattern = f"{symbol}_1D_*.parquet"
        else:
            safe_symbol = symbol.replace('/', '')
            path = f"/mnt/tick-storage/historical/crypto/{safe_symbol}/"
            pattern = f"{safe_symbol}_1D_*.parquet"
        
        files = glob.glob(os.path.join(path, pattern))
        if not files:
            return None
        
        # Load all available files and concat, or just the latest if only one
        dfs = []
        for file in files:
            try:
                dfs.append(pd.read_parquet(file))
            except Exception as e:
                logger.error(f"Error reading {file}: {e}")
                
        if not dfs:
            return None
            
        df = pd.concat(dfs, ignore_index=True)
        
        # Find time column
        time_col = None
        for col in ['ts', 'timestamp', 'date']:
            if col in df.columns:
                time_col = col
                break
                
        if time_col is None:
            logger.error(f"No time column found in {symbol} data")
            return None
            
        df = df.sort_values(by=time_col, ascending=True).reset_index(drop=True)
        
        if len(df) < self.MIN_BARS:
            return None
            
        return df.tail(self.LOOKBACK_BARS).copy()

    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        # 1. Returns: pct_change of close column
        df['returns'] = df['close'].pct_change()
        
        # 2. Volatility: rolling(10).std() of returns
        df['volatility'] = df['returns'].rolling(window=10).std()
        
        # 3. Volume ratio: volume / volume.rolling(20).mean()
        if 'volume' in df.columns:
            df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
        else:
            df['volume_ratio'] = 1.0 # fallback
            
        # 4. Range ratio: (high - low) / close
        if all(c in df.columns for c in ['high', 'low', 'close']):
            df['range_ratio'] = (df['high'] - df['low']) / df['close']
        else:
            df['range_ratio'] = 0.0 # fallback
            
        # Drop NaN rows
        df_clean = df.dropna(subset=['returns', 'volatility', 'volume_ratio', 'range_ratio'])
        
        if len(df_clean) < self.MIN_BARS:
            return None
            
        features = df_clean[['returns', 'volatility', 'volume_ratio', 'range_ratio']].values
        
        # Standardize: (x - mean) / std per column
        means = np.mean(features, axis=0)
        stds = np.std(features, axis=0)
        # Avoid division by zero
        stds[stds == 0] = 1.0
        features = (features - means) / stds
        
        return features

    def _fit_model(self, symbol: str, features: np.ndarray) -> GaussianHMM:
        model = GaussianHMM(
            n_components=self.N_STATES,
            covariance_type='full',
            n_iter=100,
            random_state=42
        )
        model.fit(features)
        self.models[symbol] = model
        return model

    def _classify_regime(self, model: GaussianHMM, features: np.ndarray) -> dict:
        hidden_states = model.predict(features)
        current_state = int(hidden_states[-1])
        state_probs = model.predict_proba(features)[-1]
        current_prob = float(state_probs[current_state])
        
        means = model.means_
        returns_col = means[:, 0]
        vol_col = means[:, 1]
        
        state_regimes = {}
        sorted_by_returns = np.argsort(returns_col)
        sorted_by_vol = np.argsort(vol_col)
        
        state_regimes[sorted_by_returns[-1]] = 'BULL'
        state_regimes[sorted_by_returns[0]] = 'BEAR'
        remaining = [s for s in range(4) if s not in state_regimes]
        vol_remaining = sorted(remaining, key=lambda x: vol_col[x], reverse=True)
        state_regimes[vol_remaining[0]] = 'VOLATILE'
        state_regimes[vol_remaining[1]] = 'QUIET'
        
        regime = state_regimes.get(current_state)
        if regime is None or not np.isclose(float(np.sum(state_probs)), 1.0, atol=1e-6):
            raise ValueError("invalid regime state/probabilities")
        
        return {
            'regime': regime,
            'hidden_state': current_state,
            'regime_probability': current_prob,
            'volatility': float(features[-1, 1]),
            'trend_strength': float(features[-1, 0]),
            'volume_ratio': float(features[-1, 2]),
            'state_map': state_regimes
        }

    async def analyze(self) -> dict:
        results = {}
        
        # NOTE: previously read os.environ['SUPABASE_KEY'] which is never set in
        # this project (the env var is SUPABASE_SERVICE_ROLE_KEY), so every
        # regime_states write was silently skipped. Reuse the credentials
        # already resolved by BaseAgent (anon → service-role fallback).
        supabase_url = self.supabase_url or os.environ.get('SUPABASE_URL')
        supabase_key = self.supabase_anon_key or os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

        for symbol in self.symbols:
            try:
                df = self._load_bars(symbol)
                if df is None:
                    logger.warning(f'[Regime] No data for {symbol}')
                    results[symbol] = {'regime': None, 'regime_probability': None,
                                       'status': 'NO_DATA', 'reason': 'bars unavailable'}
                    continue
                
                features = self._extract_features(df)
                if features is None or len(features) < self.MIN_BARS:
                    results[symbol] = {'regime': None, 'regime_probability': None,
                                       'status': 'MALFORMED', 'reason': 'features unavailable'}
                    continue
                
                model = self._fit_model(symbol, features)
                classification = self._classify_regime(model, features)
                classification['status'] = 'VALID'
                classification['timestamp'] = datetime.now(timezone.utc).isoformat()
                results[symbol] = classification
                
                if supabase_url and supabase_key:
                    row = {
                        'symbol': symbol,
                        'asset_class': self.asset_class,
                        'regime': classification['regime'],
                        'regime_probability': classification['regime_probability'],
                        'volatility': classification['volatility'],
                        'trend_strength': classification['trend_strength'],
                        'volume_ratio': classification['volume_ratio'],
                        'hidden_state': classification['hidden_state'],
                        'detected_at': datetime.now(timezone.utc).isoformat()
                    }
                    from common.safe_write import safe_write_sync
                    safe_write_sync(
                        "regime_states", row, "regime-detector",
                        _url=supabase_url, _key=supabase_key,
                    )
                
                # Publish to NATS
                if hasattr(self, 'nc') and self.nc and self.nc.is_connected:
                    await self.nc.publish(
                        f"regime.{self.asset_class}.{symbol}",
                        str(classification).encode()
                    )
                
            except Exception as e:
                logger.error(f'[Regime] Error for {symbol}: {e}')
                results[symbol] = {'regime': None, 'regime_probability': None,
                                   'status': 'ERROR', 'reason': type(e).__name__}
        
        regimes = [r['regime'] for r in results.values() if r.get('status') == 'VALID']
        from collections import Counter
        regime_counts = Counter(regimes)
        overall = regime_counts.most_common(1)[0][0] if regime_counts else None
        
        return {
            'overall_regime': overall,
            'regime_status': 'VALID' if overall else 'NO_DATA',
            'symbol_regimes': results,
            'regime_distribution': dict(regime_counts),
            'strategy_recommendation': self.get_strategy_recommendation(overall),
            'detected_at': datetime.now(timezone.utc).isoformat()
        }

    def get_strategy_recommendation(self, regime: str) -> str:
        recommendations = {
            'BULL': "Follow momentum. Long bias. Trend-following favored.",
            'BEAR': "Defensive. Short bias or cash. Reduce size 20%.",
            'VOLATILE': "Morning explosion favored. Long Gamma. Reduce size 30%.",
            'QUIET': "Mean reversion. Short Premium. IV likely elevated."
        }
        return recommendations.get(regime, "Default strategy.")
