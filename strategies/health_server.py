import threading
import os
import logging
from flask import Flask, jsonify
import psutil
from strategies.options_executor import has_open_position
from config import ALPACA_CONFIG, ALPACA_BASE_URL

logger = logging.getLogger("health_server")
app = Flask(__name__)

# Global status flags
_is_ready = False

@app.route("/health")
def health():
    """Liveness check - is the process running?"""
    return jsonify({
        "status": "alive",
        "cpu_percent": psutil.cpu_percent(),
        "memory_info": psutil.virtual_memory()._asdict()
    }), 200

@app.route("/ready")
def ready():
    """Readiness check - is the bot initialized and connected?"""
    if not _is_ready:
        return jsonify({"status": "starting"}), 503
        
    # Check broker connectivity (basic check)
    broker_ok = bool(os.getenv("ALPACA_API_KEY")) and bool(os.getenv("ALPACA_API_SECRET"))
    
    return jsonify({
        "status": "ready" if broker_ok else "unhealthy",
        "paper_mode": ALPACA_CONFIG.get("PAPER", True),
        "broker_url": ALPACA_BASE_URL,
        "has_open_position": has_open_position(),
    }), 200 if broker_ok else 500

def set_ready(ready: bool = True):
    global _is_ready
    _is_ready = ready

def start_health_server(port: int = 8000):
    def run():
        # Disable Flask logging to keep output clean
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    logger.info("Health server started on port %d", port)
