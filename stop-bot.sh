#!/bin/bash
echo "Stopping bot stack..."
pkill -f run_agent_watchdog.py
sleep 1
pkill -f run_agents.py
pkill -f run_crypto_bot.py
pkill -f main.py
tmux kill-server 2>/dev/null
supabase stop 2>/dev/null
echo "Done. Verify:"
ps aux | grep -E "main.py|crypto_bot|run_agents|watchdog" | grep -v grep | grep -v "\[watchdogd\]"
