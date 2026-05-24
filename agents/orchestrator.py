"""
Orchestrator — Disrupting Alpha v2 Phase 4
LangGraph StateGraph pipeline wiring all agents together.
Two parallel pipelines: Crypto and Equities.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
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

load_dotenv()

logger = logging.getLogger("Orchestrator")

_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8641189809")


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
    greeks_decision: dict
    kelly_sizing: dict
    risk_decision: dict
    overnight_digest: dict
    cycle_timestamp: str


# ── Node implementations ──────────────────────────────────────────────────────

def regime_detection_node(state: AgentState) -> AgentState:
    """Calls Detector().analyze() and stores result in state."""
    logger.info(f"[Orchestrator] regime_detection_node executing for {state['asset_class']}...")
    asset = state.get("asset_class", "crypto")
    detector = RegimeDetector(f"{asset}-regime-detector", asset_class=asset)
    regime_summary = asyncio.run(detector.analyze())
    logger.info(f"[Orchestrator] {asset} regime_summary received: {regime_summary.get('overall_regime')}")
    return {**state, "regime_summary": regime_summary}


def market_analysis_node(state: AgentState) -> AgentState:
    """Calls MarketAnalystAgent().analyze() and stores result in state."""
    logger.info(f"[Orchestrator] market_analysis_node executing for {state['asset_class']}...")
    asset = state.get("asset_class", "crypto")
    agent = MarketAnalystAgent(f"{asset}-analyst", asset_class=asset)
    regime_summary = state.get("regime_summary")
    market_context = asyncio.run(agent.analyze(regime_summary))
    logger.info(f"[Orchestrator] {asset} market_context received: {list(market_context.keys())}")
    return {**state, "market_context": market_context}


def signal_node(state: AgentState) -> AgentState:
    """Calls SignalAgent().analyze(market_context) and stores result in state."""
    logger.info(f"[Orchestrator] signal_node executing for {state['asset_class']}...")
    asset = state.get("asset_class", "crypto")
    agent = SignalAgent(f"{asset}-signal", asset_class=asset)
    signal_recommendation = asyncio.run(agent.analyze(state["market_context"]))
    logger.info(f"[Orchestrator] {asset} signal_recommendation: {signal_recommendation}")
    return {**state, "signal_recommendation": signal_recommendation}


def greeks_intercept(state: AgentState) -> AgentState:
    """Interceptors options Greeks risk factors and calculates scalars."""
    logger.info(f"[Orchestrator] greeks_intercept executing for {state['asset_class']}...")
    greeks_decision = {
        "size_scalar": 1.0,
        "delta": 0.0,
        "gamma": 0.0,
        "theta": 0.0,
        "vega": 0.0
    }
    return {**state, "greeks_decision": greeks_decision}


def kelly_sizing_node(state: AgentState) -> AgentState:
    """Node computing data-driven Kelly Criterion portfolio allocations."""
    logger.info(f"[Orchestrator] kelly_sizing_node executing for {state['asset_class']}...")
    signal = state.get("signal_recommendation", {})
    greeks = state.get("greeks_decision", {})
    regime = state.get("regime_summary", {}).get("overall_regime", "QUIET")
    asset = state.get("asset_class", "equities")
    symbol = signal.get("symbol", "SPY")
    
    sizer = KellySizer()
    kelly_result = asyncio.run(sizer.calculate_position_size(
        symbol=symbol,
        asset_class=asset,
        regime=regime,
        greeks_scalar=greeks.get("size_scalar", 1.0)
    ))
    logger.info(f"[Orchestrator] {symbol} Kelly sizing resolved: {kelly_result.get('position_value_str')}")
    return {**state, "kelly_sizing": kelly_result}


def risk_node(state: AgentState) -> AgentState:
    """Calls RiskAgent and GreeksRiskEngine to evaluate dynamic position limits."""
    logger.info(f"[Orchestrator] risk_node executing for {state['asset_class']}...")
    asset = state.get("asset_class", "crypto")
    
    # 1. Traditional exposure checks
    agent = RiskAgent(f"{asset}-risk", asset_class=asset)
    exposure_decision = asyncio.run(agent.analyze(state["signal_recommendation"]))
    
    # 2. Layer Greeks and Kelly sizing calculations
    engine = GreeksRiskEngine(f"{asset}-greeks-risk", asset_class=asset)
    final_risk_decision = engine.evaluate(
        signal=state["signal_recommendation"],
        greeks=state.get("greeks_decision", {}),
        kelly_sizing=state.get("kelly_sizing")
    )
    
    # Block final approval if traditional exposure rules flag an overexposure BLOCK
    if exposure_decision.get("decision") == "BLOCK":
        final_risk_decision["decision"] = "BLOCK"
        final_risk_decision["reason"] = exposure_decision.get("reason", "Overexposed")
        
    logger.info(f"[Orchestrator] {asset} risk_decision finalized: {final_risk_decision}")
    return {**state, "risk_decision": final_risk_decision}


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
    """Logs report node execution."""
    logger.info(f"[Orchestrator] report_node executing for {state['asset_class']}...")
    asset = state.get("asset_class", "crypto")
    logger.info(f"[Orchestrator] {asset} pipeline cycle completed.")
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
    graph.add_node("market_analysis_node", market_analysis_node)
    graph.add_node("signal_node", signal_node)
    graph.add_node("greeks_intercept", greeks_intercept)
    graph.add_node("kelly_sizing", kelly_sizing_node)
    graph.add_node("risk_node", risk_node)
    graph.add_node("research_node", research_node)
    graph.add_node("report_node", report_node)

    # Static edges
    graph.add_edge(START, "regime_detection_node")
    graph.add_edge("regime_detection_node", "market_analysis_node")
    graph.add_edge("market_analysis_node", "signal_node")
    graph.add_edge("signal_node", "greeks_intercept")
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
    initial_state: AgentState = {
        "asset_class": "crypto",
        "regime_summary": {},
        "market_context": {},
        "signal_recommendation": {},
        "greeks_decision": {},
        "kelly_sizing": {},
        "risk_decision": {},
        "overnight_digest": {},
        "cycle_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[Orchestrator] Starting crypto cycle at {initial_state['cycle_timestamp']}")
    result = await asyncio.to_thread(_crypto_compiled_graph.invoke, initial_state)
    logger.info("[Orchestrator] Crypto cycle complete.")
    return result


async def run_equities_cycle() -> dict:
    """Run equities agent pipeline and return cycle result dict."""
    initial_state: AgentState = {
        "asset_class": "equities",
        "regime_summary": {},
        "market_context": {},
        "signal_recommendation": {},
        "greeks_decision": {},
        "kelly_sizing": {},
        "risk_decision": {},
        "overnight_digest": {},
        "cycle_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[Orchestrator] Starting equities cycle at {initial_state['cycle_timestamp']}")
    result = await asyncio.to_thread(_equities_compiled_graph.invoke, initial_state)
    logger.info("[Orchestrator] Equities cycle complete.")
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
    
    e_rs = equities_result.get("regime_summary", {})
    e_mc = equities_result.get("market_context", {})
    e_sr = equities_result.get("signal_recommendation", {})
    e_ks = equities_result.get("kelly_sizing", {})
    e_rd = equities_result.get("risk_decision", {})
    
    c_frac = c_ks.get("kelly_fraction", 0.0)
    c_wr = c_ks.get("win_rate", 0.50)
    c_pay = c_ks.get("payout_ratio", 1.5)
    
    e_frac = e_ks.get("kelly_fraction", 0.0)
    e_wr = e_ks.get("win_rate", 0.50)
    e_pay = e_ks.get("payout_ratio", 1.5)
    
    report_text = (
        "🤖 Disrupting Alpha — Full Cycle Report\n\n"
        "📊 CRYPTO\n"
        f"🎯 Market Regime: {c_rs.get('overall_regime', 'QUIET')}\n"
        f"Strategy: {c_rs.get('strategy_recommendation', 'N/A')}\n"
        f"Sentiment: {c_mc.get('avg_sentiment', 0.0):.4f} ({c_mc.get('sentiment_label', 'N/A')})\n"
        f"Signal: {c_sr.get('action', 'N/A')} | {c_sr.get('confidence', 'N/A')}\n"
        f"💰 Sizing (Kelly): {c_ks.get('symbol', 'BTC/USD')}: {c_ks.get('position_value_str', '$0')} ({c_frac:.1%} portfolio)\n"
        f"Win Rate: {c_wr:.1%} | Payout: {c_pay:.1f}x\n"
        f"Risk: {c_rd.get('decision', 'N/A')}\n\n"
        "📈 EQUITIES\n"
        f"🎯 Market Regime: {e_rs.get('overall_regime', 'QUIET')}\n"
        f"Strategy: {e_rs.get('strategy_recommendation', 'N/A')}\n"
        f"Sentiment: {e_mc.get('avg_sentiment', 0.0):.4f} ({e_mc.get('sentiment_label', 'N/A')})\n"
        f"Signal: {e_sr.get('action', 'N/A')} | {e_sr.get('confidence', 'N/A')}\n"
        f"💰 Sizing (Kelly): {e_ks.get('symbol', 'SPY')}: {e_ks.get('position_value_str', '$0')} ({e_frac:.1%} portfolio)\n"
        f"Win Rate: {e_wr:.1%} | Payout: {e_pay:.1f}x\n"
        f"Risk: {e_rd.get('decision', 'N/A')}"
    )
    
    await _send_telegram(report_text, chat_id="8641189809")
    logger.info("[Orchestrator] Combined Telegram report sent and cycle complete.")
    
    return {"crypto": crypto_result, "equities": equities_result}
