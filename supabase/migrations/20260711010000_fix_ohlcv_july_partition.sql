-- Migration: Fix ohlcv_bars July 2026 partition
-- Corrected columns list to avoid "updated_at does not exist" error:
-- 1. Create a staging table to hold the stuck July 2026 rows.
-- 2. Copy the July 2026 rows from ohlcv_bars_default (fallback partition) to staging.
-- 3. Delete those rows from ohlcv_bars_default so Postgres allows creating the new partition.
-- 4. Create the new July partition ohlcv_bars_p20260701.
-- 5. Copy the rows back from staging to ohlcv_bars (which routes them to the new partition).
-- 6. Drop the staging table.

BEGIN;

-- 1. Create staging table
CREATE TEMP TABLE staging_july_bars AS 
SELECT * FROM public.ohlcv_bars_default 
WHERE ts >= '2026-07-01 00:00:00+00' 
  AND ts <  '2026-08-01 00:00:00+00';

-- 2. Delete the rows from the default partition
DELETE FROM public.ohlcv_bars_default 
WHERE ts >= '2026-07-01 00:00:00+00' 
  AND ts <  '2026-08-01 00:00:00+00';

-- 3. Create the July partition
CREATE TABLE IF NOT EXISTS public.ohlcv_bars_p20260701 
  PARTITION OF public.ohlcv_bars 
  FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');

-- 4. Insert rows back (they will now route to ohlcv_bars_p20260701)
INSERT INTO public.ohlcv_bars (symbol, timeframe, ts, open, high, low, close, volume, vwap, trade_count, feed, created_at)
SELECT symbol, timeframe, ts, open, high, low, close, volume, vwap, trade_count, feed, created_at
FROM staging_july_bars
ON CONFLICT (symbol, timeframe, ts) DO NOTHING;

-- 5. Drop the staging table
DROP TABLE staging_july_bars;

COMMIT;

-- 6. Verify result
SELECT 
  tableoid::regclass AS partition_name,
  COUNT(*) AS row_count,
  MIN(ts)  AS oldest,
  MAX(ts)  AS newest
FROM public.ohlcv_bars
WHERE ts >= '2026-07-01 00:00:00+00'
  AND ts <  '2026-08-01 00:00:00+00'
GROUP BY tableoid
ORDER BY partition_name;
