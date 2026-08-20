# Operations Runbook

## Go-Live Checklist (Operator Must Confirm)
- [ ] Paper-trading soak completion (7 stages passed).
- [ ] Expected broker account ID is known and configured as I_CONFIRM_LIVE_TRADING_EXPECTED_ACCOUNT.
- [ ] Risk limits (MAX_DAILY_LOSS, MAX_POSITION_SIZE) are set to conservative defaults.
- [ ] Symbol allowlist configured properly.
- [ ] Market calendar/timezone aligned.
- [ ] Persistent state mount confirmed writable.
- [ ] Monitoring and alerts active.
- [ ] Kill-switch tested in paper environment.
- [ ] Flattening test completed successfully.
- [ ] Backup procedures tested.
- [ ] Rollback procedures tested.
- [ ] TRADING_MODE=live set explicitly.

## Incident Response & Kill Switch
If the bot behaves erratically:
1. **Soft Kill:** Send a SIGTERM to the process. It will stop taking new trades and attempt to flatten existing positions.
   sudo systemctl stop da-trading-bot or docker compose stop trading-bot
2. **Hard Kill:** Send a SIGKILL if it hangs.
   sudo systemctl kill da-trading-bot

## Rollback Procedure
1. Identify the previous stable commit hash.
2. Stop the bot: sudo systemctl stop da-trading-bot.
3. Check out the previous commit: git checkout <hash>.
4. Re-sync dependencies: pip install -r requirements-production.txt.
5. Restart the bot: sudo systemctl start da-trading-bot.

## Backup and Recovery
State is synchronized in Supabase and QuestDB. Ensure daily snapshots of QuestDB data volume (/mnt/tick-storage) and rely on Supabase PITR (Point-In-Time Recovery) for trade telemetry.
