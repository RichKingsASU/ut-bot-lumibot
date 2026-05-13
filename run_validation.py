import sys
import os
sys.path.append(r'C:\Users\Richa\.gemini\antigravity\scratch\lumibot_ut_bot')
from config_validator import validate_production_env
import logging

logging.basicConfig(level=logging.INFO)
validate_production_env()
print("VALIDATION_SUCCESS")
