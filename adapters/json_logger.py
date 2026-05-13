import logging
import json
import os
from datetime import datetime

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Add custom fields if present
        if hasattr(record, "trade_id"):
            log_record["trade_id"] = record.trade_id
        if hasattr(record, "order_id"):
            log_record["order_id"] = record.order_id
            
        return json.dumps(log_record)

def setup_logging():
    # In production, we use JSON logging for easier ingestion by Datadog/ELK
    is_production = os.getenv("NODE_ENV") == "production" or not os.getenv("DEBUG")
    
    handler = logging.StreamHandler()
    if is_production:
        handler.setFormatter(JsonFormatter())
    else:
        # Simple readable format for dev
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    # Suppress verbose loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
