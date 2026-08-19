# Production Runbook

Use Python 3.13.7, PostgreSQL 17, Django/Gunicorn, Django templates/static files, and an HTTPS reverse proxy. Populate only the variables in `.env.example` through a secret manager. Build `Dockerfile.django`, run migrations as an explicit release step, synchronize roles, collect static files, and start the immutable image through `docker-compose.production.yml`.

## Release
1. Back up and verify the current database; capture image digest and commit.
2. Deploy the same candidate validated in staging; run `check --deploy`, migration dry-run, then migrate.
3. Start web, verify `/operations/health/` and `/operations/ready/`, authenticate with a read-only account, and confirm kill switch defaults safe.
4. Require separate business change approval before enabling trading.

## Rollback
Stop admission, activate the kill switch, preserve logs/audit records, roll back to the prior immutable image, and prefer forward-compatible schema fixes. Restore the database only for confirmed corruption/data loss under the destructive restore runbook; reconcile every broker order and position before resuming.

Log authentication failures, trading/reconciliation/integration/database errors, kill-switch changes, and request correlation IDs to the managed log sink. Never log credentials, session cookies, order payload secrets, or database URLs.
