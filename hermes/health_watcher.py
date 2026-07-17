import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from hermes.base_agent import HermesAgent
import adapters.telegram_alerts as telegram_alerts

logger = logging.getLogger("HermesHealthWatcher")

class HealthWatcher(HermesAgent):
    def __init__(self):
        super().__init__(
            name="hermes_health_watcher",
            interval_seconds=60,
            market_hours_only=False
        )
        self.previous_states: Dict[str, str] = {}

    async def run_cycle(self) -> None:
        if not self.supabase_url or not self.supabase_key:
            logger.error("Missing Supabase credentials.")
            return

        url = f"{self.supabase_url}/rest/v1/component_heartbeat"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                components = resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch component_heartbeat: {e}")
            return

        now = datetime.now(timezone.utc)
        
        current_components = set()

        for comp in components:
            name = comp.get("component")
            current_components.add(name)
            last_success_str = comp.get("last_success_at")
            
            if not last_success_str:
                state = "UNKNOWN"
                age_minutes = 0
            else:
                try:
                    last_success = datetime.fromisoformat(last_success_str.replace("Z", "+00:00"))
                    age = now - last_success
                    age_minutes = age.total_seconds() / 60.0
                    
                    if age_minutes < 2:
                        state = "RUNNING"
                    elif age_minutes <= 10:
                        state = "STALE"
                    else:
                        state = "DOWN"
                except Exception:
                    state = "UNKNOWN"
                    age_minutes = 0

            prev_state = self.previous_states.get(name)
            
            if state != prev_state:
                if state == "STALE":
                    telegram_alerts.send_alert(f"⚠️ {name} → STALE (last seen {age_minutes:.0f}m ago)")
                elif state == "DOWN":
                    telegram_alerts.send_alert(f"🔴 {name} → DOWN (last seen {age_minutes:.0f}m ago)")
                elif state == "RUNNING" and prev_state in ("STALE", "DOWN"):
                    telegram_alerts.send_alert(f"✅ {name} → RUNNING (recovered)")
                    
                self.previous_states[name] = state

        # Check if any previously tracked components are completely missing from DB
        for name in list(self.previous_states.keys()):
            if name not in current_components:
                state = "UNKNOWN"
                if self.previous_states[name] != state:
                    telegram_alerts.send_alert(f"❓ {name} → UNKNOWN (no row exists)")
                    self.previous_states[name] = state
