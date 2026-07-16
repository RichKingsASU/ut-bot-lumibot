-- Migration: 20260715000000_add_provenance_column
-- Description: Add data_provenance column to signal_performance and trade_performance tables

ALTER TABLE IF EXISTS signal_performance
  ADD COLUMN IF NOT EXISTS data_provenance text;

ALTER TABLE IF EXISTS trade_performance
  ADD COLUMN IF NOT EXISTS data_provenance text;
