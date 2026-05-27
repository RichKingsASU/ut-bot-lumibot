#!/bin/bash
echo "=== DISRUPTING ALPHA — MORNING STARTUP ==="
echo "Time: $(date)"
echo ""

cd /home/k2/ut-bot-lumibot
source venv/bin/activate

echo "1. Health check..."
python3 scripts/health_check.py | \
  grep -E "OVERALL|✅|❌|⚠️" | tail -20

echo ""
echo "2. VaR check..."
python3 scripts/run_var_check.py 2>&1 | tail -5

echo ""
echo "3. Pairs analysis..."
python3 scripts/run_pairs_analysis.py 2>&1 | tail -8

echo ""
echo "4. Account status..."
python3 -c "
import os, httpx
from dotenv import load_dotenv
load_dotenv('/home/k2/ut-bot-lumibot/.env')
ah = {
    'APCA-API-KEY-ID': os.getenv('ALPACA_API_KEY'),
    'APCA-API-SECRET-KEY': os.getenv('ALPACA_API_SECRET')
}
base = os.getenv('ALPACA_BASE_URL')
acc = httpx.get(f'{base}/v2/account', headers=ah).json()
print(f'Equity: \${float(acc[\"equity\"]):,.2f}')
print(f'Buying power: \${float(acc[\"buying_power\"]):,.2f}')
pos = httpx.get(f'{base}/v2/positions', headers=ah).json()
print(f'Positions: {len(pos)}')
for p in pos:
    pl = float(p.get('unrealized_pl', 0))
    print(f'  {p[\"symbol\"]}: P&L=\${pl:,.2f}')
"

echo ""
echo "5. Current regimes..."
python3 -c "
import os, httpx
from dotenv import load_dotenv
load_dotenv('/home/k2/ut-bot-lumibot/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
h = {'apikey': key, 'Authorization': f'Bearer {key}'}
r = httpx.get(f'{url}/rest/v1/regime_states',
    headers=h,
    params={'select': 'symbol,regime',
            'order': 'detected_at.desc',
            'limit': '9'})
seen = {}
for row in r.json():
    if row['symbol'] not in seen:
        seen[row['symbol']] = row['regime']
        print(f'  {row[\"symbol\"]}: {row[\"regime\"]}')
"

echo ""
echo "6. Sessions..."
tmux list-sessions

echo ""
echo "=== READY FOR MARKET OPEN 9:30 AM ET ==="
