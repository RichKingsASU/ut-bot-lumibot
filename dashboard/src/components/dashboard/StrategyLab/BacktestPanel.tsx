import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Play, Settings2, Database, TrendingUp, BarChart3, ShieldCheck, Cpu, Globe, Info } from 'lucide-react';
import { StrategyIntelligence } from './StrategyIntelligence';

interface BacktestResult {
  totalReturn: string;
  sharpe: string;
  winRate: string;
  maxDrawdown: string;
  vol: string;
  version: string;
  curve: string;
}

interface Props {
  result: BacktestResult | null;
  cpuPct: number;
  onRunBacktest: (params: { startDate: string; endDate: string; capital: string; symbol: string }) => void;
  deployTarget: 'equities' | 'crypto';
  deploySymbol: string;
  onSetTarget: (t: 'equities' | 'crypto') => void;
  onSetSymbol: (s: string) => void;
  onDeploy: () => void;
}

export function BacktestPanel({
  result, cpuPct, onRunBacktest,
  deployTarget, deploySymbol, onSetTarget, onSetSymbol, onDeploy
}: Props) {
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [capital, setCapital] = useState('100,000');

  const inputCls = "w-full bg-surface-0 border border-border-muted rounded-lg py-1.5 px-3 text-[11px] text-vibrant font-mono outline-none focus:border-blue-500/50 transition-smooth";
  const labelCls = "block text-[9px] font-bold text-dim uppercase tracking-widest mb-1.5";

  return (
    <div className="flex flex-col h-full bg-surface-1 overflow-y-auto custom-scrollbar">
      {/* Header */}
      <div className="p-4 border-b border-border-muted flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings2 className="w-4 h-4 text-blue-400" />
          <h2 className="text-[10px] font-bold text-secondary uppercase tracking-[0.2em]">Lab Controls</h2>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* Parameters Section */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Database className="w-3.5 h-3.5 text-dim" />
            <span className="text-[11px] font-bold text-vibrant">Data Configuration</span>
          </div>
          
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Start Epoch</label>
              <input type="date" className={inputCls} value={startDate} onChange={e => setStartDate(e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>End Epoch</label>
              <input type="date" className={inputCls} value={endDate} onChange={e => setEndDate(e.target.value)} />
            </div>
          </div>

          <div>
            <label className={labelCls}>Initial Liquidity (USD)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[10px] text-dim">$</span>
              <input className={`${inputCls} pl-6`} value={capital} onChange={e => setCapital(e.target.value)} />
            </div>
          </div>

          <div>
            <label className={labelCls}>Execution Instrument</label>
            <div className="grid grid-cols-2 gap-2">
              {(['equities', 'crypto'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => onSetTarget(t)}
                  className={`py-2 rounded-lg border text-[10px] font-bold transition-smooth ${
                    deployTarget === t 
                      ? 'bg-blue-500/10 border-blue-500/50 text-blue-400' 
                      : 'bg-surface-0 border-border-muted text-dim hover:text-secondary'
                  }`}
                >
                  {t.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Execution Button */}
        <button
          onClick={() => onRunBacktest({ startDate, endDate, capital, symbol: deploySymbol })}
          className="w-full group relative overflow-hidden py-3 bg-blue-600 hover:bg-blue-500 rounded-xl transition-smooth shadow-lg shadow-blue-900/20"
        >
          <div className="relative z-10 flex items-center justify-center gap-2 text-white font-bold text-xs uppercase tracking-widest">
            <Play className="w-3.5 h-3.5 fill-current" />
            Initialize Simulation
          </div>
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
        </button>

        {/* Results Analytics */}
        {result ? (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 className="w-3.5 h-3.5 text-blue-400" />
              <span className="text-[11px] font-bold text-vibrant">Simulation Analytics</span>
              <span className="ml-auto text-[9px] text-dim font-mono">{result.version}</span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Net Return', value: result.totalReturn, icon: TrendingUp, color: 'text-emerald-400' },
                { label: 'Sharpe', value: result.sharpe, icon: ShieldCheck, color: 'text-blue-400' },
                { label: 'Win Rate', value: result.winRate, icon: BarChart3, color: 'text-vibrant' },
                { label: 'Max DD', value: result.maxDrawdown, icon: Info, color: 'text-rose-400' },
              ].map((m, i) => (
                <div key={i} className="p-3 bg-surface-0 border border-border-muted rounded-xl hover:border-border-active transition-smooth">
                  <div className="flex items-center gap-1.5 mb-1 text-dim">
                    <m.icon className="w-3 h-3" />
                    <span className="text-[8px] font-bold uppercase tracking-wider">{m.label}</span>
                  </div>
                  <div className={`text-base font-mono font-bold ${m.color}`}>{m.value}</div>
                </div>
              ))}
            </div>

            {/* AI Insights Card */}
            <StrategyIntelligence 
              strategyName={deploySymbol}
              confidenceScore={84}
              insights={[
                { type: 'positive', label: 'Alpha Factor Confirmed', description: 'Strong correlation with ATR breakout during NY open.' },
                { type: 'warning', label: 'Slippage Risk', description: 'Low liquidity detected in selected epoch. Backtest might be optimistic.' },
                { type: 'neutral', label: 'Parameter Tuning', description: 'Sensitivity of 2.0 is optimal for this timeframe.' }
              ]}
            />

            <button 
              onClick={onDeploy}
              className="w-full py-2.5 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 rounded-xl text-[10px] font-bold text-emerald-400 transition-smooth uppercase tracking-widest"
            >
              Commit to Production
            </button>
          </motion.div>
        ) : (
          <div className="p-8 text-center glass-panel rounded-xl border-dashed border-2 border-border-muted">
            <BarChart3 className="w-8 h-8 text-dim mx-auto mb-3 opacity-20" />
            <p className="text-[10px] text-dim leading-relaxed">
              No simulation data available.<br/>Configure parameters and initialize.
            </p>
          </div>
        )}

        {/* Infrastructure Health */}
        <div className="pt-4 border-t border-border-muted">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Cpu className="w-3 h-3 text-dim" />
              <span className="text-[9px] font-bold text-dim uppercase tracking-wider">Engine Load</span>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 font-bold">{Math.round(cpuPct)}%</span>
          </div>
          <div className="h-1 bg-surface-0 rounded-full overflow-hidden">
            <motion.div 
              initial={{ width: 0 }}
              animate={{ width: `${cpuPct}%` }}
              className={`h-full rounded-full ${cpuPct > 70 ? 'bg-rose-500' : 'bg-emerald-500'}`}
            />
          </div>
          <div className="flex items-center gap-2 mt-4 text-[9px] text-dim">
            <Globe className="w-3 h-3" />
            <span>Node: us-east-1 (Primary)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
