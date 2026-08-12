# TRAINING DOCUMENTATION: UT Bot Lumibot Operations

## 1. Daily Operations Lifecycle
This section outlines the standard daily routine for an **Operations User**.

### 09:15 EST - Pre-Market Initialization
1.  **Environment Check**: Run `python preflight_check.py`.
2.  **Dashboard Login**: Access the Control Tower and verify **Database** and **Bot Engine** status badges are green.
3.  **Start Bot**: Execute `python main.py`.

### 09:30 EST - Market Open Monitoring
1.  **Signal Watch**: Monitor the `Overview` tab for the first UT Bot signal.
2.  **Trade Verification**: When a trade fires, verify the entry price in the `In-Trade Bar`.

### 15:55 EST - Market Close / Flatten
1.  **Auto-Flatten**: The bot will automatically close positions at the `eod_flatten_time`.
2.  **Verification**: Manually verify in Alpaca that all positions are closed.
3.  **Audit**: Review the `system_audit` logs in the dashboard for any warnings.

---

## 2. Advanced Operations (Power User)
### Historical Backfilling
1.  Navigate to the **Data** tab.
2.  Select the **SEEDING** sub-tab.
3.  Click **Backfill** for the target symbol (e.g., SPY).
4.  Wait for the "Completed" status in the **Live Seed Jobs** grid before running backtests.

---

## 3. Risk Management Protocols
### Adjusting Limits
1.  Navigate to **Risk Manager > Rules**.
2.  Adjust `Max Daily Loss` or `Position Limit`.
3.  **Click SAVE**. 
4.  *Note*: The bot reads these settings at startup. If the bot is already running, you must restart it to pick up new risk rules.

---

## 4. Troubleshooting FAQ
**Q: The dashboard shows "Disconnected" for the Bot Engine.**
- **A**: Check the terminal running `main.py`. If it crashed, refer to `HARDENING_CHANGELOG.md` to see if an absolute safeguard was triggered.

**Q: I see a "Stale Data Detected" error in the logs.**
- **A**: This happens when the Alpaca WebSocket latency exceeds 90 seconds. The bot will automatically halt to prevent bad entries. Ensure your internet connection is stable.
