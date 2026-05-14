import React, { useState, useEffect } from 'react'
import { supabase } from '../../../lib/supabaseClient'
import { PageHeader } from '../../ui/PageHeader'

const colors = {
  bgPrimary: '#0d1117',
  bgSecondary: '#161b22',
  border: '#30363d',
  textPrimary: '#e6edf3',
  textMuted: '#8b949e',
  blue: '#58a6ff',
  green: '#3fb950',
  red: '#f85149',
  amber: '#e3b341',
}

const EQUITY_SYMBOLS = ['IWM', 'SPY', 'QQQ']
const TARGET_TIMEFRAMES = ['1Min', '5Min', '15Min', '1Hour', '1Day']

interface TableStat {
  symbol: string
  timeframe: string
  count: number
  latest: string | null
  latestRaw: number | null
}

// Some legacy backfills stored timeframe keys in lowercase ('15m', '1m').
// Treat these as equivalent to the canonical Alpaca format so the monitor
// surfaces data regardless of which ingestion path wrote the rows.
function normalizeTf(tf: string): string {
  const t = tf.toLowerCase()
  if (t === '1m'  || t === '1min'  || t === '1minute')  return '1Min'
  if (t === '5m'  || t === '5min'  || t === '5minute')  return '5Min'
  if (t === '15m' || t === '15min' || t === '15minute') return '15Min'
  if (t === '1h'  || t === '1hour' || t === '60m')      return '1Hour'
  if (t === '1d'  || t === '1day'  || t === 'day')      return '1Day'
  return tf
}

export default function EquitiesMonitorView() {
  const [tableStats, setTableStats] = useState<TableStat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastFetched, setLastFetched] = useState<Date | null>(null)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        // Pull aggregated bar inventory for the equity symbols. Using the
        // bar_inventory view sidesteps subtle timeframe key mismatches —
        // whatever timeframe values exist in ohlcv_bars surface here.
        const { data: inventoryRows, error: invErr } = await supabase
          .from('bar_inventory')
          .select('symbol, timeframe, bar_count, latest, last_ingested')
          .in('symbol', EQUITY_SYMBOLS)

        if (invErr) {
          console.error('[EquitiesMonitor] bar_inventory query failed:', invErr)
          setError(`bar_inventory query failed: ${invErr.message}`)
          setLoading(false)
          return
        }

        // Aggregate counts under canonical timeframe keys (merging legacy
        // lowercase keys like '15m' into '15Min').
        type Bucket = { count: number; latestMs: number | null }
        const bucket = new Map<string, Bucket>()
        for (const r of inventoryRows || []) {
          const key = `${r.symbol}::${normalizeTf(r.timeframe)}`
          const prev = bucket.get(key) || { count: 0, latestMs: null }
          // bar_inventory.latest is a DATE string from the view (no time component)
          const latestMs = r.last_ingested
            ? new Date(r.last_ingested).getTime()
            : r.latest
              ? new Date(r.latest).getTime()
              : null
          bucket.set(key, {
            count: prev.count + Number(r.bar_count || 0),
            latestMs:
              prev.latestMs == null
                ? latestMs
                : latestMs == null
                  ? prev.latestMs
                  : Math.max(prev.latestMs, latestMs),
          })
        }

        // For each symbol × timeframe pair, fetch the most recent bar's
        // exact ts so the "Latest Bar" column shows minute-level freshness.
        const stats: TableStat[] = []
        for (const symbol of EQUITY_SYMBOLS) {
          for (const tf of TARGET_TIMEFRAMES) {
            const b = bucket.get(`${symbol}::${tf}`) || { count: 0, latestMs: null }

            let latestRaw: number | null = b.latestMs
            if (b.count > 0) {
              const { data: latestRow } = await supabase
                .from('ohlcv_bars')
                .select('ts')
                .eq('symbol', symbol)
                .in('timeframe', [tf, tf.toLowerCase().replace('min', 'm')])
                .order('ts', { ascending: false })
                .limit(1)
                .maybeSingle()
              if (latestRow?.ts) latestRaw = new Date(latestRow.ts).getTime()
            }

            stats.push({
              symbol,
              timeframe: tf,
              count: b.count,
              latest: latestRaw ? new Date(latestRaw).toLocaleString() : 'No data',
              latestRaw,
            })
          }
        }

        setTableStats(stats)
        setError(null)
        setLastFetched(new Date())
      } catch (e: any) {
        console.error('[EquitiesMonitor] Unexpected error:', e)
        setError(e?.message || 'Unknown error fetching bar inventory')
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  const visibleStats = tableStats.filter(
    (s) => s.timeframe === '1Min' || s.timeframe === '15Min'
  )

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary }}>
      <PageHeader
        title="Bar inventory"
        subtitle="Market data health"
        actions={
          <span style={{ fontSize: 12, color: colors.textMuted }}>
            {lastFetched ? `Updated ${lastFetched.toLocaleTimeString()} · refreshes every 30s` : 'Refreshes every 30s'}
          </span>
        }
      />

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

      {error && (
        <div style={{
          marginBottom: 16,
          padding: 12,
          backgroundColor: 'rgba(248,81,73,0.08)',
          border: '1px solid rgba(248,81,73,0.3)',
          borderRadius: 8,
          color: colors.red,
          fontSize: 12,
        }}>
          {error}
        </div>
      )}

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
              {visibleStats.map((row, i) => {
                const ageMs = row.latestRaw ? Date.now() - row.latestRaw : null
                const isStale = !row.latestRaw || (ageMs != null && ageMs > 60 * 60 * 1000)
                const isEmpty = row.count === 0
                return (
                  <tr key={i} style={{ borderBottom: `1px solid ${colors.border}` }}>
                    <td style={{ padding: '10px 16px', fontWeight: 500, color: colors.textPrimary }}>{row.symbol}</td>
                    <td style={{ padding: '10px 16px', color: colors.textMuted }}>{row.timeframe}</td>
                    <td style={{ padding: '10px 16px', color: colors.textPrimary }}>{row.count.toLocaleString()}</td>
                    <td style={{ padding: '10px 16px', color: colors.textMuted }}>{row.latest || 'No data'}</td>
                    <td style={{ padding: '10px 16px' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        backgroundColor: isEmpty
                          ? 'rgba(248,81,73,0.12)'
                          : isStale
                            ? 'rgba(227,179,65,0.12)'
                            : 'rgba(63,185,80,0.12)',
                        color: isEmpty ? colors.red : isStale ? colors.amber : colors.green,
                      }}>
                        <span style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          backgroundColor: isEmpty ? colors.red : isStale ? colors.amber : colors.green,
                        }} />
                        {isEmpty ? 'No data' : isStale ? 'Stale' : 'Fresh'}
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
