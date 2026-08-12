# HANDOFF_V2_PHASE4.md — Disrupting Alpha v2 Phase 4

## What Was Built

### LangGraph Multi-Agent Infrastructure
Phase 4 delivered a complete multi-agent pipeline built on LangGraph, running inside a
`StateGraph` that wires five specialized agents into a single orchestrated cycle:

| Agent | File | Role |
|---|---|---|
| `BaseAgent` | `agents/base_agent.py` | Abstract base with Qdrant, Supabase REST, and sentiment helpers |
| `MarketAnalystAgent` | `agents/market_analyst.py` | Aggregates sentiment, signals, ticks; publishes to NATS + Qdrant |
| `SignalAgent` | `agents/signal_agent.py` | Combines sentiment + technical signals → BUY/SELL/HOLD; writes `agent_signals` table |
| `RiskAgent` | `agents/risk_agent.py` | Checks Alpaca exposure & buying power → APPROVE/REDUCE/BLOCK |
| `ResearchAgent` | `agents/research_agent.py` | Overnight digest: regime detection, top headlines, Qdrant memory |
| `Orchestrator` | `agents/orchestrator.py` | LangGraph `StateGraph` pipeline; conditional routing on BLOCK |
| **Runner** | `run_agents.py` | Entry point: Telegram startup + 15-min loop |

### Pipeline Flow
```
START
  → market_analysis_node  (MarketAnalystAgent)
  → signal_node           (SignalAgent → writes agent_signals)
  → risk_node             (RiskAgent)
  → [if BLOCK] research_node (ResearchAgent)
  → report_node           (Telegram cycle summary)
END
```

### Supabase Schema
New table added in `supabase/migrations/20260524_007_agent_signals.sql`:

```sql
CREATE TABLE IF NOT EXISTS agent_signals (
  id bigserial PRIMARY KEY,
  session_id text,
  symbol text,
  action text CHECK (action IN ('BUY','SELL','HOLD')),
  confidence text CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
  sentiment_score numeric(6,4),
  technical_signal text,
  reasoning text,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_signals_created
  ON agent_signals (created_at DESC);
```

---

## How to Start the Agents

```bash
# Activate the virtual environment
source venv/bin/activate

# Launch the orchestrator loop (15-min cycles, indefinitely)
python run_agents.py
```

The runner will:
1. Send a Telegram startup notification to chat `8641189809`
2. Run `run_cycle()` immediately (cycle #1)
3. Sleep 900 seconds, then repeat

### Environment Requirements
All variables must be present in `.env`:

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token for notifications |
| `TELEGRAM_CHAT_ID` | Default chat ID (8641189809) |
| `SUPABASE_URL` | Cloud Supabase REST endpoint |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role JWT for full access |
| `ALPACA_API_KEY` / `ALPACA_API_SECRET` | Paper trading credentials |
| `ALPACA_BASE_URL` | Paper API endpoint |
| `NATS_URL` | NATS broker (default: `nats://localhost:4222`) |

### Infrastructure Dependencies
| Service | Default Address | Purpose |
|---|---|---|
| Qdrant | `localhost:6333` | Vector memory (`crypto_news`, `agent_memory`) |
| NATS | `localhost:4222` | Real-time agent messaging |
| QuestDB | `localhost:9000` | Tick count queries |
| Supabase Cloud | `wnigkahkamoizjpmpuxs.supabase.co` | `news_articles`, `signal_log`, `agent_signals` |

---

## How to Verify

### 1. Check `agent_signals` Table
After at least one successful cycle, query the table:
```sql
SELECT action, confidence, sentiment_score, technical_signal, reasoning, created_at
FROM agent_signals
ORDER BY created_at DESC
LIMIT 10;
```
Expect one row per completed cycle where SignalAgent ran successfully.

### 2. Check Telegram Digests
- **Startup**: "🤖 Agent orchestrator started — LangGraph pipeline every 15min"
- **Cycle report**: "📊 Disrupting Alpha — Cycle Report" with market/signal/risk sections
- **Overnight digest** (BLOCK only): "🌙 Overnight Research Digest" with regime + headlines

### 3. Syntax Verification
```bash
source venv/bin/activate
python3 -m py_compile agents/base_agent.py && echo OK
python3 -m py_compile agents/market_analyst.py && echo OK
python3 -m py_compile agents/signal_agent.py && echo OK
python3 -m py_compile agents/risk_agent.py && echo OK
python3 -m py_compile agents/research_agent.py && echo OK
python3 -m py_compile agents/orchestrator.py && echo OK
python3 -m py_compile run_agents.py && echo OK
```
All 7 files: **OK** ✅

### 4. Check NATS Subjects
If NATS is running, subscribe to verify agent publishing:
```bash
nats sub "agents.>"
```
Expected subjects: `agents.market_context`, `agents.signal_recommendation`, `agents.risk_decision`

---

## Phase 5 Preview — Greek Calculations + Live Trading Readiness

### mibian Greeks Integration
- Install `mibian` library for Black-Scholes + implied volatility calculations
- Add `GreeksAgent` to compute delta, gamma, theta, vega, rho for options positions
- Feed Greeks into RiskAgent's position sizing (e.g., delta-weighted exposure)
- Store per-cycle Greeks snapshot in a new `options_greeks` Supabase table

### Live Trading Checklist
- [ ] Switch `ALPACA_BASE_URL` from `paper-api` → `api.alpaca.markets`
- [ ] Set `ALPACA_IS_PAPER=false`
- [ ] Add pre-trade circuit breakers: max daily loss, max position size
- [ ] Integrate `strategies/options_executor.py` into the pipeline via a new `ExecutorAgent`
- [ ] Add kill-switch: Telegram command → halt loop gracefully
- [ ] Add position reconciliation: compare agent decisions vs. actual Alpaca positions
- [ ] Enable Supabase Realtime on `agent_signals` for dashboard streaming
- [ ] Add Prometheus/Grafana metrics for cycle latency and signal distribution

---

*Generated: 2026-05-24 | Disrupting Alpha v2 Phase 4 Complete*
