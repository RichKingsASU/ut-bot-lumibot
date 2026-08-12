# Secret management — actual state

Written after auditing the running host, because the repository and the host
disagreed. Where they conflict, this file describes the host.

## Summary

| Surface | Backend | Status |
|---|---|---|
| k2 (all systemd services) | `.env` via `EnvironmentFile` | **live** |
| Netlify (dashboard) | Doppler, project `disrupting-alpha`, config `production` | per `netlify.toml` |
| CI (`validate-secrets.yml`) | Doppler via GitHub secret `DOPPLER_TOKEN` | assumed working |
| GCP Secret Manager | — | not used, no code references |

`e12a095 "complete migration to Doppler for secret management"` landed in the
repository but was **never adopted on k2**. Doppler's CLI is installed there
(v3.76.1) but unconfigured and not logged in; no systemd unit references it.

## What runs on k2

All five services read the same env file:

    EnvironmentFile=/home/k2/ut-bot-lumibot/.env

Verified against the running processes rather than the unit files:

    da-trading-bot     SUPABASE_SERVICE_ROLE_KEY   (REST)
    da-agents          SUPABASE_SERVICE_ROLE_KEY   (REST)
    da-crypto-bot      SUPABASE_SERVICE_ROLE_KEY   (REST)
    da-watchdog        SUPABASE_SERVICE_ROLE_KEY   (REST)
    da-gcp-replicator  SUPABASE_DSN + GOOGLE_APPLICATION_CREDENTIALS

Only `da-gcp-replicator` holds the Postgres DSN. The four trading services
authenticate to Supabase over REST and never see the database password, so
rotating it does not affect them.

GCP credentials are a file path, not inline JSON:

    GOOGLE_APPLICATION_CREDENTIALS=/home/k2/.config/disruptingalpha/gcp-replicator.json   (0600)

The key stays out of the environment, out of `ps` output, and out of the
journal. `ProtectSystem=strict` restricts writes only and `ProtectHome=false`,
so the unit can still read it.

## The `systemd/` directory does not describe this host

Every unit in `systemd/` launches through
`doppler run --token ${DOPPLER_TOKEN} --project disrupting-alpha --config prd`
and gates on `ConditionFileNotEmpty=/etc/systemd/system/da-doppler.conf`.
None of that is true on k2.

Unit names also differ: `da-trading.service` vs the live
`da-trading-bot.service`, `da-crypto.service` vs `da-crypto-bot.service`.
`da-agents` and `da-watchdog` collide exactly and would be overwritten.

`scripts/install-systemd.sh` is therefore guarded and refuses to run. Removing
the guard without reconciling the units first would overwrite two live services
and start a duplicate trading bot under a second name.

## `systemd/da-doppler.conf` contained a committed token

The file held a real Doppler **service token** (`dp.st.` prefix, 53 chars) and
was tracked in git from `e12a095`. It is now untracked and gitignored;
`da-doppler.conf.template` remains as the placeholder.

**Untracking does not undo the exposure.** The token is in git history and in
every clone. It must be revoked in Doppler and reissued. Treat any secret that
token could read as compromised until rotated.

## Why k2 stays on `.env`

Considered and rejected for this host:

- **Doppler** — needs `doppler login`, a service token stored in
  `/etc/systemd/system/`, and its own rotation story. Real operational weight
  for a single bare-metal box, and the token-in-a-file problem is what caused
  the leak above.
- **GCP Secret Manager** — bootstrap problem. Reading secrets requires
  authenticating to GCP, and on bare metal that means a service-account key on
  disk: a secret to fetch the secrets. Only free on GCE/GKE, where the metadata
  server supplies identity. Worth revisiting if the replicator moves to Cloud
  Run.
- **`.env`** — systemd-native, no daemon, no token, `0600`, already working.
  Adequate for one host.

If the fleet grows past this host, revisit. The decision here is scoped to k2.

## Rotation runbook

Supabase database password (only `da-gcp-replicator` uses it):

    ALTER USER postgres WITH PASSWORD '<new>';        -- what the dashboard button does
    # update SUPABASE_DSN in .env
    sudo systemctl restart da-gcp-replicator

Use 32 alphanumeric characters — avoids URL-encoding hazards in the DSN and
quoting hazards in `.env`. An unquoted value containing spaces previously broke
`source .env` at line 38 and silently truncated the environment.

GCP service-account key: stand up Workload Identity Federation, point
`GOOGLE_APPLICATION_CREDENTIALS` at the federation config, then delete the key
in GCP. Deleting the local JSON is not revocation. The code supports both --
`google.auth.default()` accepts `service_account` and `external_account`.
