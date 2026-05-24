-- Migration: 20260524_007_agent_signals
-- Creates the agent_signals table for storing LangGraph agent signal outputs.

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
