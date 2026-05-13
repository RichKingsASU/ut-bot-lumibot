import React from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 24,
        gap: 16,
      }}
    >
      <div>
        <h1
          style={{
            fontSize: 20,
            fontWeight: 600,
            color: 'var(--text-primary)',
            margin: 0,
            lineHeight: 1.25,
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <p
            style={{
              fontSize: 13,
              color: 'var(--text-muted)',
              margin: '4px 0 0',
            }}
          >
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {actions}
        </div>
      )}
    </div>
  )
}
