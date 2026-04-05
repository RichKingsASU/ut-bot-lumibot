import { useState } from 'react';

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

const EQ_SYMBOLS = ['IWM', 'SPY', 'QQQ', 'CUSTOM'];
const CR_SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD'];

export function BacktestPanel({
  result, cpuPct, onRunBacktest,
  deployTarget, deploySymbol, onSetTarget, onSetSymbol, onDeploy
}: Props) {
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [capital, setCapital] = useState('100,000.00');
  const [symbol, setSymbol] = useState('IWM - Alpaca SIP');

  const inputCls = "w-full bg-[#060810] border-b border-gray-800 text-xs py-1.5 text-gray-300 font-mono outline-none focus:border-blue-500 transition-colors mb-2";
  const labelCls = "block text-[9px] font-bold text-gray-600 uppercase tracking-widest mb-1.5";
  const sectionCls = "px-3.5 py-3 border-b border-gray-800";

  const symbols = deployTarget === 'crypto' ? CR_SYMBOLS : EQ_SYMBOLS;

  // Suppress unused variable warnings
  void onDeploy;

  return (
    <div className="flex flex-col h-full bg-[#0d0f1a] overflow-y-auto">
      {/* Header */}
      <div className="px-3.5 py-2.5 border-b border-gray-800">
        <span className="text-[9px] font-bold text-gray-600 uppercase tracking-widest">Backtest Control Panel</span>
      </div>

      {/* Historical Range */}
      <div className={sectionCls}>
        <span className={labelCls}>Historical Range</span>
        <input className={inputCls} value={startDate} onChange={e => setStartDate(e.target.value)} />
        <input className={inputCls} value={endDate} onChange={e => setEndDate(e.target.value)} style={{ marginBottom: 0 }} />
      </div>

      {/* Capital */}
      <div className={sectionCls}>
        <span className={labelCls}>Starting Capital (USD)</span>
        <input className={inputCls} value={capital} onChange={e => setCapital(e.target.value)} style={{ marginBottom: 0 }} />
      </div>

      {/* Symbol */}
      <div className={sectionCls}>
        <span className={labelCls}>Symbol & Exchange</span>
        <select
          className="w-full bg-[#060810] border-b border-gray-800 text-xs py-1.5 text-gray-300 font-mono outline-none focus:border-blue-500 appearance-none"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
        >
          <option>IWM - Alpaca SIP</option>
          <option>SPY - Alpaca SIP</option>
          <option>QQQ - Alpaca SIP</option>
          <option>BTC/USD - Alpaca Crypto</option>
          <option>ETH/USD - Alpaca Crypto</option>
          <option>SOL/USD - Alpaca Crypto</option>
        </select>
      </div>

      {/* Run button */}
      <div className={sectionCls}>
        <button
          onClick={() => onRunBacktest({ startDate, endDate, capital, symbol })}
          className="w-full flex items-center justify-center gap-2 py-2.5 bg-sky-500 hover:bg-sky-400 text-white text-[10px] font-bold rounded uppercase tracking-widest transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="2,1.5 10,6 2,10.5"/>
          </svg>
          Run Backtest
        </button>
      </div>

      {/* Last Result */}
      <div className={sectionCls}>
        <span className={labelCls} style={{ marginBottom: '8px', display: 'block' }}>
          Last Result: <span className="text-gray-400 normal-case">{result?.version || '\u2014'}</span>
        </span>
        <div className="grid grid-cols-2 gap-1.5 mb-2">
          {[
            { l: 'Total Return', v: result?.totalReturn, c: result?.totalReturn?.startsWith('+') ? 'text-green-400' : 'text-gray-300' },
            { l: 'Sharpe Ratio', v: result?.sharpe, c: 'text-gray-200' },
            { l: 'Win Rate',     v: result?.winRate,  c: 'text-gray-200' },
            { l: 'Max DD',       v: result?.maxDrawdown, c: 'text-amber-400' },
          ].map(m => (
            <div key={m.l} className="bg-[#060810] border border-gray-800 rounded p-2">
              <div className="text-[8px] text-gray-600 uppercase tracking-wider mb-1">{m.l}</div>
              <div className={`text-base font-bold font-mono ${m.c}`}>{m.v || '\u2014'}</div>
            </div>
          ))}
        </div>
        {/* Equity curve */}
        <div className="flex justify-between items-center mb-1">
          <span className="text-[8px] text-gray-600 uppercase tracking-wider">Equity Curve</span>
          <span className="text-[9px] text-green-400 font-mono">{result?.vol || ''}</span>
        </div>
        <div className="h-14 bg-[#060810] border border-gray-800 rounded overflow-hidden">
          <svg width="100%" height="56" viewBox="0 0 200 56" preserveAspectRatio="none">
            <line x1="0" y1="28" x2="200" y2="28" stroke="#1f2937" strokeWidth="0.5"/>
            {result?.curve ? (
              <polyline points={result.curve} stroke="#22c55e" strokeWidth="1.5" fill="none"/>
            ) : (
              <text x="100" y="32" textAnchor="middle" fontSize="8" fill="#374151" fontFamily="Inter">
                No results yet — run backtest
              </text>
            )}
          </svg>
        </div>
      </div>

      {/* Deploy Target */}
      <div className={sectionCls}>
        <span className={labelCls} style={{ marginBottom: '6px', display: 'block' }}>Deploy Target</span>
        <div className="flex flex-col gap-1.5 mb-3">
          {(['equities', 'crypto'] as const).map(t => (
            <button
              key={t}
              onClick={() => { onSetTarget(t); onSetSymbol(t === 'crypto' ? 'BTC/USD' : 'IWM'); }}
              className={`flex items-center gap-2 px-2.5 py-2 border rounded text-[10px] transition-colors ${
                deployTarget === t
                  ? 'border-blue-900 bg-blue-950 text-blue-400'
                  : 'border-gray-800 text-gray-600 hover:border-gray-700 hover:text-gray-400'
              }`}
            >
              {t === 'equities' ? (
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polyline points="1,9 4,6 7,7.5 10,3"/>
                </svg>
              ) : (
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="6" cy="6" r="4.5"/>
                  <path d="M4.5 4.5c0-.9.6-1.5 1.5-1.5s1.5.6 1.5 1.5-.6 1.5-1.5 1.5-1.5.6-1.5 1.5.6 1.5 1.5 1.5"/>
                </svg>
              )}
              {t === 'equities' ? 'Equities (market hours)' : 'Crypto (24/7)'}
            </button>
          ))}
        </div>
        <span className={labelCls} style={{ marginBottom: '4px', display: 'block' }}>Instrument</span>
        <div className="grid grid-cols-2 gap-1">
          {symbols.map(s => (
            <button
              key={s}
              onClick={() => onSetSymbol(s)}
              className={`py-1.5 border rounded text-[9px] font-bold transition-colors ${
                deploySymbol === s
                  ? 'border-blue-900 bg-blue-950 text-blue-400'
                  : 'border-gray-800 text-gray-600 hover:border-gray-700 hover:text-gray-400'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* CPU */}
      <div className="px-3.5 py-3 mt-auto border-t border-gray-800">
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-[9px] text-gray-600 uppercase tracking-wider font-bold">CPU Usage</span>
          <span className="text-[9px] text-green-400 font-mono">{Math.round(cpuPct)}%</span>
        </div>
        <div className="h-1 bg-[#060810] rounded overflow-hidden">
          <div
            className="h-full rounded transition-all duration-300"
            style={{
              width: `${cpuPct}%`,
              background: cpuPct > 60 ? '#f59e0b' : '#22c55e'
            }}
          />
        </div>
      </div>
    </div>
  );
}
