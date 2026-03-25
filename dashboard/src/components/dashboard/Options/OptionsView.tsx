import React, { useState } from 'react'
import { Layers, Search, ChevronDown, Activity } from 'lucide-react'

export function OptionsView() {
  const [selectedStrike, setSelectedStrike] = useState<number | null>(null)
  
  // Mock data for options chain
  const strikes = [195, 197.5, 200, 202.5, 205, 207.5, 210]
  const chainData = strikes.map(strike => ({
    strike,
    calls: { bid: 4.25, ask: 4.40, delta: 0.65, gamma: 0.02, iv: 0.28, vol: 1240 },
    puts: { bid: 1.15, ask: 1.25, delta: -0.35, gamma: 0.02, iv: 0.31, vol: 850 }
  }))

  return (
    <div style={{ padding: '24px', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Options Chain</h1>
        <div style={{ display: 'flex', gap: '12px' }}>
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              placeholder="Search symbol..." 
              defaultValue="IWM"
              style={{ padding: '8px 12px 8px 36px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text-primary)', outline: 'none' }} 
            />
          </div>
          <button style={topBtnStyle}><Activity size={16} style={{ marginRight: '8px' }} /> Analytics</button>
        </div>
      </div>

      <div style={{ flex: 1, background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', background: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border)', padding: '12px 0' }}>
          <div style={{ flex: 2, textAlign: 'center', fontSize: '11px', fontWeight: 700, color: 'var(--green)', textTransform: 'uppercase' }}>Calls</div>
          <div style={{ flex: 1, textAlign: 'center', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Strike</div>
          <div style={{ flex: 2, textAlign: 'center', fontSize: '11px', fontWeight: 700, color: 'var(--red)', textTransform: 'uppercase' }}>Puts</div>
        </div>

        <div style={{ flex: 1, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 1, borderBottom: '1px solid var(--border)' }}>
              <tr style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                <th style={thStyle}>Bid</th><th style={thStyle}>Ask</th><th style={thStyle}>Delta</th><th style={thStyle}>IV</th>
                <th style={{ ...thStyle, background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>Strike</th>
                <th style={thStyle}>Bid</th><th style={thStyle}>Ask</th><th style={thStyle}>Delta</th><th style={thStyle}>IV</th>
              </tr>
            </thead>
            <tbody>
              {chainData.map((row) => (
                <tr 
                  key={row.strike} 
                  onClick={() => setSelectedStrike(row.strike)}
                  style={{ 
                    borderBottom: '1px solid var(--border)', 
                    cursor: 'pointer',
                    background: selectedStrike === row.strike ? 'var(--blue)11' : 'transparent'
                  }}
                >
                  <td style={tdStyle}>{row.calls.bid.toFixed(2)}</td>
                  <td style={tdStyle}>{row.calls.ask.toFixed(2)}</td>
                  <td style={{ ...tdStyle, color: 'var(--green)' }}>{row.calls.delta.toFixed(2)}</td>
                  <td style={tdStyle}>{(row.calls.iv * 100).toFixed(1)}%</td>
                  <td style={{ ...tdStyle, background: 'var(--bg-tertiary)', fontWeight: 700, textAlign: 'center' }}>{row.strike}</td>
                  <td style={tdStyle}>{row.puts.bid.toFixed(2)}</td>
                  <td style={tdStyle}>{row.puts.ask.toFixed(2)}</td>
                  <td style={{ ...tdStyle, color: 'var(--red)' }}>{row.puts.delta.toFixed(2)}</td>
                  <td style={tdStyle}>{(row.puts.iv * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

const thStyle = { padding: '10px 4px', fontWeight: 600, textAlign: 'center' as const }
const tdStyle = { padding: '12px 4px', fontSize: '13px', textAlign: 'center' as const, color: 'var(--text-primary)' }
const topBtnStyle = { display: 'flex', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text-primary)', cursor: 'pointer' }
