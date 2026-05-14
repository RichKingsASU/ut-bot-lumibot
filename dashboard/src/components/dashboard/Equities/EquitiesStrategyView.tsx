import React from 'react'
import { useTradingContext } from '../../../context/TradingContext'
import { formatTimestamp } from '../../../lib/time'
import { PageHeader } from '../../ui/PageHeader'

const colors = {
  bgPrimary: '#0d1117',
  bgSecondary: '#161b22',
  bgTertiary: '#21262d',
  border: '#30363d',
  textPrimary: '#e6edf3',
  textMuted: '#8b949e',
  blue: '#58a6ff',
  green: '#3fb950',
  red: '#f85149',
  amber: '#e3b341',
}

const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export default function EquitiesStrategyView() {
  const { symbol, timeframe, signals, botStatus, loading } = useTradingContext()

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: colors.textMuted }}>
        Loading strategy data...
      </div>
    )
  }

  const statusLabel = botStatus.online
    ? botStatus.status === 'online'
      ? 'ACTIVE'
      : 'PAUSED'
    : 'STOPPED'

  const statusColor =
    statusLabel === 'ACTIVE' ? colors.green : statusLabel === 'PAUSED' ? colors.amber : colors.red

  const parameters = [
    { label: 'ATR Period', value: '14' },
    { label: 'Sensitivity', value: '2.0' },
    { label: 'Timeframe', value: timeframe },
    { label: 'Symbol', value: symbol },
  ]

  const allSignals = [...signals].reverse()

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary }}>
      <PageHeader title="Strategy config" subtitle="UT Bot ATR Trailing Stop" />
      {/* Strategy Header */}
      <div
        style={{
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: 24,
          marginBottom: 24,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: colors.textPrimary, marginBottom: 6 }}>
            UT Bot ATR Trailing Stop
          </div>
          <div style={{ fontSize: 13, color: colors.textMuted, maxWidth: 600, lineHeight: 1.6 }}>
            Automated trading strategy using ATR-based trailing stops to identify trend reversals.
            Generates BUY and SELL signals based on price crossing the dynamic trailing stop level.
          </div>
        </div>
        <span
          style={{
            display: 'inline-block',
            padding: '6px 16px',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: 1,
            backgroundColor: `${statusColor}22`,
            color: statusColor,
            border: `1px solid ${statusColor}44`,
          }}
        >
          {statusLabel}
        </span>
      </div>

      {/* Parameters Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
          marginBottom: 24,
        }}
      >
        {parameters.map((param) => (
          <div
            key={param.label}
            style={{
              backgroundColor: colors.bgSecondary,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              padding: 18,
            }}
          >
            <div
              style={{
                fontSize: 11,
                color: colors.textMuted,
                marginBottom: 6,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
              }}
            >
              {param.label}
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, color: colors.textPrimary }}>
              {param.value}
            </div>
          </div>
        ))}
      </div>

      {/* Signal History + Strategy Info row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 16 }}>
        {/* Signal History Table */}
        <div
          style={{
            backgroundColor: colors.bgSecondary,
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            maxHeight: 480,
          }}
        >
          <div
            style={{
              padding: '14px 20px',
              fontSize: 14,
              fontWeight: 600,
              color: colors.textPrimary,
              borderBottom: `1px solid ${colors.border}`,
              flexShrink: 0,
            }}
          >
            Signal History
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Time', 'Type', 'Price'].map((h) => (
                    <th
                      key={h}
                      style={{
                        position: 'sticky',
                        top: 0,
                        textAlign: 'left',
                        padding: '10px 16px',
                        fontSize: 11,
                        color: colors.textMuted,
                        borderBottom: `1px solid ${colors.border}`,
                        backgroundColor: colors.bgSecondary,
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allSignals.length === 0 && (
                  <tr>
                    <td colSpan={3} style={{ padding: 24, color: colors.textMuted, textAlign: 'center', fontSize: 13 }}>
                      No signals recorded yet
                    </td>
                  </tr>
                )}
                {allSignals.map((sig, i) => (
                  <tr key={`${sig.index}-${i}`}>
                    <td style={{ padding: '8px 16px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                      {formatTimestamp(sig.time)}
                    </td>
                    <td style={{ padding: '8px 16px', borderBottom: `1px solid ${colors.border}` }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 10px',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 600,
                          backgroundColor: sig.type === 'BUY' ? `${colors.green}22` : `${colors.red}22`,
                          color: sig.type === 'BUY' ? colors.green : colors.red,
                        }}
                      >
                        {sig.type}
                      </span>
                    </td>
                    <td style={{ padding: '8px 16px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                      {currency.format(sig.price)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Strategy Info Card */}
        <div
          style={{
            backgroundColor: colors.bgSecondary,
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            padding: 24,
            alignSelf: 'flex-start',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 16 }}>
            About This Strategy
          </div>
          <div style={{ fontSize: 13, color: colors.textMuted, lineHeight: 1.7 }}>
            <p style={{ margin: '0 0 12px 0' }}>
              The <strong style={{ color: colors.textPrimary }}>UT Bot ATR Trailing Stop</strong> strategy
              uses the Average True Range (ATR) indicator to dynamically calculate trailing stop levels
              that adapt to market volatility.
            </p>
            <p style={{ margin: '0 0 12px 0' }}>
              When price crosses above the trailing stop, a <strong style={{ color: colors.green }}>BUY</strong> signal
              is generated. When price crosses below, a <strong style={{ color: colors.red }}>SELL</strong> signal
              is triggered.
            </p>
            <p style={{ margin: '0 0 12px 0' }}>
              The ATR period (default 14) determines how many candles are used to calculate volatility,
              while the sensitivity multiplier (default 2.0) controls how far the trailing stop sits from
              the current price.
            </p>
            <p style={{ margin: 0 }}>
              This strategy works best in trending markets and is designed to let winners run while cutting
              losses quickly through its adaptive stop-loss mechanism.
            </p>
          </div>

          <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${colors.border}` }}>
            <div style={{ fontSize: 11, color: colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
              Last Signal
            </div>
            <div style={{ fontSize: 13, color: colors.textPrimary }}>
              {botStatus.last_signal
                ? `${botStatus.last_signal} at ${botStatus.last_signal_time || 'N/A'}`
                : 'No signals yet'}
            </div>
          </div>

          <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${colors.border}` }}>
            <div style={{ fontSize: 11, color: colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
              Uptime
            </div>
            <div style={{ fontSize: 13, color: colors.textPrimary }}>
              {botStatus.uptime_seconds != null
                ? `${Math.floor(botStatus.uptime_seconds / 3600)}h ${Math.floor((botStatus.uptime_seconds % 3600) / 60)}m`
                : 'Offline'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
