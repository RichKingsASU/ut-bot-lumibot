"""
Orchestrator — Disrupting Alpha v2 Phase 5 Run 4
LangGraph StateGraph pipeline wiring all agents together.
Two parallel pipelines: Crypto and Equities.
Greeks intercept circuit breaker fully wired.
"""

import asyncio
import json
import logging
import os
import datetime as _dt
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import TypedDict

import httpx
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

from agents.market_analyst import MarketAnalystAgent
from agents.signal_agent import SignalAgent
from agents.risk_agent import RiskAgent
from agents.research_agent import ResearchAgent
from agents.regime_detector import RegimeDetector
from agents.kelly_sizer import KellySizer
from agents.greeks_risk_engine import GreeksRiskEngine
from agents.gex_calculator import compute_gex
from agents.pead_signal import get_pead_signal
from agents.ma_regime_filter import get_spy_200day_ma, apply_ma_filter
from agents.market_freshness import validate_market_freshness
from agents.hitl_queue import submit_for_approval
from agents.kronos_forecaster import compare_with_timesfm as _kronos_compare

load_dotenv()

logger = logging.getLogger("Orchestrator")

from agents.node_circuit_breaker import CIRCUIT_BREAKER

_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8641189809")

# ── Daily stop module-level state ─────────────────────────────────────────────
_DAILY_STOP_ACTIVE: bool = False
_DAILY_STOP_ALERTED: bool = False

_ET = ZoneInfo("America/New_York")


def _send_daily_stop_alert(loss: float, limit: float, equity: float) -> None:
    """Send a one-shot Telegram alert when the soft daily stop is triggered."""
    global _DAILY_STOP_ALERTED
    if _DAILY_STOP_ALERTED:
        return  # Only alert once per day
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        return
    msg = (
        f"⚠️ SOFT DAILY STOP TRIGGERED\n"
        f"Daily loss: ${loss:.2f}\n"
        f"Limit: ${limit:.2f} (2.5%)\n"
        f"Current equity: ${equity:,.2f}\n"
        f"New BUY signals paused for remainder of session.\n"
        f"Hard stop remains at ${5000:.0f}."
    )
    try:
        httpx.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data={'chat_id': '8641189809', 'text': msg},
            timeout=5
        )
        _DAILY_STOP_ALERTED = True
        logger.info("[DAILY STOP] Telegram alert sent.")
    except Exception as e:
        logger.warning(f"Daily stop alert failed: {e}")


def _check_daily_stop() -> bool:
    """Query Alpaca paper account equity and set/clear _DAILY_STOP_ACTIVE.

    Returns True if the soft stop is active (daily loss > 2.5%).
    """
    global _DAILY_STOP_ACTIVE, _DAILY_STOP_ALERTED

    # Reset alert flag at the start of a new trading day (before market open)
    now_et = _dt.datetime.now(_ET)
    if now_et.hour == 9 and now_et.minute < 30:
        _DAILY_STOP_ALERTED = False

    try:
        ak = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY')
        ask = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET')
        acct_r = httpx.get(
            'https://paper-api.alpaca.markets/v2/account',
            headers={'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': ask},
            timeout=5
        )
        acct = acct_r.json()
        current_equity = float(acct.get('equity', 0))
        last_equity = float(acct.get('last_equity', current_equity))

        SOFT_STOP_PCT = 0.025
        soft_stop_usd = last_equity * SOFT_STOP_PCT
        daily_loss = last_equity - current_equity

        if daily_loss > soft_stop_usd:
            logger.warning(
                f"[DAILY STOP] Soft stop triggered — lost ${daily_loss:.2f} today "
                f"(limit: ${soft_stop_usd:.2f}). Pausing new BUY signals."
            )
            _send_daily_stop_alert(daily_loss, soft_stop_usd, current_equity)
            _DAILY_STOP_ACTIVE = True
        else:
            _DAILY_STOP_ACTIVE = False
    except Exception as e:
        logger.warning(f"[DAILY STOP] Could not check daily P&L: {e}")

    return _DAILY_STOP_ACTIVE


# ── Telegram helper ───────────────────────────────────────────────────────────

async def _send_telegram(text: str, chat_id: str = _TELEGRAM_CHAT_ID) -> None:
    """Send a Telegram message (best-effort, never raises)."""
    token = _TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; skipping Telegram notification.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram message sent successfully.")
            else:
                logger.error(f"Telegram send failed: {resp.status_code} — {resp.text}")
    except Exception as exc:
        logger.error(f"Telegram send exception: {exc}")


# ── AgentState ────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    asset_class: str  # crypto or equities
    regime_summary: dict
    market_context: dict
    signal_recommendation: dict
    debate_result: dict
    greeks_decision: dict
    kelly_sizing: dict
    risk_decision: dict
    overnight_digest: dict
    cycle_timestamp: str
    signal_decay_summary: dict
    var_result: dict
    execution_approved: bool
    execution_reason: str


# ── Node implementations ──────────────────────────────────────────────────────

def regime_detection_node(state: AgentState) -> AgentState:
    from agents.regime_detector import RegimeDetector
    from datetime import datetime, timezone
    import asyncio
    asset_class = state.get('asset_class', 'equities')
    
    try:
        detector = RegimeDetector('regime-detector', asset_class)
        regime_summary = asyncio.run(detector.analyze())
        state['regime_summary'] = regime_summary
        logger.info(
            f"[Regime] {asset_class} regime: "
            f"{regime_summary.get('overall_regime')} "
            f"({regime_summary.get('strategy_recommendation', '')[:50]})"
        )
    except Exception as e:
        logger.error(f"[Regime] Detection failed: {e}")
        state['regime_summary'] = {
            'overall_regime': 'QUIET',
            'strategy_recommendation': 'Default — regime detection unavailable',
            'symbol_regimes': {},
            'regime_distribution': {},
            'detected_at': datetime.now(timezone.utc).isoformat()
        }
    
    return state


def execution_filter_node(state: AgentState) -> AgentState:
    NODE = 'execution_filter_node'
    if CIRCUIT_BREAKER.is_open(NODE):
        logger.warning(f'[CB] {NODE} circuit open — defaulting to approved')
        state['execution_approved'] = True
        state['execution_reason'] = 'Circuit breaker bypass'
        return state

    from adapters.execution_filter import ExecutionFilter
    asset_class = state.get('asset_class', 'equities')

    if asset_class == 'crypto':
        state['execution_approved'] = True
        state['execution_reason'] = 'Crypto trades 24/7'
        CIRCUIT_BREAKER.record_success(NODE)
        return state

    try:
        ef = ExecutionFilter()
        result = ef.full_execution_check()
        state['execution_approved'] = result['approved']
        state['execution_reason'] = ', '.join(result['reasons']) if result['reasons'] else 'OK'

        if not result['approved']:
            logger.info(
                f'[Execution] SKIP: {result["recommendation"]} — {result["reasons"]}'
            )
            state['signal_recommendation'] = {
                'action': 'HOLD',
                'confidence': 'LOW',
                'reasoning': f'Execution filter: {result["reasons"]}',
                'asset_class': asset_class,
                'symbol': 'SPY'
            }
        CIRCUIT_BREAKER.record_success(NODE)
    except Exception as e:
        logger.error(f'[Execution] Filter failed: {e}')
        CIRCUIT_BREAKER.record_failure(NODE)
        state['execution_approved'] = True
        state['execution_reason'] = 'Filter error, defaulted to true'

    return state


def market_analysis_node(state: AgentState) -> AgentState:
    """Calls MarketAnalystAgent().analyze() and stores result in state."""
    try:
        logger.info(f"[Orchestrator] market_analysis_node executing for {state['asset_class']}...")
        asset = state.get("asset_class", "crypto")
        agent = MarketAnalystAgent(f"{asset}-analyst", asset_class=asset)
        regime_summary = state.get("regime_summary")
        market_context = asyncio.run(agent.analyze(regime_summary))
        logger.info(f"[Orchestrator] {asset} market_context received: {list(market_context.keys())}")
        return {**state, "market_context": market_context}
    except Exception as e:
        logger.error(f"[MarketAnalysis] Failed: {e}")
        return {**state, "market_context": {}}


def signal_node(state: AgentState) -> AgentState:
    """Calls SignalAgent().analyze(market_context, greeks_context) and stores result in state."""
    try:
        logger.info(f"[Orchestrator] signal_node executing for {state['asset_class']}...")
        asset = state.get("asset_class", "crypto")
        agent = SignalAgent(f"{asset}-signal", asset_class=asset)
        greeks_context = state.get("greeks_decision") or None
        signal_recommendation = asyncio.run(
            agent.analyze(state["market_context"], greeks_context=greeks_context)
        )
        logger.info(f"[Orchestrator] {asset} signal_recommendation: {signal_recommendation}")
        if asset == 'equities':
            ma_data = state.get('ma_data') or {}
            signal_recommendation = apply_ma_filter(signal_recommendation, ma_data)
            gex_data = state.get('gex_data') or {}
            if gex_data.get('available'):
                kelly_val = signal_recommendation.get('kelly_position_value', 0.0)
                kelly_val *= gex_data.get('size_modifier', 1.0)
                signal_recommendation['kelly_position_value'] = min(kelly_val, 2500.0)

            # ── Session filter: block BUY outside active equities windows ──────
            from agents.session_filter import get_session_context
            session = state.get('_session_context') or get_session_context()
            if not session.get('allow_buy') and signal_recommendation.get('action') == 'BUY':
                signal_recommendation['action'] = 'HOLD'
                signal_recommendation['reasoning'] = (
                    signal_recommendation.get('reasoning', '') +
                    f" | SESSION FILTER: BUY blocked — {session['reason']}"
                )
                logger.info(f"[SESSION] BUY converted to HOLD — {session['reason']}")

            # ── Conviction modifier: scale Kelly position size ─────────────────
            conv_mod = session.get('conviction_modifier', 1.0)
            if conv_mod < 1.0:
                kelly_val = signal_recommendation.get('kelly_position_value', 0)
                signal_recommendation['kelly_position_value'] = kelly_val * conv_mod
                logger.info(f"[SESSION] Kelly scaled by conviction_modifier={conv_mod}")

        # ── Daily soft stop: block BUY for all asset classes ──────────────────
        import sys as _sys
        _orch_mod = _sys.modules.get(__name__, None)
        if getattr(_orch_mod, '_DAILY_STOP_ACTIVE', False):
            if signal_recommendation.get('action') == 'BUY':
                signal_recommendation['action'] = 'HOLD'
                signal_recommendation['reasoning'] = (
                    signal_recommendation.get('reasoning', '') +
                    " | DAILY STOP: Soft 2.5% daily loss limit reached. BUY paused."
                )
                logger.info("[DAILY STOP] BUY converted to HOLD — daily stop active.")

        return {**state, "signal_recommendation": signal_recommendation}
    except Exception as e:
        logger.error(f"[Signal] Failed: {e}")
        return {**state, "signal_recommendation": {"action": "HOLD", "confidence": "LOW", "reasoning": "Error in signal node"}}


async def _debate_node_async(state: AgentState) -> AgentState:
    """Bull/Bear/Judge debate intercept (async inner).

    Runs between signal_node and greeks_intercept.
    """
    from agents.bull_agent import BullAgent
    from agents.bear_agent import BearAgent
    from agents.judge_agent import JudgeAgent

    signal = state.get('signal_recommendation', {}) or {}
    market = state.get('market_context', {}) or {}
    greeks = state.get('greeks_decision', {}) or {}
    regime = state.get('regime_summary', {}) or {}
    asset_class = state.get('asset_class', 'equities')
    default_symbol = 'ETH/USD' if asset_class == 'crypto' else 'SPY'
    symbol = signal.get('symbol', default_symbol)

    market['sentiment_trend'] = signal.get('sentiment_trend', market.get('sentiment_trend', 'STABLE'))
    market['sentiment_velocity'] = signal.get('sentiment_velocity', market.get('sentiment_velocity', 0.0))

    if asset_class == 'equities':
        from agents.pead_signal import get_pead_signal
        pead_data = get_pead_signal(symbol)
        state['pead_data'] = pead_data
        
        gex_data = state.get('gex_data') or {}
        ma_data = state.get('ma_data') or {}
        
        gex_context = f"GEX Regime: {gex_data.get('gex_regime', 'UNKNOWN')}\nNet GEX: ${gex_data.get('gex_value_millions', 0):.1f}M\nInterpretation: {gex_data.get('interpretation', 'N/A')}"
        ma_context = f"200-day MA regime: {ma_data.get('regime')} — {ma_data.get('signal')}"
        pead_context = f"Post-Earnings Signal: {pead_data.get('signal')}\n{pead_data.get('description')}"
        
        market['gex_context'] = gex_context
        market['ma_context'] = ma_context
        market['pead_context'] = pead_context
        state['market_context'] = market

    try:
        bull = BullAgent(f'{asset_class}-bull')
        bear = BearAgent(f'{asset_class}-bear')
        judge = JudgeAgent(f'{asset_class}-judge')

        bull_case = await bull.analyze(symbol, market, signal, greeks, regime)
        bear_case = await bear.analyze(symbol, market, signal, greeks, regime)
        verdict = await judge.analyze(symbol, bull_case, bear_case, signal)

        state['debate_result'] = verdict

        logger.info(
            f"[Debate] {symbol}: "
            f"Bull={bull_case['score']:.0f} "
            f"Bear={bear_case['score']:.0f} "
            f"Verdict={verdict['verdict']} "
            f"({verdict['confidence_score']:.0f}%)"
        )

        if verdict['verdict'] in ['AVOID', 'STRONG_AVOID']:
            signal.setdefault('reasoning', '')
            signal['action'] = 'HOLD'
            signal['confidence'] = 'LOW'
            signal['reasoning'] += (
                f" | Debate: {verdict['verdict']} "
                f"({verdict['reasoning'][:100]})"
            )
            state['signal_recommendation'] = signal

    except Exception as e:
        logger.error(f"[Debate] Failed: {e}")
        state['debate_result'] = {
            'verdict': 'NEUTRAL',
            'proceed': True,
            'confidence_score': 50.0,
            'bull_score': 50.0,
            'bear_score': 50.0,
        }

    return state


def debate_node(state: AgentState) -> AgentState:
    """Bull/Bear/Judge debate node — wired between signal_node and greeks_intercept."""
    NODE = 'debate_node'
    if CIRCUIT_BREAKER.is_open(NODE):
        logger.warning(f'[CB] {NODE} circuit open — skipping debate')
        state['debate_result'] = {
            'verdict': 'NEUTRAL',
            'proceed': True,
            'confidence_score': 50.0,
            'bull_score': 50.0,
            'bear_score': 50.0,
        }
        return state

    logger.info(f"[Orchestrator] debate_node executing for {state['asset_class']}...")
    try:
        result = asyncio.run(_debate_node_async(dict(state)))
        CIRCUIT_BREAKER.record_success(NODE)
        return result
    except Exception as e:
        logger.error(f'[Debate] Node failed: {e}')
        CIRCUIT_BREAKER.record_failure(NODE)
        state['debate_result'] = {
            'verdict': 'NEUTRAL',
            'proceed': True,
            'confidence_score': 50.0,
            'bull_score': 50.0,
            'bear_score': 50.0,
        }
        return state


async def _greeks_intercept_async(state: AgentState) -> AgentState:
    """Full Greeks circuit-breaker intercept node (async inner)."""
    import pytz
    from datetime import datetime
    from collectors.option_data_worker import get_cached_greeks, is_market_hours
    from agents.greeks_risk_engine import GreeksRiskEngine
    import os, requests

    signal = state.get('signal_recommendation', {})
    asset_class = state.get('asset_class', 'equities')
    symbol = signal.get('symbol', 'ETH/USD' if asset_class == 'crypto' else 'SPY')

    # Only run Greeks for equities during market hours
    if asset_class == 'crypto' or not is_market_hours():
        iv_rank = 50.0
        gamma = 0.0
        trade_mode = 'NEUTRAL'
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if supabase_url and service_role_key:
                headers = {
                    "apikey": service_role_key,
                    "Authorization": f"Bearer {service_role_key}",
                }
                url = f"{supabase_url}/rest/v1/greeks_snapshots"
                params = {
                    "symbol": f"eq.{symbol}",
                    "order": "snapshot_at.desc",
                    "limit": "1"
                }
                resp = requests.get(url, headers=headers, params=params, timeout=5.0)
                if resp.status_code == 200 and resp.json():
                    greeks_snap = resp.json()[0]
                    iv_rank = float(greeks_snap.get("iv_rank", 50.0))
                    gamma = float(greeks_snap.get("gamma", 0.0))
                    trade_mode = greeks_snap.get("trade_mode", "NEUTRAL")
                    logger.info(f"[Greeks] Using historical Supabase greeks for outside market hours: iv_rank={iv_rank}, gamma={gamma}")
        except Exception as e:
            logger.warning(f"[Greeks] Failed to query Supabase greeks in outside market hours block: {e}")

        state['greeks_decision'] = {
            'action': 'APPROVE',
            'reason': 'Crypto or outside market hours — Greeks skipped',
            'trigger': 'SKIPPED',
            'size_scalar': 1.0,
            'position_value': 2500.0,
            'trade_mode': trade_mode,
            'iv_rank': iv_rank,
            'gamma': gamma,
            'delta': 0.0,
            'rvol': 1.0,
            'alerts': []
        }
        return state

    # Get cached Greeks
    greeks = get_cached_greeks(symbol)

    if greeks is None:
        logger.info(f"[Greeks] No cached data for {symbol} in memory, trying Supabase greeks_snapshots...")
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if supabase_url and service_role_key:
                headers = {
                    "apikey": service_role_key,
                    "Authorization": f"Bearer {service_role_key}",
                }
                url = f"{supabase_url}/rest/v1/greeks_snapshots"
                params = {
                    "symbol": f"eq.{symbol}",
                    "order": "snapshot_at.desc",
                    "limit": "1"
                }
                resp = requests.get(url, headers=headers, params=params, timeout=5.0)
                if resp.status_code == 200 and resp.json():
                    greeks = resp.json()[0]
                    logger.info(f"[Greeks] Successfully retrieved latest Greeks from Supabase for {symbol}")
        except Exception as e:
            logger.warning(f"[Greeks] Failed to query Supabase greeks_snapshots: {e}")

    if greeks is None:
        logger.warning(f"[Greeks] No cached data for {symbol} — using safe defaults")
        state['greeks_decision'] = {
            'action': 'APPROVE',
            'reason': 'No Greeks data — market may be closed or worker not running',
            'trigger': 'NO_DATA',
            'size_scalar': 0.75,
            'position_value': 1875.0,
            'trade_mode': 'NEUTRAL',
            'iv_rank': 50.0,
            'gamma': 0.0,
            'delta': 0.0,
            'rvol': 1.0,
            'alerts': []
        }
        return state

    # Run full circuit breaker
    engine = GreeksRiskEngine()
    kelly = state.get('kelly_sizing', {})
    risk_decision = engine.evaluate(signal, greeks, kelly_sizing=kelly)

    # Send Telegram alert if needed
    if engine.should_alert_telegram(risk_decision):
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        msg = engine.format_telegram_alert(risk_decision, symbol)
        try:
            requests.post(
                f'https://api.telegram.org/bot{token}/sendMessage',
                json={'chat_id': '8641189809', 'text': msg},
                timeout=5
            )
        except Exception as e:
            logger.warning(f"[Greeks] Telegram alert failed: {e}")

    # If BLOCK — override risk_decision downstream
    if risk_decision['action'] == 'BLOCK':
        state['risk_decision'] = {
            'decision': 'BLOCK',
            'reason': risk_decision['reason'],
            'greeks_trigger': risk_decision['trigger'],
            'exposure_pct': 0.0,
            'buying_power': 0.0,
            'recommended_size_pct': 0.0,
            'asset_class': asset_class
        }

    state['greeks_decision'] = risk_decision
    return state


def greeks_intercept(state: AgentState) -> AgentState:
    """Full Greeks circuit-breaker intercept node — wired into the LangGraph pipeline."""
    try:
        logger.info(f"[Orchestrator] greeks_intercept executing for {state['asset_class']}...")
        return asyncio.run(_greeks_intercept_async(dict(state)))
    except Exception as e:
        logger.error(f"[Greeks] Failed: {e}")
        state['greeks_decision'] = {
            'action': 'APPROVE',
            'reason': 'Greeks logic failed, defaulted to approve',
            'trigger': 'ERROR',
            'size_scalar': 1.0,
            'position_value': 2500.0,
            'trade_mode': 'NEUTRAL',
            'iv_rank': 50.0,
            'gamma': 0.0,
            'delta': 0.0,
            'rvol': 1.0,
            'alerts': []
        }
        return state


def kelly_sizing_node(state: AgentState) -> AgentState:
    """Node computing data-driven Kelly Criterion portfolio allocations."""
    try:
        logger.info(f"[Orchestrator] kelly_sizing_node executing for {state['asset_class']}...")
        signal = state.get("signal_recommendation", {})
        greeks = state.get("greeks_decision", {})
        regime = state.get("regime_summary", {}).get("overall_regime", "QUIET")
        asset = state.get("asset_class", "equities")
        symbol = signal.get("symbol", "ETH/USD" if asset == "crypto" else "SPY")
        
        sizer = KellySizer()
        kelly_result = asyncio.run(sizer.calculate_position_size(
            symbol=symbol,
            asset_class=asset,
            regime=regime,
            greeks_scalar=greeks.get("size_scalar", 1.0)
        ))
        
        gex_data = state.get('gex_data') or {}
        if asset == 'equities' and gex_data.get('available') and gex_data.get('size_modifier') is not None:
            orig_val = kelly_result.get('position_value', 2500.0)
            scaled_val = orig_val * gex_data['size_modifier']
            scaled_val = min(scaled_val, 2500.0)
            kelly_result['position_value'] = scaled_val
            kelly_result['position_value_str'] = f"${scaled_val:.2f}"
            kelly_result['adjusted_kelly'] = kelly_result.get('adjusted_kelly', 0.0) * gex_data['size_modifier']
            logger.info(f"[Orchestrator] Scaled Kelly position size by GEX modifier {gex_data['size_modifier']}: {orig_val} -> {scaled_val}")

        if state.get('debate_result', {}).get('verdict') == 'PROCEED_CAUTIOUSLY':
            orig_val = kelly_result.get('position_value', 2500.0)
            scaled_val = orig_val * 0.5
            kelly_result['position_value'] = scaled_val
            kelly_result['position_value_str'] = f"${scaled_val:.2f}"
            kelly_result['adjusted_kelly'] = kelly_result.get('adjusted_kelly', 0.0) * 0.5
            logger.info(f"[Orchestrator] Scaled Kelly position size by 50% due to PROCEED_CAUTIOUSLY debate verdict: {orig_val} -> {scaled_val}")
        logger.info(f"[Orchestrator] {symbol} Kelly sizing resolved: {kelly_result.get('position_value_str')}")
        return {**state, "kelly_sizing": kelly_result}
    except Exception as e:
        logger.error(f"[Kelly] Failed: {e}")
        return {**state, "kelly_sizing": {"position_value": 2500, "position_value_str": "$2500", "kelly_fraction": 0.0, "win_rate": 0.5, "payout_ratio": 1.0}}


def risk_node(state: AgentState) -> AgentState:
    """Calls RiskAgent and GreeksRiskEngine to evaluate dynamic position limits."""
    try:
        logger.info(f"[Orchestrator] risk_node executing for {state['asset_class']}...")
        asset_class = state.get("asset_class", "crypto")
        greeks = state.get("greeks_decision", {})
        kelly = state.get("kelly_sizing", {})
        
        try:
            from agents.var_risk_engine import VaRRiskEngine
            var_engine = VaRRiskEngine()
            var_result = asyncio.run(var_engine.full_risk_check())

            if var_result['overall_action'] == 'STOP':
                try:
                    import os, requests
                    token = os.getenv('TELEGRAM_BOT_TOKEN')
                    if token:
                        msg = var_engine.format_telegram_alert(var_result)
                        requests.post(
                            f'https://api.telegram.org/bot{token}/sendMessage',
                            json={'chat_id': '8641189809', 'text': msg},
                            timeout=5
                        )
                except Exception as e:
                    logger.warning(f"[VaR] Telegram alert failed: {e}")

                state['risk_decision'] = {
                    'decision': 'BLOCK',
                    'reason': var_result['drawdown']['reason'],
                    'var_trigger': True,
                    'drawdown_pct': var_result['drawdown']['drawdown_pct'],
                    'exposure_pct': 0.0,
                    'recommended_size_pct': 0.0,
                    'asset_class': asset_class
                }
                state['var_result'] = var_result
                return state

            elif var_result['overall_action'] == 'PAUSE':
                state['risk_decision'] = {
                    'decision': 'HOLD',
                    'reason': var_result['drawdown']['reason'],
                    'var_trigger': True,
                    'recommended_size_pct': 0.0,
                    'asset_class': asset_class
                }
                state['var_result'] = var_result
                return state

            elif var_result['overall_action'] == 'REDUCE':
                try:
                    import os, requests
                    token = os.getenv('TELEGRAM_BOT_TOKEN')
                    if token:
                        msg = var_engine.format_telegram_alert(var_result)
                        requests.post(
                            f'https://api.telegram.org/bot{token}/sendMessage',
                            json={'chat_id': '8641189809', 'text': msg},
                            timeout=5
                        )
                except Exception as e:
                    pass
                kelly['position_value'] = kelly.get('position_value', 2500) * 0.5
                state['kelly_sizing'] = kelly

            state['var_result'] = var_result
        except Exception as e:
            logger.error(f'[VaR] Failed, continuing: {e}')
            var_result = {'overall_action': 'OK',
                          'var': {'var_pct': 0.01, 'breach': False},
                          'drawdown': {'drawdown_pct': 0.0, 'action': 'OK'},
                          'concentration': {'breach': False, 'alerts': []}}
            state['var_result'] = var_result

        # 1. Traditional exposure checks
        agent = RiskAgent(f"{asset_class}-risk", asset_class=asset_class)
        exposure_decision = asyncio.run(agent.analyze(state["signal_recommendation"]))
        
        # 2. Layer Greeks and Kelly sizing calculations
        from agents.greeks_risk_engine import GreeksRiskEngine
        engine = GreeksRiskEngine()
        final_risk_decision = engine.evaluate(
            signal=state["signal_recommendation"],
            greeks=state.get("greeks_decision", {}),
            kelly_sizing=state.get("kelly_sizing")
        )
        
        # Block final approval if traditional exposure rules flag an overexposure BLOCK
        if exposure_decision.get("decision") == "BLOCK":
            final_risk_decision["decision"] = "BLOCK"
            final_risk_decision["reason"] = exposure_decision.get("reason", "Overexposed")
            
        logger.info(f"[Orchestrator] {asset_class} risk_decision finalized: {final_risk_decision}")
        return {**state, "risk_decision": final_risk_decision}
    except Exception as e:
        logger.error(f'[RiskNode] Failed: {e}')
        return {**state, "risk_decision": {"decision": "HOLD", "reason": "Risk node crashed", "asset_class": state.get("asset_class", "crypto")}}


def research_node(state: AgentState) -> AgentState:
    """Calls ResearchAgent().analyze() and stores overnight_digest in state.
    Triggered only when risk_decision == BLOCK.
    """
    logger.info(f"[Orchestrator] research_node executing for {state['asset_class']} (triggered by BLOCK decision)...")
    asset = state.get("asset_class", "crypto")
    agent = ResearchAgent(f"{asset}-research", asset_class=asset)
    overnight_digest = asyncio.run(agent.analyze())
    logger.info(f"[Orchestrator] {asset} overnight_digest regime: {overnight_digest.get('regime')}")
    return {**state, "overnight_digest": overnight_digest}


def report_node(state: AgentState) -> AgentState:
    """Logs report node execution and updates the Supabase agent_signals row with final pipeline outputs."""
    logger.info(f"[Orchestrator] report_node executing for {state['asset_class']}...")
    asset = state.get("asset_class", "crypto")
    gd = state.get("greeks_decision", {})
    trigger = gd.get("trigger", "SKIPPED")
    if trigger in ("SKIPPED", "NO_DATA"):
        greeks_line = f"Greeks: {'Market closed' if trigger == 'SKIPPED' else 'No data'}"
    else:
        greeks_line = (
            f"Greeks: {gd.get('trade_mode', 'NEUTRAL')} "
            f"| IV Rank: {gd.get('iv_rank', 0.0):.0f} "
            f"| Gamma: {gd.get('gamma', 0.0):.4f}"
        )
    logger.info(f"[Orchestrator] {asset} pipeline cycle completed. {greeks_line}")

    # HITL approval gate (GATE 3)
    try:
        sig = state.get("signal_recommendation", {})
        signal_id = sig.get("id")
        if (sig.get('action') == 'BUY'
                and state.get('execution_approved', False)
                and os.getenv('HITL_ENABLED', 'false').lower() == 'true'):
            # Enrich signal with pipeline context for the queue
            hitl_signal = dict(sig)
            debate_res = state.get('debate_result', {})
            kelly_sz = state.get('kelly_sizing', {})
            regime_sum = state.get('regime_summary', {})
            hitl_signal['debate_verdict'] = debate_res.get('verdict')
            hitl_signal['debate_bull_score'] = debate_res.get('bull_score')
            hitl_signal['debate_bear_score'] = debate_res.get('bear_score')
            hitl_signal['regime'] = regime_sum.get('overall_regime')
            hitl_signal['kelly_position_value'] = kelly_sz.get('position_value', 0)
            hitl_signal['asset_class'] = state.get('asset_class', 'equities')
            submit_for_approval(hitl_signal)
            logger.info(f"[HITL] Signal for {sig.get('symbol')} submitted for human approval — execution held")
    except Exception as e:
        logger.warning(f"[HITL] Submit error in report_node: {e}")

    # Update cloud Supabase agent_signals table with the rich cycle metrics
    try:
        sig = state.get("signal_recommendation", {})
        signal_id = sig.get("id")
        if signal_id:
            supabase_url = os.getenv("SUPABASE_URL")
            service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if supabase_url and service_role_key:
                url = f"{supabase_url}/rest/v1/agent_signals?id=eq.{signal_id}"
                headers = {
                    "apikey": service_role_key,
                    "Authorization": f"Bearer {service_role_key}",
                    "Content-Type": "application/json",
                }
                
                # Fetch components
                regime_sum = state.get("regime_summary", {})
                debate_res = state.get("debate_result", {})
                kelly_sz = state.get("kelly_sizing", {})
                risk_dec = state.get("risk_decision", {})
                
                update_payload = {
                    "signal_type": sig.get("technical_signal"),
                    "sentiment_score": float(sig.get("sentiment_score") or 0.0) if sig.get("sentiment_score") is not None else None,
                    "sentiment_trend": sig.get("sentiment_trend"),
                    "timesfm_forecast": sig.get("timesfm_forecast"),
                    "timesfm_pct": float(sig.get("timesfm_pct") or 0.0) if sig.get("timesfm_pct") is not None else None,
                    "trade_mode": gd.get("trade_mode"),
                    "iv_rank": float(gd.get("iv_rank") or 0.0) if gd.get("iv_rank") is not None else None,
                    "gamma": float(gd.get("gamma") or 0.0) if gd.get("gamma") is not None else None,
                    "sentiment_velocity": float(sig.get("sentiment_velocity") or 0.0) if sig.get("sentiment_velocity") is not None else None,
                    "debate_bull_score": float(debate_res.get("bull_score") or 0.0) if debate_res.get("bull_score") is not None else None,
                    "debate_bear_score": float(debate_res.get("bear_score") or 0.0) if debate_res.get("bear_score") is not None else None,
                    "debate_verdict": debate_res.get("verdict"),
                    "kelly_position_value": float(kelly_sz.get("position_value") or 0.0) if kelly_sz.get("position_value") is not None else None,
                    "regime": regime_sum.get("overall_regime"),
                    "execution_approved": bool(state.get("execution_approved", True)),
                    "macro_approved": not (state.get("execution_reason", "") and "Macro" in state.get("execution_reason", "")),
                    # Since we modified action/confidence in the debate node, update them too!
                    "action": sig.get("action"),
                    "confidence": sig.get("confidence"),
                    "reasoning": sig.get("reasoning"),
                }
                
                import requests
                resp = requests.patch(url, headers=headers, json=update_payload, timeout=5)
                if resp.status_code in (200, 204):
                    logger.info(f"[SUPABASE] Successfully updated agent_signal ID {signal_id} with full pipeline metrics.")
                else:
                    logger.warning(f"[SUPABASE] Failed to update agent_signal ID {signal_id} ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.warning(f"[SUPABASE] Error updating agent_signal table in report_node: {e}")

    return state


# ── Conditional routing ───────────────────────────────────────────────────────

def _route_after_risk(state: AgentState) -> str:
    """Route to research_node if BLOCK, otherwise directly to report_node."""
    decision = state.get("risk_decision", {}).get("decision", "")
    if decision == "BLOCK":
        logger.info("[Orchestrator] Risk decision is BLOCK → routing to research_node.")
        return "research_node"
    logger.info(f"[Orchestrator] Risk decision is {decision} → routing to report_node.")
    return "report_node"


# ── Build and compile the graph ───────────────────────────────────────────────

def _build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("regime_detection_node", regime_detection_node)
    graph.add_node("execution_filter_node", execution_filter_node)
    graph.add_node("market_analysis_node", market_analysis_node)
    graph.add_node("signal_node", signal_node)
    graph.add_node("debate_node", debate_node)
    graph.add_node("greeks_intercept", greeks_intercept)
    graph.add_node("kelly_sizing", kelly_sizing_node)
    graph.add_node("risk_node", risk_node)
    graph.add_node("research_node", research_node)
    graph.add_node("report_node", report_node)

    # Static edges
    graph.add_edge(START, "regime_detection_node")
    graph.add_edge("regime_detection_node", "execution_filter_node")
    graph.add_edge("execution_filter_node", "market_analysis_node")
    graph.add_edge("market_analysis_node", "signal_node")
    graph.add_edge("signal_node", "debate_node")
    graph.add_edge("debate_node", "greeks_intercept")
    graph.add_edge("greeks_intercept", "kelly_sizing")
    graph.add_edge("kelly_sizing", "risk_node")

    # Conditional edge: BLOCK → research_node → report_node; else → report_node
    graph.add_conditional_edges(
        "risk_node",
        _route_after_risk,
        {
            "research_node": "research_node",
            "report_node": "report_node",
        },
    )

    graph.add_edge("research_node", "report_node")
    graph.add_edge("report_node", END)

    return graph


_crypto_compiled_graph = _build_graph().compile()
_equities_compiled_graph = _build_graph().compile()


# ── Public API ────────────────────────────────────────────────────────────────

async def run_crypto_cycle() -> dict:
    """Run crypto agent pipeline and return cycle result dict."""
    # GATE 2 — Stale price data halt (crypto uses ETH/USD)
    if not validate_market_freshness('ETH/USD', 'crypto'):
        logger.warning("Crypto cycle HALTED — stale price data")
        return {"halted": True, "reason": "stale_data", "asset_class": "crypto"}

    # GATE 3 — Soft daily stop check (crypto always active, but BUY still blocked)
    _check_daily_stop()

    # ── Kronos parallel forecast (non-blocking — best-effort) ────────────────
    kronos_crypto = {}
    try:
        kronos_crypto = await asyncio.to_thread(_kronos_compare, 'ETH/USD')
    except Exception as _ke:
        logger.warning(f'[KRONOS] Crypto compare failed (non-fatal): {_ke}')

    initial_state: AgentState = {
        "asset_class": "crypto",
        "regime_summary": {},
        "market_context": {},
        "signal_recommendation": {},
        "debate_result": {},
        "greeks_decision": {},
        "kelly_sizing": {},
        "risk_decision": {},
        "overnight_digest": {},
        "cycle_timestamp": datetime.now(timezone.utc).isoformat(),
        "kronos_comparison": kronos_crypto,
    }
    logger.info(f"[Orchestrator] Starting crypto cycle at {initial_state['cycle_timestamp']}")
    result = await asyncio.to_thread(_crypto_compiled_graph.invoke, initial_state)
    result['kronos_comparison'] = kronos_crypto
    logger.info("[Orchestrator] Crypto cycle complete.")
    return result


async def run_equities_cycle() -> dict:
    """Run equities agent pipeline and return cycle result dict."""
    # GATE 2 — Stale price data halt
    if not validate_market_freshness('SPY', 'equities'):
        logger.warning("Equities cycle HALTED — stale price data")
        return {"halted": True, "reason": "stale_data", "asset_class": "equities"}

    # GATE 3 — Time-of-day session filter
    from agents.session_filter import get_session_context
    session = get_session_context()
    logger.info(f"[SESSION] {session['session']} — {session['reason']}")
    if not session['equities_active']:
        logger.info("[SESSION] Equities not active this session — skipping cycle")
        return {
            "halted": True,
            "reason": "session_inactive",
            "asset_class": "equities",
            "session": session['session'],
            "session_reason": session['reason'],
        }

    # GATE 4 — Soft daily stop check
    _check_daily_stop()

    gex_data = compute_gex()
    ma_data = get_spy_200day_ma()

    # ── Kronos parallel forecast (non-blocking — best-effort) ────────────────
    kronos_eq = {}
    try:
        kronos_eq = await asyncio.to_thread(_kronos_compare, 'SPY')
    except Exception as _ke:
        logger.warning(f'[KRONOS] Equities compare failed (non-fatal): {_ke}')

    initial_state: AgentState = {
        "asset_class": "equities",
        "regime_summary": {},
        "market_context": {},
        "signal_recommendation": {},
        "debate_result": {},
        "greeks_decision": {},
        "kelly_sizing": {},
        "risk_decision": {},
        "overnight_digest": {},
        "cycle_timestamp": datetime.now(timezone.utc).isoformat(),
        "gex_data": gex_data,
        "ma_data": ma_data,
        "_session_context": session,
        "kronos_comparison": kronos_eq,
    }
    logger.info(f"[Orchestrator] Starting equities cycle at {initial_state['cycle_timestamp']}")
    result = await asyncio.to_thread(_equities_compiled_graph.invoke, initial_state)
    result['kronos_comparison'] = kronos_eq
    logger.info("[Orchestrator] Equities cycle complete.")
    # Propagate session context so run_cycle can include it in the report
    result['_session_context'] = session
    return result


async def run_cycle() -> dict:
    """Invoke both crypto and equities pipelines in parallel, then send a combined report."""
    logger.info("[Orchestrator] Starting dual-pipeline cycle...")
    
    crypto_result, equities_result = await asyncio.gather(
        run_crypto_cycle(),
        run_equities_cycle()
    )
    
    c_rs = crypto_result.get("regime_summary", {})
    c_mc = crypto_result.get("market_context", {})
    c_sr = crypto_result.get("signal_recommendation", {})
    c_ks = crypto_result.get("kelly_sizing", {})
    c_rd = crypto_result.get("risk_decision", {})
    c_gd = crypto_result.get("greeks_decision", {})
    c_db = crypto_result.get("debate_result", {})

    e_rs = equities_result.get("regime_summary", {})
    e_mc = equities_result.get("market_context", {})
    e_sr = equities_result.get("signal_recommendation", {})
    e_ks = equities_result.get("kelly_sizing", {})
    e_rd = equities_result.get("risk_decision", {})
    e_gd = equities_result.get("greeks_decision", {})
    e_db = equities_result.get("debate_result", {})

    c_frac = c_ks.get("adjusted_kelly", c_ks.get("kelly_fraction", 0.0))
    c_wr = c_ks.get("win_rate", 0.50)
    c_pay = c_ks.get("payout_ratio", 1.5)

    e_frac = e_ks.get("adjusted_kelly", e_ks.get("kelly_fraction", 0.0))
    e_wr = e_ks.get("win_rate", 0.50)
    e_pay = e_ks.get("payout_ratio", 1.5)

    c_var = crypto_result.get('var_result', {})
    c_var_pct = c_var.get('var', {}).get('var_pct', 0.0)
    c_dd_pct = c_var.get('drawdown', {}).get('drawdown_pct', 0.0)

    e_var = equities_result.get('var_result', {})
    e_var_pct = e_var.get('var', {}).get('var_pct', 0.0)
    e_dd_pct = e_var.get('drawdown', {}).get('drawdown_pct', 0.0)

    c_art = c_mc.get('article_count', 0)
    e_art = e_mc.get('article_count', 0)

    # Greeks lines
    def _greeks_line(gd: dict) -> str:
        trigger = gd.get("trigger", "SKIPPED")
        if trigger == "SKIPPED":
            return "⚡ Greeks: Market closed"
        if trigger == "NO_DATA":
            return "⚡ Greeks: No data"
        return (
            f"⚡ Greeks: {gd.get('trade_mode', 'NEUTRAL')} "
            f"| IV Rank: {gd.get('iv_rank', 0.0):.0f} "
            f"| Gamma: {gd.get('gamma', 0.0):.4f}"
        )

    # Sentiment line (status-aware, None-safe). When status != OK the avg is None,
    # so the STATUS leads the line — a missing/failed read can never render as a
    # phantom 0.0000.
    def _sentiment_line(mc: dict, sr: dict, art: int) -> str:
        from agents import sentiment_status as ss
        status = mc.get("sentiment_status", ss.OK)
        avg = mc.get("avg_sentiment")
        trend = sr.get("sentiment_trend", "STABLE")
        if status == ss.OK and avg is not None:
            return f"📰 Sentiment: {avg:.4f} ({art} articles) | Velocity: {trend}"
        # Not OK: avg is None. Render the status, never a number.
        if status == ss.STALE:
            detail = f"last article >{ss.STALENESS_MIN}m old"
        elif status == ss.ERROR:
            detail = "sentiment fetch failed"
        else:  # NO_DATA (and any unexpected non-OK status)
            detail = f"{art} scored articles"
        return f"📰 Sentiment: {status} ({detail})"

    # Debate lines
    def _debate_line(db: dict) -> str:
        if not db or db.get("verdict") in (None, "NEUTRAL"):
            return "⚖️ Debate: n/a"
        reasoning = db.get("reasoning", "")
        reasoning_display = reasoning[:300] + ("..." if len(reasoning) > 300 else "")
        return (
            f"⚖️ Debate: Bull {db.get('bull_score', 0.0):.0f} vs Bear {db.get('bear_score', 0.0):.0f}\n"
            f"Verdict: {db.get('verdict', 'N/A')} ({db.get('confidence_score', 0.0):.0f}%)\n"
            f"{reasoning_display}"
        )

    c_sym = c_ks.get("symbol", "ETH/USD")
    c_sym_regime_dict = c_rs.get('symbol_regimes', {}).get(c_sym, {})
    c_symbol_regime = c_sym_regime_dict.get('regime', c_rs.get('overall_regime', 'QUIET'))
    c_symbol_regime_prob = c_sym_regime_dict.get('regime_probability', 1.0)

    e_sym = e_ks.get("symbol", "SPY")
    e_sym_regime_dict = e_rs.get('symbol_regimes', {}).get(e_sym, {})
    e_symbol_regime = e_sym_regime_dict.get('regime', e_rs.get('overall_regime', 'QUIET'))
    e_symbol_regime_prob = e_sym_regime_dict.get('regime_probability', 1.0)

    gex_data = equities_result.get("gex_data") or {}
    ma_data = equities_result.get("ma_data") or {}
    pead_data = equities_result.get("pead_data") or {}

    # ── Kronos forecast lines ──────────────────────────────────────────────────
    def _kronos_line(kc: dict, label: str) -> str:
        if not kc or not kc.get('kronos', {}).get('direction'):
            return f'🔮 Kronos ({label}): unavailable'
        k = kc['kronos']
        t = kc.get('timesfm', {})
        agree_icon = '✅' if kc.get('agree') else '⚠️'
        t_dir = t.get('direction', 'N/A')
        t_pct = t.get('pct_change', 0.0)
        return (
            f'🔮 Kronos ({k.get("model", "Kronos")}): '
            f'{k["direction"]} {k["pct_change"]:+.2f}% | '
            f'TimesFM: {t_dir} {t_pct:+.2f}% | '
            f'{agree_icon} {kc.get("agreement_signal", "")}'
        )

    c_kronos = crypto_result.get('kronos_comparison') or {}
    e_kronos = equities_result.get('kronos_comparison') or {}

    report_text = (
        "🤖 Disrupting Alpha — Full Cycle Report\n\n"
        "📊 CRYPTO\n"
        f"🎯 Regime: {c_symbol_regime} ({c_symbol_regime_prob:.0%})\n"
        f"{_sentiment_line(c_mc, c_sr, c_art)}\n"
        f"{_kronos_line(c_kronos, 'ETH/USD')}\n"
        f"Signal: {c_sr.get('action', 'N/A')} | {c_sr.get('confidence', 'N/A')}\n"
        f"{_debate_line(c_db)}\n"
        f"💰 Sizing (Kelly): {c_ks.get('symbol', 'BTC/USD')}: {c_ks.get('position_value_str', '$0')} ({c_frac:.1%} adj. portfolio)\n"
        f"Win Rate: {c_wr:.1%} | Payout: {c_pay:.1f}x\n"
        f"{_greeks_line(c_gd)}\n"
        f"📉 VaR: {c_var_pct:.1%} daily | DD: {c_dd_pct:.1%}\n"
        f"🕐 Execution: {'APPROVED' if crypto_result.get('execution_approved', True) else 'SKIP'} — {crypto_result.get('execution_reason', 'N/A')}\n"
        f"Risk: {c_rd.get('decision', 'N/A')}\n\n"
        "📈 EQUITIES\n"
        f"🎯 Regime: {e_symbol_regime} ({e_symbol_regime_prob:.0%})\n"
        f"📊 Market Context:\n"
        f"GEX: {gex_data.get('gex_regime', 'UNKNOWN')} (${gex_data.get('gex_value_millions', 0):.0f}M)\n"
        f"200MA: {ma_data.get('regime', 'UNKNOWN')} ({ma_data.get('pct_from_ma', 0):+.1f}%)\n"
        f"PEAD: {pead_data.get('signal', 'NEUTRAL')} {pead_data.get('description','')[:60]}\n"
        f"{_kronos_line(e_kronos, 'SPY')}\n"
        f"{_sentiment_line(e_mc, e_sr, e_art)}\n"
        f"Signal: {e_sr.get('action', 'N/A')} | {e_sr.get('confidence', 'N/A')}\n"
        f"{_debate_line(e_db)}\n"
        f"💰 Sizing (Kelly): {e_ks.get('symbol', 'SPY')}: {e_ks.get('position_value_str', '$0')} ({e_frac:.1%} adj. portfolio)\n"
        f"Win Rate: {e_wr:.1%} | Payout: {e_pay:.1f}x\n"
        f"{_greeks_line(e_gd)}\n"
        f"📉 VaR: {e_var_pct:.1%} daily | DD: {e_dd_pct:.1%}\n"
        f"🕐 Execution: {'APPROVED' if equities_result.get('execution_approved', True) else 'SKIP'} — {equities_result.get('execution_reason', 'N/A')}\n"
        f"Risk: {e_rd.get('decision', 'N/A')}\n"
        f"🕐 Session: {equities_result.get('_session_context', {}).get('session', 'N/A')} — {equities_result.get('_session_context', {}).get('reason', 'N/A')}"
    )

    await _send_telegram(report_text, chat_id="8641189809")
    logger.info("[Orchestrator] Combined Telegram report sent and cycle complete.")

    return {"crypto": crypto_result, "equities": equities_result}
