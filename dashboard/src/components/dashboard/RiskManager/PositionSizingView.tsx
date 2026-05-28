import React, { useState, useEffect } from 'react'
import { useTradingContext } from '../../../context/TradingContext'
import { DataFreshness } from '../../DataFreshness'
import { PageHeader } from '../../ui/PageHeader'
import { supabase } from '../../../lib/supabaseClient'
import { ShieldAlert, Info, TrendingUp } from 'lucide-react'

interface KellyRow {
  symbol: string
  assetClass: string
  lastSignal: string
  confidence: number
  kellyPct: number
  suggestedSize: number
  capped: boolean
  warning: boolean
}

const PositionSizingView: React.FC = () => {
  const { account } = useTradingContext()
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [kellyRows, setKellyRows] = useState<KellyRow[]>([])
  const [loading, setLoading] = useState(true)

  const portfolioValue = account ? parseFloat(account.portfolio_value || account.equity) : 100000

  useEffect(() => {
    let cancelled = false

    async function fetchKellyData() {
      try {
        setLoading(true)
        // 1. Fetch latest regime state
        const { data: regimeRow } = await supabase
          .from('regime_states')
          .select('regime')
          .order('detected_at', { ascending: false })
          .limit(1)
          .maybeSingle()

        const regime = String(regimeRow?.regime || 'QUIET').toUpperCase()
        let regimeScalar = 0.8
        if (regime === 'BULL') regimeScalar = 1.0
        else if (regime === 'QUIET') regimeScalar = 0.8
        else if (regime === 'VOLATILE') regimeScalar = 0.6
        else if (regime === 'BEAR') regimeScalar = 0.4

        // 2. Fetch agent signals where action != 'HOLD' limit 20
        const { data: signals } = await supabase
          .from('agent_signals')
          .select('symbol, action, confidence, created_at, asset_class')
          .neq('action', 'HOLD')
          .order('created_at', { ascending: false })
          .limit(40)

        if (cancelled) return

        // Group by symbol, take latest
        const latestBySymbol: Record<string, any> = {}
        if (signals) {
          for (const s of signals) {
            if (!latestBySymbol[s.symbol]) {
              latestBySymbol[s.symbol] = s
            }
          }
        }

        const rows: KellyRow[] = Object.keys(latestBySymbol).map((sym) => {
          const s = latestBySymbol[sym]
          const confidence = s.confidence ? Number(s.confidence) : 0.5
          // Suggested Size = account_equity * (confidence * 0.25 * regime_scalar)
          const rawSize = portfolioValue * (confidence * 0.25 * regimeScalar)
          const limitCap = 2500
          const suggestedSize = Math.min(rawSize, limitCap)
          const capped = rawSize > limitCap
          const warning = rawSize > limitCap

          // Kelly % = (confidence * 0.25 * regime_scalar) * 100
          const kellyPct = confidence * 0.25 * regimeScalar * 100

          return {
            symbol: sym,
            assetClass: String(s.asset_class || 'Equities').toUpperCase(),
            lastSignal: String(s.action || 'BUY'),
            confidence,
            kellyPct,
            suggestedSize,
            capped,
            warning,
          }
        })

        setKellyRows(rows)
        setLastUpdated(new Date())
      } catch (err) {
        console.error('Failed to fetch Kelly position sizing data:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchKellyData()
    return () => {
      cancelled = true
    }
  }, [portfolioValue])

  const cardStyle: React.CSSProperties = {
    backgroundColor: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: 8,
    padding: 24,
  }

  const tableHeaderStyle: React.CSSProperties = {
    padding: '12px 16px',
    textAlign: 'left',
    fontWeight: 600,
    color: 'var(--text-muted, #8b949e)',
    fontSize: 11,
    borderBottom: '1px solid var(--border, #30363d)',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  }

  const tableCellStyle: React.CSSProperties = {
    padding: '14px 16px',
    fontSize: 13,
    borderBottom: '1px solid var(--border, #30363d)',
    color: 'var(--text-primary, #e6edf3)',
  }

  // Any warning row to display
  const warnings = kellyRows.filter(r => r.warning)

  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      <PageHeader
        title="Risk position sizing"
        subtitle="Live Kelly sizing & guidelines"
        actions={<DataFreshness lastUpdated={lastUpdated} />}
      />

      {/* Warnings area */}
      {warnings.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
          {warnings.map((w) => {
            const rawRec = portfolioValue * (w.confidence * 0.25 * 0.8) // approx raw sizing
            return (
              <div
                key={w.symbol}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '12px 16px',
                  backgroundColor: 'rgba(240, 136, 62, 0.10)',
                  border: '1px solid rgba(240, 136, 62, 0.35)',
                  borderRadius: 8,
                  fontSize: 13,
                  color: 'var(--orange, #f0883e)',
                }}
              >
                <ShieldAlert size={18} />
                <span>
                  <strong>Warning:</strong> Kelly recommends <strong>${Math.round(rawRec).toLocaleString()}</strong> for <strong>{w.symbol}</strong> but max position limit is <strong>$2,500</strong>. Sizing will be capped.
                </span>
              </div>
            )
          })}
        </div>
      )}

      {/* Main position sizing panel containing the live Kelly sizing table */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
            Live Kelly Sizing Table
          </h3>
          <span style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Info size={14} /> Account equity: ${Math.round(portfolioValue).toLocaleString()}
          </span>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted, #8b949e)' }}>
            Loading live signals and calculating sizing...
          </div>
        ) : kellyRows.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted, #8b949e)', border: '1px dashed var(--border, #30363d)', borderRadius: 8 }}>
            No recent active signals found. Complete an intelligence cycle to generate sizing.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-tertiary, #21262d)' }}>
                  <th style={tableHeaderStyle}>Symbol</th>
                  <th style={tableHeaderStyle}>Asset Class</th>
                  <th style={tableHeaderStyle}>Last Signal</th>
                  <th style={tableHeaderStyle}>Kelly %</th>
                  <th style={tableHeaderStyle}>Suggested $ Size</th>
                </tr>
              </thead>
              <tbody>
                {kellyRows.map((row) => (
                  <tr key={row.symbol} style={{ transition: 'background-color 0.15s' }}>
                    <td style={{ ...tableCellStyle, fontWeight: 700, color: 'var(--blue, #58a6ff)' }}>
                      {row.symbol}
                    </td>
                    <td style={tableCellStyle}>
                      {row.assetClass}
                    </td>
                    <td style={tableCellStyle}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 600,
                          backgroundColor: row.lastSignal === 'BUY' ? 'rgba(63, 185, 80, 0.15)' : 'rgba(248, 81, 73, 0.15)',
                          color: row.lastSignal === 'BUY' ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                        }}
                      >
                        {row.lastSignal}
                      </span>
                    </td>
                    <td style={{ ...tableCellStyle, fontFamily: 'monospace' }}>
                      {row.kellyPct.toFixed(2)}%
                    </td>
                    <td style={{ ...tableCellStyle, fontWeight: 600 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ color: row.capped ? 'var(--orange, #f0883e)' : 'var(--green, #3fb950)' }}>
                          ${row.suggestedSize.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </span>
                        {row.capped && (
                          <span style={{ fontSize: 10, color: 'var(--text-muted, #8b949e)', fontStyle: 'italic' }}>
                            (capped at limit)
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Sizing Methodology Info */}
      <div style={{ ...cardStyle, marginTop: 24 }}>
        <h4 style={{ margin: '0 0 12px 0', fontSize: 14, fontWeight: 600 }}>Sizing Methodology & Rules</h4>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted, #8b949e)', lineHeight: 1.6 }}>
          Recommended sizes are computed programmatically using the latest <strong>confidence levels</strong> from our multi-agent debates, scaled by a <strong>regime multiplier</strong> based on HMM state (Bull = 1.0x, Quiet = 0.8x, Volatile = 0.6x, Bear = 0.4x). All active positions are strictly capped at a max safety guard threshold of <strong>$2,500.00</strong> to guarantee capital protection in high volatility environments.
        </p>
      </div>
    </div>
  )
}

export default PositionSizingView

