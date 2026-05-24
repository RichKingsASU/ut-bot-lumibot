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
    market_context: dict
    signal_recommendation: dict
    risk_decision: dict
    overnight_digest: dict
    cycle_timestamp: str


# ── Node implementations ──────────────────────────────────────────────────────

def market_analysis_node(state: AgentState) -> AgentState:
    """Calls MarketAnalystAgent().analyze() and stores result in state."""
    logger.info(f"[Orchestrator] market_analysis_node executing for {state['asset_class']}...")
    asset = state.get("asset_class", "crypto")
    agent = MarketAnalystAgent(f"{asset}-analyst", asset_class=asset)
    market_context = asyncio.run(agent.analyze())
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


def risk_node(state: AgentState) -> AgentState:
    """Calls RiskAgent().analyze(signal_recommendation) and stores result in state."""
    logger.info(f"[Orchestrator] risk_node executing for {state['asset_class']}...")
    asset = state.get("asset_class", "crypto")
    agent = RiskAgent(f"{asset}-risk", asset_class=asset)
    risk_decision = asyncio.run(agent.analyze(state["signal_recommendation"]))
    logger.info(f"[Orchestrator] {asset} risk_decision: {risk_decision}")
    return {**state, "risk_decision": risk_decision}


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
    graph.add_node("market_analysis_node", market_analysis_node)
    graph.add_node("signal_node", signal_node)
    graph.add_node("risk_node", risk_node)
    graph.add_node("research_node", research_node)
    graph.add_node("report_node", report_node)

    # Static edges
    graph.add_edge(START, "market_analysis_node")
    graph.add_edge("market_analysis_node", "signal_node")
    graph.add_edge("signal_node", "risk_node")

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
        "market_context": {},
        "signal_recommendation": {},
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
        "market_context": {},
        "signal_recommendation": {},
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
    
    c_mc = crypto_result.get("market_context", {})
    c_sr = crypto_result.get("signal_recommendation", {})
    c_rd = crypto_result.get("risk_decision", {})
    
    e_mc = equities_result.get("market_context", {})
    e_sr = equities_result.get("signal_recommendation", {})
    e_rd = equities_result.get("risk_decision", {})
    
    report_text = (
        "🤖 Disrupting Alpha — Full Cycle Report\n\n"
        "📊 CRYPTO\n"
        f"Sentiment: {c_mc.get('avg_sentiment', 0.0):.4f} ({c_mc.get('sentiment_label', 'N/A')})\n"
        f"Signal: {c_sr.get('action', 'N/A')} | {c_sr.get('confidence', 'N/A')}\n"
        f"Risk: {c_rd.get('decision', 'N/A')}\n\n"
        "📈 EQUITIES\n"
        f"Sentiment: {e_mc.get('avg_sentiment', 0.0):.4f} ({e_mc.get('sentiment_label', 'N/A')})\n"
        f"Signal: {e_sr.get('action', 'N/A')} | {e_sr.get('confidence', 'N/A')}\n"
        f"Risk: {e_rd.get('decision', 'N/A')}"
    )
    
    await _send_telegram(report_text, chat_id="8641189809")
    logger.info("[Orchestrator] Combined Telegram report sent and cycle complete.")
    
    return {"crypto": crypto_result, "equities": equities_result}
