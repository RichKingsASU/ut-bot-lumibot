# Netlify Deployment Configuration

This document covers the edge hosting and serverless function environment settings for the React/Vite dashboard.

## ⚙️ Build and Routing Settings
The frontend is hosted at [disruptingalpha.com](https://disruptingalpha.com) and is configured using the repository `dashboard/netlify.toml` file.

* **Base Directory:** `dashboard`
* **Build Command:** `npm run build` (runs Vite build compiler)
* **Publish Directory:** `dist` (holds the static compiled JS, CSS, and HTML assets)
* **SPA Redirects:**
  ```toml
  [[redirects]]
    from = "/*"
    to = "/index.html"
    status = 200
  ```
  *This ensures that frontend paths (e.g. `/news/sentiment`, `/system/health`) are handled correctly by React Router.*

---

## ⚡ Serverless Netlify Functions
Serverless endpoints are implemented under `dashboard/netlify/functions/` to proxy database queries and protect sensitive backend API keys.

1. **`get-system-health.ts`**: Fetches Alpaca account, database status, latest signals, and returns an aggregated health JSON payload.
2. **`get-pipeline-status.ts`**: Evaluates SLA runtimes, agent reasoning/debates, and current market regimes.
3. **`supabase-query.ts`**: Secure proxy endpoint for direct frontend Supabase actions.

---

## 🔒 Production Environment Variables (Netlify Dashboard)

To prevent backend requests from failing with a `502: key is required` error, ensure the following keys are populated in your Netlify Environment settings:
* `SUPABASE_URL`: `https://wnigkahkamoizjpmpuxs.supabase.co`
* `SUPABASE_SERVICE_ROLE_KEY`: Service role JWT token (from your Supabase dashboard).
* `ALPACA_API_KEY`: Alpaca Account Key ID.
* `ALPACA_API_SECRET`: Alpaca Account Secret Key.
* `ALPACA_BASE_URL`: Alpaca API Base URL.
* `ADMIN_API_KEY`: Secret string matching `X-Admin-API-Key` headers for route authorization.
