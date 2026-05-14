import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';

export interface TradingMetrics {
  winRate: number | null;
  totalTrades: number | null;
  totalPnl: number | null;
  maxDrawdown: number | null;
  openPositions: number | null;
  loading: boolean;
  error: string | null;
}

const INITIAL: TradingMetrics = {
  winRate: null,
  totalTrades: null,
  totalPnl: null,
  maxDrawdown: null,
  openPositions: null,
  loading: true,
  error: null,
};

export function useMetrics(): TradingMetrics {
  const [metrics, setMetrics] = useState<TradingMetrics>(INITIAL);

  useEffect(() => {
    let cancelled = false;

    async function fetchMetrics() {
      try {
        const { data, error } = await supabase
          .from('portfolio_snapshots')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(1)
          .maybeSingle();

        if (cancelled) return;
        if (error) throw error;

        const row = (data || {}) as Record<string, unknown>;
        const num = (v: unknown): number | null =>
          typeof v === 'number' && Number.isFinite(v) ? v : null;

        setMetrics({
          winRate: num(row.win_rate ?? row.winRate),
          totalTrades: num(row.total_trades ?? row.totalTrades),
          totalPnl: num(row.total_pnl ?? row.totalPnl),
          maxDrawdown: num(row.max_drawdown ?? row.maxDrawdown),
          openPositions: num(row.open_positions ?? row.openPositions),
          loading: false,
          error: null,
        });
      } catch {
        if (cancelled) return;
        setMetrics((prev) => ({ ...prev, loading: false, error: 'Metrics unavailable' }));
      }
    }

    fetchMetrics();
    return () => {
      cancelled = true;
    };
  }, []);

  return metrics;
}
