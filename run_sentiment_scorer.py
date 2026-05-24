import os
import requests
import asyncio
from dotenv import load_dotenv
import collectors.sentiment_scorer as sentiment_scorer

def send_telegram_startup():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = "8641189809"
    
    if not token:
        print("[STARTUP] TELEGRAM_BOT_TOKEN not found in env.")
        return
        
    msg = "🧠 Sentiment scorer started — FinBERT processing news.crypto"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("[STARTUP] Telegram startup notification sent successfully!")
        else:
            print(f"[STARTUP] Telegram notification failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"[STARTUP] Telegram notification error: {e}")

if __name__ == "__main__":
    send_telegram_startup()
    asyncio.run(sentiment_scorer.main())
