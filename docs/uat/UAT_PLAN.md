# Production UAT Plan

Status: **NOT EXECUTED — stakeholder sign-off required.** Use isolated PostgreSQL 17 and an Alpaca paper account.

| Scenario | Required actor/result |
|---|---|
| Login/logout/session expiry | Every role; secure session and successful expiry |
| Dashboard/report/history | Viewer; accurate persisted read-only data |
| Order create/duplicate/limit | Trader; one pending order, duplicate deduplicated, excess rejected |
| Partial/rejected/cancelled order | Trader + Operator; state converges to broker |
| Reconciliation discrepancy | Operator; discrepancy recorded, reviewed, resolved |
| Kill switch during outage | Operator; new trading stops and audit record persists |
| Unauthorized mutations | Viewer/Analyst/Auditor; HTTP 403 |
| Broker timeout/stale market data | Trader; fail closed, visible error, no duplicate |
| Process/database restart | Operator; persisted state and broker reconciliation converge |
| Backup/restore/rollback | Operations; integrity checks and measured RPO/RTO pass |

Sign-off record: Business owner ___ / Trading risk ___ / Security ___ / Operations ___ / FDE ___ / date ___ / release SHA ___. No blank signature may be treated as approval.
