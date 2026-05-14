import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { PageHeader } from '../../ui/PageHeader'
import { PriceChart, type PriceChartBar } from '../../ui/PriceChart'
import { supabase } from '../../../lib/supabaseClient'
import { formatSharpe } from '../../../lib/metrics'

interface StrategyOption {
  id: string
  name: string
  filename?: string
}

interface BacktestRun {
  id: string
  strategyName: string
  symbol: string
  startDate: string
  endDate: string
  totalReturn: number | null
  sharpe: number | null
  maxDrawdown: number | null
  totalTrades: number | null
  winRate: number | null
  equityCurve: PriceChartBar[]
  runAt: string
}

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

const DEFAULT_STRATEGIES: StrategyOption[] = [
  { id: 'ut-bot-v2', name: 'UT Bot Scalper V2', filename: 'ut_bot_scalper_v2.py' },
  { id: 'ema-crossover', name: 'EMA Crossover', filename: 'ema_crossover.py' },
  { id: 'btc-momentum', name: 'BTC Momentum', filename: 'btc_momentum.py' },
  { id: 'rsi-reversion', name: 'RSI Mean Reversion', filename: 'rsi_mean_reversion.py' },
]

const SYMBOLS = ['IWM', 'SPY', 'QQQ', 'BTC/USD', 'ETH/USD']

function tabBtnStyle(active: boolean): React.CSSProperties {
  return {
    padding: '8px 16px',
    fontSize: 13,
    fontWeight: 600,
    background: 'transparent',
    border: 'none',
    color: active ? colors.blue : colors.textMuted,
    borderBottom: active ? `2px solid ${colors.blue}` : '2px solid transparent',
    cursor: 'pointer',
    transition: 'color 0.15s',
  }
}

export default function BacktestView() {
  const navigate = useNavigate()
  const location = useLocation()
  const [strategies, setStrategies] = useState<StrategyOption[]>(DEFAULT_STRATEGIES)
  const [strategyId, setStrategyId] = useState<string>(DEFAULT_STRATEGIES[0].id)
  const [symbol, setSymbol] = useState<string>('IWM')
  const [startDate, setStartDate] = useState<string>('2025-01-01')
  const [endDate, setEndDate] = useState<string>(new Date().toISOString().split('T')[0])
  const [running, setRunning] = useState(false)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [latest, setLatest] = useState<BacktestRun | null>(null)
  const [history, setHistory] = useState<BacktestRun[]>([])

  useEffect(() => {
    let cancelled = false
    async function loadStrategies() {
      try {
        const { data, error } = await supabase
          .from('strategies')
          .select('id, name, filename')
          .order('name', { ascending: true })
        if (cancelled || error || !data || data.length === 0) return
        setStrategies(
          data.map((r: { id: string | number; name: string; filename?: string }) => ({
            id: String(r.id),
            name: r.name,
            filename: r.filename,
          })),
        )
      } catch {
        // Use defaults
      }
    }
    void loadStrategies()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadHistory() {
      try {
        const { data, error } = await supabase
          .from('backtest_results')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(20)
        if (cancelled || error || !data) return
        const rows: BacktestRun[] = data.map(
          (r: Record<string, unknown>): BacktestRun => ({
            id: String(r.id ?? r.created_at ?? Math.random()),
            strategyName: String(r.strategy_name ?? r.strategyName ?? '—'),
            symbol: String(r.symbol ?? '—'),
            startDate: String(r.start_date ?? r.startDate ?? ''),
            endDate: String(r.end_date ?? r.endDate ?? ''),
            totalReturn: typeof r.total_return === 'number' ? r.total_return : null,
            sharpe: typeof r.sharpe === 'number' ? r.sharpe : null,
            maxDrawdown: typeof r.max_drawdown === 'number' ? r.max_drawdown : null,
            totalTrades: typeof r.total_trades === 'number' ? r.total_trades : null,
            winRate: typeof r.win_rate === 'number' ? r.win_rate : null,
            equityCurve: [],
            runAt: String(r.created_at ?? new Date().toISOString()),
          }),
        )
        setHistory(rows)
      } catch {
        // history stays in local session state
      }
    }
    void loadHistory()
    return () => {
      cancelled = true
    }
  }, [])

  const handleRun = useCallback(async () => {
    setRunning(true)
    setStatusMsg(null)
    const strategy = strategies.find((s) => s.id === strategyId) || strategies[0]

    try {
      const res = await fetch('/.netlify/functions/run-backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategyId: strategy.id,
          symbol,
          startDate,
          endDate,
        }),
      })
      if (!res.ok) throw new Error(`run-backtest returned ${res.status}`)
      const data = await res.json()
      if (data?.error) throw new Error(data.error)

      const run: BacktestRun = {
        id: String(data.id ?? `${Date.now()}`),
        strategyName: strategy.name,
        symbol,
        startDate,
        endDate,
        totalReturn: typeof data.totalReturn === 'number' ? data.totalReturn : null,
        sharpe: typeof data.sharpe === 'number' ? data.sharpe : null,
        maxDrawdown: typeof data.maxDrawdown === 'number' ? data.maxDrawdown : null,
        totalTrades: typeof data.totalTrades === 'number' ? data.totalTrades : null,
        winRate: typeof data.winRate === 'number' ? data.winRate : null,
        equityCurve: Array.isArray(data.equityCurve) ? data.equityCurve : [],
        runAt: new Date().toISOString(),
      }
      setLatest(run)
      setHistory((prev) => [run, ...prev].slice(0, 20))
    } catch (e) {
      setStatusMsg(
        e instanceof Error && e.message.includes('run-backtest')
          ? 'Backtest engine not yet connected — wire /.netlify/functions/run-backtest to enable runs.'
          : 'Backtest run failed. Check the network tab and try again.',
      )
    } finally {
      setRunning(false)
    }
  }, [strategies, strategyId, symbol, startDate, endDate])

  const fmtPct = (v: number | null) => (v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`)
  const fmtNum = (v: number | null) => (v == null ? '—' : String(v))

  const onEditorTab = location.pathname === '/strategy-lab/editor' || location.pathname === '/strategy-lab'

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary, color: colors.textPrimary }}>
      <PageHeader title="Strategy lab" subtitle="Backtest" />

      {/* Editor / Backtest tabs */}
      <div style={{ display: 'flex', gap: 4, borderBottom: `1px solid ${colors.border}`, marginBottom: 20 }}>
        <button style={tabBtnStyle(onEditorTab)} onClick={() => navigate('/strategy-lab/editor')}>
          Editor
        </button>
        <button style={tabBtnStyle(!onEditorTab)} onClick={() => navigate('/strategy-lab/backtest')}>
          Backtest
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20 }}>
        {/* Parameter panel */}
        <div style={{ backgroundColor: colors.bgSecondary, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16 }}>Configuration</div>

          <label style={{ fontSize: 11, color: colors.textMuted, display: 'block', marginBottom: 4 }}>Strategy</label>
          <select
            value={strategyId}
            onChange={(e) => setStrategyId(e.target.value)}
            style={{
              width: '100%', padding: '8px 10px', fontSize: 13,
              background: colors.bgTertiary, color: colors.textPrimary,
              border: `1px solid ${colors.border}`, borderRadius: 6, marginBottom: 14,
            }}
          >
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          <label style={{ fontSize: 11, color: colors.textMuted, display: 'block', marginBottom: 4 }}>Symbol</label>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            style={{
              width: '100%', padding: '8px 10px', fontSize: 13,
              background: colors.bgTertiary, color: colors.textPrimary,
              border: `1px solid ${colors.border}`, borderRadius: 6, marginBottom: 14,
            }}
          >
            {SYMBOLS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
            <div>
              <label style={{ fontSize: 11, color: colors.textMuted, display: 'block', marginBottom: 4 }}>Start Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                style={{
                  width: '100%', padding: '8px 10px', fontSize: 13,
                  background: colors.bgTertiary, color: colors.textPrimary,
                  border: `1px solid ${colors.border}`, borderRadius: 6,
                }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: colors.textMuted, display: 'block', marginBottom: 4 }}>End Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                style={{
                  width: '100%', padding: '8px 10px', fontSize: 13,
                  background: colors.bgTertiary, color: colors.textPrimary,
                  border: `1px solid ${colors.border}`, borderRadius: 6,
                }}
              />
            </div>
          </div>

          <button
            onClick={handleRun}
            disabled={running}
            style={{
              width: '100%', padding: '10px', fontSize: 13, fontWeight: 600,
              color: '#fff', background: running ? '#1f6feb88' : '#1f6feb',
              border: 'none', borderRadius: 6, cursor: running ? 'wait' : 'pointer',
            }}
          >
            {running ? 'Running...' : 'Run Backtest'}
          </button>

          {statusMsg && (
            <div style={{ marginTop: 12, fontSize: 12, color: colors.amber, lineHeight: 1.5 }}>
              {statusMsg}
            </div>
          )}
        </div>

        {/* Results panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ backgroundColor: colors.bgSecondary, border: `1px solid ${colors.border}`, borderRadius: 8, padding: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16 }}>Latest Result</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 16 }}>
              {[
                { l: 'Total Return', v: fmtPct(latest?.totalReturn ?? null), c: (latest?.totalReturn ?? 0) >= 0 ? colors.green : colors.red },
                { l: 'Sharpe', v: formatSharpe(latest?.sharpe ?? null), c: colors.amber },
                { l: 'Max Drawdown', v: fmtPct(latest?.maxDrawdown ?? null), c: colors.red },
                { l: 'Total Trades', v: fmtNum(latest?.totalTrades ?? null), c: colors.blue },
                { l: 'Win Rate', v: latest?.winRate == null ? '—' : `${latest.winRate}%`, c: colors.green },
              ].map((card) => (
                <div key={card.l} style={{ background: colors.bgTertiary, border: `1px solid ${colors.border}`, borderRadius: 6, padding: 12 }}>
                  <div style={{ fontSize: 10, color: colors.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>{card.l}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: card.c }}>{card.v}</div>
                </div>
              ))}
            </div>

            <div style={{ fontSize: 11, color: colors.textMuted, marginBottom: 6 }}>Equity Curve</div>
            <div style={{ background: colors.bgTertiary, border: `1px solid ${colors.border}`, borderRadius: 6, padding: 8 }}>
              {latest && latest.equityCurve.length > 0 ? (
                <PriceChart bars={latest.equityCurve} symbol={latest.symbol} height={220} />
              ) : (
                <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.textMuted, fontSize: 13 }}>
                  Run a backtest to see the equity curve
                </div>
              )}
            </div>
          </div>

          {/* Run history */}
          <div style={{ backgroundColor: colors.bgSecondary, border: `1px solid ${colors.border}`, borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', fontSize: 13, fontWeight: 600, borderBottom: `1px solid ${colors.border}` }}>
              Run History
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Strategy', 'Symbol', 'Date Range', 'Return', 'Sharpe', 'Run At'].map((h) => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '10px 16px', fontSize: 11,
                      color: colors.textMuted, borderBottom: `1px solid ${colors.border}`,
                      textTransform: 'uppercase', letterSpacing: 0.5,
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: 24, textAlign: 'center', color: colors.textMuted, fontSize: 13 }}>
                      No backtest runs yet
                    </td>
                  </tr>
                )}
                {history.map((run) => (
                  <tr key={run.id}>
                    <td style={{ padding: '10px 16px', fontSize: 13, borderBottom: `1px solid ${colors.border}` }}>{run.strategyName}</td>
                    <td style={{ padding: '10px 16px', fontSize: 13, borderBottom: `1px solid ${colors.border}` }}>{run.symbol}</td>
                    <td style={{ padding: '10px 16px', fontSize: 12, color: colors.textMuted, borderBottom: `1px solid ${colors.border}` }}>
                      {run.startDate} → {run.endDate}
                    </td>
                    <td style={{ padding: '10px 16px', fontSize: 13, color: (run.totalReturn ?? 0) >= 0 ? colors.green : colors.red, borderBottom: `1px solid ${colors.border}` }}>
                      {fmtPct(run.totalReturn)}
                    </td>
                    <td style={{ padding: '10px 16px', fontSize: 13, borderBottom: `1px solid ${colors.border}` }}>
                      {formatSharpe(run.sharpe)}
                    </td>
                    <td style={{ padding: '10px 16px', fontSize: 12, color: colors.textMuted, borderBottom: `1px solid ${colors.border}` }}>
                      {new Date(run.runAt).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
