import React, { useState, useEffect } from 'react';
import { toUserMessage } from '../lib/apiError';

interface InventoryItem {
  symbol: string;
  timeframe: string;
  feed: string;
  bar_count: number;
  earliest_date: string;
  latest_date: string;
  approx_trading_days: number;
  last_ingested: string;
}

interface OptionsInventoryItem {
  underlying: string;
  feed: string;
  snapshot_days: number;
  total_rows: number;
  earliest_date: string;
  latest_date: string;
}

export const DataInventory: React.FC = () => {
  const [data, setData] = useState<{ bars: InventoryItem[], options: OptionsInventoryItem[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [btStatus, setBtStatus] = useState<any>(null);

  const fetchInventory = async () => {
    try {
      const res = await fetch('/.netlify/functions/supabase-query?type=inventory');
      if (!res.ok) throw new Error('Failed to fetch inventory');
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(toUserMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory();
    const interval = setInterval(fetchInventory, 60000);
    return () => clearInterval(interval);
  }, []);

  const runBacktest = async () => {
    setBtStatus('Running...');
    try {
      const res = await fetch('/.netlify/functions/run-backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: 'IWM',
          timeframe: '15m',
          date_start: '2024-01-01',
          date_end: '2024-12-31'
        })
      });
      const result = await res.json();
      setBtStatus(`Done! Return: ${result.total_return_pct.toFixed(2)}%`);
    } catch (err) {
      setBtStatus('Error triggered backtest');
    }
  };

  if (loading) return <div className="p-4 text-slate-400 italic">Loading inventory...</div>;
  if (error) return <div className="p-4 text-red-400">Error: {error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-100 uppercase tracking-wider">Database Data Inventory</h3>
        <button 
          onClick={runBacktest}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-xs font-bold rounded transition-colors"
        >
          {btStatus || 'Run IWM Backtest'}
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-800/50 text-slate-400 uppercase">
            <tr>
              <th className="px-3 py-2">Symbol</th>
              <th className="px-3 py-2">TF</th>
              <th className="px-3 py-2">Feed</th>
              <th className="px-3 py-2 text-right">Bars</th>
              <th className="px-3 py-2">From</th>
              <th className="px-3 py-2">To</th>
              <th className="px-3 py-2 text-right">Days</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {data?.bars.map((item, i) => (
              <tr key={i} className="hover:bg-slate-800/30">
                <td className="px-3 py-2 font-mono font-bold text-blue-400">{item.symbol}</td>
                <td className="px-3 py-2">{item.timeframe}</td>
                <td className="px-3 py-2 opacity-60">{item.feed}</td>
                <td className="px-3 py-2 text-right font-mono">{item.bar_count.toLocaleString()}</td>
                <td className="px-3 py-2 opacity-60">{item.earliest_date}</td>
                <td className="px-3 py-2 opacity-60">{item.latest_date}</td>
                <td className="px-3 py-2 text-right">{item.approx_trading_days}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="space-y-3">
        <h4 className="text-sm font-bold text-slate-400 uppercase tracking-tighter">Options Chain Snapshots</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-400">
            <thead className="bg-slate-800/30">
              <tr>
                <th className="px-3 py-1">Underlying</th>
                <th className="px-3 py-1">Feed</th>
                <th className="px-3 py-1 text-right">Snap Days</th>
                <th className="px-3 py-1 text-right">Total Rows</th>
                <th className="px-3 py-1">Range</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {data?.options.map((item, i) => (
                <tr key={i}>
                  <td className="px-3 py-2 font-bold text-orange-400">{item.underlying}</td>
                  <td className="px-3 py-2">{item.feed}</td>
                  <td className="px-3 py-2 text-right">{item.snapshot_days}</td>
                  <td className="px-3 py-2 text-right font-mono">{item.total_rows.toLocaleString()}</td>
                  <td className="px-3 py-2 text-[10px] opacity-60">{item.earliest_date} → {item.latest_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
