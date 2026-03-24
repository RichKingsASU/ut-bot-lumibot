import React from 'react'
import type { AlpacaAccount } from '../../types/alpaca'
import { fmtCurrency, fmtPnL, fmtPercent } from '../../utils/formatters'

interface AccountOverviewProps {
  account: AlpacaAccount | null
  loading: boolean
}

export const AccountOverview: React.FC<AccountOverviewProps> = ({ account, loading }) => {
  if (loading && !account) {
    return <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>Loading account...</div>
  }
  if (!account) {
    return <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>No account data</div>
  }

  const portfolioValue = parseFloat(account.portfolio_value)
  const cash = parseFloat(account.cash)
  const buyingPower = parseFloat(account.buying_power)
  const equity = parseFloat(account.equity)
  const longMV = parseFloat(account.long_market_value)
  const unrealPl = parseFloat(account.unrealized_pl)
  const realPl = parseFloat(account.realized_pl)
  const invested = portfolioValue - cash
  const allocPct = portfolioValue > 0 ? (invested / portfolioValue) * 100 : 0

  const row = (label: string, val: string, color?: string) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{label}</span>
      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, fontWeight: 500, color: color ?? 'var(--text-primary)' }}>{val}</span>
    </div>
  )

  return (
    <div style={{ padding: '12px 12px' }}>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>PORTFOLIO VALUE</div>
        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>
          {fmtCurrency(portfolioValue)}
        </div>
      </div>

      {row('Equity', fmtCurrency(equity))}
      {row('Cash', fmtCurrency(cash))}
      {row('Buying Power', fmtCurrency(buyingPower))}
      {row('Invested', fmtCurrency(invested))}
      {row('Unrealized P&L', fmtPnL(unrealPl), unrealPl >= 0 ? 'var(--green)' : 'var(--red)')}
      {row('Realized P&L', fmtPnL(realPl), realPl >= 0 ? 'var(--green)' : 'var(--red)')}
      {row('Day Trades', String(account.daytrade_count))}

      <div style={{ marginTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>CAPITAL ALLOCATED</span>
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{allocPct.toFixed(1)}%</span>
        </div>
        <div className="progress-bar">
          <div className="progress-bar-fill" style={{ width: `${Math.min(allocPct, 100)}%`, background: allocPct > 80 ? 'var(--amber)' : 'var(--blue)' }} />
        </div>
      </div>
    </div>
  )
}
