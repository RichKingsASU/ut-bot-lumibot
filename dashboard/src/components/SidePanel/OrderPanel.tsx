import React, { useState } from 'react'
import type { AlpacaOrder } from '../../types/alpaca'
import { fmtPrice, fmtDateTime } from '../../utils/formatters'

interface OrderPanelProps {
  orders: AlpacaOrder[]
}

type Tab = 'orders' | 'history' | 'alerts'

const statusClass: Record<string, string> = {
  filled: 'badge-green',
  partially_filled: 'badge-amber',
  new: 'badge-amber',
  pending_new: 'badge-amber',
  accepted: 'badge-amber',
  canceled: 'badge-gray',
  expired: 'badge-gray',
  rejected: 'badge-red',
}

export const OrderPanel: React.FC<OrderPanelProps> = ({ orders }) => {
  const [tab, setTab] = useState<Tab>('orders')

  const open = orders.filter((o) => ['new', 'pending_new', 'accepted', 'partially_filled'].includes(o.status))
  const history = orders.filter((o) => !['new', 'pending_new', 'accepted'].includes(o.status)).slice(0, 20)

  const renderOrder = (o: AlpacaOrder) => (
    <div key={o.id} style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <span className={`badge ${o.side === 'buy' ? 'badge-green' : 'badge-red'}`} style={{ fontSize: 10 }}>{o.side.toUpperCase()}</span>
        <span style={{ fontWeight: 600, fontSize: 12 }}>{o.symbol}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{o.qty} @ {o.limit_price ? `$${fmtPrice(parseFloat(o.limit_price))}` : 'MKT'}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
        <span className={`badge ${statusClass[o.status] ?? 'badge-gray'}`} style={{ fontSize: 10 }}>{o.status.toUpperCase()}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{fmtDateTime(o.submitted_at)}</span>
      </div>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
        {(['orders', 'history', 'alerts'] as Tab[]).map((t) => (
          <button
            key={t}
            id={`order-tab-${t}`}
            onClick={() => setTab(t)}
            style={{
              flex: 1, padding: '8px 0', border: 'none', cursor: 'pointer',
              background: tab === t ? 'var(--bg-tertiary)' : 'transparent',
              color: tab === t ? 'var(--text-primary)' : 'var(--text-muted)',
              fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
              borderBottom: tab === t ? '2px solid var(--blue)' : '2px solid transparent',
            }}
          >{t}</button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {tab === 'orders' && (
          open.length > 0 ? open.map(renderOrder) : (
            <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>No open orders</div>
          )
        )}
        {tab === 'history' && (
          history.length > 0 ? history.map(renderOrder) : (
            <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>No order history</div>
          )
        )}
        {tab === 'alerts' && (
          <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>Price alerts coming soon</div>
        )}
      </div>
    </div>
  )
}
