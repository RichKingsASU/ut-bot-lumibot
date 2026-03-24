/**
 * Currency, percent, time, and number formatters
 */

export function fmtCurrency(value: number | string, decimals = 2): string {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '$0.00'
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  return `${sign}$${abs.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
}

export function fmtPnL(value: number | string): string {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '$0.00'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${fmtCurrency(n)}`
}

export function fmtPercent(value: number | string, decimals = 2): string {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '0.00%'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${(n * 100).toFixed(decimals)}%`
}

export function fmtPrice(value: number | string, decimals = 2): string {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '0.00'
  return n.toFixed(decimals)
}

export function fmtNumber(value: number | string, decimals = 0): string {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '0'
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function fmtDuration(startTime: Date | string): string {
  const start = typeof startTime === 'string' ? new Date(startTime) : startTime
  const elapsed = Math.floor((Date.now() - start.getTime()) / 1000)
  const h = Math.floor(elapsed / 3600)
  const m = Math.floor((elapsed % 3600) / 60)
  const s = elapsed % 60
  return `${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`
}

export function fmtTime(date: Date | string, tz = 'America/New_York'): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleTimeString('en-US', {
    timeZone: tz,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function fmtDateTime(date: Date | string, tz = 'America/New_York'): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleString('en-US', {
    timeZone: tz,
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function fmtShares(qty: number | string): string {
  const n = typeof qty === 'string' ? parseFloat(qty) : qty
  if (isNaN(n)) return '0'
  return Number.isInteger(n) ? n.toString() : n.toFixed(2)
}

export function colorForValue(value: number | string): string {
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n) || n === 0) return 'var(--text-muted)'
  return n > 0 ? 'var(--green)' : 'var(--red)'
}
