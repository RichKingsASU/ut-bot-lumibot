#!/bin/bash
source "$(dirname "$0")/check_mount.sh"
# Start all Disrupting Alpha services
cd /home/k2/ut-bot-lumibot
source venv/bin/activate

echo "1. Starting Docker services..."
docker compose up -d questdb nats qdrant tick-collector news-collector
sleep 10

echo "2. Killing existing tmux sessions..."
tmux kill-session -t agents 2>/dev/null
tmux kill-session -t crypto-bot 2>/dev/null
tmux kill-session -t trading-bot 2>/dev/null
tmux kill-session -t sentiment 2>/dev/null
tmux kill-session -t vectors 2>/dev/null
tmux kill-session -t options 2>/dev/null
tmux kill-session -t telegram-bot 2>/dev/null
tmux kill-session -t watchdog 2>/dev/null

echo "3. Starting all tmux sessions..."
tmux new-session -d -s crypto-bot \
  "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_crypto_bot.py"
tmux new-session -d -s trading-bot \
  "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python main.py"
tmux new-session -d -s sentiment \
  "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_sentiment_scorer.py"
tmux new-session -d -s vectors \
  "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_vector_store.py"
tmux new-session -d -s options \
  "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_option_data_worker.py"
tmux new-session -d -s agents \
  "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_agents.py"
tmux new-session -d -s telegram-bot \
  "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_telegram_bot.py"
tmux new-session -d -s watchdog \
  "cd /home/k2/ut-bot-lumibot && source venv/bin/activate && python run_agent_watchdog.py"

echo "4. Waiting 20 seconds for services to initialize..."
sleep 20

echo "5. Running health check..."
HEALTH_OUT=$(python3 scripts/health_check.py)
echo "$HEALTH_OUT"

if echo "$HEALTH_OUT" | grep -q "GREEN"; then
    HEALTH="GREEN"
elif echo "$HEALTH_OUT" | grep -q "YELLOW"; then
    HEALTH="YELLOW"
else
    HEALTH="RED"
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SESSIONS=$(tmux list-sessions 2>/dev/null | wc -l)
DOCKER=$(docker ps --format '{{.Names}}' | grep -E "questdb|nats|qdrant|tick-collector|news-collector" | wc -l)

MSG="🚀 Disrupting Alpha V2 Started
Sessions: $SESSIONS/8
Docker: $DOCKER/5
Health: $HEALTH
Time: $TIMESTAMP"

echo "6. Sending Telegram confirmation..."
set -a
source .env
set +a
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="8641189809" \
    -d text="$MSG" > /dev/null

echo "All done."
