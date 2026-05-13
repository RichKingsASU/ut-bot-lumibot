import logging
import json
import os
from datetime import datetime
from enum import Enum

class ErrorCategory(Enum):
    RECOVERABLE = "RECOVERABLE"
    CRITICAL = "CRITICAL"
    SECURITY = "SECURITY"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    STRATEGY = "STRATEGY"

class StructuredLogger:
    def __init__(self, name="lumibot_bot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _scrub(self, data):
        """Redact sensitive keys from log data."""
        if not isinstance(data, dict):
            return data
        sensitive_keys = {"api_key", "secret", "token", "password", "key", "authorization"}
        scrubbed = {}
        for k, v in data.items():
            if any(sk in k.lower() for sk in sensitive_keys):
                scrubbed[k] = "[REDACTED]"
            elif isinstance(v, dict):
                scrubbed[k] = self._scrub(v)
            else:
                scrubbed[k] = v
        return scrubbed

    def _log(self, level, message, category=ErrorCategory.RECOVERABLE, **kwargs):
        scrubbed_kwargs = self._scrub(kwargs)
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "category": category.value if isinstance(category, ErrorCategory) else category,
            "message": message,
            **scrubbed_kwargs
        }
        # Print as JSON for external log aggregators
        print(json.dumps(log_entry))
        
        # Also log to standard logger
        log_msg = f"[{level}] [{category.value if isinstance(category, ErrorCategory) else category}] {message}"
        if level == "INFO":
            self.logger.info(log_msg)
        elif level == "WARNING":
            self.logger.warning(log_msg)
        elif level == "ERROR":
            self.logger.error(log_msg)

        # ── Operational Hardening: Send to Supabase if critical ────────
        try:
            from adapters import supabase_logger
            if level in ["ERROR", "WARNING"] or category == ErrorCategory.SECURITY:
                supabase_logger.log_alert(level, str(category), message, kwargs)
            
            if category in [ErrorCategory.STRATEGY, ErrorCategory.INFRASTRUCTURE]:
                supabase_logger.log_audit(level, "LOGGED", message, kwargs)
        except ImportError:
            pass

    def info(self, message, category=ErrorCategory.RECOVERABLE, **kwargs):
        self._log("INFO", message, category, **kwargs)

    def warning(self, message, category=ErrorCategory.RECOVERABLE, **kwargs):
        self._log("WARNING", message, category, **kwargs)

    def error(self, message, category=ErrorCategory.CRITICAL, **kwargs):
        self._log("ERROR", message, category, **kwargs)

    def security(self, message, **kwargs):
        self._log("ERROR", message, ErrorCategory.SECURITY, **kwargs)

# Global instance
bot_logger = StructuredLogger()
