import React, { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FlaskConical, Play, Pause, Square, Upload, Download, Save, FastForward } from 'lucide-react'

interface Strategy {
  id: number
  name: string
  description: string
}

const mockStrategies: Strategy[] = [
  { id: 1, name: 'UT Bot Scalper V2', description: 'ATR-based scalping strategy with trailing stop' },
  { id: 2, name: 'EMA Crossover', description: 'Dual EMA crossover with volume confirmation' },
  { id: 3, name: 'RSI Mean Reversion', description: 'RSI oversold/overbought mean reversion' },
]

const StrategyLabView: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') || 'editor'

  const [selectedStrategy, setSelectedStrategy] = useState<number>(1)
  const [params, setParams] = useState({
    atrPeriod: 14,
    sensitivity: 1.5,
    timeframe: '15m',
    symbol: 'AAPL',
  })

  const [backtestConfig, setBacktestConfig] = useState({
    startDate: '2025-01-01',
    endDate: '2026-01-01',
    initialBalance: 100000,
  })
  const [backtestProgress, setBacktestProgress] = useState<number | null>(null)
  const [replaySpeed, setReplaySpeed] = useState(1)
  const [replayState, setReplayState] = useState<'stopped' | 'playing' | 'paused'>('stopped')
  const [executionLog, setExecutionLog] = useState<string[]>([
    '[INFO] Strategy Lab initialized',
    '[INFO] Ready to run backtest or live replay',
  ])

  const setTab = (tab: string) => {
    setSearchParams({ tab })
  }

  const runBacktest = () => {
    setBacktestProgress(0)
    setExecutionLog(prev => [...prev, `[RUN] Starting backtest from ${backtestConfig.startDate} to ${backtestConfig.endDate}`])
    const interval = setInterval(() => {
      setBacktestProgress(prev => {
        if (prev === null || prev >= 100) {
          clearInterval(interval)
          setExecutionLog(p => [
            ...p,
            '[OK] Backtest complete. 247 trades executed.',
            '[OK] Net P&L: +$12,340.56 | Sharpe: 1.82 | Max DD: -4.2%',
          ])
          return 100
        }
        return prev + 5
      })
    }, 200)
  }

  const cardStyle: React.CSSProperties = {
    background: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '12px',
    padding: '20px',
  }

  const btnStyle: React.CSSProperties = {
    padding: '8px 16px',
    background: 'var(--bg-tertiary, #21262d)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '8px',
    color: 'var(--text-primary, #e6edf3)',
    cursor: 'pointer',
    fontSize: '13px',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 12px',
    background: 'var(--bg-tertiary, #21262d)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '6px',
    color: 'var(--text-primary, #e6edf3)',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box',
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    color: 'var(--text-muted, #8b949e)',
    fontSize: '12px',
    marginBottom: '6px',
  }

  return (
    <div style={{ padding: '24px', background: 'var(--bg-primary, #0d1117)', minHeight: '100vh', color: 'var(--text-primary, #e6edf3)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '24px' }}>
        <FlaskConical size={24} style={{ color: 'var(--blue, #58a6ff)' }} />
        <h1 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>Strategy Lab</h1>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '24px', borderBottom: '1px solid var(--border, #30363d)', paddingBottom: '0' }}>
        {[
          { key: 'editor', label: 'Editor' },
          { key: 'backtest', label: 'Backtest & Replay' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setTab(tab.key)}
            style={{
              padding: '10px 20px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab.key ? '2px solid var(--blue, #58a6ff)' : '2px solid transparent',
              color: activeTab === tab.key ? 'var(--text-primary, #e6edf3)' : 'var(--text-muted, #8b949e)',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: activeTab === tab.key ? 600 : 400,
              marginBottom: '-1px',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Editor Tab */}
      {activeTab === 'editor' && (
        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '16px' }}>
          {/* Strategy library */}
          <div style={cardStyle}>
            <h2 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 12px 0', color: 'var(--text-muted, #8b949e)' }}>
              Strategy Library
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {mockStrategies.map(s => (
                <button
                  key={s.id}
                  onClick={() => setSelectedStrategy(s.id)}
                  style={{
                    textAlign: 'left',
                    padding: '10px 12px',
                    background: selectedStrategy === s.id ? 'var(--bg-tertiary, #21262d)' : 'transparent',
                    border: selectedStrategy === s.id ? '1px solid var(--blue, #58a6ff)' : '1px solid transparent',
                    borderRadius: '8px',
                    color: 'var(--text-primary, #e6edf3)',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>{s.name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #8b949e)' }}>{s.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Parameter form */}
          <div style={cardStyle}>
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 20px 0' }}>
              {mockStrategies.find(s => s.id === selectedStrategy)?.name} - Parameters
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
              <div>
                <label style={labelStyle}>ATR Period</label>
                <input
                  type="number"
                  value={params.atrPeriod}
                  onChange={e => setParams(p => ({ ...p, atrPeriod: parseInt(e.target.value) || 0 }))}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Sensitivity</label>
                <input
                  type="number"
                  step="0.1"
                  value={params.sensitivity}
                  onChange={e => setParams(p => ({ ...p, sensitivity: parseFloat(e.target.value) || 0 }))}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Timeframe</label>
                <select
                  value={params.timeframe}
                  onChange={e => setParams(p => ({ ...p, timeframe: e.target.value }))}
                  style={inputStyle}
                >
                  <option value="1m">1m</option>
                  <option value="5m">5m</option>
                  <option value="15m">15m</option>
                  <option value="1h">1h</option>
                  <option value="4h">4h</option>
                  <option value="1d">1d</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Symbol</label>
                <input
                  type="text"
                  value={params.symbol}
                  onChange={e => setParams(p => ({ ...p, symbol: e.target.value }))}
                  style={inputStyle}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button style={{ ...btnStyle, background: 'var(--blue, #58a6ff)', color: '#0d1117', fontWeight: 600, border: 'none' }}>
                <Save size={14} />
                Save
              </button>
              <button style={btnStyle}>
                <Upload size={14} />
                Import JSON
              </button>
              <button style={btnStyle}>
                <Download size={14} />
                Export JSON
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Backtest & Replay Tab */}
      {activeTab === 'backtest' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Backtest config */}
          <div style={cardStyle}>
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px 0' }}>Backtest Mode</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: '16px', alignItems: 'end' }}>
              <div>
                <label style={labelStyle}>Start Date</label>
                <input
                  type="date"
                  value={backtestConfig.startDate}
                  onChange={e => setBacktestConfig(c => ({ ...c, startDate: e.target.value }))}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>End Date</label>
                <input
                  type="date"
                  value={backtestConfig.endDate}
                  onChange={e => setBacktestConfig(c => ({ ...c, endDate: e.target.value }))}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Initial Balance ($)</label>
                <input
                  type="number"
                  value={backtestConfig.initialBalance}
                  onChange={e => setBacktestConfig(c => ({ ...c, initialBalance: parseInt(e.target.value) || 0 }))}
                  style={inputStyle}
                />
              </div>
              <button
                onClick={runBacktest}
                disabled={backtestProgress !== null && backtestProgress < 100}
                style={{
                  ...btnStyle,
                  background: 'var(--green, #3fb950)',
                  color: '#0d1117',
                  fontWeight: 600,
                  border: 'none',
                  opacity: backtestProgress !== null && backtestProgress < 100 ? 0.6 : 1,
                }}
              >
                <Play size={14} />
                Run Backtest
              </button>
            </div>

            {backtestProgress !== null && (
              <div style={{ marginTop: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted, #8b949e)' }}>
                    {backtestProgress < 100 ? 'Running backtest...' : 'Backtest complete'}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted, #8b949e)' }}>{backtestProgress}%</span>
                </div>
                <div style={{ height: '6px', background: 'var(--bg-tertiary, #21262d)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${backtestProgress}%`,
                      background: backtestProgress < 100 ? 'var(--blue, #58a6ff)' : 'var(--green, #3fb950)',
                      borderRadius: '3px',
                      transition: 'width 0.2s',
                    }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Live Replay */}
          <div style={cardStyle}>
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px 0' }}>Live Replay</h2>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', gap: '4px' }}>
                <button
                  onClick={() => setReplayState(replayState === 'playing' ? 'paused' : 'playing')}
                  style={{
                    ...btnStyle,
                    background: replayState === 'playing' ? 'var(--amber, #e3b341)' : 'var(--green, #3fb950)',
                    color: '#0d1117',
                    fontWeight: 600,
                    border: 'none',
                  }}
                >
                  {replayState === 'playing' ? <Pause size={14} /> : <Play size={14} />}
                  {replayState === 'playing' ? 'Pause' : 'Play'}
                </button>
                <button
                  onClick={() => setReplayState('stopped')}
                  style={{ ...btnStyle, background: 'var(--red, #f85149)', color: '#0d1117', fontWeight: 600, border: 'none' }}
                >
                  <Square size={14} />
                  Stop
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: '8px' }}>
                <FastForward size={14} style={{ color: 'var(--text-muted, #8b949e)' }} />
                <span style={{ color: 'var(--text-muted, #8b949e)', fontSize: '12px', marginRight: '4px' }}>Speed:</span>
                {[1, 2, 5, 10].map(speed => (
                  <button
                    key={speed}
                    onClick={() => setReplaySpeed(speed)}
                    style={{
                      padding: '4px 10px',
                      background: replaySpeed === speed ? 'var(--blue, #58a6ff)' : 'var(--bg-tertiary, #21262d)',
                      border: '1px solid var(--border, #30363d)',
                      borderRadius: '4px',
                      color: replaySpeed === speed ? '#0d1117' : 'var(--text-primary, #e6edf3)',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: replaySpeed === speed ? 700 : 400,
                    }}
                  >
                    {speed}x
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Execution log */}
          <div style={cardStyle}>
            <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 12px 0' }}>Execution Log</h2>
            <div
              style={{
                background: '#000000',
                borderRadius: '8px',
                padding: '16px',
                fontFamily: 'monospace',
                fontSize: '13px',
                color: 'var(--green, #3fb950)',
                minHeight: '200px',
                maxHeight: '320px',
                overflowY: 'auto',
                lineHeight: 1.8,
                border: '1px solid var(--border, #30363d)',
              }}
            >
              {executionLog.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
              <div style={{ opacity: 0.5 }}>{'>'} _</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default StrategyLabView
