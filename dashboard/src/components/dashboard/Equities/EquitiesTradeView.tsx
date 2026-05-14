import React from 'react'
import { useTradingContext } from '../../../context/TradingContext'
import { formatTimestamp } from '../../../lib/time'
import { PageHeader } from '../../ui/PageHeader'
import { PriceChart } from '../../ui/PriceChart'
import { useAlpacaBars } from '../../../hooks/useAlpacaBars'

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

const SYMBOLS = ['IWM', 'SPY', 'QQQ']

export default function EquitiesTradeView() {
  const {
    symbol,
    setSymbol,
    timeframe,
    isInTrade,
    activePosition,
    signals,
    loading,
  } = useTradingContext()

  const recentSignals = [...signals].reverse().slice(0, 20)
  const { bars: chartBars } = useAlpacaBars(symbol, timeframe || '15Min', 200)

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: colors.textMuted }}>
        Loading trade data...
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: colors.bgPrimary }}>
      <div style={{ padding: '20px 24px 0' }}>
        <PageHeader title="Equities trading" subtitle="IWM · SPY · QQQ" />
      </div>
      {/* Symbol Tabs */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          borderBottom: `1px solid ${colors.border}`,
          backgroundColor: colors.bgSecondary,
          flexShrink: 0,
        }}
      >
        {SYMBOLS.map((sym) => (
          <button
            key={sym}
            onClick={() => setSymbol(sym)}
            style={{
              padding: '12px 28px',
              fontSize: 13,
              fontWeight: 600,
              color: sym === symbol ? colors.blue : colors.textMuted,
              backgroundColor: 'transparent',
              border: 'none',
              borderBottom: sym === symbol ? `2px solid ${colors.blue}` : '2px solid transparent',
              cursor: 'pointer',
              transition: 'color 0.15s',
            }}
          >
            {sym}
          </button>
        ))}
      </div>

      {/* Main content: chart + position panel */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Chart Area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div
            style={{
              flex: 1,
              backgroundColor: colors.bgSecondary,
              margin: 16,
              marginRight: 0,
              borderRadius: 8,
              border: `1px solid ${colors.border}`,
              padding: 12,
              minHeight: 320,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 8, fontWeight: 600 }}>
              {symbol} · {timeframe || '15Min'}
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <PriceChart bars={chartBars} symbol={symbol} height={320} />
            </div>
          </div>

          {/* Signal Log */}
          <div
            style={{
              height: 220,
              flexShrink: 0,
              margin: '0 16px 16px 16px',
              marginRight: 0,
              backgroundColor: colors.bgSecondary,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div
              style={{
                padding: '12px 16px',
                fontSize: 13,
                fontWeight: 600,
                color: colors.textPrimary,
                borderBottom: `1px solid ${colors.border}`,
                flexShrink: 0,
              }}
            >
              Signal Log
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
                          padding: '8px 12px',
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
                  {recentSignals.length === 0 && (
                    <tr>
                      <td colSpan={3} style={{ padding: 16, color: colors.textMuted, textAlign: 'center', fontSize: 13 }}>
                        No signals yet
                      </td>
                    </tr>
                  )}
                  {recentSignals.map((sig, i) => (
                    <tr key={`${sig.index}-${i}`}>
                      <td style={{ padding: '6px 12px', fontSize: 12, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                        {formatTimestamp(sig.time, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </td>
                      <td style={{ padding: '6px 12px', borderBottom: `1px solid ${colors.border}` }}>
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
                      <td style={{ padding: '6px 12px', fontSize: 12, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                        {currency.format(sig.price)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Position Panel */}
        <div
          style={{
            width: 280,
            flexShrink: 0,
            backgroundColor: colors.bgSecondary,
            borderLeft: `1px solid ${colors.border}`,
            padding: 20,
            margin: '16px 16px 16px 16px',
            borderRadius: 8,
            border: `1px solid ${colors.border}`,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 20 }}>
            Position
          </div>

          {isInTrade && activePosition ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div
                style={{
                  display: 'inline-flex',
                  alignSelf: 'flex-start',
                  padding: '4px 12px',
                  borderRadius: 4,
                  fontSize: 12,
                  fontWeight: 600,
                  backgroundColor: activePosition.side === 'long' ? `${colors.green}22` : `${colors.red}22`,
                  color: activePosition.side === 'long' ? colors.green : colors.red,
                  textTransform: 'uppercase',
                }}
              >
                {activePosition.side}
              </div>

              {[
                { label: 'Symbol', value: activePosition.symbol },
                { label: 'Quantity', value: activePosition.qty },
                { label: 'Entry Price', value: currency.format(parseFloat(activePosition.avg_entry_price)) },
                { label: 'Current Price', value: currency.format(parseFloat(activePosition.current_price)) },
                {
                  label: 'Unrealized P&L',
                  value: currency.format(parseFloat(activePosition.unrealized_pl)),
                  color: parseFloat(activePosition.unrealized_pl) >= 0 ? colors.green : colors.red,
                },
                { label: 'Market Value', value: currency.format(parseFloat(activePosition.market_value)) },
              ].map((row) => (
                <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 12, color: colors.textMuted }}>{row.label}</span>
                  <span style={{ fontSize: 13, fontWeight: 500, color: row.color || colors.textPrimary }}>
                    {row.value}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textMuted, fontSize: 13 }}>
              No active position
            </div>
          )}

          {isInTrade && activePosition && (
            <div style={{ marginTop: 'auto', paddingTop: 20, borderTop: `1px solid ${colors.border}` }}>
              <button
                onClick={async () => {
                  if (window.confirm('EMERGENCY: Are you sure you want to CANCEL all orders and CLOSE all positions?')) {
                    const storedKey = localStorage.getItem('ADMIN_API_KEY');
                    if (!storedKey) {
                      alert('Error: Admin API Key not found in local storage. Please set it in System Settings.');
                      return;
                    }

                    try {
                      const res = await fetch('/.netlify/functions/alpaca-flatten', {
                        method: 'POST',
                        headers: { 'x-admin-api-key': storedKey }
                      });
                      if (res.ok) {
                        alert('Emergency flatten initiated successfully.');
                      } else {
                        const errData = await res.json();
                        alert(`Failed to initiate flatten: ${errData.error || res.statusText}`);
                      }
                    } catch (e) {
                      console.error('Flatten error:', e);
                      alert('Network error while initiating flatten.');
                    }
                  }
                }}
                style={{
                  width: '100%',
                  padding: '12px',
                  backgroundColor: `${colors.red}22`,
                  color: colors.red,
                  border: `1px solid ${colors.red}44`,
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseOver={(e) => (e.currentTarget.style.backgroundColor = `${colors.red}33`)}
                onMouseOut={(e) => (e.currentTarget.style.backgroundColor = `${colors.red}22`)}
              >
                FLATTEN ALL POSITIONS
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
