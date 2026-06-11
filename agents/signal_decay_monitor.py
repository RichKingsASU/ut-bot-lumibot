import os
import httpx
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from scipy.stats import spearmanr
import numpy as np

from agents.base_agent import BaseAgent

logger = logging.getLogger("SignalDecayMonitor")

# CONSTANTS
IC_HEALTHY_THRESHOLD = 0.02    # IC above this = healthy
IC_DEGRADING_THRESHOLD = 0.005 # IC below this = degrading
IC_DEAD_THRESHOLD = 0.0        # IC at or below = dead
LOOKBACK_DAYS = 30             # rolling window
MIN_TRADES = 10                # minimum for calculation
FORWARD_BARS = 5               # bars ahead to measure return (for reference)

class SignalDecayMonitor(BaseAgent):

    def __init__(self, name: str):
        super().__init__(name)
        # Configure the complete universe list
        self.symbols = [
            "SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL",
            "BTC/USD", "ETH/USD", "SOL/USD"
        ]
        
    async def query_supabase_with_fallback(
        self,
        table: str,
        select: str = "*",
        filters: dict = None,
        limit: int = 1000
    ) -> list:
        """Queries both Cloud and Local Supabase REST APIs, returning the first successful result."""
        targets = []
        if self.supabase_url and self.supabase_anon_key:
            targets.append((self.supabase_url, self.supabase_anon_key, "CLOUD"))
            
        local_url = os.getenv("SUPABASE_LOCAL_URL")
        local_key = os.getenv("SUPABASE_LOCAL_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_LOCAL_ANON_KEY")
        if local_url and local_key:
            targets.append((local_url, local_key, "LOCAL"))
            
        for url, key, label in targets:
            target_url = f"{url}/rest/v1/{table}"
            headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}"
            }
            params = {
                "select": select,
                "limit": limit
            }
            if filters:
                params.update(filters)
                
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(target_url, headers=headers, params=params)
                    if resp.status_code == 200:
                        logger.info(f"Retrieved {len(resp.json())} rows from {label} {table}.")
                        return resp.json()
                    else:
                        logger.warning(f"{label} Supabase REST query to {table} failed: {resp.status_code} — {resp.text}")
            except Exception as e:
                logger.error(f"Failed to query {label} Supabase {table}: {e}")
                
        return []

    async def get_signal_history(
        self,
        symbol: str,
        lookback_days: int = LOOKBACK_DAYS
    ) -> list:
        """Query signal_log from Supabase filtered by symbol and created_at."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        filters = {
            "symbol": f"eq.{symbol}",
            "created_at": f"gt.{cutoff}",
            "order": "created_at.asc"
        }
        
        rows = await self.query_supabase_with_fallback(
            table="signal_log",
            select="signal_type,buy_sig,sell_sig,close_price,created_at",
            filters=filters,
            limit=1000
        )
        return rows

    async def get_trade_outcomes(
        self,
        symbol: str,
        lookback_days: int = LOOKBACK_DAYS
    ) -> list:
        """Query trade_performance from Supabase filtered by symbol and created_at."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        filters = {
            "symbol": f"eq.{symbol}",
            "created_at": f"gt.{cutoff}",
            "order": "created_at.asc"
        }
        
        rows = await self.query_supabase_with_fallback(
            table="trade_performance",
            select="signal_type,pnl_pct,win,created_at",
            filters=filters,
            limit=1000
        )
        return rows

    def calculate_ic(
        self,
        signals: list,
        outcomes: list
    ) -> float:
        """Match signals to outcomes by timestamp proximity and calculate Spearman rank correlation."""
        def parse_dt(dt_str):
            if not dt_str:
                return None
            try:
                # Standardize ISO format parsing (e.g. replace Z with UTC offset)
                s = dt_str.replace('Z', '+00:00')
                return datetime.fromisoformat(s)
            except Exception:
                return None

        matched_pairs = []
        
        for sig in signals:
            sig_time = parse_dt(sig.get('created_at'))
            if not sig_time:
                continue
                
            # Parse signal score
            buy_sig = sig.get('buy_sig')
            buy_sig_bool = buy_sig in (True, 1, "true", "True", "1") if not isinstance(buy_sig, bool) else buy_sig
            sell_sig = sig.get('sell_sig')
            sell_sig_bool = sell_sig in (True, 1, "true", "True", "1") if not isinstance(sell_sig, bool) else sell_sig
            
            sig_score = 1 if buy_sig_bool else (-1 if sell_sig_bool else 0)
            sig_type = sig.get('signal_type')
            
            # Find the closest trade outcome of the same signal_type
            matching_outcomes = [o for o in outcomes if o.get('signal_type') == sig_type]
            if not matching_outcomes:
                continue
                
            closest_outcome = None
            min_diff = None
            
            for o in matching_outcomes:
                o_time = parse_dt(o.get('created_at'))
                if not o_time:
                    continue
                diff = abs((o_time - sig_time).total_seconds())
                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    closest_outcome = o
            
            # Require proximity within 5 days to ensure signal-trade logical alignment
            if closest_outcome and min_diff <= 86400 * 5:
                pnl_pct = float(closest_outcome.get('pnl_pct', 0.0) or 0.0)
                # Convert trade PnL to predicted-frame return: sig_score * pnl_pct (so winning shorts align positively)
                matched_pairs.append((sig_score, sig_score * pnl_pct))
                
        if len(matched_pairs) < MIN_TRADES:
            logger.info(f"Fewer than {MIN_TRADES} matched pairs ({len(matched_pairs)}). Returning None.")
            return None
            
        signal_scores = [p[0] for p in matched_pairs]
        actual_returns = [p[1] for p in matched_pairs]
        
        try:
            ic, pvalue = spearmanr(signal_scores, actual_returns)
            if np.isnan(ic):
                return 0.0
            return float(ic)
        except Exception as e:
            logger.error(f"Error calculating Spearman rank correlation: {e}")
            return None

    def classify_status(self, ic: float, trade_count: int) -> tuple:
        """Classify signal status based on IC score and trade count."""
        if trade_count < MIN_TRADES:
            return ('INSUFFICIENT_DATA', 
                    'Not enough trades to evaluate signal quality')
        
        if ic is None:
            return ('INSUFFICIENT_DATA',
                    'Cannot calculate IC — insufficient matched data')
        
        if ic >= IC_HEALTHY_THRESHOLD:
            return ('HEALTHY',
                    f'Signal healthy. IC={ic:.4f} — edge confirmed')
        
        if ic >= IC_DEGRADING_THRESHOLD:
            return ('DEGRADING',
                    f'Signal degrading. IC={ic:.4f} — monitor closely, consider reducing size 25%')
        
        if ic >= IC_DEAD_THRESHOLD:
            return ('DEGRADING',
                    f'Signal weak. IC={ic:.4f} — reduce size 50%, review strategy')
        
        return ('DEAD',
                f'Signal dead. IC={ic:.4f} — DISABLE strategy, investigate immediately')

    async def write_signal_performance(self, payload: dict) -> None:
        """Write performance record to local and cloud Supabase signal_performance table."""
        targets = []
        if self.supabase_url and self.supabase_anon_key:
            targets.append((self.supabase_url, self.supabase_anon_key, "CLOUD"))
            
        local_url = os.getenv("SUPABASE_LOCAL_URL")
        local_key = os.getenv("SUPABASE_LOCAL_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_LOCAL_ANON_KEY")
        if local_url and local_key:
            targets.append((local_url, local_key, "LOCAL"))
            
        for url, key, label in targets:
            target_url = f"{url}/rest/v1/signal_performance"
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
                        logger.info(f"Recorded signal performance for {payload.get('symbol')} to Supabase {label}.")
                    else:
                        logger.error(f"Failed to record signal performance to Supabase {label}: {resp.status_code} — {resp.text}")
            except Exception as e:
                logger.error(f"Failed to write signal performance to Supabase {label}: {e}")

    async def _send_alert(self, text: str) -> None:
        """Helper to send instant alert to Telegram."""
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID', '8641189809')
        if not token:
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    async def analyze(self) -> dict:
        """Run full signal health check across all configured symbols."""
        healthy_list = []
        degrading_list = []
        dead_list = []
        insufficient_list = []
        summary_table = []
        
        for symbol in self.symbols:
            logger.info(f"Analyzing signal decay for {symbol}...")
            signals = await self.get_signal_history(symbol)
            outcomes = await self.get_trade_outcomes(symbol)
            
            trade_count = len(outcomes)
            ic = self.calculate_ic(signals, outcomes)
            status, recommendation = self.classify_status(ic, trade_count)
            if status == 'INSUFFICIENT_DATA':
                ic = None
            
            # Calculate win rate and avg return for writing to database
            win_count = sum(1 for o in outcomes if o.get('win') in (True, 1, "true", "True", "1"))
            win_rate = win_count / trade_count if trade_count > 0 else 0.0
            avg_return = sum(float(o.get('pnl_pct', 0.0) or 0.0) for o in outcomes) / trade_count if trade_count > 0 else 0.0
            
            # Map asset class based on symbol structure
            asset_class = "crypto" if "/" in symbol else "equities"
            # Deduce signal type (e.g. 'ut_bot' as baseline strategy)
            signal_type = "ut_bot"
            
            # Prepare database payload
            payload = {
                "symbol": symbol,
                "asset_class": asset_class,
                "signal_type": signal_type,
                "information_coefficient": float(ic) if ic is not None else None,
                "win_rate": float(win_rate),
                "avg_return": float(avg_return),
                "trade_count": int(trade_count),
                "lookback_days": int(LOOKBACK_DAYS),
                "status": status,
                "recommendation": recommendation,
                "calculated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.write_signal_performance(payload)
            
            # Group by status
            if status == 'HEALTHY':
                healthy_list.append(symbol)
            elif status == 'DEGRADING':
                # Check recommendation to differentiate degrading vs weak/degrading
                if ic is not None and ic < 0.005:
                    degrading_list.append(f"{symbol} (weak)")
                else:
                    degrading_list.append(symbol)
            elif status == 'DEAD':
                dead_list.append(symbol)
            else:
                insufficient_list.append(symbol)
                
            summary_table.append({
                "symbol": symbol,
                "ic": ic,
                "status": status,
                "trade_count": trade_count,
                "recommendation": recommendation
            })
            
            # Trigger immediate Telegram alerts
            if status == 'DEAD':
                alert = (
                    f"🚨 <b>SIGNAL DEAD: {symbol}</b>\n"
                    f"IC = {ic:.4f} (threshold: {IC_DEAD_THRESHOLD})\n"
                    f"{trade_count} trades analyzed\n"
                    f"<b>ACTION REQUIRED:</b> Review {symbol} strategy immediately"
                )
                await self._send_alert(alert)
            elif status == 'DEGRADING':
                alert = (
                    f"⚠️ <b>Signal Degrading: {symbol}</b>\n"
                    f"IC = {ic:.4f} | Trades: {trade_count}\n"
                    f"Recommendation: {recommendation}"
                )
                await self._send_alert(alert)
                
        # Determine overall health
        if dead_list:
            overall_health = "CRITICAL"
        elif degrading_list:
            overall_health = "WARNING"
        else:
            overall_health = "HEALTHY"
            
        return {
            "symbols_analyzed": len(self.symbols),
            "healthy": healthy_list,
            "degrading": degrading_list,
            "dead": dead_list,
            "insufficient_data": insufficient_list,
            "overall_health": overall_health,
            "summary_table": summary_table,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

    def format_daily_report(self, decay_summary: dict) -> str:
        """Format signal health decay summary report as standard Telegram message."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        def format_list(lst):
            return ", ".join(lst) if lst else "None"
            
        # Get worst 3 by IC score (ignoring insufficient data)
        valid_items = [item for item in decay_summary['summary_table'] if item['ic'] is not None]
        valid_items.sort(key=lambda x: x['ic'])
        worst_lines = []
        for item in valid_items[:3]:
            worst_lines.append(f"• {item['symbol']}: IC = {item['ic']:.4f}")
        worst_text = "\n".join(worst_lines) if worst_lines else "None"
        
        report = (
            f"📊 <b>Signal Health Report</b>\n"
            f"Date: {date_str}\n\n"
            f"✅ Healthy ({len(decay_summary['healthy'])}): {format_list(decay_summary['healthy'])}\n"
            f"⚠️ Degrading ({len(decay_summary['degrading'])}): {format_list(decay_summary['degrading'])}\n"
            f"🚨 Dead ({len(decay_summary['dead'])}): {format_list(decay_summary['dead'])}\n"
            f"📊 Insufficient data ({len(decay_summary['insufficient_data'])}): {format_list(decay_summary['insufficient_data'])}\n\n"
            f"Overall Status: <b>{decay_summary['overall_health']}</b>\n\n"
            f"Worst performing by IC:\n"
            f"{worst_text}"
        )
        return report
