import os
import httpx
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger("safe_write")
logger.setLevel(logging.INFO)

# Thread-safe in-memory tracking of degraded components and cycle counts
_lock = threading.Lock()
_degraded_components = set()
_cycle_counts = {}

async def _send_telegram_alert(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "8641189809")
    if not token:
        logger.warning("[SAFE_WRITE] Telegram bot token missing, alert not sent.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
            if resp.status_code >= 300:
                logger.warning(f"[SAFE_WRITE] Telegram API error ({resp.status_code}): {resp.text}")
    except Exception as te:
        logger.error(f"[SAFE_WRITE] Failed to send Telegram heartbeat alert: {te}")

def _send_telegram_alert_sync(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "8641189809")
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
            if resp.status_code >= 300:
                logger.warning(f"[SAFE_WRITE] Telegram API error sync ({resp.status_code}): {resp.text}")
    except Exception as te:
        logger.error(f"[SAFE_WRITE] Failed to send Telegram heartbeat alert sync: {te}")

# ── Async APIs ──────────────────────────────────────────────────────────────

async def safe_write_async(table: str, payload: dict, component: str, method: str = "post", params: dict = None, upsert: bool = False, _url: str = None, _key: str = None) -> bool:
    """
    Perform an async write to Supabase table.
    Updates component_heartbeat, triggers Telegram alert on state transition,
    and drops database write exceptions.
    Pass _url/_key to override env credentials for multi-target callers.
    """
    url = _url or os.getenv("SUPABASE_URL")
    key = _key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logger.warning(f"[SAFE_WRITE] Supabase credentials missing — write to {table} skipped for {component}")
        return False

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # merge-duplicates turns an INSERT into an upsert on the primary key,
        # required for singleton/keyed rows (bot_status id=1, component_status
        # process_name) that would otherwise 409 on every write.
        "Prefer": "return=minimal,resolution=merge-duplicates" if upsert else "return=minimal",
    }

    # Increment cycle count
    with _lock:
        _cycle_counts[component] = _cycle_counts.get(component, 0) + 1
        cycle_val = _cycle_counts[component]

    now_iso = datetime.now(timezone.utc).isoformat()
    success = False
    error_msg = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method.lower() == "post":
                resp = await client.post(f"{url}/rest/v1/{table}", headers=headers, json=payload, params=params)
            elif method.lower() == "patch":
                resp = await client.patch(f"{url}/rest/v1/{table}", headers=headers, json=payload, params=params)
            elif method.lower() == "put":
                resp = await client.put(f"{url}/rest/v1/{table}", headers=headers, json=payload, params=params)
            else:
                raise ValueError(f"Unsupported write method: {method}")
            
            if resp.status_code in (200, 201, 204):
                success = True
            else:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        error_msg = str(e)

    # Prepare heartbeat record
    heartbeat_payload = {
        "component": component,
        "cycle_count": cycle_val,
        "meta": {"table": table, "method": method}
    }

    alert_to_send = None
    with _lock:
        is_degraded = component in _degraded_components

        if success:
            heartbeat_payload.update({
                "status": "OK",
                "last_success_at": now_iso,
                "last_error": None,
                "last_error_at": None
            })
            if is_degraded:
                _degraded_components.remove(component)
                alert_to_send = f"✅ <b>Component Recovered: {component}</b>\nWrite to <code>{table}</code> succeeded."
        else:
            logger.warning(f"[SAFE_WRITE] {component} failed to write to {table}: {error_msg}")
            heartbeat_payload.update({
                "status": "DEGRADED",
                "last_error": error_msg,
                "last_error_at": now_iso
            })
            if not is_degraded:
                _degraded_components.add(component)
                alert_to_send = (
                    f"🚨 <b>Component Degraded: {component}</b>\n"
                    f"Failed to write to <code>{table}</code>\n"
                    f"Error: <code>{error_msg}</code>"
                )

    if alert_to_send:
        await _send_telegram_alert(alert_to_send)

    # Upsert to component_heartbeat
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            hb_resp = await client.post(
                f"{url}/rest/v1/component_heartbeat",
                json=heartbeat_payload,
                headers={**headers, "Prefer": "resolution=merge-duplicates"},
            )
            if hb_resp.status_code >= 300:
                logger.warning(f"[SAFE_WRITE] Failed to upsert heartbeat for {component} (HTTP {hb_resp.status_code}): {hb_resp.text[:200]}")
    except Exception as hbe:
        logger.warning(f"[SAFE_WRITE] Failed to upsert heartbeat for {component}: {hbe}")

    return success

async def beat_async(component: str, status: str = "OK", last_error: str = None, meta: dict = None) -> None:
    """Send an async periodic status update to component_heartbeat."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    with _lock:
        _cycle_counts[component] = _cycle_counts.get(component, 0) + 1
        cycle_val = _cycle_counts[component]

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "component": component,
        "status": status,
        "cycle_count": cycle_val,
        "meta": meta or {}
    }
    
    if status == "OK":
        payload.update({
            "last_success_at": now_iso,
            "last_error": None,
            "last_error_at": None
        })
    else:
        payload.update({
            "last_error": last_error,
            "last_error_at": now_iso
        })

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{url}/rest/v1/component_heartbeat", json=payload, headers=headers)
    except Exception as e:
        logger.warning(f"[SAFE_WRITE] Failed to send async heartbeat for {component}: {e}")

# ── Sync APIs ───────────────────────────────────────────────────────────────

def safe_write_sync(table: str, payload: dict, component: str, method: str = "post", params: dict = None, upsert: bool = False, _url: str = None, _key: str = None) -> bool:
    """Sync version of safe_write_async. Pass _url/_key to override env credentials."""
    url = _url or os.getenv("SUPABASE_URL")
    key = _key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logger.warning(f"[SAFE_WRITE] Supabase credentials missing — write to {table} skipped for {component}")
        return False

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # merge-duplicates turns an INSERT into an upsert on the primary key,
        # required for singleton/keyed rows (bot_status id=1, component_status
        # process_name) that would otherwise 409 on every write.
        "Prefer": "return=minimal,resolution=merge-duplicates" if upsert else "return=minimal",
    }

    with _lock:
        _cycle_counts[component] = _cycle_counts.get(component, 0) + 1
        cycle_val = _cycle_counts[component]

    now_iso = datetime.now(timezone.utc).isoformat()
    success = False
    error_msg = None

    try:
        with httpx.Client(timeout=10.0) as client:
            if method.lower() == "post":
                resp = client.post(f"{url}/rest/v1/{table}", headers=headers, json=payload, params=params)
            elif method.lower() == "patch":
                resp = client.patch(f"{url}/rest/v1/{table}", headers=headers, json=payload, params=params)
            elif method.lower() == "put":
                resp = client.put(f"{url}/rest/v1/{table}", headers=headers, json=payload, params=params)
            else:
                raise ValueError(f"Unsupported write method: {method}")
            
            if resp.status_code in (200, 201, 204):
                success = True
            else:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        error_msg = str(e)

    heartbeat_payload = {
        "component": component,
        "cycle_count": cycle_val,
        "meta": {"table": table, "method": method}
    }

    alert_to_send = None
    with _lock:
        is_degraded = component in _degraded_components

        if success:
            heartbeat_payload.update({
                "status": "OK",
                "last_success_at": now_iso,
                "last_error": None,
                "last_error_at": None
            })
            if is_degraded:
                _degraded_components.remove(component)
                alert_to_send = f"✅ <b>Component Recovered: {component}</b>\nWrite to <code>{table}</code> succeeded."
        else:
            logger.warning(f"[SAFE_WRITE] {component} failed to write to {table}: {error_msg}")
            heartbeat_payload.update({
                "status": "DEGRADED",
                "last_error": error_msg,
                "last_error_at": now_iso
            })
            if not is_degraded:
                _degraded_components.add(component)
                alert_to_send = (
                    f"🚨 <b>Component Degraded: {component}</b>\n"
                    f"Failed to write to <code>{table}</code>\n"
                    f"Error: <code>{error_msg}</code>"
                )

    if alert_to_send:
        _send_telegram_alert_sync(alert_to_send)

    try:
        with httpx.Client(timeout=10.0) as client:
            hb_resp = client.post(
                f"{url}/rest/v1/component_heartbeat",
                json=heartbeat_payload,
                headers={**headers, "Prefer": "resolution=merge-duplicates"},
            )
            if hb_resp.status_code >= 300:
                logger.warning(f"[SAFE_WRITE] Failed to upsert heartbeat for {component} (HTTP {hb_resp.status_code}): {hb_resp.text[:200]}")
    except Exception as hbe:
        logger.warning(f"[SAFE_WRITE] Failed to upsert heartbeat for {component}: {hbe}")

    return success

def beat_sync(component: str, status: str = "OK", last_error: str = None, meta: dict = None) -> None:
    """Send a sync periodic status update to component_heartbeat."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    with _lock:
        _cycle_counts[component] = _cycle_counts.get(component, 0) + 1
        cycle_val = _cycle_counts[component]

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "component": component,
        "status": status,
        "cycle_count": cycle_val,
        "meta": meta or {}
    }
    
    if status == "OK":
        payload.update({
            "last_success_at": now_iso,
            "last_error": None,
            "last_error_at": None
        })
    else:
        payload.update({
            "last_error": last_error,
            "last_error_at": now_iso
        })

    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(f"{url}/rest/v1/component_heartbeat", json=payload, headers=headers)
    except Exception as e:
        logger.warning(f"[SAFE_WRITE] Failed to send sync heartbeat for {component}: {e}")
