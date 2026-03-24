import React, { useRef, useEffect } from 'react'
import type { LogEntry } from '../types/dashboard'
import { fmtTime } from '../utils/formatters'

interface BottomLogBarProps {
  logs: LogEntry[]
  connected: boolean
}

const levelColors: Record<string, string> = {
  info: 'var(--text-muted)',
  warning: 'var(--amber)',
  error: 'var(--red)',
  success: 'var(--green)',
}

export const BottomLogBar: React.FC<BottomLogBarProps> = ({ logs, connected }) => {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth
    }
  }, [logs])

  const recent = logs.slice(-10)

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px',
      padding: '0 12px',
      background: 'var(--bg-secondary)',
      borderTop: '1px solid var(--border)',
      height: '28px',
      flexShrink: 0,
    }}>
      <span style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, whiteSpace: 'nowrap' }}>BOT LOG</span>

      <div
        ref={scrollRef}
        style={{ flex: 1, display: 'flex', gap: '16px', overflow: 'hidden', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}
      >
        {recent.length === 0 ? (
          <span style={{ color: 'var(--text-muted)' }}>Waiting for events...</span>
        ) : (
          recent.map((log) => (
            <span key={log.id} style={{ color: levelColors[log.level] ?? 'var(--text-muted)', whiteSpace: 'nowrap' }}>
              [{fmtTime(log.timestamp)}] {log.message}
            </span>
          ))
        )}
      </div>

      <span style={{ color: connected ? 'var(--green)' : 'var(--red)', fontSize: 10, whiteSpace: 'nowrap' }}>
        <span className="pulse-dot" style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: connected ? 'var(--green)' : 'var(--red)', marginRight: 4, verticalAlign: 'middle' }} />
        {connected ? 'LIVE' : 'OFFLINE'}
      </span>
    </div>
  )
}
