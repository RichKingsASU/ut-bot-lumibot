# Product Integration & MCP Connection Audit

This document records the verification and connection status of all required MCP servers, external developer platforms, and repository configurations.

## 📊 Connection Summary

| Platform / MCP | Role | Status | Connection Details |
| :--- | :--- | :---: | :--- |
| **GitHub** | Version Control & Remotes | 🟢 **CONNECTED** | Tracked to remote `RichKingsASU/ut-bot-lumibot.git` on branch `audit/supabase-usage-jun26`. |
| **Supabase** | Cloud DB / Backend | 🟢 **CONNECTED** | REST endpoint responsive, 10 core schemas verified, RLS active, read/write permissions validated. |
| **Netlify** | Edge Hosting | 🟢 **CONNECTED** | [disruptingalpha.com](https://disruptingalpha.com) is live. API endpoints repaired. |
| **Harness** | CI/CD | 🔴 **NOT CONFIGURED**| No pipelines or connectors currently exist in the repository workspace. |
| **Notion** | Product Documentation | 🔴 **NOT CONFIGURED**| No Notion sync or pages are currently integrated with the workspace. |
| **Stitch** | Design Source | ⚪ **REFERENCED** | Design and spec files are referenced in codebase comments but no active tooling is connected. |

---

## 🔍 Detailed Connection Status

### 1. GitHub Configuration
* **Remote URL:** `https://github.com/RichKingsASU/ut-bot-lumibot.git`
* **Current Branch:** `audit/supabase-usage-jun26`
* **Actions Visibility:** Repo is configured with GitHub Actions, though local snap blocks direct runner audits.
* **Scope Verification:** GitHub tokens verified for repo access and commit pushes.

### 2. Supabase Integration
* **Project Reference:** `wnigkahkamoizjpmpuxs`
* **Region:** `us-east-1` (Virginia)
* **Status:** `ACTIVE_HEALTHY`
* **Database Connection:** Confirmed with a success status from `/rest/v1/` endpoints.
* **Anon Key:** Placed in example config for building.
* **Service Role Key:** Verified from local `.env` configuration.

### 3. Netlify Hosting
* **Production Domain:** [disruptingalpha.com](https://disruptingalpha.com)
* **Status:** Live edge node.
* **Functions Target:** `dashboard/netlify/functions/` (14 active serverless functions).
* **Repair:** Fixed 400 Bad Request query errors inside Netlify Functions `get-system-health` and `get-pipeline-status` by mapping `probability:regime_probability`.

### 4. Harness CI/CD
* **Status:** Offline/Not configured.
* **Findings:** No Harness YAML configurations or Harness tokens are present. A proposed Harness CI/CD plan has been drafted in [HARNESS_TESTING_PLAN.md](file:///home/k2/ut-bot-lumibot/docs/HARNESS_TESTING_PLAN.md).

### 5. Notion Integration
* **Status:** Offline/Not configured.
* **Findings:** No Notion workspace bindings detected. A document sync strategy is outlined in [USER_ACTION_REQUIRED.md](file:///home/k2/ut-bot-lumibot/docs/USER_ACTION_REQUIRED.md).

### 6. Stitch Design Source
* **Status:** References only.
* **Findings:** Visual layout and typography elements reference Stitch design system guidelines, but there is no active live sync.
