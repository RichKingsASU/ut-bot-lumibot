"""
Orchestrator — Disrupting Alpha v2 Phase 4
LangGraph StateGraph pipeline wiring all agents together.

Pipeline:
    START → market_analysis_node → signal_node → risk_node
                                                     ↓
                              (BLOCK) → research_node → report_node → END
                              (else)  → report_node → END
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
    market_context: dict
    signal_recommendation: dict
    risk_decision: dict
    overnight_digest: dict
    cycle_timestamp: str


# ── Node implementations ──────────────────────────────────────────────────────

def market_analysis_node(state: AgentState) -> AgentState:
    """Calls MarketAnalystAgent().analyze() and stores result in state."""
    logger.info("[Orchestrator] market_analysis_node executing...")
    market_context = asyncio.run(
        MarketAnalystAgent().analyze()
    )
    logger.info(f"[Orchestrator] market_context received: {list(market_context.keys())}")
    return {**state, "market_context": market_context}


def signal_node(state: AgentState) -> AgentState:
    """Calls SignalAgent().analyze(market_context) and stores result in state."""
    logger.info("[Orchestrator] signal_node executing...")
    signal_recommendation = asyncio.run(
        SignalAgent().analyze(state["market_context"])
    )
    logger.info(f"[Orchestrator] signal_recommendation: {signal_recommendation}")
    return {**state, "signal_recommendation": signal_recommendation}


def risk_node(state: AgentState) -> AgentState:
    """Calls RiskAgent().analyze(signal_recommendation) and stores result in state."""
    logger.info("[Orchestrator] risk_node executing...")
    risk_decision = asyncio.run(
        RiskAgent().analyze(state["signal_recommendation"])
    )
    logger.info(f"[Orchestrator] risk_decision: {risk_decision}")
    return {**state, "risk_decision": risk_decision}


def research_node(state: AgentState) -> AgentState:
    """Calls ResearchAgent().analyze() and stores overnight_digest in state.
    Triggered only when risk_decision == BLOCK.
    """
    logger.info("[Orchestrator] research_node executing (triggered by BLOCK decision)...")
    overnight_digest = asyncio.run(
        ResearchAgent().analyze()
    )
    logger.info(f"[Orchestrator] overnight_digest regime: {overnight_digest.get('regime')}")
    return {**state, "overnight_digest": overnight_digest}


def report_node(state: AgentState) -> AgentState:
    """Sends a full-cycle Telegram summary and returns final state."""
    logger.info("[Orchestrator] report_node executing...")

    mc = state.get("market_context", {})
    sr = state.get("signal_recommendation", {})
    rd = state.get("risk_decision", {})
    od = state.get("overnight_digest", {})
    ts = state.get("cycle_timestamp", datetime.now(timezone.utc).isoformat())

    # Build summary message
    digest_line = ""
    if od:
        digest_line = (
            f"\n\n🌙 <b>Overnight Digest</b>\n"
            f"  Regime: {od.get('regime', 'N/A')} | "
            f"Avg Sentiment: {od.get('avg_sentiment_24h', 'N/A')}"
        )

    message = (
        f"📊 <b>Disrupting Alpha — Cycle Report</b>\n"
        f"🕐 {ts}\n\n"
        f"🏦 <b>Market Context</b>\n"
        f"  Sentiment: {mc.get('avg_sentiment', 'N/A'):.4f} ({mc.get('sentiment_label', 'N/A')})\n"
        f"  Tick Count: {mc.get('tick_count', 'N/A')}\n\n"
        f"🎯 <b>Signal Recommendation</b>\n"
        f"  Action: {sr.get('action', 'N/A')} | "
        f"Confidence: {sr.get('confidence', 'N/A')}\n"
        f"  Reasoning: {sr.get('reasoning', 'N/A')}\n\n"
        f"🛡️ <b>Risk Decision</b>\n"
        f"  Decision: {rd.get('decision', 'N/A')} | "
        f"Exposure: {rd.get('exposure_pct', 0.0):.2%}\n"
        f"  Reason: {rd.get('reason', 'N/A')}"
        f"{digest_line}"
    )

    asyncio.run(
        _send_telegram(message, chat_id="8641189809")
    )

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


_compiled_graph = _build_graph().compile()


# ── Public API ────────────────────────────────────────────────────────────────

async def run_cycle() -> AgentState:
    """Invoke the full agent pipeline and return the final AgentState."""
    initial_state: AgentState = {
        "market_context": {},
        "signal_recommendation": {},
        "risk_decision": {},
        "overnight_digest": {},
        "cycle_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[Orchestrator] Starting cycle at {initial_state['cycle_timestamp']}")
    result = await asyncio.to_thread(_compiled_graph.invoke, initial_state)
    logger.info("[Orchestrator] Cycle complete.")
    return result
