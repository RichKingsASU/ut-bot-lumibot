import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
from agents.regime_detector import RegimeDetector

async def main():
    load_dotenv()
    
    # Run Equities
    equities_detector = RegimeDetector('equities-regime', asset_class='equities')
    equities_report = await equities_detector.analyze()
    
    # Run Crypto
    crypto_detector = RegimeDetector('crypto-regime', asset_class='crypto')
    crypto_report = await crypto_detector.analyze()
    
    print("=== FULL REGIME REPORT ===")
    print("EQUITIES:", json.dumps(equities_report, indent=2))
    print("CRYPTO:", json.dumps(crypto_report, indent=2))
    
    def summarize_symbols(report):
        lines = []
        for sym, data in report.get('symbol_regimes', {}).items():
            lines.append(f"  {sym}: {data.get('regime')} ({data.get('regime_probability', 0):.1%})")
        return "\n".join(lines)
    
    telegram_text = f"""🎯 Regime Detection Report
Equities: {equities_report.get('overall_regime')}
{summarize_symbols(equities_report)}

Crypto: {crypto_report.get('overall_regime')}
{summarize_symbols(crypto_report)}

Strategy: {equities_report.get('strategy_recommendation')}"""
    
    print("\n=== TELEGRAM PREVIEW ===")
    print(telegram_text)
    
    # Send Telegram
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if token:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": "8641189809", "text": telegram_text}
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    print("✅ Telegram sent successfully.")
                else:
                    print(f"❌ Telegram failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")
    else:
        print("⚠️ No TELEGRAM_BOT_TOKEN set.")

if __name__ == "__main__":
    asyncio.run(main())
