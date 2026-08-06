# Domain Dictionary: GCP Replication System

## 1. Ubiquitous Language & Terminology Mapping

To eliminate terminology drift and context fragmentation between legacy execution engines, intermediate SQLite caching, and our downstream telemetry warehouse (BigQuery), we adhere strictly to the following canonical abstractions:

| Legacy / Drift Term      | Canonical FDE Term             | Definition & Context |
|--------------------------|--------------------------------|----------------------|
| log_entry, 
ow       | **Payload**                    | A single, atomic JSON record representing a market event or trade execution state to be streamed to GCP. |
| cache_db, local_db   | **State WAL**                  | The local SQLite Write-Ahead Log used to buffer and persist trade records and sync cursors when the primary database is unreachable. |
| 	imestamp, 	ime_key  | **Epoch (created_at)**         | The ISO-8601 UTC timestamp representing the exact insertion time of the Payload. |
| push_to_cloud          | **Ingestion Stream**           | The deterministic action of routing Payloads over TLS 1.3 to GCP Pub/Sub or BigQuery. |
| last_seen_id           | **Monotonic Cursor**           | The compound tuple (created_at, id) used to track the exact watermark of successful replication. |
| 
econnect_timer        | **Exponential Backoff**        | The mathematically scaling delay period managed by the Circuit Breaker after a network partition. |

## 2. Database Schema Definitions

### a) SQLite Cursor State Table (sync_cursors)
This table physically persists the watermark (Monotonic Cursor) for each replicated table. If the out-of-process daemon crashes or the k2 server reboots, the daemon queries this table to resume ingestion precisely where it left off, ensuring zero data loss and preventing duplicate egress costs.

`sql
CREATE TABLE IF NOT EXISTS sync_cursors (
    table_name TEXT PRIMARY KEY,
    last_sync_created_at TEXT,
    last_sync_id INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
`

### b) PostgreSQL & BigQuery Replication Tables (The Compound Cursor)

**The Millisecond Race Condition Flaw:**
Querying by created_at alone is a major architectural race condition. In a high-frequency trading environment, multiple transactions can commit within the exact same millisecond. If the ingestion loop paginates by created_at > :last_time, it risks silently skipping sibling records that share the same millisecond timestamp but were committed a fraction of a millisecond later.

**The Solution:**
We enforce a **Compound Monotonic Cursor Tuple (created_at, id)**.
All queries must execute as:
`sql
SELECT * FROM staging_table 
WHERE (created_at, id) > (:last_sync_created_at, :last_sync_id) 
ORDER BY created_at ASC, id ASC 
LIMIT 1000;
`
This mathematically guarantees deterministic pagination across millisecond-colliding records.

## 3. Telemetry Structure Mapping
When a Payload is streamed to GCP, we map the following structures:
- **Pub/Sub Ordering Key:** Mapped to the id field to guarantee sequential downstream processing.
- **BigQuery insertId:** Derived from SHA-256(JSON_PAYLOAD) to enforce strict idempotency and deduplication within the data warehouse, regardless of network retries.

## 4. Canonical Architecture Decision

Canonical implementation is: `replication/gcp_replicator_daemon.py`.
Deprecated/removed: `gcp-ingestion-bridge.py` and `edge-wal-system.py`.

Reasoning: Based on a ground-truth filesystem audit, the out-of-process daemon (Narrative A) is the actual implemented architecture in the repository. The proposed ingestion bridge and WAL system files (Narrative B) do not exist in the codebase.
