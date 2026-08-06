"""
run_agents.py — Disrupting Alpha v2 Phase 4
Entry point: sends Telegram startup notification, then runs the LangGraph
orchestrator pipeline every 15 minutes indefinitely.
Also runs a daily signal decay health check at 8:00 PM ET.

Usage:
    python run_agents.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
import pytz
import httpx
import requests
from dotenv import load_dotenv

from adapters import component_heartbeat

# ── Bootstrap ──────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("RunAgents")

_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8641189809")

_CYCLE_INTERVAL_SECONDS = 900  # 15 minutes


# ── Telegram helper ────────────────────────────────────────────────────────────

async def _send_telegram(text: str, chat_id: str = _TELEGRAM_CHAT_ID) -> None:
    """Send a Telegram message (best-effort, never raises)."""
    token = _TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; skipping Telegram notification.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram message sent successfully.")
            else:
                logger.error(f"Telegram send failed: {resp.status_code} — {resp.text}")
    except Exception as exc:
        logger.error(f"Telegram send exception: {exc}")


# ── Daily health check helper ──────────────────────────────────────────────────

async def run_dma_daily_evaluation() -> None:
    """Evaluate DMA 20/200 crossover after market close. Logs to signal_log + Telegram alert on crossover."""
    logger.info("[RunAgents] Running DMA 20/200 daily evaluation...")
    try:
        from pathlib import Path
        import pandas as pd
        from strategies.dma_crossover import DmaCrossoverStrategy

        storage = Path("/mnt/tick-storage/historical/equities/SPY")
        files = sorted(storage.glob("SPY_1D_*.parquet"))
        if not files:
            logger.warning("[RunAgents] No SPY daily parquet data found for DMA evaluation")
            return

        dfs = [pd.read_parquet(f) for f in files]
        df = pd.concat(dfs, ignore_index=True)
        if "ts" in df.columns and "timestamp" not in df.columns:
            df = df.rename(columns={"ts": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"])
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()

        strat = DmaCrossoverStrategy(fast_period=20, slow_period=200)
        result = strat.evaluate(df)

        strat.log_signal_sync(result)

        if result.get("is_crossover"):
            strat.send_crossover_alert_sync(result)
            logger.info(f"[RunAgents] DMA CROSSOVER: {result['action']} signal on {result.get('bar_time')}")
        else:
            logger.info(f"[RunAgents] DMA evaluation: HOLD (fast_ma={result.get('fast_ma')}, slow_ma={result.get('slow_ma')})")

    except Exception as exc:
        logger.error(f"[RunAgents] DMA evaluation error: {exc}", exc_info=True)


async def run_daily_signal_health() -> dict:
    """Run once per day at 8:00 PM ET to analyze signal performance and send Telegram report."""
    logger.info("[RunAgents] Running daily signal health check...")
    try:
        from agents.signal_decay_monitor import SignalDecayMonitor
        monitor = SignalDecayMonitor('signal-decay-monitor')
        summary = await monitor.analyze()
        report = monitor.format_daily_report(summary)
        
        # Send daily Telegram report
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID', '8641189809')
        if token:
            url = f'https://api.telegram.org/bot{token}/sendMessage'
            requests.post(
                url,
                json={'chat_id': chat_id, 'text': report, 'parse_mode': 'HTML'}
            )
            logger.info("[RunAgents] Daily signal health Telegram report sent successfully.")
        return summary
    except Exception as exc:
        logger.error(f"[RunAgents] Error in run_daily_signal_health: {exc}", exc_info=True)
        return {}


async def send_morning_briefing() -> None:
    """Send Telegram message at 9:15 AM ET daily with Greeks and system status."""
    logger.info("[RunAgents] Sending morning briefing...")
    try:
        from supabase import create_client
        
        # Connect to Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not supabase_key:
            logger.warning("[RunAgents] Supabase credentials missing, cannot send briefing.")
            return
            
        supabase = create_client(supabase_url, supabase_key)
        
        # Get latest regime
        regime_data = supabase.table("regime_states").select("*").order("detected_at", desc=True).limit(1).execute()
        overall_regime = "UNKNOWN"
        if regime_data.data:
            overall_regime = regime_data.data[0].get("regime", "UNKNOWN")
            
        strategy_recommendation = "HOLD" if overall_regime == "UNKNOWN" else "TREND_FOLLOWING" if overall_regime == "BULL_NORMAL" else "MEAN_REVERSION"
            
        # Get latest greeks for symbols
        symbols = ['SPY', 'QQQ', 'IWM', 'NVDA', 'TSLA', 'AAPL']
        greeks_text = ""
        for sym in symbols:
            snap = supabase.table("greeks_snapshots").select("*").eq("symbol", sym).order("snapshot_at", desc=True).limit(1).execute()
            if snap.data:
                d = snap.data[0]
                greeks_text += f"  {sym}: IV Rank {d.get('iv_rank', 0):.0f} ({d.get('trade_mode', 'NEUTRAL')})\n"
                
        # Get circuit breakers (gamma > 0.05 in last 24h)
        now_utc = datetime.utcnow()
        twenty_four_hours_ago = (now_utc.timestamp() - 86400) * 1000 # Just an approx ISO
        
        alerts_text = "NONE"
        cb_data = supabase.table("greeks_snapshots").select("symbol, gamma").gt("gamma", 0.05).order("snapshot_at", desc=True).limit(5).execute()
        if cb_data.data:
            alerts_text = "\n".join([f"  {d['symbol']} Gamma: {d['gamma']:.3f}" for d in cb_data.data])
            
        # Get tick count from QuestDB
        questdb_count = 0
        try:
            resp = requests.get("http://localhost:9000/exec?query=SELECT+count()+FROM+ticks", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if "dataset" in data and len(data["dataset"]) > 0:
                    questdb_count = data["dataset"][0][0]
        except Exception as e:
            logger.error(f"QuestDB error: {e}")
            
        # News and signals counts
        today_iso = datetime.now(pytz.timezone('America/New_York')).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc).isoformat()
        
        news_count = 0
        news_resp = supabase.table("news_articles").select("id", count="exact").gt("created_at", today_iso).execute()
        if hasattr(news_resp, 'count') and news_resp.count is not None:
            news_count = news_resp.count
            
        signals_count = 0
        signals_resp = supabase.table("agent_signals").select("id", count="exact").gt("created_at", today_iso).execute()
        if hasattr(signals_resp, 'count') and signals_resp.count is not None:
            signals_count = signals_resp.count
            
        now_str = datetime.now(pytz.timezone('America/New_York')).strftime("%Y-%m-%d")
        
        msg = f"""📊 <b>Disrupting Alpha — Morning Greeks Briefing</b>
{now_str} | Pre-market

🎯 <b>Today's Regime:</b> {overall_regime}
Strategy: {strategy_recommendation}

📈 <b>Symbol Status:</b>
{greeks_text}
⚡ <b>Alerts:</b>
{alerts_text}

🔢 <b>Data:</b>
Tick count: {questdb_count}
News articles (24h): {news_count}
Agent signals today: {signals_count}"""

        await _send_telegram(msg)
    except Exception as exc:
        logger.error(f"[RunAgents] Error in morning briefing: {exc}", exc_info=True)

async def send_afternoon_check() -> None:
    """Send Telegram message at 2:00 PM ET daily."""
    logger.info("[RunAgents] Sending afternoon check...")
    try:
        from supabase import create_client
        import requests
        
        # Connect to Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not supabase_key:
            return
            
        supabase = create_client(supabase_url, supabase_key)
        
        # Get regime states
        today_iso = datetime.now(pytz.timezone('America/New_York')).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc).isoformat()
        
        regime_data = supabase.table("regime_states").select("*").gte("detected_at", today_iso).order("detected_at", desc=True).execute()
        current_regime = "UNKNOWN"
        morning_regime = "UNKNOWN"
        
        if regime_data.data:
            current_regime = regime_data.data[0].get("regime", "UNKNOWN")
            morning_regime = regime_data.data[-1].get("regime", "UNKNOWN")
            
        shift_detected = "YES" if current_regime != morning_regime else "NO"
        
        # Alpaca positions
        import alpaca_trade_api as tradeapi
        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_API_SECRET")
        base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        
        positions_count = 0
        unrealized_pl = 0.0
        if api_key and api_secret:
            try:
                api = tradeapi.REST(api_key, api_secret, base_url, api_version='v2')
                positions = api.list_positions()
                positions_count = len(positions)
                unrealized_pl = sum(float(p.unrealized_pl) for p in positions)
            except Exception as e:
                logger.error(f"Alpaca error: {e}")
                
        time_str = datetime.now(pytz.timezone('America/New_York')).strftime("%I:%M %p ET")
        
        rec = "Regime changed — review positions" if shift_detected == "YES" else "Regime stable — hold current strategy"
        
        msg = f"""🔄 <b>Afternoon Regime Check</b>
{time_str}

Morning regime: {morning_regime}
Current regime: {current_regime}
Shift detected: {shift_detected}

📊 <b>P&L Update:</b>
Open positions: {positions_count}
Unrealized P&L: ${unrealized_pl:.2f}

Recommendation:
{rec}"""

        await _send_telegram(msg)
    except Exception as exc:
        logger.error(f"[RunAgents] Error in afternoon check: {exc}", exc_info=True)


# ── Main loop ──────────────────────────────────────────────────────────────────

async def main() -> None:
    """Send startup notification, then run the orchestrator pipeline every 15 min."""
    # Import after load_dotenv so agents pick up env vars
    from agents.orchestrator import run_cycle, _poll_kill_switch

    startup_message = (
        "🤖 Agent orchestrator started — LangGraph pipeline every 15min"
    )
    await _send_telegram(startup_message, chat_id="8641189809")
    logger.info(startup_message)

    cycle_count = 0
    morning_sent = False
    afternoon_sent = False
    dma_evaluated = False
    
    while True:
        # Kill switch: poll Supabase bot_status at the start of every cycle
        if _poll_kill_switch():
            logger.warning("[RunAgents] Kill switch activated — exiting agent loop cleanly.")
            await _send_telegram("🛑 Kill switch activated — da-agents halting cleanly.")
            break

        now_et = datetime.now(pytz.timezone('America/New_York'))
        
        # Reset daily flags at midnight
        if now_et.hour == 0 and now_et.minute == 0:
            morning_sent = False
            afternoon_sent = False
            dma_evaluated = False
            
        # Morning briefing at 9:15 AM ET
        if now_et.hour == 9 and now_et.minute == 15 and not morning_sent:
            await send_morning_briefing()
            morning_sent = True
            
        # Afternoon check at 2:00 PM ET
        if now_et.hour == 14 and now_et.minute == 0 and not afternoon_sent:
            await send_afternoon_check()
            afternoon_sent = True
            
        cycle_count += 1
        logger.info(f"[RunAgents] ── Starting cycle #{cycle_count} (ET: {now_et.strftime('%H:%M:%S')}) ──")
        
        try:
            await run_cycle()
            logger.info(f"[RunAgents] ── Cycle #{cycle_count} complete ──")
            # Component heartbeat: written ONLY on successful cycle completion,
            # so its freshness is the "cycle advanced" signal the watchdog uses.
            component_heartbeat.beat(
                "run_agents",
                status="ok",
                last_successful_cycle_id=cycle_count,
            )
        except (httpx.ConnectError, httpx.TimeoutException,
                ConnectionResetError, OSError) as e:
            logger.warning(f"Network error: {e} — retrying in 60s")
            await asyncio.sleep(60)
            continue
        except Exception as e:
            logger.error(f"Cycle error: {e} — retrying in 30s")
            await asyncio.sleep(30)
            continue

        # Daily at 4:30 PM ET: DMA 20/200 crossover evaluation (after market close)
        if now_et.hour == 16 and now_et.minute >= 30 and not dma_evaluated:
            await run_dma_daily_evaluation()
            dma_evaluated = True

        # Daily at 8:00 PM ET: signal health check
        if now_et.hour == 20 and now_et.minute < 15:
            await run_daily_signal_health()

        logger.info(
            f"[RunAgents] Sleeping {_CYCLE_INTERVAL_SECONDS}s until next cycle..."
        )
        await asyncio.sleep(_CYCLE_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
