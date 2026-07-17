-- 20260716000000_apply_rls_policies.sql
-- Enforce Row Level Security (RLS) on critical operational tables

-- 1. hitl_gate
CREATE TABLE IF NOT EXISTS hitl_gate (
    id bigserial PRIMARY KEY,
    symbol text NOT NULL,
    approved boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

ALTER TABLE hitl_gate ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access for authenticated users to hitl_gate"
ON hitl_gate FOR SELECT
TO authenticated, service_role
USING (true);

CREATE POLICY "Allow insert/update for service_role to hitl_gate"
ON hitl_gate FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- 2. kill_switch
CREATE TABLE IF NOT EXISTS kill_switch (
    id bigserial PRIMARY KEY,
    is_active boolean DEFAULT false,
    reason text,
    activated_by text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

ALTER TABLE kill_switch ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access for authenticated users to kill_switch"
ON kill_switch FOR SELECT
TO authenticated, service_role
USING (true);

CREATE POLICY "Allow insert/update for service_role to kill_switch"
ON kill_switch FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- 3. trade_log
CREATE TABLE IF NOT EXISTS trade_log (
    id bigserial PRIMARY KEY,
    symbol text NOT NULL,
    action text,
    qty integer,
    price numeric,
    trade_time timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now()
);

ALTER TABLE trade_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access for authenticated users to trade_log"
ON trade_log FOR SELECT
TO authenticated, service_role
USING (true);

CREATE POLICY "Allow insert/update for service_role to trade_log"
ON trade_log FOR ALL
TO service_role
USING (true)
WITH CHECK (true);
