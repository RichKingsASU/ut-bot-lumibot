import React, { useState } from 'react'
import { useTradingContext } from '../../../context/TradingContext'
import { DataFreshness } from '../../DataFreshness'

const SYMBOL_LIMITS = [
  { symbol: 'IWM', maxShares: 500, maxValue: 105000 },
  { symbol: 'SPY', maxShares: 200, maxValue: 106000 },
  { symbol: 'QQQ', maxShares: 250, maxValue: 100000 },
  { symbol: 'AAPL', maxShares: 300, maxValue: 54000 },
  { symbol: 'TSLA', maxShares: 150, maxValue: 37500 },
  { symbol: 'NVDA', maxShares: 100, maxValue: 90000 },
]

const PositionSizingView: React.FC = () => {
  const { account, positions } = useTradingContext()
  const [maxPositionPct, setMaxPositionPct] = useState(10)
  const [winRate, setWinRate] = useState(55)
  const [winLossRatio, setWinLossRatio] = useState(1.5)
  const [lastUpdated] = useState<Date | null>(new Date())

  const portfolioValue = account ? parseFloat(account.portfolio_value) : 0
  const maxPositionValue = (maxPositionPct / 100) * portfolioValue

  // Kelly Criterion: f = (win_rate * ratio - (1 - win_rate)) / ratio
  const wr = winRate / 100
  const kellyFraction = Math.max(0, (wr * winLossRatio - (1 - wr)) / winLossRatio)
  const kellyPositionSize = kellyFraction * portfolioValue
  const exceedsLimit = kellyPositionSize > maxPositionValue && maxPositionValue > 0

  // Compute current usage from real positions
  const symbolLimitsWithUsage = SYMBOL_LIMITS.map((limit) => {
    const pos = positions.find((p) => p.symbol === limit.symbol)
    const posValue = pos ? Math.abs(parseFloat(String(pos.market_value))) : 0
    const currentUsage = limit.maxValue > 0 ? Math.round((posValue / limit.maxValue) * 100) : 0
    return { ...limit, currentUsage: Math.min(currentUsage, 100) }
  })

  // Compute portfolio allocation from real positions
  const allocationData = positions.length > 0
    ? (() => {
        const total = positions.reduce((s, p) => s + Math.abs(parseFloat(String(p.market_value))), 0)
        const colors = ['#58a6ff', '#3fb950', '#f85149', '#e3b341', '#bc8cff', '#f0883e']
        const items = positions.map((p, i) => ({
          symbol: p.symbol,
          pct: total > 0 ? Math.round((Math.abs(parseFloat(String(p.market_value))) / (portfolioValue || total)) * 100) : 0,
          color: colors[i % colors.length],
        }))
        const invested = items.reduce((s, i) => s + i.pct, 0)
        if (invested < 100) {
          items.push({ symbol: 'Cash', pct: 100 - invested, color: '#8b949e' })
        }
        return items
      })()
    : [{ symbol: 'Cash', pct: 100, color: '#8b949e' }]

  const cardStyle: React.CSSProperties = {
    backgroundColor: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: 8,
    padding: 24,
  }

  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Position Sizing</h2>
        <DataFreshness lastUpdated={lastUpdated} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        {/* Max Position Size Slider */}
        <div style={cardStyle}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>
            Max Position Size
          </h3>
          <div style={{ fontSize: 36, fontWeight: 700, color: 'var(--blue, #58a6ff)', marginBottom: 4 }}>
            {maxPositionPct}%
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted, #8b949e)', marginBottom: 16 }}>
            ${maxPositionValue.toLocaleString(undefined, { maximumFractionDigits: 0 })} of ${portfolioValue.toLocaleString(undefined, { maximumFractionDigits: 0 })} portfolio
          </div>
          <input
            type="range"
            min={1}
            max={25}
            value={maxPositionPct}
            onChange={e => setMaxPositionPct(Number(e.target.value))}
            style={{
              width: '100%',
              accentColor: '#58a6ff',
              cursor: 'pointer',
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted, #8b949e)', marginTop: 4 }}>
            <span>1%</span>
            <span>25%</span>
          </div>
        </div>

        {/* Kelly Criterion Calculator */}
        <div style={cardStyle}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>
            Kelly Criterion Calculator
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)', display: 'block', marginBottom: 4 }}>
                Win Rate (%)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={winRate}
                onChange={e => setWinRate(Number(e.target.value))}
                style={{
                  width: '100%', padding: '8px 12px', borderRadius: 6,
                  border: '1px solid var(--border, #30363d)',
                  backgroundColor: 'var(--bg-tertiary, #21262d)',
                  color: 'var(--text-primary, #e6edf3)', fontSize: 14,
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)', display: 'block', marginBottom: 4 }}>
                Win/Loss Ratio
              </label>
              <input
                type="number"
                min={0}
                step={0.1}
                value={winLossRatio}
                onChange={e => setWinLossRatio(Number(e.target.value))}
                style={{
                  width: '100%', padding: '8px 12px', borderRadius: 6,
                  border: '1px solid var(--border, #30363d)',
                  backgroundColor: 'var(--bg-tertiary, #21262d)',
                  color: 'var(--text-primary, #e6edf3)', fontSize: 14,
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{
              backgroundColor: 'var(--bg-tertiary, #21262d)',
              borderRadius: 6, padding: 12, marginTop: 4,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)' }}>Optimal Fraction</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--blue, #58a6ff)' }}>
                  {(kellyFraction * 100).toFixed(1)}%
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)' }}>Recommended Size</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: exceedsLimit ? '#e3b341' : '#3fb950' }}>
                  ${kellyPositionSize.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
              </div>
              {exceedsLimit && (
                <div style={{
                  fontSize: 11, color: '#e3b341', marginTop: 8,
                  padding: '6px 8px', backgroundColor: 'rgba(227,179,65,0.1)', borderRadius: 4,
                }}>
                  Kelly recommends ${kellyPositionSize.toLocaleString(undefined, { maximumFractionDigits: 0 })} but your max position limit is ${maxPositionValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}. The system will cap at ${maxPositionValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Per-Symbol Position Limits */}
      <div style={{ ...cardStyle, marginBottom: 20 }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>
          Per-Symbol Position Limits
        </h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--bg-tertiary, #21262d)' }}>
              {['Symbol', 'Max Shares', 'Max $ Value', 'Current Usage'].map(h => (
                <th key={h} style={{
                  padding: '10px 16px', textAlign: 'left', fontWeight: 600,
                  color: 'var(--text-muted, #8b949e)', fontSize: 12,
                  borderBottom: '1px solid var(--border, #30363d)',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbolLimitsWithUsage.map(row => (
              <tr key={row.symbol}>
                <td style={{ padding: '10px 16px', fontWeight: 700, color: 'var(--blue, #58a6ff)', borderBottom: '1px solid var(--border, #30363d)' }}>
                  {row.symbol}
                </td>
                <td style={{ padding: '10px 16px', borderBottom: '1px solid var(--border, #30363d)' }}>
                  {row.maxShares.toLocaleString()}
                </td>
                <td style={{ padding: '10px 16px', borderBottom: '1px solid var(--border, #30363d)' }}>
                  ${row.maxValue.toLocaleString()}
                </td>
                <td style={{ padding: '10px 16px', borderBottom: '1px solid var(--border, #30363d)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ flex: 1, height: 6, borderRadius: 3, backgroundColor: 'var(--bg-tertiary, #21262d)', overflow: 'hidden' }}>
                      <div style={{
                        width: `${row.currentUsage}%`, height: '100%', borderRadius: 3,
                        backgroundColor: row.currentUsage > 75 ? '#f85149' : row.currentUsage > 50 ? '#e3b341' : '#3fb950',
                      }} />
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted, #8b949e)', minWidth: 36, textAlign: 'right' }}>
                      {row.currentUsage}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Portfolio Allocation */}
      <div style={cardStyle}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>
          Current Portfolio Allocation
        </h3>
        {positions.length === 0 ? (
          <div style={{ color: 'var(--text-muted, #8b949e)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
            No open positions
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', height: 32, borderRadius: 6, overflow: 'hidden', marginBottom: 16 }}>
              {allocationData.map(d => (
                <div key={d.symbol} style={{ width: `${d.pct}%`, backgroundColor: d.color, position: 'relative' }} title={`${d.symbol}: ${d.pct}%`} />
              ))}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
              {allocationData.map(d => (
                <div key={d.symbol} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: d.color }} />
                  <span style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)' }}>{d.symbol}</span>
                  <span style={{ fontSize: 12, fontWeight: 600 }}>{d.pct}%</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default PositionSizingView
