import os
import sys
import requests
from dotenv import load_dotenv

def send_message(message: str):
    # Load .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(env_path)
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = "8641189809" # As specified in task
    
    if not token:
        print("TELEGRAM_BOT_TOKEN not found in .env", file=sys.stderr)
        sys.exit(1)
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("Message sent successfully")
        else:
            print(f"Failed to send: {resp.status_code} - {resp.text}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_telegram.py <message>", file=sys.stderr)
        sys.exit(1)
    send_message(sys.argv[1])
