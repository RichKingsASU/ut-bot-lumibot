import abc
import os
import asyncio
import logging
import signal
import httpx
from datetime import datetime, timezone, time
from dotenv import load_dotenv

import adapters.telegram_alerts as telegram_alerts

logger = logging.getLogger("HermesBaseAgent")

class HermesAgent(abc.ABC):
    def __init__(self, name: str, interval_seconds: int, market_hours_only: bool = False):
        self.name = name
        self.interval_seconds = interval_seconds
        self.market_hours_only = market_hours_only
        self._shutdown_event = asyncio.Event()

        load_dotenv()
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY_HERMES")

        # Set up shutdown signals
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                asyncio.get_event_loop().add_signal_handler(sig, self._handle_shutdown, sig)
            except NotImplementedError:
                pass # Windows does not support add_signal_handler

    def _handle_shutdown(self, *args):
        logger.info(f"[{self.name}] Received shutdown signal.")
        self._shutdown_event.set()

    def _is_market_hours(self) -> bool:
        now = datetime.now(timezone.utc)
        # EST/EDT approximation - not fully robust to daylight savings but matches pattern
        # Real market hours are 09:30-16:00 ET. The prompt requests 09:25-16:05 ET.
        # This will use a simplified UTC check (assuming NY time is UTC-4 or UTC-5).
        # To be completely safe and avoid pytz dependencies if not present, we will use a naive approach
        # or rely on the system timezone.
        # Given this is a simple check, we will use a basic time range check in UTC assuming UTC-4 (EDT).
        # We will use ET by converting to UTC or simply use UTC time.
        # Let's use `datetime.now()` with `astimezone` if available, or just check weekday for now.
        
        # Simplified: Mon-Fri
        if now.weekday() >= 5:
            return False
            
        import pytz
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(eastern)
        
        market_open = time(9, 25)
        market_close = time(16, 5)
        current_time = now_et.time()
        
        return market_open <= current_time <= market_close

    async def _write_heartbeat(self, status: str, meta: dict = None, error: str = None):
        """Writes to component_heartbeat via Supabase REST API."""
        if not self.supabase_url or not self.supabase_key:
            logger.warning(f"[{self.name}] Missing Supabase credentials, skipping heartbeat.")
            return

        url = f"{self.supabase_url}/rest/v1/component_heartbeat"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        
        now_iso = datetime.now(timezone.utc).isoformat()
        
        payload = {
            "component": self.name,
            "status": status,
            "cycle_count": getattr(self, "_cycle_count", 0),
        }
        
        if status == "running":
            payload["last_success_at"] = now_iso
        elif status == "error":
            payload["last_error"] = error
            payload["last_error_at"] = now_iso
            
        if meta is not None:
            payload["meta"] = meta

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
        except Exception as e:
            logger.error(f"[{self.name}] Failed to write heartbeat: {e}")

    @abc.abstractmethod
    async def run_cycle(self) -> None:
        """To be implemented by subclass."""
        pass

    async def start(self):
        logger.info(f"[{self.name}] Starting Hermes Agent. Interval: {self.interval_seconds}s")
        self._cycle_count = 0
        
        while not self._shutdown_event.is_set():
            if self.market_hours_only and not self._is_market_hours():
                logger.debug(f"[{self.name}] Outside market hours, skipping cycle.")
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.interval_seconds)
                except asyncio.TimeoutError:
                    pass
                continue

            try:
                await self.run_cycle()
                self._cycle_count += 1
                await self._write_heartbeat("running", meta={"summary": f"Completed cycle {self._cycle_count}"})
            except Exception as e:
                logger.error(f"[{self.name}] Error in cycle: {e}")
                await self._write_heartbeat("error", error=str(e))
                telegram_alerts.send_alert(f"🚨 [{self.name}] Cycle Error:\n{e}")

            # Sleep for interval
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

        logger.info(f"[{self.name}] Shutting down.")
        await self._write_heartbeat("stopped", meta={"summary": "Agent stopped cleanly."})
