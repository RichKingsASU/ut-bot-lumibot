import numpy as np
import polars as pl
from hmmlearn.hmm import GaussianHMM
from agents.base_agent import BaseAgent
import glob
import logging
from datetime import datetime, timezone
import httpx
import json
import os

logger = logging.getLogger("RegimeDetector")

class RegimeDetector(BaseAgent):

  N_STATES = 4  # BULL, BEAR, VOLATILE, QUIET
  LOOKBACK_BARS = 252  # ~1 year of daily bars
  MIN_BARS = 60  # minimum bars needed to fit HMM

  REGIME_LABELS = {
    0: "QUIET",
    1: "BULL",
    2: "VOLATILE",
    3: "BEAR"
  }

  def __init__(self, name: str, asset_class: str = "equities", nats_url: str = None):
    super().__init__(name)
    self.asset_class = asset_class
    self.models = {}  # fitted HMM per symbol
    self.symbols = (
      ['SPY', 'QQQ', 'IWM', 'NVDA', 'TSLA', 'AAPL']
      if asset_class == 'equities'
      else ['BTC/USD', 'ETH/USD', 'SOL/USD']
    )
    
    is_docker = os.path.exists("/.dockerenv")
    default_nats = "nats://nats:4222" if is_docker else "nats://localhost:4222"
    self.nats_url = nats_url or os.getenv("NATS_URL") or default_nats

  def _load_bars(self, symbol: str) -> pl.DataFrame:
    """Load historical bars from Parquet on 8TB drive."""
    symbol_safe = symbol.replace("/", "")
    if self.asset_class == 'equities':
        path_pattern = f"/mnt/tick-storage/historical/equities/{symbol}/{symbol}_1D_*.parquet"
    else:
        path_pattern = f"/mnt/tick-storage/historical/crypto/{symbol_safe}/{symbol_safe}_1D_*.parquet"
        
    files = glob.glob(path_pattern)
    if not files:
        logger.warning(f"No daily Parquet files found for symbol {symbol} with path pattern {path_pattern}")
        return None
        
    try:
        # Read matching parquet files
        dfs = [pl.read_parquet(f) for f in files]
        if len(dfs) == 1:
            df = dfs[0]
        else:
            df = pl.concat(dfs)
            
        timestamp_col = "ts" if "ts" in df.columns else "timestamp"
        
        # Sort and deduplicate by timestamp
        df = df.sort(timestamp_col)
        df = df.unique(subset=[timestamp_col], keep="last")
        
        if len(df) < self.MIN_BARS:
            logger.warning(f"Fewer than {self.MIN_BARS} bars loaded for {symbol} (got {len(df)})")
            return None
            
        # Return last LOOKBACK_BARS rows
        return df.tail(self.LOOKBACK_BARS)
    except Exception as e:
        logger.error(f"Error loading historical bars for {symbol}: {e}")
        return None

  def _extract_features(self, df: pl.DataFrame) -> np.ndarray:
    """Extract 4 features per bar for HMM."""
    close_col = "close"
    volume_col = "volume"
    high_col = "high"
    low_col = "low"
    
    # Check if necessary columns are present
    for col in [close_col, volume_col, high_col, low_col]:
        if col not in df.columns:
            logger.error(f"Column {col} missing from DataFrame. Available: {df.columns}")
            return None

    # Returns: (close - close.shift(1)) / close.shift(1)
    df_feat = df.with_columns([
        ((pl.col(close_col) - pl.col(close_col).shift(1)) / pl.col(close_col).shift(1)).alias("returns")
    ])
    
    # Volatility: rolling 10-bar std of returns
    # Volume ratio: volume / volume.rolling(20).mean()
    # Range ratio: (high - low) / close
    df_feat = df_feat.with_columns([
        pl.col("returns").rolling_std(window_size=10).alias("volatility"),
        (pl.col(volume_col) / pl.col(volume_col).rolling_mean(window_size=20)).alias("volume_ratio"),
        ((pl.col(high_col) - pl.col(low_col)) / pl.col(close_col)).alias("range_ratio")
    ])
    
    # Save the original unstandardized feature values before dropping nulls
    self._last_unstandardized_row = df_feat.tail(1).to_dicts()[0] if len(df_feat) > 0 else {}
    
    feature_cols = ["returns", "volatility", "volume_ratio", "range_ratio"]
    df_clean = df_feat.select(feature_cols).drop_nulls()
    
    if len(df_clean) < 10:
        logger.warning("Fewer than 10 clean rows remaining after feature extraction and dropping NaNs.")
        return None
        
    features = df_clean.to_numpy()
    
    # Standardize each feature (zero mean, unit variance)
    mean = features.mean(axis=0)
    std = features.std(axis=0)
    std[std == 0] = 1.0  # prevent division by zero
    standardized_features = (features - mean) / std
    
    return standardized_features

  def _fit_model(self, symbol: str, features: np.ndarray) -> GaussianHMM:
    """Fit GaussianHMM with N_STATES hidden states."""
    model = GaussianHMM(
      n_components=self.N_STATES,
      covariance_type="full",
      n_iter=100,
      random_state=42
    )
    model.fit(features)
    self.models[symbol] = model
    return model

  def _classify_regime(
    self,
    model: GaussianHMM,
    features: np.ndarray,
    symbol: str
  ) -> dict:
    """Get most likely hidden state sequence and map to regime label dynamically."""
    hidden_states = model.predict(features)
    current_state = int(hidden_states[-1])
    
    # Get state probabilities for current bar
    state_probs = model.predict_proba(features)[-1]
    current_prob = float(state_probs[current_state])
    
    # Map state to regime label by analyzing means dynamically:
    #   Highest mean returns -> BULL
    #   Lowest mean returns -> BEAR
    #   Highest volatility feature -> VOLATILE (among remaining two)
    #   Lowest volatility -> QUIET (among remaining two)
    means = model.means_  # shape (N_STATES, N_FEATURES), features order: [returns, volatility, volume_ratio, range_ratio]
    returns_means = means[:, 0]
    vol_means = means[:, 1]
    
    sorted_by_returns = np.argsort(returns_means)
    bear_state = int(sorted_by_returns[0])
    bull_state = int(sorted_by_returns[3])
    
    remaining_states = [int(sorted_by_returns[1]), int(sorted_by_returns[2])]
    if vol_means[remaining_states[0]] > vol_means[remaining_states[1]]:
        volatile_state = remaining_states[0]
        quiet_state = remaining_states[1]
    else:
        volatile_state = remaining_states[1]
        quiet_state = remaining_states[0]
        
    state_to_regime = {
        bull_state: "BULL",
        bear_state: "BEAR",
        volatile_state: "VOLATILE",
        quiet_state: "QUIET"
    }
    
    regime = state_to_regime[current_state]
    all_state_probs = {state_to_regime[s]: float(state_probs[s]) for s in range(self.N_STATES)}
    
    # Unstandardized current metrics from last row
    raw_volatility = float(self._last_unstandardized_row.get("volatility", 0.0) or 0.0)
    raw_return = float(self._last_unstandardized_row.get("returns", 0.0) or 0.0)
    raw_volume_ratio = float(self._last_unstandardized_row.get("volume_ratio", 1.0) or 1.0)
    
    return {
      "regime": regime,
      "hidden_state": current_state,
      "regime_probability": current_prob,
      "volatility": raw_volatility,
      "trend_strength": raw_return,
      "volume_ratio": raw_volume_ratio,
      "all_state_probs": all_state_probs
    }

  async def analyze(self) -> dict:
    """Run full HMM regime detection process."""
    symbol_regimes = {}
    regime_counts = {"BULL": 0, "BEAR": 0, "VOLATILE": 0, "QUIET": 0}
    
    for symbol in self.symbols:
        df = self._load_bars(symbol)
        if df is None:
            continue
            
        features = self._extract_features(df)
        if features is None:
            continue
            
        try:
            model = self._fit_model(symbol, features)
            classification = self._classify_regime(model, features, symbol)
            symbol_regimes[symbol] = {
                "regime": classification["regime"],
                "probability": classification["regime_probability"]
            }
            regime_counts[classification["regime"]] += 1
            
            # 1. Write to Supabase regime_states table via REST API
            targets = []
            if self.supabase_url and self.supabase_anon_key:
                targets.append((self.supabase_url, self.supabase_anon_key, "CLOUD"))
                
            local_url = os.getenv("SUPABASE_LOCAL_URL")
            local_key = os.getenv("SUPABASE_LOCAL_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_LOCAL_ANON_KEY")
            if local_url and local_key:
                targets.append((local_url, local_key, "LOCAL"))
                
            payload = {
                "symbol": symbol,
                "asset_class": self.asset_class,
                "regime": classification["regime"],
                "regime_probability": float(classification["regime_probability"]),
                "volatility": float(classification["volatility"]),
                "trend_strength": float(classification["trend_strength"]),
                "volume_ratio": float(classification["volume_ratio"]),
                "hidden_state": int(classification["hidden_state"]),
                "detected_at": datetime.now(timezone.utc).isoformat()
            }
            
            for url, key, label in targets:
                target_url = f"{url}/rest/v1/regime_states"
                headers = {
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                }
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(target_url, headers=headers, json=payload)
                        if resp.status_code in (200, 201):
                            logger.info(f"Regime state for {symbol} written to Supabase {label}.")
                        else:
                            logger.error(
                                f"Supabase {label} insert failed for {symbol}: {resp.status_code} — {resp.text}"
                            )
                except Exception as e:
                    logger.error(f"Failed to write regime state to Supabase {label}: {e}")
            
            if not targets:
                logger.warning("Supabase credentials not set; skipping database write.")
                
            # 2. Publish to NATS: regime.{asset_class}.{symbol}
            try:
                import nats
                nc = await nats.connect(self.nats_url)
                nats_payload = {
                    "symbol": symbol,
                    "regime": classification["regime"],
                    "probability": float(classification["regime_probability"]),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                subject = f"regime.{self.asset_class}.{symbol}"
                await nc.publish(
                    subject,
                    json.dumps(nats_payload).encode("utf-8")
                )
                await nc.close()
                logger.info(f"Published NATS regime message for {symbol} to {subject}")
            except Exception as e:
                logger.error(f"Failed to publish regime message to NATS: {e}")
                
        except Exception as e:
            logger.error(f"Failed to process regime detection for {symbol}: {e}", exc_info=True)
            
    # Determine overall market regime:
    # - If majority of symbols are BULL → overall = BULL
    # - If majority are BEAR → overall = BEAR
    # - If majority are VOLATILE → overall = VOLATILE
    # - Otherwise → overall = QUIET
    total_analyzed = len(symbol_regimes)
    overall_regime = "QUIET"
    
    if total_analyzed > 0:
        threshold = total_analyzed / 2.0
        if regime_counts["BULL"] > threshold:
            overall_regime = "BULL"
        elif regime_counts["BEAR"] > threshold:
            overall_regime = "BEAR"
        elif regime_counts["VOLATILE"] > threshold:
            overall_regime = "VOLATILE"
        else:
            overall_regime = "QUIET"
            
    strategy_recommendation = self.get_strategy_recommendation(overall_regime)
    
    return {
      "overall_regime": overall_regime,
      "symbol_regimes": symbol_regimes,
      "regime_distribution": regime_counts,
      "strategy_recommendation": strategy_recommendation,
      "detected_at": datetime.now(timezone.utc).isoformat()
    }

  def get_strategy_recommendation(self, overall_regime: str) -> str:
    if overall_regime == "BULL":
        return ("Follow momentum. Long bias. "
                "Trend-following favored. "
                "Reduce hedge positions.")
    elif overall_regime == "BEAR":
        return ("Defensive posture. Short bias or cash. "
                "Increase hedge. Reduce position sizes 20%.")
    elif overall_regime == "VOLATILE":
        return ("Morning explosion favored. "
                "Long Gamma mode. "
                "Tighten stops. "
                "Reduce size 30% — whipsaw risk.")
    else:  # QUIET
        return ("Mean reversion favored. "
                "Short Premium mode. "
                "IV likely elevated — sell options premium. "
                "Wider stops acceptable.")
