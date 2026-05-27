import asyncio
import sys
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')
sys.path.insert(0, '/home/k2/ut-bot-lumibot')

from agents.var_risk_engine import VaRRiskEngine

async def run():
    engine = VaRRiskEngine()
    result = await engine.full_risk_check()
    var_res = result['var']
    dd_res = result['drawdown']
    conc_res = result['concentration']

    print(f"VaR (95%, 30d): {var_res['var_pct']:.2%} (${var_res['var_dollar']:,.0f})")
    print(f"Drawdown (30d): {dd_res['drawdown_pct']:.2%}")
    print(f"Positions: {conc_res['position_count']} (Crypto: {conc_res['crypto_exposure_pct']:.1%}, Equity: {conc_res['equity_exposure_pct']:.1%})")
    print(f"Overall Action: {result['overall_action']}")
    
    if result['overall_action'] != 'OK':
        try:
            import os, requests
            token = os.getenv('TELEGRAM_BOT_TOKEN')
            if token:
                msg = engine.format_telegram_alert(result)
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
