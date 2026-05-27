import os
import subprocess
import time
import httpx
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('AgentWatchdog')

STALL_THRESHOLD_MINUTES = 25
MAX_RESTARTS_PER_HOUR = 3
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = '8641189809'
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

restart_times = []


def send_telegram(msg: str):
    try:
        httpx.post(
            f'https://api.telegram.org/'
            f'bot{TELEGRAM_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': msg},
            timeout=5)
    except Exception as e:
        logger.error(f'Telegram failed: {e}')


def get_last_signal_age_minutes() -> float:
    try:
        r = httpx.get(
            f'{SUPABASE_URL}/rest/v1/agent_signals',
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            },
            params={
                'select': 'created_at',
                'order': 'created_at.desc',
                'limit': '1'
            },
            timeout=10)
        rows = r.json()
        if not rows:
            return 9999
        last = datetime.fromisoformat(
            rows[0]['created_at'].replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - last
        return age.total_seconds() / 60
    except Exception as e:
        logger.error(f'Signal age check failed: {e}')
        return 9999


def is_session_alive(name: str) -> bool:
    result = subprocess.run(
        ['tmux', 'has-session', '-t', name],
        capture_output=True)
    return result.returncode == 0


def can_restart() -> bool:
    now = time.time()
    recent = [t for t in restart_times
              if now - t < 3600]
    restart_times.clear()
    restart_times.extend(recent)
    return len(recent) < MAX_RESTARTS_PER_HOUR


def restart_agents():
    if not can_restart():
        msg = ('🚨 Watchdog: Too many restarts this hour'
               '\nManual intervention needed')
        logger.error(msg)
        send_telegram(msg)
        return False

    subprocess.run(
        ['tmux', 'kill-session', '-t', 'agents'],
        capture_output=True)
    time.sleep(3)
    subprocess.Popen([
        'tmux', 'new-session', '-d',
        '-s', 'agents',
        'cd /home/k2/ut-bot-lumibot && '
        'source venv/bin/activate && '
        'python run_agents.py'
    ])
    restart_times.append(time.time())
    logger.info('Agents session restarted')
    return True


def main():
    logger.info('Agent watchdog started')
    send_telegram(
        '🐕 Agent watchdog online\n'
        f'Monitoring every 2min\n'
        f'Auto-restart if stalled > {STALL_THRESHOLD_MINUTES}min'
    )

    while True:
        try:
            age = get_last_signal_age_minutes()
            alive = is_session_alive('agents')

            logger.info(
                f'Signal age: {age:.1f}min | '
                f'Session: {"alive" if alive else "DEAD"}'
            )

            if not alive:
                logger.warning('Agents session DEAD')
                send_telegram(
                    f'🔄 Auto-restart: agents session dead\n'
                    f'Restarts this hour: {len(restart_times)}'
                )
                restart_agents()
                time.sleep(90)

            elif age > STALL_THRESHOLD_MINUTES:
                logger.warning(
                    f'Signals stalled {age:.0f}min')
                send_telegram(
                    f'🔄 Auto-restart: signals stalled '
                    f'{age:.0f}min\n'
                    f'Restarts this hour: {len(restart_times)}'
                )
                restart_agents()
                time.sleep(90)

            else:
                time.sleep(120)

        except Exception as e:
            logger.error(f'Watchdog error: {e}')
            time.sleep(60)


if __name__ == '__main__':
    main()
