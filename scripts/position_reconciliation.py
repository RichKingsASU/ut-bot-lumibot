import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')

async def reconcile_positions():
    alpaca_key = os.getenv('ALPACA_API_KEY')
    alpaca_secret = os.getenv('ALPACA_API_SECRET')
    alpaca_base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    headers_alpaca = {
        'APCA-API-KEY-ID': alpaca_key,
        'APCA-API-SECRET-KEY': alpaca_secret
    }
    
    headers_supabase = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Get Alpaca positions
            pos_resp = await client.get(f"{alpaca_base}/v2/positions", headers=headers_alpaca)
            alpaca_positions = pos_resp.json() if pos_resp.status_code == 200 else []
            alpaca_symbols = set(p['symbol'] for p in alpaca_positions)

            # 2. Get Supabase snapshot
            snap_resp = await client.get(
                f"{supabase_url}/rest/v1/portfolio_snapshots",
                headers=headers_supabase,
                params={
                    "select": "symbols",
                    "order": "created_at.desc",
                    "limit": "1"
                }
            )
            snapshot_symbols = set()
            if snap_resp.status_code == 200:
                rows = snap_resp.json()
                if rows and 'symbols' in rows[0] and rows[0]['symbols']:
                    # Assuming symbols is a list of strings
                    snapshot_symbols = set(rows[0]['symbols'])

            # Compare
            mismatch = alpaca_symbols != snapshot_symbols
            
            if mismatch:
                msg = (
                    f"⚠️ Position Mismatch Detected\n"
                    f"Alpaca shows: {sorted(list(alpaca_symbols))}\n"
                    f"Snapshot shows: {sorted(list(snapshot_symbols))}\n"
                    f"Action: Manual review needed"
                )
                print(msg)
                
                token = os.getenv('TELEGRAM_BOT_TOKEN')
                if token:
                    await client.post(
                        f'https://api.telegram.org/bot{token}/sendMessage',
                        json={'chat_id': '8641189809', 'text': msg}
                    )
            else:
                print("Positions reconciled successfully.")
                print(f"Symbols: {sorted(list(alpaca_symbols))}")

    except Exception as e:
        print(f"Error during position reconciliation: {e}")

if __name__ == '__main__':
    asyncio.run(reconcile_positions())
