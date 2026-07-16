# Supabase Database Audit

This report documents the schema constraints, row counts, and client configurations of the cloud Supabase database.

## 📊 Database Schema & Row Counts

The database schemas were verified, and all core tables are online and populated.

| Table Name | Count | Primary Key | Critical Fields |
| :--- | :---: | :--- | :--- |
| `agent_signals` | 5,114 | `id` (bigserial) | `symbol`, `action`, `confidence`, `asset_class`, `reasoning` |
| `regime_states` | 16,832 | `id` (bigserial) | `symbol`, `asset_class`, `regime`, `regime_probability`, `detected_at` |
| `news_articles` | 39,893 | `id` (bigserial) | `title`, `url` (unique), `sentiment_score`, `published_at` |
| `portfolio_snapshots`| 26,486| `id` (bigserial) | `equity`, `buying_power`, `positions`, `snapshot_at` |
| `greeks_snapshots` | 1,434 | `id` (bigserial) | `symbol`, `delta`, `gamma`, `theta`, `vega`, `implied_volatility` |
| `signal_performance` | 441 | `id` (bigserial) | `symbol`, `information_coefficient`, `calculated_at` |
| `user_settings` | 2 | `id` (uuid) | `key`, `value`, `updated_at` |
| `risk_config` | 1 | `id` (uuid) | `mode`, `rules`, `updated_at` |
| `system_alerts` | 0 | `id` (bigserial) | `level`, `message`, `source`, `created_at` |
| `bot_status` | 1 | `id` (bigint) | `last_heartbeat`, `status`, `target_status` |

---

## 🔒 Row Level Security (RLS) & Access
* **Read Policies:** Configured for public access (`anon` role) on all display tables (`agent_signals`, `regime_states`, `news_articles`, `portfolio_snapshots`, `greeks_snapshots`, `signal_performance`) to allow the frontend to load and render charts.
* **Write Policies:** Restricted to authenticated/service role actions to prevent unauthorized trade insertion, signal overrides, or settings modifications.

---

## 🚀 Edge Functions
Supabase Edge Functions are hosted under the project reference `wnigkahkamoizjpmpuxs`.
* **Database Webhook Functions:** Active for alerting.
* **Stream Listeners:** Connect database updates to internal services.
