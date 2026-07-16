# Setting up Harness.io for Product & Reliability Tests

This repository is equipped with a ready-to-use Harness pipeline configuration at [.harness/pipeline.yaml](file:///c:/Users/Richa/ut-bot-lumibot/.harness/pipeline.yaml). 

Follow these steps to connect and configure your project on [Harness.io](https://harness.io).

---

## 🚀 Setup Steps

### 1. Register and Create a Project
1. Log in to your Harness account at [app.harness.io](https://app.harness.io).
2. Create a new **Project** named `disrupting-alpha` under the default organization.

### 2. Configure Git Connection
1. In your project settings, navigate to **Connectors** and add a **GitHub Connector**.
2. Set your repository URL to `https://github.com/RichKingsASU/ut-bot-lumibot`.
3. Provide your GitHub Personal Access Token (PAT) as a credential.

### 3. Add Environment Secrets
If your unit tests or migration checks require API keys, configure them inside the **Harness Secret Manager**:
1. Go to **Secrets** inside your Harness project settings.
2. Add the following secrets if needed (e.g. mock tokens, testing credentials):
   - `ALPACA_API_KEY`
   - `ALPACA_API_SECRET`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_URL`

### 4. Create the Pipeline from Git
1. Go to the **Pipelines** module in Harness and click **Create Pipeline**.
2. Select **Remote** (Git-based pipeline) as your setup method.
3. Reference the existing configuration file path: `.harness/pipeline.yaml`.
4. Define a **Trigger** to automatically run the pipeline:
   - On **Push** events to the `main` branch.
   - On **Pull Request** creation/update events.

---

## 🚦 What the Pipeline Executes

The pipeline goes through 4 automated stages to guarantee product stability and operational reliability:

1. **Python Quality Audits (`flake8`, `safety`)**:
   - Performs syntax sanity checks and dependencies vulnerability scans.
2. **Backend Unit & Integration Tests (`pytest`)**:
   - Runs the test suite under [tests/](file:///c:/Users/Richa/ut-bot-lumibot/tests/) to verify trade calculations, indicators, and tool logic.
3. **Frontend Typecheck & Production Build (`tsc`, `vite build`)**:
   - Ensures the Vite/React TS compiler completes successfully and packages assets without bundle-time errors.
4. **Supabase SQL Verification**:
   - Loops through SQL migration scripts to catch syntactical errors before deploying schemas to production.
