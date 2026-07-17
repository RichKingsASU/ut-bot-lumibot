-- Gate 3: HITL (Human-In-The-Loop) approval queue
CREATE TABLE IF NOT EXISTS hitl_queue (
    id bigserial PRIMARY KEY,
    symbol text NOT NULL,
    asset_class text NOT NULL,
    proposed_action text NOT NULL,
    proposed_size_usd numeric(10,2) NOT NULL,
    debate_verdict text,
    bull_score numeric(5,2),
    bear_score numeric(5,2),
    regime text,
    sentiment_score numeric(6,4),
    kelly_pct numeric(6,4),
    reasoning_summary text,
    approved boolean DEFAULT false,
    approved_at timestamptz,
    rejected boolean DEFAULT false,
    rejected_at timestamptz,
    executed boolean DEFAULT false,
    executed_at timestamptz,
    created_at timestamptz DEFAULT now()
);
