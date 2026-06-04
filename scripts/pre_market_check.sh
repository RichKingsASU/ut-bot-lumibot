#!/bin/bash
# Pre-market readiness check — runs at 8:45 AM ET on trading days
cd /home/k2/ut-bot-lumibot
source venv/bin/activate

python3 -c "
import os, httpx, datetime
from dotenv import load_dotenv
load_dotenv('/home/k2/ut-bot-lumibot/.env')

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
h = {'apikey': key, 'Authorization': f'Bearer {key}'}
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
now = datetime.datetime.now(datetime.timezone.utc)

def q(table, params):
    try:
        r = httpx.get(f'{url}/rest/v1/{table}', headers=h, params=params, timeout=5)
        return r.json()
    except:
        return []

# Check bot heartbeat
bot_status = q('bot_status', {'limit': '1'})
hb_status = '❌ unknown'
if bot_status:
    hb = bot_status[0].get('last_heartbeat', '')
    if hb:
        try:
            hb_dt = datetime.datetime.fromisoformat(hb.replace('Z', '+00:00'))
            age = (now - hb_dt).total_seconds()
            hb_status = f'✅ {int(age)}s ago' if age < 120 else f'⚠️ STALE {int(age/60)}m ago'
        except Exception as e:
            hb_status = f'⚠️ parse error: {e}'

# Check last signal
signals = q('agent_signals', {'order': 'created_at.desc', 'limit': '1'})
sig_status = '❌ none'
if signals:
    try:
        sig_ts = signals[0].get('created_at', '')
        sig_dt = datetime.datetime.fromisoformat(sig_ts.replace('Z', '+00:00'))
        age = (now - sig_dt).total_seconds()
        sig_status = f'✅ {int(age/60)}m ago — {signals[0].get(\"symbol\",\"?\")} {signals[0].get(\"action\",\"?\")}'
    except Exception as e:
        sig_status = f'⚠️ parse error: {e}'

# Check Alpaca
alpaca_equity = '?'
try:
    ak = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY')
    ask = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET')
    r = httpx.get('https://paper-api.alpaca.markets/v2/account',
        headers={'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': ask}, timeout=5)
    alpaca_equity = f'\${float(r.json().get(\"equity\",0)):,.2f}'
except:
    pass

# Check tmux sessions and systemd services
import subprocess
sessions = subprocess.run(['tmux', 'list-sessions', '-F', '#{session_name}'],
    capture_output=True, text=True).stdout.strip().split('\n')
required_tmux = ['sentiment','vectors','options','telegram-bot','watchdog']
required_systemd = {
    'agents': 'da-agents',
    'crypto-bot': 'da-crypto-bot',
    'trading-bot': 'da-trading-bot'
}
statuses = []
for s in ['agents','crypto-bot','trading-bot','sentiment','vectors','options','telegram-bot','watchdog']:
    if s in required_systemd:
        unit = required_systemd[s]
        is_active = subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode == 0
        statuses.append(f'  {\"✅\" if is_active else \"❌\"} {s} (systemd)')
    else:
        statuses.append(f'  {\"✅\" if s in sessions else \"❌\"} {s} (tmux)')
session_status = '\n'.join(statuses)

# Overall health
issues = hb_status.count('⚠️') + hb_status.count('❌') + sig_status.count('❌')
overall = '🟢 READY FOR TRADING' if issues == 0 else '🔴 ISSUES DETECTED'

msg = f'''🌅 PRE-MARKET CHECK — {now.strftime(\"%H:%M\")} UTC

💼 Equity: {alpaca_equity}
🤖 Heartbeat: {hb_status}
⚡ Last Signal: {sig_status}

🖥️ Sessions:
{session_status}

{overall}
disruptingalpha.com/admin/health'''

try:
    httpx.post(f'https://api.telegram.org/bot{bot_token}/sendMessage',
        data={'chat_id': '8641189809', 'text': msg}, timeout=10)
except Exception as e:
    print(f'WARNING: Telegram send failed: {e}')
print(msg)
" >> /home/k2/logs/pre_market.log 2>&1
