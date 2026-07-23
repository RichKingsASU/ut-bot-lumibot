import logging
import threading

logger = logging.getLogger(__name__)

_warned_unrecognized_key = False
_warn_lock = threading.Lock()

def get_supabase_headers(key: str, extra: dict | None = None) -> dict:
    global _warned_unrecognized_key
    headers = {"apikey": key}
    
    if key.startswith("sb_"):
        pass  # no Authorization header
    else:
        parts = key.split(".")
        if len(parts) == 3 and parts[0].startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        else:
            with _warn_lock:
                if not _warned_unrecognized_key:
                    logger.warning("unrecognized Supabase key format")
                    _warned_unrecognized_key = True

    if extra:
        headers.update(extra)
    return headers
