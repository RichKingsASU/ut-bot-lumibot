import React, { useState, useEffect } from 'react'
import { AlertTriangle, X } from 'lucide-react'
import { getAdminKey } from '../lib/apiClient'

export function AdminKeyBanner() {
  const [missing, setMissing] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const check = () => setMissing(!getAdminKey())
    check()
    // Re-check when another tab writes to localStorage
    window.addEventListener('storage', check)
    return () => window.removeEventListener('storage', check)
  }, [])

  if (!missing || dismissed) return null

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '9px 16px',
      backgroundColor: 'rgba(227, 179, 65, 0.10)',
      borderBottom: '1px solid rgba(227, 179, 65, 0.25)',
      color: '#e3b341',
      fontSize: '13px',
      flexShrink: 0,
    }}>
      <AlertTriangle size={14} style={{ flexShrink: 0 }} />
      <span>
        Admin API Key not configured — market data unavailable.{' '}
        <a href="/settings" style={{ color: '#58a6ff', textDecoration: 'underline' }}>
          Go to Settings
        </a>{' '}
        to configure.
      </span>
      <button
        onClick={() => setDismissed(true)}
        style={{
          marginLeft: 'auto',
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          padding: '2px',
          display: 'flex',
          alignItems: 'center',
        }}
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  )
}
