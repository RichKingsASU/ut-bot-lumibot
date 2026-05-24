import asyncio
import os
import httpx
from dotenv import load_dotenv
import agents.telegram_bot as telegram_bot

load_dotenv('/home/k2/ut-bot-lumibot/.env')

async def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = '8641189809'
    
    startup_msg = "🤖 Disrupting Alpha Command Bot Online\nType /help for available commands"
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            await client.post(url, json={"chat_id": chat_id, "text": startup_msg})
            print("Sent startup message.")
        except Exception as e:
            print(f"Could not send startup message: {e}")
            
    await telegram_bot.poll()

if __name__ == '__main__':
    asyncio.run(main())
