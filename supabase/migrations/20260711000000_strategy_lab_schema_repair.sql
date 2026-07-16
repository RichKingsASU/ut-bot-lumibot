-- 20260711000000_strategy_lab_schema_repair.sql
-- Repair strategies table schema to add missing columns and adjust status check constraint

-- 1. Add missing columns
ALTER TABLE public.strategies 
ADD COLUMN IF NOT EXISTS filename text,
ADD COLUMN IF NOT EXISTS params jsonb;

-- 2. Update status check constraint to support all frontend statuses
ALTER TABLE public.strategies DROP CONSTRAINT IF EXISTS strategies_status_check;
ALTER TABLE public.strategies ADD CONSTRAINT strategies_status_check CHECK (status IN ('active', 'inactive', 'testing', 'draft', 'deployed', 'archived'));
