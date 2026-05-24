import os
import requests
import asyncio
import logging
from dotenv import load_dotenv
from collectors.qdrant_init import init_qdrant
import collectors.vector_store as vector_store

def send_telegram_startup():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = "8641189809"
    
    if not token:
        print("[STARTUP] TELEGRAM_BOT_TOKEN not found in env.")
        return
        
    msg = "🔍 Vector store started — embeddings flowing to Qdrant"
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    # Task 7: Call qdrant_init from run_vector_store.py on startup
    print("[STARTUP] Initializing Qdrant collections...")
    init_qdrant()
    
    # Task 5: Send Telegram startup notification
    send_telegram_startup()
    
    # Task 5: Start the vector store service
    asyncio.run(vector_store.main())
