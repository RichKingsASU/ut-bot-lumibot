import { useState, useEffect } from 'react';

interface UseSupabaseDataProps {
  symbol: string;
  timeframe?: string;
  limit?: number;
  mode: 'live' | 'historical';
}

export const useSupabaseData = ({ symbol, timeframe = '15m', limit = 100, mode }: UseSupabaseDataProps) => {
  const [bars, setBars] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (mode === 'live') return;

    const fetchBars = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/.netlify/functions/supabase-query?type=bars&symbol=${symbol}&timeframe=${timeframe}&limit=${limit}`);
        if (!response.ok) throw new Error('Failed to fetch historical bars');
        const data = await response.json();
        setBars(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchBars();
  }, [symbol, timeframe, limit, mode]);

  return { bars, loading, error, source: mode === 'live' ? 'WebSocket' : 'Supabase' };
};
