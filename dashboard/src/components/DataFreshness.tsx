import { useState, useEffect } from 'react'

interface Props {
  lastUpdated: Date | null
}

export function DataFreshness({ lastUpdated }: Props) {
  const [label, setLabel] = useState('')

  useEffect(() => {
    const update = () => {
      if (!lastUpdated) {
        setLabel('Never updated')
        return
      }
      const secs = Math.floor((Date.now() - lastUpdated.getTime()) / 1000)
      if (secs < 10) setLabel('Just updated')
      else if (secs < 60) setLabel(`${secs}s ago`)
      else if (secs < 3600) setLabel(`${Math.floor(secs / 60)}m ago`)
      else setLabel(`${Math.floor(secs / 3600)}h ago`)
    }
    update()
    const interval = setInterval(update, 5000)
    return () => clearInterval(interval)
  }, [lastUpdated])

  const color = !lastUpdated
    ? 'color: #f85149'
    : Date.now() - lastUpdated.getTime() < 30000
      ? 'color: #3fb950'
      : Date.now() - lastUpdated.getTime() < 120000
        ? 'color: #e3b341'
        : 'color: #f85149'

  const colorVal = !lastUpdated
    ? '#f85149'
    : Date.now() - lastUpdated.getTime() < 30000
      ? '#3fb950'
      : Date.now() - lastUpdated.getTime() < 120000
        ? '#e3b341'
        : '#f85149'

  return (
    <span style={{ fontSize: 11, color: colorVal, opacity: 0.6 }}>
      Updated {label}
    </span>
  )
}
