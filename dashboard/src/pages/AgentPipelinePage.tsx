import React, { useState, useEffect } from 'react';
import { Cpu, RefreshCw, AlertCircle, Sparkles, TrendingUp, Info } from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';

interface LastCycleInfo {
  ran_at: string | null;
  cycle_age_seconds: number;
  asset_class_last: string;
}

interface SignalItem {
  symbol: string;
  action: string;
  confidence: number;
  reasoning: string;
  created_at: string;
}

interface RegimeSummaryItem {
  symbol: string;
  regime: string;
  regime_probability: number;
  detected_at: string;
}

interface DebateInfo {
  bull_score: number | null;
  bear_score: number | null;
  verdict: string | null;
  confidence: number | null;
}

interface PipelineResponse {
  last_cycle: LastCycleInfo;
  crypto_signals: SignalItem[];
  equity_signals: SignalItem[];
  regime_summary: RegimeSummaryItem[];
  debate: DebateInfo;
}

export default function AgentPipelinePage() {
  const [data, setData] = useState<PipelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [secondsAgo, setSecondsAgo] = useState(0);

  const adminKey = localStorage.getItem('ADMIN_API_KEY') || '';

  const fetchData = async () => {
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (adminKey) {
        headers['X-Admin-API-Key'] = adminKey;
      }

      const res = await fetch('/.netlify/functions/get-pipeline-status', { headers });
      if (!res.ok) {
        if (res.status === 401) {
          throw new Error('Unauthorized. Please set your Admin API Key in Settings.');
        }
        throw new Error(`HTTP error ${res.status}`);
      }

      const json = await res.json();
      setData(json);
      setError(null);
      setSecondsAgo(0);
    } catch (err: any) {
      console.error('Failed to fetch pipeline status:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
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
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
          <span className="text-sm font-semibold uppercase tracking-wider">Analyzing Intelligence Pipeline...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 h-full bg-zinc-950 text-red-400 flex items-center justify-center">
        <div className="max-w-md p-6 bg-zinc-900 border border-red-500/20 rounded-xl space-y-4 shadow-2xl">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-red-500" />
            <h3 className="text-lg font-bold text-white uppercase tracking-wider">Pipeline Connection Failure</h3>
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

  const { last_cycle, crypto_signals, equity_signals, regime_summary, debate } = data;

  // Cycle age minutes logic
  const cycleMins = Math.floor(last_cycle.cycle_age_seconds / 60);

  const getAgeColorClass = (mins: number) => {
    if (mins < 20) return 'bg-emerald-950/40 text-emerald-400 border border-emerald-500/20';
    if (mins < 60) return 'bg-amber-950/40 text-amber-400 border border-amber-500/20';
    return 'bg-red-950/40 text-red-400 border border-red-500/20';
  };

  // Verdict style
  const getVerdictStyle = (verdict: string | null) => {
    if (!verdict) return 'bg-zinc-800 text-zinc-400 border-zinc-700';
    if (verdict === 'ENTER') return 'bg-emerald-950 text-emerald-400 border border-emerald-500/30';
    if (verdict === 'AVOID') return 'bg-rose-950 text-rose-400 border border-rose-500/30';
    return 'bg-zinc-900 text-zinc-300 border border-zinc-700';
  };

  // Regime badge styling
  const getRegimeClasses = (r: string) => {
    switch (r.toUpperCase()) {
      case 'BULL':
        return 'bg-green-950/30 text-green-400 border border-green-500/20';
      case 'BEAR':
        return 'bg-red-950/30 text-red-400 border border-red-500/20';
      case 'VOLATILE':
        return 'bg-amber-950/30 text-amber-400 border border-amber-500/20';
      case 'QUIET':
        return 'bg-blue-950/30 text-blue-400 border border-blue-500/20';
      default:
        return 'bg-zinc-800 text-zinc-400 border border-zinc-700';
    }
  };

  return (
    <div className="p-6 space-y-6 h-full overflow-y-auto bg-zinc-950 text-zinc-100 custom-scrollbar">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <PageHeader title="Agent Pipeline" subtitle="LangGraph Intelligence debate & decision matrix" />
        <div className="flex items-center gap-2 text-xs text-zinc-400 bg-zinc-900/60 px-3 py-1.5 rounded-lg border border-zinc-800/80">
          <Cpu className="w-3.5 h-3.5 text-indigo-400" />
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

      {/* ROW 1: Cycle Status Bar */}
      <div className={`w-full p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${getAgeColorClass(cycleMins)}`}>
        <div className="flex items-center gap-3">
          <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
          <div>
            <span className="font-bold tracking-wider text-xs uppercase">
              Last intelligence cycle ran: {cycleMins} {cycleMins === 1 ? 'minute' : 'minutes'} ago
            </span>
            <p className="text-[10px] opacity-80 mt-0.5">
              Ran at: {last_cycle.ran_at ? new Date(last_cycle.ran_at).toLocaleTimeString() : 'N/A'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] uppercase tracking-widest font-black opacity-70">Last cycle trigger:</span>
          <span className="px-2.5 py-1 bg-indigo-950/80 border border-indigo-500/30 text-indigo-300 text-xs font-bold rounded-lg uppercase tracking-wider">
            {last_cycle.asset_class_last}
          </span>
        </div>
      </div>

      {/* ROW 2: Debate Scorecard */}
      <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg space-y-6">
        <div className="text-center space-y-1">
          <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-400">Market Debate — Last Verdict</h3>
          <p className="text-[10px] text-zinc-500">Autonomous consensus between Bull and Bear analysts</p>
        </div>

        {debate.bull_score === null && debate.bear_score === null ? (
          <div className="p-6 text-center text-zinc-500 text-xs bg-zinc-950/50 rounded-xl border border-zinc-800/80">
            Debate data unavailable — check agents
          </div>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-2xl mx-auto">
              {/* Bull Score */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs font-bold">
                  <span className="text-green-400 uppercase tracking-widest">Bull Analyst Score</span>
                  <span className="text-green-400 font-mono text-sm">{debate.bull_score}%</span>
                </div>
                <div className="h-2.5 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800">
                  <div
                    className="h-full bg-green-500 transition-all duration-1000"
                    style={{ width: `${debate.bull_score}%` }}
                  />
                </div>
              </div>

              {/* Bear Score */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs font-bold">
                  <span className="text-red-400 uppercase tracking-widest">Bear Analyst Score</span>
                  <span className="text-red-400 font-mono text-sm">{debate.bear_score}%</span>
                </div>
                <div className="h-2.5 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800">
                  <div
                    className="h-full bg-red-500 transition-all duration-1000"
                    style={{ width: `${debate.bear_score}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="flex flex-col items-center justify-center gap-2 pt-2 border-t border-zinc-800/50 max-w-2xl mx-auto">
              <span className="text-[9px] uppercase tracking-widest font-bold text-zinc-500">Cycle Verdict</span>
              <div className="flex items-center gap-3">
                <span className={`px-4 py-1.5 rounded-lg text-sm font-black tracking-wider uppercase ${getVerdictStyle(debate.verdict)}`}>
                  {debate.verdict || 'HOLD'}
                </span>
                {debate.confidence !== null && (
                  <span className="text-xs font-mono text-zinc-400 bg-zinc-950 border border-zinc-800/80 px-2.5 py-1.5 rounded-lg">
                    Confidence: <span className="font-bold text-indigo-400">{debate.confidence}%</span>
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ROW 3: Two Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT: Crypto Pipeline */}
        <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
            <span className="text-lg">🔮</span>
            <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Crypto Cycle</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                  <th className="pb-2">Time</th>
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2">Action</th>
                  <th className="pb-2">Conf</th>
                  <th className="pb-2">Reasoning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {crypto_signals.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-4 text-center text-zinc-500">No crypto signals</td>
                  </tr>
                ) : (
                  crypto_signals.map((s, i) => {
                    const reasoningText = s.reasoning ? (s.reasoning.length > 80 ? s.reasoning.substring(0, 80) + '...' : s.reasoning) : 'N/A';
                    return (
                      <tr key={i} className="hover:bg-zinc-800/20">
                        <td className="py-3 text-zinc-400 font-mono">
                          {new Date(s.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="py-3 text-zinc-200 font-bold">{s.symbol}</td>
                        <td className={`py-3 ${s.action === 'BUY' ? 'text-green-400 font-bold' : s.action === 'SELL' ? 'text-red-400 font-bold' : 'text-zinc-500'}`}>
                          {s.action}
                        </td>
                        <td className="py-3 font-mono">{(s.confidence * 100).toFixed(0)}%</td>
                        <td className="py-3 text-zinc-400 max-w-[200px] truncate" title={s.reasoning}>{reasoningText}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* RIGHT: Equities Pipeline */}
        <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
            <span className="text-lg">📈</span>
            <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Equities Cycle</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                  <th className="pb-2">Time</th>
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2">Action</th>
                  <th className="pb-2">Conf</th>
                  <th className="pb-2">Reasoning</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {equity_signals.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-4 text-center text-zinc-500">No equity signals</td>
                  </tr>
                ) : (
                  equity_signals.map((s, i) => {
                    const reasoningText = s.reasoning ? (s.reasoning.length > 80 ? s.reasoning.substring(0, 80) + '...' : s.reasoning) : 'N/A';
                    return (
                      <tr key={i} className="hover:bg-zinc-800/20">
                        <td className="py-3 text-zinc-400 font-mono">
                          {new Date(s.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="py-3 text-zinc-200 font-bold">{s.symbol}</td>
                        <td className={`py-3 ${s.action === 'BUY' ? 'text-green-400 font-bold' : s.action === 'SELL' ? 'text-red-400 font-bold' : 'text-zinc-500'}`}>
                          {s.action}
                        </td>
                        <td className="py-3 font-mono">{(s.confidence * 100).toFixed(0)}%</td>
                        <td className="py-3 text-zinc-400 max-w-[200px] truncate" title={s.reasoning}>{reasoningText}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ROW 4: Regime Summary */}
      <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl shadow-lg space-y-4">
        <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
          <Info className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Current Regime Context</h3>
        </div>
        {regime_summary.length === 0 ? (
          <p className="text-xs text-zinc-500 text-center py-4">No regime summary states available.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
            {regime_summary.map((r, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg flex flex-col items-center justify-center text-center transition-all ${getRegimeClasses(
                  r.regime
                )}`}
              >
                <span className="text-[10px] font-bold tracking-widest text-zinc-400 uppercase">{r.symbol}</span>
                <span className="text-xs font-black mt-1 uppercase tracking-wide">{r.regime}</span>
                <span className="text-[10px] opacity-80 mt-0.5">{(r.regime_probability * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
