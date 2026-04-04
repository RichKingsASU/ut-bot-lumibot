import React, { useState, useEffect } from 'react'
import { supabase } from '../../../lib/supabaseClient'

const colors = {
  bgPrimary: '#0d1117',
  bgSecondary: '#161b22',
  border: '#30363d',
  textPrimary: '#e6edf3',
  textMuted: '#8b949e',
  blue: '#58a6ff',
  green: '#3fb950',
  red: '#f85149',
}

interface TableStat {
  symbol: string
  timeframe: string
  count: number
  latest: string
}

export default function EquitiesMonitorView() {
  const [tableStats, setTableStats] = useState<TableStat[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      const symbols = ['IWM', 'SPY', 'QQQ']
      const timeframes = ['1Min', '15Min']
      const stats: TableStat[] = []

      for (const symbol of symbols) {
        for (const tf of timeframes) {
          const { count } = await supabase
            .from('ohlcv_bars')
            .select('*', { count: 'exact', head: true })
            .eq('symbol', symbol)
            .eq('timeframe', tf)

          const { data: latest } = await supabase
            .from('ohlcv_bars')
            .select('ts')
            .eq('symbol', symbol)
            .eq('timeframe', tf)
            .order('ts', { ascending: false })
            .limit(1)
            .single()

          stats.push({
            symbol,
            timeframe: tf,
            count: count || 0,
            latest: latest?.ts
              ? new Date(latest.ts).toLocaleString()
              : 'No data',
          })
        }
      }
      setTableStats(stats)
      setLoading(false)
    }

    fetchStats()
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div style={{ fontSize: 18, fontWeight: 600, color: colors.textPrimary }}>
          Equities — Data Monitor
        </div>
        <span style={{ fontSize: 12, color: colors.textMuted }}>Refreshes every 30s</span>
      </div>

      {/* Market Hours Banner */}
      <div style={{
        marginBottom: 16,
        padding: 12,
        backgroundColor: 'rgba(88,166,255,0.08)',
        border: '1px solid rgba(88,166,255,0.2)',
        borderRadius: 8,
      }}>
        <span style={{ fontSize: 12, color: colors.blue }}>
          Equities bot runs during market hours only — Mon–Fri 9:30 AM – 4:00 PM ET
        </span>
      </div>

      {loading ? (
        <div style={{ fontSize: 13, color: colors.textMuted }}>Loading data stats...</div>
      ) : (
        <div style={{
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          overflow: 'hidden',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Symbol', 'Timeframe', 'Bar Count', 'Latest Bar', 'Status'].map(h => (
                  <th key={h} style={{
                    textAlign: 'left',
                    padding: '12px 16px',
                    fontSize: 11,
                    color: colors.textMuted,
                    borderBottom: `1px solid ${colors.border}`,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    fontWeight: 500,
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableStats.map((row, i) => {
                const isStale = row.latest === 'No data' ||
                  (new Date().getTime() - new Date(row.latest).getTime()) > 3600000
                return (
                  <tr key={i} style={{ borderBottom: `1px solid ${colors.border}` }}>
                    <td style={{ padding: '10px 16px', fontWeight: 500, color: colors.textPrimary }}>{row.symbol}</td>
                    <td style={{ padding: '10px 16px', color: colors.textMuted }}>{row.timeframe}</td>
                    <td style={{ padding: '10px 16px', color: colors.textPrimary }}>{row.count.toLocaleString()}</td>
                    <td style={{ padding: '10px 16px', color: colors.textMuted }}>{row.latest}</td>
                    <td style={{ padding: '10px 16px' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        backgroundColor: isStale ? 'rgba(248,81,73,0.12)' : 'rgba(63,185,80,0.12)',
                        color: isStale ? colors.red : colors.green,
                      }}>
                        <span style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          backgroundColor: isStale ? colors.red : colors.green,
                        }} />
                        {isStale ? 'Stale' : 'Fresh'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
