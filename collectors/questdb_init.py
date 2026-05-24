import os
import logging
import httpx

logger = logging.getLogger("QuestDBInit")

IS_DOCKER = os.path.exists("/.dockerenv")
QUESTDB_URL = "http://questdb:9000" if IS_DOCKER else "http://localhost:9000"

CREATE_TICKS_TABLE = """
CREATE TABLE IF NOT EXISTS ticks (
  symbol SYMBOL,
  price DOUBLE,
  size DOUBLE,
  timestamp TIMESTAMP
) TIMESTAMP(timestamp) PARTITION BY DAY WAL;
"""

CREATE_OHLCV_TABLE = """
CREATE TABLE IF NOT EXISTS ohlcv_1m (
  symbol SYMBOL,
  open DOUBLE,
  high DOUBLE,
  low DOUBLE,
  close DOUBLE,
  volume DOUBLE,
  timestamp TIMESTAMP
) TIMESTAMP(timestamp) PARTITION BY DAY WAL;
"""

def init_questdb_schema(questdb_url: str = QUESTDB_URL) -> bool:
    """Connect to QuestDB REST API and initialize the required schemas."""
    logger.info(f"Initializing QuestDB schema via REST API at {questdb_url}...")
    
    # QuestDB executes SQL via http://<host>:<port>/exec?query=<sql>
    exec_url = f"{questdb_url}/exec"
    
    success = True
    for table_name, query in [("ticks", CREATE_TICKS_TABLE), ("ohlcv_1m", CREATE_OHLCV_TABLE)]:
        try:
            resp = httpx.get(exec_url, params={"query": query.strip()}, timeout=10.0)
            if resp.status_code == 200:
                logger.info(f"QuestDB table '{table_name}' checked/created successfully.")
            else:
                logger.error(f"Failed to create QuestDB table '{table_name}': {resp.status_code} - {resp.text}")
                success = False
        except Exception as e:
            logger.error(f"Error communicating with QuestDB for table '{table_name}': {e}")
            success = False
            
    return success

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_questdb_schema()
