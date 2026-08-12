# Harness.io & Doppler Secret Setup

> **A real service token was committed here in `e12a095` and has been redacted.**
> Redaction does not remove it from git history. That token must be revoked in
> Doppler and reissued. Never paste a live token into this file — it is tracked.


To allow your Harness `.harness/ci_pipeline.yaml` pipeline to fetch secrets natively from Doppler during testing, you must add the Doppler service token to your Harness Secrets Manager.

## Step-by-Step Instructions

1. **Log in** to your Harness.io account.
2. Navigate to your **Project** (or Org/Account level depending on where you want the secret scoped).
3. Go to **Project Setup** > **Secrets**.
4. Click **+ New Secret** and select **Text**.
5. Set the **Secret Name** exactly as: `DOPPLER_TOKEN`
6. Set the **Secret Value** to your dedicated Harness service token:
   `<paste-your-doppler-service-token-here>`
7. Click **Save**.

The `.harness/ci_pipeline.yaml` is already configured with `<+secrets.getValue("DOPPLER_TOKEN")>` to inject this into the build environment automatically!
