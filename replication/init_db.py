import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'sync_state.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    with conn:
        # 1. Sync Cursors Table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sync_cursors (
                table_name TEXT PRIMARY KEY,
                last_sync_created_at TIMESTAMP,
                last_sync_id INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. Replication Audit Log Table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS replication_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT,
                payload_sha256 TEXT,
                gcp_transaction_receipt TEXT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 3. Explicit Compound Index to optimize cursor query lookups
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_sync_cursors_compound 
            ON sync_cursors (last_sync_created_at, last_sync_id)
        ''')
        
    print(f"✅ Crash-Safe Sync Schema initialized successfully at {DB_PATH}")
    conn.close()

if __name__ == "__main__":
    init_db()
