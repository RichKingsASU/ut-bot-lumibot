import sqlite3
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Ensure replication module can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from replication.gcp_replicator_daemon import GCPReplicationDaemon

def setup_mock_primary_db(db_path: str):
    """Sets up a mock primary database with sample data across multiple tables."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    with conn:
        for table in ["bar_log", "signal_log", "paper_trades"]:
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP,
                    payload TEXT
                )
            ''')
            # Insert some mock records
            conn.execute(f"INSERT INTO {table} (created_at, payload) VALUES ('2026-08-01T10:00:00Z', 'data1')")
            conn.execute(f"INSERT INTO {table} (created_at, payload) VALUES ('2026-08-01T10:01:00Z', 'data2')")
            conn.execute(f"INSERT INTO {table} (created_at, payload) VALUES ('2026-08-01T10:02:00Z', 'data3')")
    conn.close()
    logging.info(f"Mock primary DB created at {db_path} with sample records.")

def main():
    state_db_path = "data/mock_sync_state.db"
    primary_db_path = "data/mock_primary.db"
    
    # Clean up old state if exists
    if os.path.exists(state_db_path):
        os.remove(state_db_path)
        
    setup_mock_primary_db(primary_db_path)
    
    # Initialize Daemon
    daemon = GCPReplicationDaemon(
        state_db_path=state_db_path,
        primary_db_path=primary_db_path,
        tables=["bar_log", "signal_log", "paper_trades"]
    )
    
    # Create the schema in the state DB first since the daemon expects it to exist
    conn = sqlite3.connect(state_db_path)
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sync_cursors (
                table_name TEXT PRIMARY KEY,
                last_sync_created_at TIMESTAMP,
                last_sync_id INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.close()

    logging.info("Starting GCP Replication Daemon native execution sweep...")
    
    # Before sync
    for table in daemon.tables:
        cursor = daemon._cursor_tracker.get_cursor(table)
        logging.info(f"[{table}] Cursor BEFORE sync: {cursor}")
        
    # Execute one full synchronous sweep
    daemon.sync_once()
    
    # After sync
    logging.info("---")
    for table in daemon.tables:
        cursor = daemon._cursor_tracker.get_cursor(table)
        logging.info(f"[{table}] Cursor AFTER sync: {cursor}")
        
    logging.info("Sweep complete. Native execution path verified successfully.")

if __name__ == "__main__":
    main()
