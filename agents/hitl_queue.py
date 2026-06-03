import os, httpx, datetime, logging
from typing import Optional
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = '8641189809'

def _headers():
    return {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json', 'Prefer': 'return=representation'}

def submit_for_approval(signal: dict) -> Optional[int]:
    payload = {
        'symbol': signal.get('symbol'),
        'asset_class': signal.get('asset_class'),
        'proposed_action': signal.get('action', 'BUY'),
        'proposed_size_usd': min(float(signal.get('kelly_position_value', 0)), 2500.0),
        'debate_verdict': signal.get('debate_verdict'),
        'bull_score': signal.get('debate_bull_score'),
        'bear_score': signal.get('debate_bear_score'),
        'regime': signal.get('regime'),
        'sentiment_score': signal.get('sentiment_score'),
        'reasoning_summary': str(signal.get('reasoning', ''))[:500],
    }
    try:
        r = httpx.post(f'{SUPABASE_URL}/rest/v1/hitl_queue',
            headers=_headers(), json=payload, timeout=5)
        if r.status_code in (200, 201):
            row = r.json()
            qid = row[0].get('id') if isinstance(row, list) else row.get('id')
            _telegram_alert(signal, qid)
            return qid
    except Exception as e:
        logger.error(f"[HITL] Submit error: {e}")
    return None

def get_approved_signals() -> list:
    try:
        r = httpx.get(f'{SUPABASE_URL}/rest/v1/hitl_queue',
            headers=_headers(),
            params={'approved': 'eq.true', 'executed': 'eq.false',
                    'rejected': 'eq.false', 'order': 'approved_at.asc'},
            timeout=5)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        logger.error(f"[HITL] Poll error: {e}")
        return []

def mark_executed(qid: int):
    try:
        httpx.patch(f'{SUPABASE_URL}/rest/v1/hitl_queue?id=eq.{qid}',
            headers=_headers(),
            json={'executed': True, 'executed_at': datetime.datetime.utcnow().isoformat()},
            timeout=5)
    except Exception as e:
        logger.error(f"[HITL] Mark executed error: {e}")

def _telegram_alert(signal: dict, qid: Optional[int]):
    if not TELEGRAM_TOKEN:
        return
    msg = (f"🔔 TRADE SIGNAL AWAITING APPROVAL\n"
           f"Symbol: {signal.get('symbol')}\n"
           f"Action: {signal.get('action')}\n"
           f"Size: ${min(float(signal.get('kelly_position_value',0)),2500):.2f}\n"
           f"Verdict: {signal.get('debate_verdict')}\n"
           f"Bull: {signal.get('debate_bull_score')} Bear: {signal.get('debate_bear_score')}\n"
           f"Regime: {signal.get('regime')}\n"
           f"Queue ID: {qid}\n"
           f"➡️ disruptingalpha.com/admin/hitl")
    try:
        httpx.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            data={'chat_id': CHAT_ID, 'text': msg}, timeout=5)
    except Exception as e:
        logger.warning(f"[HITL] Telegram alert failed: {e}")
