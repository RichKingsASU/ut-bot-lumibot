import React, { useState, useEffect, useRef } from 'react';
import {
  Cpu,
  RefreshCw,
  AlertCircle,
  Sparkles,
  TrendingUp,
  Info,
  Clock,
  Loader2,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { BentoGrid, BentoTile } from '../components/ui/BentoLayouts';
import { Badge } from '../components/ui/Badge';
import { Skeleton } from '../components/ui/Skeleton';
import { netlifyFetch } from '../lib/apiClient';

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

// ─── Sub-Components ─────────────────────────────────────────────────────────

function TileHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("px-4 pt-4 pb-2 flex items-center justify-between", className)}>
      {children}
    </div>
  );
}

function TileTitle({ icon: Icon, children }: { icon?: React.ElementType; children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
      {Icon && <Icon size={13} className="opacity-60" />}
      {children}
    </h3>
  );
}

function ScoreBar({ label, score, color }: { label: string; score: number | null; color: string }) {
  if (score === null) return null;
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center text-[10px] font-bold">
        <span className="uppercase tracking-wider text-muted-foreground">{label}</span>
        <span className="font-mono tabular-nums" style={{ color }}>{score}%</span>
      </div>
      <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

function SignalTable({ signals, emptyMessage }: { signals: SignalItem[]; emptyMessage: string }) {
  return (
    <div className="overflow-x-auto custom-scrollbar">
      <table className="w-full text-xs" role="grid">
        <thead>
          <tr className="border-b border-border">
            {['Time', 'Symbol', 'Action', 'Conf', 'Reasoning'].map((h) => (
              <th key={h} scope="col" className="text-left px-2 py-1.5 text-[9px] font-bold text-muted-foreground uppercase tracking-wider">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/30">
          {signals.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-6 text-center text-muted-foreground text-xs">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            signals.map((s, i) => {
              const actionColor = s.action === 'BUY' ? 'text-[#10b981]' : s.action === 'SELL' ? 'text-[#ef4444]' : 'text-muted-foreground';
              const reasoningText = s.reasoning ? (s.reasoning.length > 60 ? s.reasoning.substring(0, 60) + '…' : s.reasoning) : '—';
              return (
                <tr key={i} className="hover:bg-accent/5 transition-colors">
                  <td className="px-2 py-2 text-muted-foreground font-mono tabular-nums">
                    {new Date(s.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="px-2 py-2 font-bold text-foreground">{s.symbol}</td>
                  <td className="px-2 py-2">
                    <span className={cn("font-bold", actionColor)}>{s.action}</span>
                  </td>
                  <td className="px-2 py-2 font-mono tabular-nums text-foreground">{(s.confidence * 100).toFixed(0)}%</td>
                  <td className="px-2 py-2 text-muted-foreground max-w-[180px] truncate" title={s.reasoning}>
                    {reasoningText}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────

const MAX_AUTH_FAILURES = 3

export default function AgentPipelinePage() {
  const [data, setData] = useState<PipelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [secondsAgo, setSecondsAgo] = useState(0);
  const authFailures = useRef(0);
  const stoppedRef = useRef(false);

  const fetchData = async () => {
    if (stoppedRef.current) return;
    try {
      const res = await netlifyFetch('get-pipeline-status');
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
      console.error('Failed to fetch pipeline status:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    stoppedRef.current = false;
    authFailures.current = 0;
    fetchData();
    const interval = setInterval(() => { if (!stoppedRef.current) fetchData(); }, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const counter = setInterval(() => {
      setSecondsAgo((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(counter);
  }, []);

  // ─── Loading State ──────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <BentoGrid>
          {Array.from({ length: 6 }).map((_, i) => (
            <BentoTile key={i} colSpan={i < 2 ? 2 : 1}>
              <div className="p-4 space-y-3">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-2 w-full" />
              </div>
            </BentoTile>
          ))}
        </BentoGrid>
      </div>
    );
  }

  // ─── Error State ────────────────────────────────────────────────────────

  if (error) {
    return (
      <div className="p-8 flex items-center justify-center h-full">
        <div className="max-w-md p-6 bg-card border border-destructive/20 rounded-xl space-y-4 shadow-lg">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-destructive" />
            <h3 className="text-sm font-bold text-foreground uppercase tracking-wider">Pipeline Connection Failure</h3>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">{error}</p>
          <button
            onClick={() => {
              setLoading(true);
              fetchData();
            }}
            className="w-full py-2 bg-destructive/10 hover:bg-destructive/20 border border-destructive/30 text-destructive font-semibold text-xs rounded-lg transition-all"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { last_cycle, crypto_signals, equity_signals, regime_summary, debate } = data;
  const cycleMins = Math.floor(last_cycle.cycle_age_seconds / 60);
  const cycleStale = cycleMins >= 60;

  const getRegimeColor = (r: string) => {
    switch (r.toUpperCase()) {
      case 'BULL': return '#10b981';
      case 'BEAR': return '#ef4444';
      case 'VOLATILE': return '#f59e0b';
      case 'QUIET': return '#3b82f6';
      default: return '#8b949e';
    }
  };

  const verdictColor = debate.verdict === 'ENTER' ? '#10b981' : debate.verdict === 'AVOID' ? '#ef4444' : '#8b949e';

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="p-4 lg:p-6 h-full overflow-y-auto custom-scrollbar">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">Agent Control Plane</h1>
          <p className="text-[11px] text-muted-foreground">LangGraph intelligence pipeline • advisory mode — not wired to execution</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[9px] font-mono tabular-nums gap-1">
            <Clock size={10} />
            {secondsAgo}s ago
          </Badge>
          <button
            onClick={() => { setLoading(true); fetchData(); }}
            className="p-1.5 rounded-md hover:bg-accent transition-colors text-muted-foreground"
            aria-label="Refresh pipeline data"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* ── Advisory Banner ─────────────────────────────────────────────── */}
      <div className="mb-4 px-3 py-2 rounded-lg border border-amber-500/20 bg-amber-500/5 flex items-center gap-2 text-[11px] text-amber-400 font-medium" role="alert">
        <Info size={14} />
        <span>
          <strong>Advisory Only:</strong> The multi-agent brain produces signals but is <strong>not yet wired</strong> to execution decisions.
          All trade actions require manual human confirmation via the trading interface.
        </span>
      </div>

      {/* ── Bento Grid ──────────────────────────────────────────────────── */}
      <BentoGrid className="grid-cols-1 md:grid-cols-2 lg:grid-cols-4 auto-rows-[minmax(160px,auto)] gap-3">

        {/* TILE: Last Cycle Status */}
        <BentoTile colSpan={2} className={cn(
          "bg-card/60 backdrop-blur-sm border-border/40",
          cycleStale && "border-destructive/30"
        )}>
          <TileHeader>
            <TileTitle icon={Sparkles}>Last Intelligence Cycle</TileTitle>
            {cycleStale && (
              <Badge variant="destructive" className="text-[9px]">STALE</Badge>
            )}
          </TileHeader>
          <div className="px-4 pb-4 flex items-center justify-between gap-4">
            <div>
              <span className={cn(
                "text-3xl font-black tabular-nums font-mono tracking-tight",
                cycleMins < 20 ? "text-[#10b981]" : cycleMins < 60 ? "text-[#f59e0b]" : "text-[#ef4444]"
              )}>
                {cycleMins}m
              </span>
              <span className="text-xs text-muted-foreground ml-1.5">ago</span>
              <p className="text-[10px] text-muted-foreground mt-0.5 font-mono">
                {last_cycle.ran_at ? new Date(last_cycle.ran_at).toLocaleTimeString() : 'N/A'}
              </p>
            </div>
            <div className="text-right">
              <span className="text-[9px] text-muted-foreground uppercase tracking-wider block mb-1">Last Trigger</span>
              <Badge variant="secondary" className="text-[10px] font-mono uppercase">
                {last_cycle.asset_class_last}
              </Badge>
            </div>
          </div>
        </BentoTile>

        {/* TILE: Debate Verdict */}
        <BentoTile colSpan={2} className="bg-card/60 backdrop-blur-sm border-border/40">
          <TileHeader>
            <TileTitle icon={TrendingUp}>Market Debate</TileTitle>
            <Badge variant="outline" className="text-[9px]">ADVISORY</Badge>
          </TileHeader>
          <div className="px-4 pb-4 space-y-3">
            {debate.bull_score === null && debate.bear_score === null ? (
              <p className="text-xs text-muted-foreground text-center py-4">Debate data unavailable</p>
            ) : (
              <>
                <ScoreBar label="Bull Analyst" score={debate.bull_score} color="#10b981" />
                <ScoreBar label="Bear Analyst" score={debate.bear_score} color="#ef4444" />
                <div className="flex items-center justify-between pt-2 border-t border-border/30">
                  <span className="text-[9px] text-muted-foreground uppercase tracking-wider font-bold">Verdict</span>
                  <div className="flex items-center gap-2">
                    <span
                      className="text-sm font-black uppercase tracking-wider"
                      style={{ color: verdictColor }}
                    >
                      {debate.verdict || 'HOLD'}
                    </span>
                    {debate.confidence !== null && (
                      <span className="text-[10px] font-mono text-muted-foreground tabular-nums">
                        {debate.confidence}%
                      </span>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </BentoTile>

        {/* TILE: Crypto Signals */}
        <BentoTile colSpan={2} rowSpan={2} className="bg-card/60 backdrop-blur-sm border-border/40 overflow-hidden">
          <TileHeader>
            <TileTitle icon={Cpu}>Crypto Agent Signals</TileTitle>
            <span className="text-[9px] text-muted-foreground font-mono">{crypto_signals.length} signals</span>
          </TileHeader>
          <div className="px-4 pb-4 flex-1 overflow-auto custom-scrollbar">
            <SignalTable signals={crypto_signals} emptyMessage="No crypto signals" />
          </div>
        </BentoTile>

        {/* TILE: Equity Signals */}
        <BentoTile colSpan={2} rowSpan={2} className="bg-card/60 backdrop-blur-sm border-border/40 overflow-hidden">
          <TileHeader>
            <TileTitle icon={TrendingUp}>Equity Agent Signals</TileTitle>
            <span className="text-[9px] text-muted-foreground font-mono">{equity_signals.length} signals</span>
          </TileHeader>
          <div className="px-4 pb-4 flex-1 overflow-auto custom-scrollbar">
            <SignalTable signals={equity_signals} emptyMessage="No equity signals" />
          </div>
        </BentoTile>

        {/* TILE: Regime Summary */}
        <BentoTile colSpan={4} className="bg-card/60 backdrop-blur-sm border-border/40">
          <TileHeader>
            <TileTitle icon={Info}>Regime Context</TileTitle>
            <span className="text-[9px] text-muted-foreground font-mono">{regime_summary.length} symbols</span>
          </TileHeader>
          <div className="px-4 pb-4">
            {regime_summary.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">No regime data</p>
            ) : (
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
                {regime_summary.map((r, i) => (
                  <div
                    key={i}
                    className="flex flex-col items-center justify-center p-2 rounded-lg border bg-card/40 text-center"
                    style={{ borderColor: `${getRegimeColor(r.regime)}30` }}
                  >
                    <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider">{r.symbol}</span>
                    <span
                      className="text-xs font-black uppercase mt-0.5"
                      style={{ color: getRegimeColor(r.regime) }}
                    >
                      {r.regime}
                    </span>
                    <span className="text-[9px] text-muted-foreground font-mono tabular-nums">
                      {(r.regime_probability * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </BentoTile>

      </BentoGrid>
    </div>
  );
}
