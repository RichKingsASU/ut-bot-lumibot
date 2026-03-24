import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Alpaca Configuration
ALPACA_CONFIG = {
    "API_KEY": os.getenv("ALPACA_API_KEY"),
    "API_SECRET": os.getenv("ALPACA_API_SECRET"),
    "PAPER": os.getenv("ALPACA_IS_PAPER", "true").lower() == "true",
}
