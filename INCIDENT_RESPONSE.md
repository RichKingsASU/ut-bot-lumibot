# INCIDENT RESPONSE PLAYBOOK — UT BOT TRADING PLATFORM

## 🚨 SEV-1: CRITICAL TRADING FAILURE
**Symptoms:** 
- Bot submitting duplicate orders.
- Bot failing to exit positions on signal.
- Max Daily Loss breached but trading continues.
- Stale data guard failing (trading on old bars).

**Immediate Actions:**
1. **EMERGENCY KILL SWITCH**: 
   - Open Alpaca Dashboard -> Account Settings -> "Close All Positions".
   - Or run: `docker-compose stop trading-bot`.
2. **SUSPEND API KEYS**:
   - Rotate Alpaca API Secret immediately to prevent any further automated orders.
3. **LOG ANALYSIS**:
   - Check JSON logs for `order_id` and `trade_pnl`.
   - Look for `FATAL` or `ERROR` tags in `ut-bot-executor` container.

---

## 🛑 SEV-2: SYSTEM INSTABILITY
**Symptoms:**
- Database connectivity lost (`Supabase write failed`).
- Health server reporting `503` or `500`.
- Websocket frequent reconnects.

**Actions:**
1. **VERIFY CONNECTIVITY**:
   - Run `curl http://localhost:8000/ready`.
   - Check Supabase status.
2. **GRACEFUL RESTART**:
   - `docker-compose restart trading-bot`.
   - Bot will automatically run `sync_state_with_broker` on startup to reconcile.

---

## 📉 SEV-3: DATA INTEGRITY / DASHBOARD
**Symptoms:**
- Dashboard showing stale P&L.
- Historical data mismatch.

**Actions:**
1. **CLEAR RUNTIME CONFIG**:
   - Delete `runtime_config.json`.
   - Restart bot to load defaults from `.env`.

---

## 🔄 ROLLBACK PROCEDURE
If a new deployment causes issues:
1. **Stop Current Stack**: `docker-compose down`.
2. **Revert to Last Stable Tag**:
   - `git checkout [STABLE_TAG]`
3. **Re-deploy**: `docker-compose up -d --build`.
4. **Manual Verification**:
   - Verify `ALPACA_IS_PAPER=true` is set.
   - Check `/ready` endpoint.
