# User Action Required — Integration & Setup Guide

Due to snap confinement and system security boundary limitations, certain credentials, host processes, and integration hook configurations must be initialized manually in your host terminal and provider administration panels.

---

## 💻 1. Host Process Startup (Background Workers)

Since systemd services are not currently configured as unit files on your host system, you must start the core engines in the background using `nohup` (or inside a `tmux` session):

```bash
# Navigate to project and activate virtual environment
cd /home/k2/ut-bot-lumibot
source venv/bin/activate

# Start the background trading and agent orchestrator processes
nohup python run_agents.py > logs/run_agents.log 2>&1 &
nohup python run_crypto_bot.py > logs/run_crypto_bot.log 2>&1 &
nohup python main.py > logs/main.log 2>&1 &
```

---

## 🌐 2. Netlify Dashboard Configuration (REST APIs Fix)

If you deploy updates to Netlify, you must populate the missing environment variables in your Netlify settings so that edge serverless functions do not fail with a `502: key is required` error.

1. Open your Netlify admin dashboard for **disruptingalpha.com**.
2. Navigate to **Site settings** > **Environment variables**.
3. Add the following keys (copy values from your local `/home/k2/ut-bot-lumibot/.env` file):
   * `SUPABASE_URL`
   * `SUPABASE_SERVICE_ROLE_KEY`
   * `ALPACA_API_KEY`
   * `ALPACA_API_SECRET`
   * `ALPACA_BASE_URL`
   * `ADMIN_API_KEY`

---

## 📝 3. Notion & Stitch Sync Integration

If you want to enable Notion page logging or sync Stitch design sources to your workspace, follow these setup structures:

### Notion Integration Setup
1. Create a Notion integration token at [notion.so/my-integrations](https://www.notion.so/my-integrations) with **Read/Write** permissions.
2. Share your target documentation database page with the integration.
3. Add the Notion credential to your root `.env` file:
   ```env
   NOTION_API_KEY=secret_your_token_here
   NOTION_PAGE_ID=your_page_uuid_here
   ```

### Stitch Design Source Setup
1. Save generated UI assets, screenshots, or design tokens inside `dashboard/public/assets/stitch/`.
2. Reference design variables inside `dashboard/tailwind.config.ts` to keep styling values synced with design source updates.
