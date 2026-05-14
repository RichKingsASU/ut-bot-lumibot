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
    """Consolidated health report for the dashboard."""
    broker_ok = bool(os.getenv("ALPACA_API_KEY")) and bool(os.getenv("ALPACA_API_SECRET"))
    
    return jsonify({
        "status": "ready" if (_is_ready and broker_ok) else "starting",
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "websocket": "connected" if _is_ready else "disconnected", # Simplified for now
        "paper_mode": ALPACA_CONFIG.get("PAPER", True),
        "has_open_position": has_open_position(),
        "uptime": int(psutil.Process().create_time())
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
