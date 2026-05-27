import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')
sys.path.insert(0, '/home/k2/ut-bot-lumibot')

from agents.pairs_trader import PairsTrader

async def run():
    trader = PairsTrader()
    try:
        result = await asyncio.wait_for(trader.analyze(), timeout=30)
    except asyncio.TimeoutError:
        print("Pairs trader timed out after 30s")
        return
    except Exception as e:
        print(f"Pairs trader error: {e}")
        return
    
    print(f"Pairs Analyzed: {result['pairs_analyzed']}")
    print(f"Active Signals: {result['active_signals']}")
    
    for opp in result['opportunities']:
        print(f"{opp['pair']} | Z: {opp['current_zscore']:.2f} | HL: {opp['half_life']:.0f}d | Sig: {opp['signal']}")
        
    top = result['top_opportunity']
    if top:
        msg = (
            f"📊 Pairs Trading Analysis\n"
            f"{top['pair']}: Z-score {top['current_zscore']:.2f} → {top['signal']}\n"
            f"  Cointegrated: {'YES' if top['cointegrated'] else 'NO'} (p={top['pvalue']:.3f})\n"
            f"  Half-life: {top['half_life']:.0f} days\n"
            f"  Action: {top['signal']}"
        )
        try:
            import requests
            token = os.getenv('TELEGRAM_BOT_TOKEN')
            if token:
                requests.post(
                    f'https://api.telegram.org/bot{token}/sendMessage',
                    json={'chat_id': '8641189809', 'text': msg},
                    timeout=5
                )
                print("Telegram alert sent.")
        except Exception as e:
            print(f"Failed to send Telegram alert: {e}")

if __name__ == '__main__':
    asyncio.run(run())
