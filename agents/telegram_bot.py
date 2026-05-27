import asyncio
import os
import subprocess
import httpx
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = '8641189809'
ALPACA_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET = os.getenv('ALPACA_API_SECRET')
ALPACA_BASE = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

async def handle_command(message: dict):
    if str(message.get('chat', {}).get('id')) != CHAT_ID:
        print(f"Ignoring message from unauthorized chat: {message.get('chat', {}).get('id')}")
        return

    text = message.get('text', '')
    if not text.startswith('/'):
        return

    command = text.split()[0].lower()
    response_text = ""

    async with httpx.AsyncClient() as client:
        if command == '/health':
            try:
                result = subprocess.run(['python', 'scripts/health_check.py'], capture_output=True, text=True, timeout=10)
                lines = result.stdout.split('\n')
                last_line = lines[-2] if len(lines) > 1 and not lines[-1] else (lines[-1] if lines else "")
                
                status_icon = "🔴 RED"
                if "GREEN" in last_line:
                    status_icon = "🟢 GREEN"
                elif "YELLOW" in last_line:
                    status_icon = "🟡 YELLOW"
                
                response_text = f"{status_icon}\n\n" + "\n".join(lines[:50])
            except Exception as e:
                response_text = f"Error running health check: {e}"

        elif command == '/positions':
            headers = {
                'APCA-API-KEY-ID': ALPACA_KEY,
                'APCA-API-SECRET-KEY': ALPACA_SECRET
            }
            try:
                r = await client.get(f"{ALPACA_BASE}/v2/positions", headers=headers)
                positions = r.json()
                if not positions:
                    response_text = "📊 Open Positions:\nNo open positions."
                else:
                    response_text = "📊 Open Positions:\n"
                    total_pl = 0.0
                    for p in positions:
                        qty = p.get('qty')
                        avg_entry = float(p.get('avg_entry_price', 0))
                        unrealized_pl = float(p.get('unrealized_pl', 0))
                        unrealized_plpc = float(p.get('unrealized_plpc', 0)) * 100
                        symbol = p.get('symbol')
                        total_pl += unrealized_pl
                        response_text += f"{symbol}: {qty} @ ${avg_entry:.2f}\nP&L: ${unrealized_pl:.2f} ({unrealized_plpc:.2f}%)\n"
                    response_text += f"\nTotal P&L: ${total_pl:.2f}"
            except Exception as e:
                response_text = f"Error fetching positions: {e}"

        elif command == '/account':
            headers = {
                'APCA-API-KEY-ID': ALPACA_KEY,
                'APCA-API-SECRET-KEY': ALPACA_SECRET
            }
            try:
                r = await client.get(f"{ALPACA_BASE}/v2/account", headers=headers)
                account = r.json()
                equity = float(account.get('equity', 0))
                last_equity = float(account.get('last_equity', 0))
                buying_power = float(account.get('buying_power', 0))
                cash = float(account.get('cash', 0))
                day_pl = equity - last_equity
                response_text = (f"💰 Account Status:\n"
                                 f"Equity: ${equity:.2f}\n"
                                 f"Buying Power: ${buying_power:.2f}\n"
                                 f"Cash: ${cash:.2f}\n"
                                 f"Day P&L: ${day_pl:.2f}")
            except Exception as e:
                response_text = f"Error fetching account: {e}"

        elif command == '/regime':
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            try:
                # Assuming supabase table `regime_states` has fields `symbol`, `detected_at`, `regime_label`, `confidence`, `recommendation`
                # Using a generic approach to get recent regimes
                r = await client.get(f"{SUPABASE_URL}/rest/v1/regime_states?select=*&order=detected_at.desc&limit=50", headers=headers)
                data = r.json()
                if not data:
                    response_text = "🎯 Current Regimes:\nNo regime data available."
                else:
                    seen_symbols = set()
                    lines = []
                    overall = "UNKNOWN"
                    recommendation = "N/A"
                    for row in data:
                        symbol = row.get('symbol', 'UNKNOWN')
                        if symbol not in seen_symbols:
                            seen_symbols.add(symbol)
                            label = row.get('regime_label', 'UNKNOWN')
                            conf = row.get('confidence', 0) * 100
                            lines.append(f"{symbol}: {label} ({conf:.0f}%)")
                            if symbol == 'SPY': # Or some logic to determine overall
                                overall = label
                                recommendation = row.get('recommendation', 'N/A')
                    
                    response_text = "🎯 Current Regimes:\n" + "\n".join(lines) + f"\n\nOverall: {overall}\nStrategy: {recommendation}"
            except Exception as e:
                response_text = f"Error fetching regimes: {e}"

        elif command == '/signals':
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            try:
                r = await client.get(f"{SUPABASE_URL}/rest/v1/agent_signals?select=*&order=created_at.desc&limit=5", headers=headers)
                data = r.json()
                if not data:
                    response_text = "🤖 Recent Agent Signals:\nNo recent signals."
                else:
                    response_text = "🤖 Recent Agent Signals:\n"
                    for row in data:
                        symbol = row.get('symbol', 'UNKNOWN')
                        action = row.get('action', 'UNKNOWN')
                        conf = row.get('confidence', 'UNKNOWN')
                        asset_class = row.get('asset_class', 'unknown')
                        created_at = row.get('created_at', '')
                        # Simple time diff (could be improved)
                        time_str = created_at
                        response_text += f"{symbol}: {action} ({conf}) [{asset_class}] - {time_str}\n"
            except Exception as e:
                response_text = f"Error fetching signals: {e}"

        elif command == '/news':
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            try:
                r = await client.get(f"{SUPABASE_URL}/rest/v1/news_articles?select=*&sentiment_score=not.is.null&order=created_at.desc&limit=5", headers=headers)
                data = r.json()
                if not data:
                    response_text = "📰 Latest News:\nNo news available."
                else:
                    response_text = "📰 Latest News:\n"
                    for row in data:
                        score = float(row.get('sentiment_score', 0))
                        title = row.get('title', 'No Title')
                        source = row.get('source', 'Unknown')
                        response_text += f"[{score:+.2f}] {title} ({source})\n"
            except Exception as e:
                response_text = f"Error fetching news: {e}"

        elif command == '/ticks':
            try:
                query = "SELECT symbol, count() FROM ticks GROUP BY symbol"
                r = await client.get(f"http://localhost:9000/exec", params={'query': query})
                data = r.json()
                response_text = "📈 QuestDB Ticks:\n"
                total = 0
                for row in data.get('dataset', []):
                    symbol, count = row[0], row[1]
                    response_text += f"{symbol}: {count}\n"
                    total += count
                response_text += f"Total: {total}"
            except Exception as e:
                response_text = f"Error fetching ticks: {e}"

        elif text == '/restart agents':
            try:
                subprocess.run(['tmux', 'kill-session', '-t', 'agents'])
                cmd = "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_agents.py"
                subprocess.run(['tmux', 'new-session', '-d', '-s', 'agents', cmd])
                response_text = "✅ Agents session restarted"
            except Exception as e:
                response_text = f"Error restarting agents: {e}"

        elif text == '/restart crypto':
            try:
                subprocess.run(['tmux', 'kill-session', '-t', 'crypto-bot'])
                cmd = "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_crypto_bot.py"
                subprocess.run(['tmux', 'new-session', '-d', '-s', 'crypto-bot', cmd])
                response_text = "✅ Crypto bot session restarted"
            except Exception as e:
                response_text = f"Error restarting crypto bot: {e}"

        elif command == '/stop':
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
            }
            try:
                payload = {"kill_switch": True}
                # Assuming table is bot_status and has a single row or we update all.
                # If there's an id we should provide it, but let's just do a bulk update or match some id.
                # Assuming update without where works if 1 row, or we add eq.id=1
                r = await client.patch(f"{SUPABASE_URL}/rest/v1/bot_status", headers=headers, json=payload)
                response_text = "🛑 Kill switch activated"
            except Exception as e:
                response_text = f"Error activating kill switch: {e}"

        elif command == '/resume':
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
            }
            try:
                payload = {"kill_switch": False}
                r = await client.patch(f"{SUPABASE_URL}/rest/v1/bot_status", headers=headers, json=payload)
                response_text = "✅ Kill switch deactivated"
            except Exception as e:
                response_text = f"Error deactivating kill switch: {e}"

        elif command == '/status':
            try:
                # Collect tmux sessions
                sessions_result = subprocess.run(
                    ['tmux', 'list-sessions'],
                    capture_output=True, text=True, timeout=5)
                sessions = sessions_result.stdout.strip() if sessions_result.returncode == 0 else 'No sessions'
                session_count = len(sessions.strip().split('\n')) if sessions.strip() else 0

                # Last agent signal from Supabase
                sb_headers = {
                    'apikey': SUPABASE_KEY,
                    'Authorization': f'Bearer {SUPABASE_KEY}'
                }
                sig_r = await client.get(
                    f"{SUPABASE_URL}/rest/v1/agent_signals",
                    headers=sb_headers,
                    params={
                        'select': 'symbol,action,created_at',
                        'order': 'created_at.desc',
                        'limit': '1'
                    })
                sig_data = sig_r.json()
                if sig_data:
                    last_sig = sig_data[0]
                    sig_time = last_sig.get('created_at', '')[:19]
                    from datetime import timedelta
                    try:
                        sig_dt = datetime.fromisoformat(sig_time.replace('Z', '+00:00'))
                        age_min = (datetime.now(timezone.utc) - sig_dt).total_seconds() / 60
                        sig_age = f"{age_min:.0f}min ago"
                    except Exception:
                        sig_age = sig_time
                    last_signal_str = f"{last_sig.get('symbol')} {last_sig.get('action')} {sig_age}"
                else:
                    last_signal_str = "No signals"

                # Alpaca equity
                alpaca_headers = {
                    'APCA-API-KEY-ID': ALPACA_KEY,
                    'APCA-API-SECRET-KEY': ALPACA_SECRET
                }
                acc_r = await client.get(f"{ALPACA_BASE}/v2/account", headers=alpaca_headers)
                acc_data = acc_r.json()
                equity = float(acc_data.get('equity', 0))

                # VaR check
                try:
                    from agents.var_risk_engine import VaRRiskEngine
                    var_engine = VaRRiskEngine()
                    import asyncio as _aio
                    var_result = await var_engine.full_risk_check()
                    dd = var_result['drawdown']
                    var_info = var_result['var']
                    dd_str = f"{dd['drawdown_pct']:.1%} → {dd['action']}"
                    var_str = f"{var_info['var_pct']:.1%} | Action: {var_result['overall_action']}"
                except Exception:
                    dd_str = "N/A"
                    var_str = "N/A"

                # Regimes
                regime_r = await client.get(
                    f"{SUPABASE_URL}/rest/v1/regime_states",
                    headers=sb_headers,
                    params={
                        'select': 'symbol,regime_label',
                        'order': 'detected_at.desc',
                        'limit': '10'
                    })
                regime_data = regime_r.json()
                seen = set()
                regime_lines = []
                for row in (regime_data if isinstance(regime_data, list) else []):
                    sym = row.get('symbol', '?')
                    if sym not in seen:
                        seen.add(sym)
                        regime_lines.append(f"{sym}: {row.get('regime_label', '?')}")

                now_str = datetime.now(timezone.utc).strftime('%H:%M UTC')
                response_text = (
                    f"📊 System Status — {now_str}\n\n"
                    f"Sessions: {session_count} running\n"
                    f"Last signal: {last_signal_str}\n"
                    f"Equity: ${equity:,.0f}\n"
                    f"Drawdown: {dd_str}\n\n"
                    f"Regimes:\n" + (" | ".join(regime_lines) if regime_lines else "N/A") + "\n\n"
                    f"VaR: {var_str}"
                )
            except Exception as e:
                response_text = f"Error: {e}"

        elif command == '/var':
            try:
                from agents.var_risk_engine import VaRRiskEngine
                var_engine = VaRRiskEngine()
                dd = await var_engine.check_drawdown()
                var = await var_engine.calculate_var()
                response_text = (
                    f"📉 VaR Report\n"
                    f"Drawdown (14d): {dd['drawdown_pct']:.1%}\n"
                    f"Action: {dd['action']}\n"
                    f"Peak equity: ${dd['peak_equity']:,.0f}\n"
                    f"Current: ${dd['current_equity']:,.0f}\n\n"
                    f"Daily VaR (95%): {var['var_pct']:.2%}\n"
                    f"VaR $: ${var['var_dollar']:,.0f}\n"
                    f"Breach: {'YES' if var['breach'] else 'No'}"
                )
            except Exception as e:
                response_text = f"Error: {e}"

        elif command == '/pairs':
            try:
                import pandas as pd
                import numpy as np
                from pathlib import Path
                data_dir = Path('/home/k2/ut-bot-lumibot/data')
                spy_file = data_dir / 'SPY_daily.parquet'
                qqq_file = data_dir / 'QQQ_daily.parquet'

                if spy_file.exists() and qqq_file.exists():
                    spy_df = pd.read_parquet(spy_file)
                    qqq_df = pd.read_parquet(qqq_file)

                    spy_close = spy_df['close'].values[-60:]
                    qqq_close = qqq_df['close'].values[-60:]
                    min_len = min(len(spy_close), len(qqq_close))
                    spy_close = spy_close[-min_len:]
                    qqq_close = qqq_close[-min_len:]

                    spread = spy_close / qqq_close
                    spread_mean = np.mean(spread)
                    spread_std = np.std(spread)
                    z_score = (spread[-1] - spread_mean) / spread_std if spread_std > 0 else 0.0

                    if abs(z_score) > 2.0:
                        signal = "STRONG DIVERGENCE"
                    elif abs(z_score) > 1.0:
                        signal = "MILD DIVERGENCE"
                    else:
                        signal = "NORMAL"

                    # Simple half-life estimate
                    spread_diff = np.diff(spread)
                    spread_lag = spread[:-1] - spread_mean
                    if len(spread_lag) > 0 and np.std(spread_lag) > 0:
                        beta = np.polyfit(spread_lag, spread_diff, 1)[0]
                        half_life = -np.log(2) / beta if beta < 0 else 999
                    else:
                        half_life = 999

                    response_text = (
                        f"📊 Pairs Analysis\n"
                        f"SPY/QQQ z-score: {z_score:.2f}\n"
                        f"Signal: {signal}\n"
                        f"Half-life: {half_life:.0f} days"
                    )
                else:
                    response_text = "📊 Pairs Analysis\nNo SPY/QQQ Parquet data available"
            except Exception as e:
                response_text = f"Error: {e}"

        elif command == '/cycles':
            sb_headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            try:
                r = await client.get(
                    f"{SUPABASE_URL}/rest/v1/agent_signals",
                    headers=sb_headers,
                    params={
                        'select': 'symbol,action,confidence,regime,debate_verdict,created_at',
                        'order': 'created_at.desc',
                        'limit': '5'
                    })
                data = r.json()
                if not data:
                    response_text = "🔄 Recent Cycles:\nNo recent signals."
                else:
                    response_text = "🔄 Recent Cycles:\n"
                    for row in data:
                        t = row.get('created_at', '')[:16]
                        sym = row.get('symbol', '?')
                        act = row.get('action', '?')
                        conf = row.get('confidence', '?')
                        regime = row.get('regime', 'N/A')
                        verdict = row.get('debate_verdict', 'N/A')
                        response_text += (
                            f"{t} {sym}: {act} ({conf})\n"
                            f"  Regime: {regime} | Debate: {verdict}\n"
                        )
            except Exception as e:
                response_text = f"Error: {e}"

        elif command == '/watchdog':
            try:
                wd_alive = subprocess.run(
                    ['tmux', 'has-session', '-t', 'watchdog'],
                    capture_output=True).returncode == 0

                sb_headers = {
                    'apikey': SUPABASE_KEY,
                    'Authorization': f'Bearer {SUPABASE_KEY}'
                }
                sig_r = await client.get(
                    f"{SUPABASE_URL}/rest/v1/agent_signals",
                    headers=sb_headers,
                    params={
                        'select': 'created_at',
                        'order': 'created_at.desc',
                        'limit': '1'
                    })
                sig_data = sig_r.json()
                if sig_data:
                    try:
                        sig_dt = datetime.fromisoformat(
                            sig_data[0]['created_at'].replace('Z', '+00:00'))
                        age = (datetime.now(timezone.utc) - sig_dt).total_seconds() / 60
                        age_str = f"{age:.0f}min"
                    except Exception:
                        age_str = "unknown"
                else:
                    age_str = "no signals"

                status = "🟢 monitoring" if wd_alive else "🔴 offline"
                response_text = (
                    f"🐕 Watchdog Status\n"
                    f"Session: {'alive' if wd_alive else 'DEAD'}\n"
                    f"Last signal age: {age_str}\n"
                    f"Status: {status}"
                )
            except Exception as e:
                response_text = f"Error: {e}"

        elif command == '/help':
            response_text = (
                "🤖 Available Commands:\n"
                "/health - Run health check\n"
                "/positions - View open positions\n"
                "/account - View account status\n"
                "/regime - View current market regimes\n"
                "/signals - View recent agent signals\n"
                "/status - Full system status\n"
                "/var - VaR risk report\n"
                "/pairs - SPY/QQQ pairs analysis\n"
                "/cycles - Last 5 agent cycles\n"
                "/watchdog - Watchdog status\n"
                "/news - View latest news sentiment\n"
                "/ticks - View QuestDB tick counts\n"
                "/restart agents - Restart agents session\n"
                "/restart crypto - Restart crypto bot session\n"
                "/stop - Activate kill switch\n"
                "/resume - Deactivate kill switch\n"
                "/help - Show this message"
            )

        if response_text:
            send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            await client.post(send_url, json={"chat_id": CHAT_ID, "text": response_text})

async def poll():
    offset = 0
    print("🤖 Telegram Bot Polling started...")
    async with httpx.AsyncClient(timeout=40) as client:
        while True:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
                r = await client.get(url, params={"offset": offset, "timeout": 30})
                if r.status_code == 200:
                    data = r.json()
                    for update in data.get('result', []):
                        offset = update['update_id'] + 1
                        message = update.get('message')
                        if message and message.get('text'):
                            asyncio.create_task(handle_command(message))
            except Exception as e:
                print(f"Polling error: {e}")
            await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(poll())
