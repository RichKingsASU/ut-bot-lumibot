-- Create component_heartbeat table
CREATE TABLE IF NOT EXISTS public.component_heartbeat (
    component text PRIMARY KEY,
    status text NOT NULL DEFAULT 'OK',
    last_success_at timestamp with time zone,
    last_error text,
    last_error_at timestamp with time zone,
    cycle_count integer DEFAULT 0,
    meta jsonb DEFAULT '{}'::jsonb
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.component_heartbeat ENABLE ROW LEVEL SECURITY;

-- Drop policy if exists and create a new one
DROP POLICY IF EXISTS "Allow public read access to component_heartbeat" ON public.component_heartbeat;
CREATE POLICY "Allow public read access to component_heartbeat"
ON public.component_heartbeat
FOR SELECT
TO public
USING (true);
