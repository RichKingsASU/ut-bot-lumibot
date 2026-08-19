# PostgreSQL 17 Backup and Restore

## Scope and objectives
Back up the authoritative Django PostgreSQL database with `pg_dump` custom format. Proposed objectives pending business approval: RPO 24 hours, RTO 2 hours, 30 daily and 12 monthly encrypted/off-site copies. Credentials must come from the secret manager.

## Procedure
1. Set a least-privilege `DATABASE_URL` and an encrypted `BACKUP_DIR`; run `scripts/postgres/backup.sh`.
2. Copy both `.dump` and `.sha256` to immutable encrypted storage and alert on missed backups.
3. Provision an isolated PostgreSQL **17** restore database. Never rehearse against production.
4. Set `RESTORE_DATABASE_URL` and `CONFIRM_DESTRUCTIVE_RESTORE=RESTORE`, then run `scripts/postgres/restore.sh BACKUP.dump`.
5. Run migrations/checks, compare table row counts and business-selected checksums, start Django against the restored database, and execute health/login/dashboard/order-read Selenium checks.
6. Record timestamps, versions, artifact checksum, counts, result, operator, reviewer, and measured RPO/RTO in the drill record.

## Evidence status — BLOCKED
On 2026-08-19 the execution host had neither Docker nor `psql`/`pg_dump`; therefore no backup or restore was executed. PR-006 remains **OPEN** and Backup + Restore remains **FAIL**. Scripts existing is not evidence of recovery.
