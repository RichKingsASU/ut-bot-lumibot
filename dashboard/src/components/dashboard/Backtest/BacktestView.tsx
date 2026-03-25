import React, { useState } from 'react'
import { History, Play, FileText, BarChart2, Info } from 'lucide-react'

interface BacktestViewProps {
  symbol: string
  timeframe: string
}

export function BacktestView({ symbol, timeframe }: BacktestViewProps) {
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState(0)

  const handleStartBacktest = () => {
    setIsRunning(true)
    setProgress(0)
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval)
          setIsRunning(false)
          return 100
        }
        return prev + 5
      })
    }, 200)
  }

  return (
    <div style={{ padding: '24px', flex: 1, display: 'flex', gap: '24px', overflow: 'hidden' }}>
      {/* Configuration Panel */}
      <div style={{ width: '320px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Backtesting</h1>
        
        <div style={configBoxStyle}>
          <h2 style={sectionTitleStyle}>Strategy Configuration</h2>
          <div style={inputGroupStyle}>
            <label style={labelStyle}>Strategy</label>
            <select style={selectStyle}>
              <option>UT Bot Scalper V2</option>
              <option>Trend Following EMA</option>
              <option>Mean Reversion RSI</option>
            </select>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ ...inputGroupStyle, flex: 1 }}>
              <label style={labelStyle}>Start Date</label>
              <input type="date" defaultValue="2024-01-01" style={inputStyle} />
            </div>
            <div style={{ ...inputGroupStyle, flex: 1 }}>
              <label style={labelStyle}>End Date</label>
              <input type="date" defaultValue="2024-03-01" style={inputStyle} />
            </div>
          </div>
          <div style={inputGroupStyle}>
            <label style={labelStyle}>Initial Balance</label>
            <input type="number" defaultValue="100000" style={inputStyle} />
          </div>
          <button 
            disabled={isRunning}
            onClick={handleStartBacktest}
            style={{ 
              ...primaryBtnStyle, 
              background: isRunning ? 'var(--bg-tertiary)' : 'var(--blue)',
              opacity: isRunning ? 0.7 : 1
            }}
          >
            <Play size={18} style={{ marginRight: '8px' }} />
            {isRunning ? `Running (${progress}%)` : 'Run Backtest'}
          </button>
        </div>

        <div style={{ ...configBoxStyle, background: 'var(--blue)11', border: '1px solid var(--blue)33' }}>
          <div style={{ display: 'flex', alignItems: 'center', color: 'var(--blue)', marginBottom: '8px' }}>
            <Info size={16} style={{ marginRight: '8px' }} />
            <span style={{ fontWeight: 600, fontSize: '13px' }}>Pro Tip</span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Higher timeframe backtests run faster but may skip intra-candle price action details.
          </p>
        </div>
      </div>

      {/* Results Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '24px', overflow: 'hidden' }}>
        <div style={{ ...configBoxStyle, flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', borderStyle: 'dashed' }}>
          {!isRunning && progress === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
              <BarChart2 size={48} strokeWidth={1} style={{ marginBottom: '16px', opacity: 0.3 }} />
              <div>Configure and run a backtest to see results here</div>
            </div>
          ) : (
            <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                  <h3 style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Execution Log</h3>
                  <span style={{ fontSize: '12px', color: 'var(--blue)' }}>{progress}% Complete</span>
               </div>
               <div style={{ flex: 1, background: 'black', borderRadius: '4px', padding: '12px', fontFamily: 'monospace', fontSize: '12px', color: '#0f0', overflow: 'auto' }}>
                  [INFO] Initializing Lumibot engine...<br/>
                  [INFO] Loading historical data for {symbol} ({timeframe})...<br/>
                  [INFO] Backtest range: 2024-01-01 to 2024-03-01<br/>
                  {progress > 20 && <>[DATA] Loaded 4,520 candles<br/></>}
                  {progress > 40 && <>[STRAT] Applying UT Bot Scalper V2 logic...<br/></>}
                  {progress > 60 && <>[TRADE] BUY target hit @ 198.40 (2024-01-05)<br/></>}
                  {progress > 80 && <>[TRADE] SELL trailing stop hit @ 202.15 (2024-01-12)<br/></>}
                  {progress === 100 && <><br/>[SUCCESS] Backtest completed in 2.4s<br/>[STATS] Sharpe: 1.84 | Drawdown: 4.2%</>}
               </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const configBoxStyle = { padding: '24px', background: 'var(--bg-secondary)', borderRadius: '12px', border: '1px solid var(--border)' }
const sectionTitleStyle = { fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '20px' }
const inputGroupStyle = { marginBottom: '16px' }
const labelStyle = { display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' as const }
const inputStyle = { width: '100%', padding: '10px', background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text-primary)', outline: 'none' }
const selectStyle = { ...inputStyle, cursor: 'pointer' }
const primaryBtnStyle = { width: '100%', padding: '12px', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: '12px' }
