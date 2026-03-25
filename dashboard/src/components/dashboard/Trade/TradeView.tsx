import React from 'react'

export function TradeView({ children }: { children?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
      {children}
    </div>
  )
}
