# Deployment Guide

## Architecture
The UT Bot LUMIBOT system consists of:
- **Trading Bot (main.py):** Python process responsible for executing the Alpaca Lumibot strategy.
- **Data Collectors:** Python services for pulling ticks, news, and sentiment into message queues.
- **Support Services:** QuestDB, NATS, Qdrant running in Docker Compose.

## Prerequisites
- Linux OS (Ubuntu 22.04+ recommended)
- Python 3.11
- Docker and Docker Compose
- Alpaca API Credentials
- Supabase Project URL and Service Key

## Option 1: Native Systemd (Recommended for Trading Bot)
Data services run in Docker, while the trading bot runs natively on the host for minimal latency and direct file lock access.

1. Clone the repository and configure .env based on .env.example.
2. Start the data pipeline:
   docker compose up -d questdb nats qdrant tick-collector news-collector
3. Set up the Python virtual environment:
   python3.11 -m venv venv && source venv/bin/activate
   pip install -r requirements-production.txt
4. Install systemd service:
   sudo bash systemd/install.sh
5. Start the bot:
   sudo systemctl start da-trading-bot

## Option 2: Full Docker Deployment
If you prefer running the bot in a container (e.g., for Kubernetes or isolated environments).

1. Build and run the entire stack including the deprecated standalone trading bot profile:
   docker compose --profile deprecated-legacy-trading up -d
2. Monitor health:
   curl -f http://localhost:8000/health
