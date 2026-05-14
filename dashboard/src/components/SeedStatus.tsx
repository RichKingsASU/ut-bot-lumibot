import React, { useState, useEffect } from 'react';
import { toUserMessage } from '../lib/apiError';

interface BarInventory {
  symbol: string;
  timeframe: string;
  feed: string;
  bar_count: number;
  earliest: string;
  latest: string;
  approx_trading_days: number;
}

interface OptionsSummary {
  underlying: string;
  snap_date: string;
  contracts: number;
  calls: number;
  puts: number;
  with_greeks: number;
  dte_0: number;
  nearest_expiry: string;
  furthest_expiry: string;
  avg_iv: number;
  last_snapshot: string;
}

interface SeedJob {
  id: number;
  job_type: string;
  symbol: string;
  timeframe?: string;
  status: string;
  rows_written: number;
  started_at: string;
  error_msg?: string;
  metadata?: any;
}

interface SeedStatusData {
  bar_inventory: BarInventory[];
  options_summary: OptionsSummary[];
  active_jobs: SeedJob[];
  storage_estimate: {
    ohlcv_row_count: number;
    options_row_count: number;
    approx_mb: number;
  };
}

const SeedStatus: React.FC = () => {
  const [data, setData] = useState<SeedStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/.netlify/functions/seed-status');
      if (!res.ok) throw new Error('Failed to fetch seeding status');
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err: any) {
      setError(toUserMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const triggerBackfill = async (symbol: string, timeframe: string) => {
    const key = `${symbol}-${timeframe}`;
    if (triggering === key) return;
    setTriggering(key);
    try {
      const res = await fetch('/.netlify/functions/seed-bars-background', {
        method: 'POST',
        body: JSON.stringify({ symbol, timeframe, days: 730 })
      });
      if (!res.ok) throw new Error('Failed to trigger backfill');
      alert(`Triggered ${timeframe} backfill for ${symbol}`);
      fetchStatus();
    } catch (err: any) {
      alert(toUserMessage(err));
    } finally {
      setTriggering(null);
    }
  };

  const triggerOptionsSeed = async (underlying: string) => {
    if (triggering === underlying) return;
    setTriggering(underlying);
    try {
      const res = await fetch('/.netlify/functions/seed-options-background', {
        method: 'POST',
        body: JSON.stringify({ underlying, dte_max: 60 })
      });
      if (!res.ok) throw new Error('Failed to trigger options seed');
      alert(`Triggered options seed for ${underlying}`);
      fetchStatus();
    } catch (err: any) {
      alert(toUserMessage(err));
    } finally {
      setTriggering(null);
    }
  };

  if (loading && !data) return <div className="text-white p-8">Loading seeding status...</div>;
  if (error) return <div className="text-red-400 p-8">Error: {error}</div>;

  return (
    <div className="space-y-8 p-6 bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <span className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse" />
          Data Seeding & Collection Status
        </h2>
        <div className="text-sm text-slate-400">
          Storage: <span className="text-emerald-400">{data?.storage_estimate.approx_mb} MB</span> used 
          ({data?.storage_estimate.ohlcv_row_count.toLocaleString()} bars, {data?.storage_estimate.options_row_count.toLocaleString()} options)
        </div>
      </div>

      {/* Active Jobs */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-300">Live Seed Jobs</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.active_jobs.map(job => (
            <div key={job.id} className="bg-white/5 border border-white/10 p-4 rounded-xl space-y-2">
              <div className="flex justify-between">
                <span className="text-xs uppercase tracking-wider text-slate-500 font-bold">{job.job_type}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  job.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                  job.status === 'running' ? 'bg-blue-500/20 text-blue-400 animate-pulse' :
                  job.status === 'failed' ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-400'
                }`}>
                  {job.status}
                </span>
              </div>
              <div className="text-lg font-bold text-white">{job.symbol} {job.timeframe}</div>
              <div className="text-sm text-slate-400">{job.rows_written.toLocaleString()} rows written</div>
              {job.status === 'running' && (
                <div className="w-full bg-white/10 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-blue-500 h-full w-[60%] animate-shimmer" />
                </div>
              )}
              {job.error_msg && <div className="text-xs text-red-400 truncate">{job.error_msg}</div>}
            </div>
          ))}
          {data?.active_jobs.length === 0 && (
            <div className="col-span-full text-slate-500 italic py-4">No active or recent jobs found.</div>
          )}
        </div>
      </div>

      {/* Bar Inventory */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-300">Bar Inventory (SIP)</h3>
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-widest font-bold">
              <tr>
                <th className="px-4 py-3">Symbol</th>
                <th className="px-4 py-3">TF</th>
                <th className="px-4 py-3">Feed</th>
                <th className="px-4 py-3">Bars</th>
                <th className="px-4 py-3">Range</th>
                <th className="px-4 py-3">Last Ingest</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {data?.bar_inventory.map(bar => (
                <tr key={`${bar.symbol}-${bar.timeframe}`} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-white">{bar.symbol}</td>
                  <td className="px-4 py-3">{bar.timeframe}</td>
                  <td className="px-4 py-3"><span className="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded font-bold uppercase">{bar.feed}</span></td>
                  <td className="px-4 py-3">{bar.bar_count.toLocaleString()}</td>
                  <td className="px-4 py-3 text-xs">{bar.earliest} to {bar.latest}</td>
                  <td className="px-4 py-3 text-xs">{new Date(bar.latest).toLocaleTimeString()}</td>
                  <td className="px-4 py-3">
                    <button 
                      onClick={() => triggerBackfill(bar.symbol, bar.timeframe)}
                      disabled={!!triggering}
                      className="text-emerald-400 hover:text-emerald-300 disabled:opacity-50 text-xs font-bold uppercase"
                    >
                      {triggering === `${bar.symbol}-${bar.timeframe}` ? '...' : 'Backfill'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Options Summary */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-300">Options Chain Collection (OPRA)</h3>
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px] tracking-widest font-bold">
              <tr>
                <th className="px-4 py-3">Underlying</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Contracts</th>
                <th className="px-4 py-3">Greeks</th>
                <th className="px-4 py-3">Avg IV</th>
                <th className="px-4 py-3">Range (Exp)</th>
                <th className="px-4 py-3">Last Snap</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-300">
              {data?.options_summary.map(opt => (
                <tr key={`${opt.underlying}-${opt.snap_date}`} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-white">{opt.underlying}</td>
                  <td className="px-4 py-3">{opt.snap_date}</td>
                  <td className="px-4 py-3">{opt.contracts} <span className="text-slate-500">({opt.calls}C/{opt.puts}P)</span></td>
                  <td className="px-4 py-3">{opt.with_greeks} <span className="text-[10px] text-slate-500">+{opt.dte_0} 0DTE</span></td>
                  <td className="px-4 py-3 text-emerald-400 font-mono">{(opt.avg_iv * 100).toFixed(1)}%</td>
                  <td className="px-4 py-3 text-xs">{opt.nearest_expiry} to {opt.furthest_expiry}</td>
                  <td className="px-4 py-3 text-xs">{new Date(opt.last_snapshot).toLocaleTimeString()}</td>
                  <td className="px-4 py-3">
                    <button 
                      onClick={() => triggerOptionsSeed(opt.underlying)}
                      disabled={!!triggering}
                      className="text-emerald-400 hover:text-emerald-300 disabled:opacity-50 text-xs font-bold uppercase"
                    >
                      {triggering === opt.underlying ? '...' : 'Re-Seed'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default SeedStatus;
