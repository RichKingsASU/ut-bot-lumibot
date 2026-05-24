#!/bin/bash
# Start all Disrupting Alpha services
cd /home/k2/ut-bot-lumibot
source venv/bin/activate

# Kill existing sessions
tmux kill-session -t agents 2>/dev/null
tmux kill-session -t crypto-bot 2>/dev/null
tmux kill-session -t trading-bot 2>/dev/null
tmux kill-session -t sentiment 2>/dev/null
tmux kill-session -t vectors 2>/dev/null
tmux kill-session -t options 2>/dev/null
tmux kill-session -t telegram-bot 2>/dev/null

# Start all services
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

# Start Docker services
docker compose up -d questdb nats qdrant tick-collector news-collector

echo "All services started"
tmux list-sessions
