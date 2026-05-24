import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Activity, AlertTriangle, Zap, Clock, ShieldAlert } from 'lucide-react';

interface GreekData {
  symbol: string;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  iv_rank: number;
  rvol: number;
  trade_mode: string;
  snapshot_at: string;
  underlying_price: number;
}

interface HighGammaEvent {
  symbol: string;
  gamma: number;
  trade_mode: string;
  snapshot_at: string;
}

interface GreeksResponse {
  symbols: Record<string, GreekData>;
  high_gamma_events: HighGammaEvent[];
  last_updated: string;
  market_open: boolean;
}

export default function GreeksHeatmap() {
  const [data, setData] = useState<GreeksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGreeks = async () => {
    try {
      // Assuming Netlify functions are available at /.netlify/functions/get-greeks
      const res = await fetch('/.netlify/functions/get-greeks');
      if (!res.ok) throw new Error('Failed to fetch Greeks data');
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGreeks();
    const interval = setInterval(fetchGreeks, 60000); // every 60s
    return () => clearInterval(interval);
  }, []);

  const getRowStyle = (d: GreekData) => {
    if (d.gamma > 0.08) return 'bg-red-900/40 border border-red-500/50';
    if (d.gamma > 0.05) return 'bg-orange-900/30 border border-orange-500/30';
    if (d.iv_rank < 25) return 'bg-emerald-900/20';
    if (d.iv_rank > 75) return 'bg-amber-900/20';
    return 'bg-surface-1 border border-border-muted/50 hover:bg-surface-2';
  };

  const getModeBadge = (mode: string) => {
    switch (mode) {
      case 'LONG_GAMMA':
        return <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-[10px] font-bold border border-emerald-500/30">LONG GAMMA</span>;
      case 'SHORT_PREMIUM':
        return <span className="px-2 py-1 bg-orange-500/20 text-orange-400 rounded text-[10px] font-bold border border-orange-500/30">SHORT PREMIUM</span>;
      default:
        return <span className="px-2 py-1 bg-zinc-500/20 text-zinc-400 rounded text-[10px] font-bold border border-zinc-500/30">NEUTRAL</span>;
    }
  };

  const calculateScore = (d: GreekData) => {
    let score = 50; // base score
    if (d.iv_rank < 25) score += (25 - d.iv_rank);
    if (d.iv_rank > 75) score += (d.iv_rank - 75);
    if (d.rvol > 2) score += 20;
    return Math.min(100, score);
  };

  if (loading && !data) {
    return (
      <div className="p-6 h-full flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-4 text-dim">
          <Activity className="w-8 h-8 animate-spin" />
          <span>Loading Greeks Engine...</span>
        </div>
      </div>
    );
  }

  const symbolsList = data ? Object.values(data.symbols) : [];
  const topOpps = [...symbolsList].sort((a, b) => calculateScore(b) - calculateScore(a)).slice(0, 3);

  return (
    <div className="p-6 h-full overflow-y-auto custom-scrollbar flex flex-col gap-6">
      {/* HEADER */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Zap className="w-6 h-6 text-yellow-500" />
          <h1 className="text-xl font-bold text-vibrant">Greeks Heatmap</h1>
        </div>
        <div className="flex items-center gap-4">
          {data?.market_open ? (
            <span className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg text-xs font-bold border border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              MARKET OPEN
            </span>
          ) : (
            <span className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 text-zinc-400 rounded-lg text-xs font-bold border border-zinc-700">
              <span className="w-2 h-2 rounded-full bg-zinc-500" />
              MARKET CLOSED
            </span>
          )}
          <span className="flex items-center gap-2 text-xs text-dim">
            <Clock className="w-4 h-4" />
            {data?.last_updated ? new Date(data.last_updated).toLocaleTimeString() : 'N/A'}
          </span>
        </div>
      </div>

      {!data?.market_open && (
        <div className="p-4 bg-zinc-900/50 border border-zinc-800 rounded-xl text-center text-sm text-dim">
          Market Closed — Greeks unavailable or using stale data.
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* MAIN TABLE (takes 2 columns on lg) */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-sm font-bold text-secondary uppercase tracking-wider">Symbol Matrix</h2>
          <div className="bg-surface-0 border border-border-muted rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-1 text-dim text-[10px] uppercase tracking-wider border-b border-border-muted/50">
                    <th className="p-3 font-semibold">Symbol</th>
                    <th className="p-3 font-semibold text-right">Delta</th>
                    <th className="p-3 font-semibold text-right">Gamma</th>
                    <th className="p-3 font-semibold text-right">Theta</th>
                    <th className="p-3 font-semibold text-right">Vega</th>
                    <th className="p-3 font-semibold text-right">IV Rank</th>
                    <th className="p-3 font-semibold text-right">RVOL</th>
                    <th className="p-3 font-semibold text-center">Mode</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {symbolsList.map((d) => (
                    <tr key={d.symbol} className={`transition-colors ${getRowStyle(d)} border-b border-border-muted/10 last:border-0`}>
                      <td className="p-3 font-bold text-vibrant">{d.symbol}</td>
                      <td className="p-3 text-right text-secondary">{d.delta.toFixed(3)}</td>
                      <td className={`p-3 text-right font-medium ${d.gamma > 0.05 ? 'text-red-400' : 'text-secondary'}`}>{d.gamma.toFixed(3)}</td>
                      <td className="p-3 text-right text-secondary">{d.theta.toFixed(3)}</td>
                      <td className="p-3 text-right text-secondary">{d.vega.toFixed(3)}</td>
                      <td className={`p-3 text-right font-medium ${d.iv_rank < 25 ? 'text-emerald-400' : d.iv_rank > 75 ? 'text-amber-400' : 'text-secondary'}`}>
                        {d.iv_rank.toFixed(0)}
                      </td>
                      <td className={`p-3 text-right ${d.rvol > 2.5 ? 'font-bold text-vibrant' : 'text-secondary'}`}>
                        {d.rvol.toFixed(2)}
                      </td>
                      <td className="p-3 text-center">{getModeBadge(d.trade_mode)}</td>
                    </tr>
                  ))}
                  {symbolsList.length === 0 && (
                    <tr>
                      <td colSpan={8} className="p-6 text-center text-dim">No Greeks data available.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div className="space-y-6">
          
          {/* OPPORTUNITY SCORE */}
          <div className="space-y-4">
            <h2 className="text-sm font-bold text-secondary uppercase tracking-wider">Opportunity Radar</h2>
            <div className="bg-surface-0 border border-border-muted rounded-xl p-4 space-y-4">
              {topOpps.map((d, i) => {
                const score = calculateScore(d);
                return (
                  <div key={d.symbol} className="p-3 bg-surface-1 border border-border-muted/50 rounded-lg space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-vibrant">{d.symbol}</span>
                      {getModeBadge(d.trade_mode)}
                    </div>
                    <div className="flex justify-between text-xs text-dim mb-1">
                      <span>Score: {score.toFixed(0)}</span>
                      <span>IVR: {d.iv_rank.toFixed(0)} | RVOL: {d.rvol.toFixed(1)}</span>
                    </div>
                    <div className="h-1.5 w-full bg-surface-2 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }} 
                        animate={{ width: `${score}%` }} 
                        className={`h-full ${score > 70 ? 'bg-emerald-500' : score > 50 ? 'bg-amber-500' : 'bg-blue-500'}`} 
                      />
                    </div>
                  </div>
                );
              })}
              {topOpps.length === 0 && <div className="text-sm text-dim text-center py-2">No opportunities detected.</div>}
            </div>
          </div>

          {/* CIRCUIT BREAKER ALERTS */}
          <div className="space-y-4">
            <h2 className="text-sm font-bold flex items-center gap-2 text-red-400 uppercase tracking-wider">
              <ShieldAlert className="w-4 h-4" />
              Circuit Breaker Alerts
            </h2>
            <div className="bg-surface-0 border border-red-500/20 rounded-xl p-4 space-y-3">
              {data?.high_gamma_events?.map((evt, i) => (
                <div key={i} className="flex items-center justify-between p-3 bg-red-900/20 border border-red-500/30 rounded-lg">
                  <div>
                    <div className="text-sm font-bold text-red-400">{evt.symbol}</div>
                    <div className="text-[10px] text-red-300/70">{new Date(evt.snapshot_at).toLocaleString()}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-mono text-red-300">γ = {evt.gamma.toFixed(3)}</div>
                    <div className="text-[10px] uppercase text-red-400/80 mt-0.5">{evt.trade_mode}</div>
                  </div>
                </div>
              ))}
              {(!data?.high_gamma_events || data.high_gamma_events.length === 0) && (
                <div className="text-sm text-emerald-500/70 text-center py-4 flex flex-col items-center gap-2">
                  <ShieldAlert className="w-6 h-6 text-emerald-500/30" />
                  No extreme gamma events (24h)
                </div>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
