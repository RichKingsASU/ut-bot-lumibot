import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config_validator import validate_production_env
import logging

logging.basicConfig(level=logging.INFO)
validate_production_env()
print("VALIDATION_SUCCESS")
