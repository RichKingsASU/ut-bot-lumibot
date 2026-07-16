import React, { useState, useEffect, useRef } from 'react';
import { Shield, Activity, RefreshCw, AlertTriangle, TrendingUp, DollarSign, Wallet, Clipboard, Database, Globe } from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { netlifyFetch } from '../lib/apiClient';

interface AccountData {
  equity: number;
  buying_power: number;
  portfolio_value: number;
  daytrade_count: number;
}

interface PipelineData {
  heartbeat_at: string | null;
  heartbeat_age_seconds: number;
  kill_switch_active: boolean;
  is_healthy: boolean;
}

interface RegimeData {
  symbol: string;
  regime: string;
  probability: number;
  detected_at: string;
}

interface SignalData {
  symbol: string;
  action: string;
  confidence: number;
  asset_class: string;
  created_at: string;
}

interface CountsData {
  signals_total: number;
  news_24h: number;
  regime_states: number;
  snapshots: number;
}

interface HealthResponse {
  account: AccountData;
  pipeline: PipelineData;
  regimes: RegimeData[];
  signals: SignalData[];
  counts: CountsData;
  positions: any | null;
}

const MAX_AUTH_FAILURES = 3

export default function SystemHealthPage() {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [secondsAgo, setSecondsAgo] = useState(0);
  const authFailures = useRef(0);
  const stoppedRef = useRef(false);

  const fetchData = async () => {
    if (stoppedRef.current) return;
    try {
      const res = await netlifyFetch('get-system-health');
      if (res.status === 401) {
        authFailures.current += 1;
        if (authFailures.current >= MAX_AUTH_FAILURES) stoppedRef.current = true;
        setError('Unauthorized — set Admin API Key in Settings.');
        return;
      }
      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`);
      }

      const json = await res.json();
      setData(json);
      setError(null);
      setSecondsAgo(0);
      authFailures.current = 0;
    } catch (err: any) {
      console.error('Failed to fetch system health:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    stoppedRef.current = false;
    authFailures.current = 0;
    fetchData();
    const interval = setInterval(() => { if (!stoppedRef.current) fetchData(); }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const counter = setInterval(() => {
      setSecondsAgo((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(counter);
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-full text-zinc-400">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
          <span className="text-sm font-semibold uppercase tracking-wider">Loading System Health...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 h-full bg-zinc-950 text-red-400 flex items-center justify-center">
        <div className="max-w-md p-6 bg-zinc-900 border border-red-500/20 rounded-xl space-y-4 shadow-2xl">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-6 h-6 text-red-500" />
            <h3 className="text-lg font-bold text-white uppercase tracking-wider">Access Denied / Connection Error</h3>
          </div>
          <p className="text-sm text-zinc-400 leading-relaxed">{error}</p>
          <button
            onClick={() => {
              setLoading(true);
              fetchData();
            }}
            className="w-full py-2.5 bg-red-900/30 hover:bg-red-900/50 border border-red-500/40 text-red-300 font-semibold rounded-lg transition-all"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { account, pipeline, regimes, signals, counts, positions } = data;

  // Format currency
  const fmt = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

  // Day trade color logic
  const getDayTradeColor = (count: number) => {
    if (count >= 4) return 'text-red-500';
    if (count >= 3) return 'text-amber-500';
    return 'text-zinc-100';
  };

  // Regime styling
  const getRegimeClasses = (r: string) => {
    switch (r.toUpperCase()) {
      case 'BULL':
        return 'bg-green-950/40 text-green-400 border border-green-500/20';
      case 'BEAR':
        return 'bg-red-950/40 text-red-400 border border-red-500/20';
      case 'VOLATILE':
        return 'bg-amber-950/40 text-amber-400 border border-amber-500/20';
      case 'QUIET':
        return 'bg-blue-950/40 text-blue-400 border border-blue-500/20';
      default:
        return 'bg-zinc-800 text-zinc-400 border border-zinc-700';
    }
  };

  return (
    <div className="p-6 space-y-6 h-full overflow-y-auto bg-zinc-950 text-zinc-100 custom-scrollbar">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <PageHeader title="System Health" subtitle="Pre-market Operations & Intelligence Sentinel" />
        <div className="flex items-center gap-2 text-xs text-zinc-400 bg-zinc-900/60 px-3 py-1.5 rounded-lg border border-zinc-800/80">
          <Activity className="w-3.5 h-3.5 text-blue-500" />
          <span>Last refreshed: {secondsAgo}s ago</span>
          <button
            onClick={() => {
              setLoading(true);
              fetchData();
            }}
            className="ml-2 p-1 hover:bg-zinc-800 rounded transition-colors text-zinc-300"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* ROW 1: Pipeline Status Banner */}
      <div className="w-full">
        {pipeline.kill_switch_active ? (
          <div className="p-4 bg-red-950/40 border border-red-500/30 rounded-xl flex items-center justify-between shadow-[0_0_30px_rgba(239,68,68,0.1)]">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 bg-red-500 rounded-full animate-ping" />
              <div>
                <h3 className="font-bold text-red-400 uppercase tracking-widest text-sm">🛑 KILL SWITCH ACTIVE</h3>
                <p className="text-xs text-zinc-400 mt-0.5">Pre-market/live trading executions are currently halted by operator</p>
              </div>
            </div>
            <div className="text-right text-xs font-mono text-zinc-500">
              Heartbeat: {pipeline.heartbeat_at ? new Date(pipeline.heartbeat_at).toLocaleTimeString() : 'N/A'} ({pipeline.heartbeat_age_seconds}s age)
            </div>
          </div>
        ) : !pipeline.is_healthy ? (
          <div className="p-4 bg-red-950/40 border border-red-500/30 rounded-xl flex items-center justify-between shadow-[0_0_30px_rgba(239,68,68,0.1)]">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
              <div>
                <h3 className="font-bold text-red-400 uppercase tracking-widest text-sm">⚠ PIPELINE STALE</h3>
                <p className="text-xs text-zinc-400 mt-0.5">Heartbeat age exceeds 120 seconds. Sentinel loop might be offline.</p>
              </div>
            </div>
            <div className="text-right text-xs font-mono text-red-300">
              Age: {pipeline.heartbeat_age_seconds}s
            </div>
          </div>
        ) : (
          <div className="p-4 bg-emerald-950/40 border border-emerald-500/30 rounded-xl flex items-center justify-between shadow-[0_0_30px_rgba(16,185,129,0.1)]">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <div>
                <h3 className="font-bold text-emerald-400 uppercase tracking-widest text-sm">✓ PIPELINE ALIVE & HEALTHY</h3>
                <p className="text-xs text-zinc-400 mt-0.5">V2 sentinel stack actively pulsing heartbeat to Supabase</p>
              </div>
            </div>
            <div className="text-right text-xs font-mono text-emerald-300">
              Heartbeat: {pipeline.heartbeat_at ? new Date(pipeline.heartbeat_at).toLocaleTimeString() : 'N/A'} ({pipeline.heartbeat_age_seconds}s age)
            </div>
          </div>
        )}
      </div>

      {/* ROW 2: Account KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Card 1: Total Equity */}
        <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg flex items-center gap-4 hover:border-zinc-700 transition-colors">
          <div className="p-3 bg-blue-500/10 text-blue-400 rounded-lg">
            <DollarSign className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-semibold text-zinc-400 tracking-wider">Total Equity</p>
            <h4 className={`text-xl font-bold mt-1 ${account.equity >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {fmt(account.equity)}
            </h4>
          </div>
        </div>

        {/* Card 2: Buying Power */}
        <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg flex items-center gap-4 hover:border-zinc-700 transition-colors">
          <div className="p-3 bg-indigo-500/10 text-indigo-400 rounded-lg">
            <Wallet className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-semibold text-zinc-400 tracking-wider">Buying Power</p>
            <h4 className="text-xl font-bold mt-1 text-zinc-100">{fmt(account.buying_power)}</h4>
          </div>
        </div>

        {/* Card 3: Portfolio Value */}
        <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg flex items-center gap-4 hover:border-zinc-700 transition-colors">
          <div className="p-3 bg-purple-500/10 text-purple-400 rounded-lg">
            <Clipboard className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-semibold text-zinc-400 tracking-wider">Portfolio Value</p>
            <h4 className="text-xl font-bold mt-1 text-zinc-100">{fmt(account.portfolio_value)}</h4>
          </div>
        </div>

        {/* Card 4: Day Trade Count */}
        <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg flex items-center gap-4 hover:border-zinc-700 transition-colors">
          <div className="p-3 bg-amber-500/10 text-amber-400 rounded-lg">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-semibold text-zinc-400 tracking-wider">Day Trade Count</p>
            <h4 className={`text-xl font-bold mt-1 ${getDayTradeColor(account.daytrade_count)}`}>
              {account.daytrade_count} / 4
            </h4>
          </div>
        </div>
      </div>

      {/* ROW 3: Regime Grid */}
      <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg space-y-4">
        <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
          <Globe className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">HMM Regime States — All Symbols</h3>
        </div>
        {regimes.length === 0 ? (
          <p className="text-xs text-zinc-500 text-center py-4">No HMM regimes active or captured in states table.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
            {regimes.map((r, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg flex flex-col items-center justify-center text-center transition-all ${getRegimeClasses(
                  r.regime
                )}`}
              >
                <span className="text-[10px] font-bold tracking-widest text-zinc-400 uppercase">{r.symbol}</span>
                <span className="text-xs font-black mt-1 uppercase tracking-wide">{r.regime}</span>
                <span className="text-[10px] opacity-80 mt-0.5">{(r.probability * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ROW 4: Side by side columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT: Latest Agent Signals */}
        <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg flex flex-col">
          <div className="flex items-center gap-2 border-b border-zinc-800 pb-3 mb-4">
            <Activity className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Latest Agent Signals (Last 5)</h3>
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                  <th className="pb-2">Time</th>
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2">Asset Class</th>
                  <th className="pb-2">Action</th>
                  <th className="pb-2 text-right">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {signals.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-4 text-center text-zinc-500">No agent signals found</td>
                  </tr>
                ) : (
                  signals.map((sig, i) => {
                    const actionColors =
                      sig.action === 'BUY'
                        ? 'text-green-400 font-bold'
                        : sig.action === 'SELL'
                        ? 'text-red-400 font-bold'
                        : 'text-zinc-500';
                    return (
                      <tr key={i} className="hover:bg-zinc-800/20">
                        <td className="py-3 text-zinc-400 font-mono">
                          {new Date(sig.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </td>
                        <td className="py-3 text-zinc-200 font-bold">{sig.symbol}</td>
                        <td className="py-3 text-zinc-400 capitalize">{sig.asset_class}</td>
                        <td className={`py-3 ${actionColors}`}>{sig.action}</td>
                        <td className="py-3 text-right font-mono">{(sig.confidence * 100).toFixed(0)}%</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* RIGHT: Data Layer Counts */}
        <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
            <Database className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Data Layer Counts</h3>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-zinc-950/60 border border-zinc-800/80 rounded-lg text-center">
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold block">Total Signals</span>
              <span className="text-2xl font-black text-blue-400 font-mono block mt-1">{counts.signals_total}</span>
            </div>
            <div className="p-4 bg-zinc-950/60 border border-zinc-800/80 rounded-lg text-center">
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold block">News (24h)</span>
              <span className="text-2xl font-black text-purple-400 font-mono block mt-1">{counts.news_24h}</span>
            </div>
            <div className="p-4 bg-zinc-950/60 border border-zinc-800/80 rounded-lg text-center">
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold block">Regime States</span>
              <span className="text-2xl font-black text-amber-400 font-mono block mt-1">{counts.regime_states}</span>
            </div>
            <div className="p-4 bg-zinc-950/60 border border-zinc-800/80 rounded-lg text-center">
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold block">Snapshots</span>
              <span className="text-2xl font-black text-green-400 font-mono block mt-1">{counts.snapshots}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ROW 5: Latest Position Snapshot */}
      <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg space-y-4">
        <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
          <Shield className="w-4 h-4 text-zinc-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Latest Position Snapshot</h3>
        </div>
        {positions ? (
          <div className="space-y-3">
            <div className="flex justify-between items-center text-xs text-zinc-400 bg-zinc-950 p-3 rounded-lg border border-zinc-800">
              <span>Snapshot Timestamp: <span className="font-mono text-zinc-200">{new Date(positions.snapshot_at).toLocaleString()}</span></span>
              <span>Available Cash: <span className="font-bold text-green-400">{fmt(positions.cash || 0)}</span></span>
            </div>
            <div className="p-4 bg-zinc-950 rounded-lg border border-zinc-800 overflow-x-auto">
              <pre className="text-xs text-zinc-300 font-mono leading-relaxed max-h-60 overflow-y-auto">
                {JSON.stringify(positions.positions || positions, null, 2)}
              </pre>
            </div>
          </div>
        ) : (
          <p className="text-xs text-zinc-500 text-center py-4">No position data yet</p>
        )}
      </div>
    </div>
  );
}
