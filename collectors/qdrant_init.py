import os
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

logger = logging.getLogger("QdrantInit")

IS_DOCKER = os.path.exists("/.dockerenv")
QDRANT_HOST = "qdrant" if IS_DOCKER else "localhost"
QDRANT_PORT = 6333

def init_qdrant():
    """Initialize Qdrant collections if they don't exist."""
    logger.info(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    
    # 1. crypto_news
    try:
        if not client.collection_exists(collection_name="crypto_news"):
            logger.info("Creating Qdrant collection 'crypto_news'...")
            client.create_collection(
                collection_name="crypto_news",
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            logger.info("Collection 'crypto_news' created successfully.")
        else:
            logger.info("Collection 'crypto_news' already exists.")
    except Exception as e:
        logger.error(f"Error creating collection 'crypto_news': {e}")
        raise e

    # 2. agent_memory
    try:
        if not client.collection_exists(collection_name="agent_memory"):
            logger.info("Creating Qdrant collection 'agent_memory'...")
            client.create_collection(
                collection_name="agent_memory",
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            logger.info("Collection 'agent_memory' created successfully.")
        else:
            logger.info("Collection 'agent_memory' already exists.")
    except Exception as e:
        logger.error(f"Error creating collection 'agent_memory': {e}")
        raise e
        
    logger.info("Qdrant initialization completed successfully.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    init_qdrant()
