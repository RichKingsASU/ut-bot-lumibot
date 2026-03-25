import React, { useState } from 'react'
import { OHLCBar } from '../../OHLCBar'
import { IndicatorToolbar } from '../../IndicatorToolbar'
import { CandlestickChart } from '../../CandlestickChart'
import { VolumeChart } from '../../VolumeChart'
import { AccountOverview } from '../../SidePanel/AccountOverview'
import { ActiveTrade } from '../../SidePanel/ActiveTrade'
import { Positions } from '../../SidePanel/Positions'
import { OrderPanel } from '../../SidePanel/OrderPanel'
import { BotStatus } from '../../SidePanel/BotStatus'
import SeedStatus from '../../SeedStatus'
import type { IndicatorState, OHLCV, OHLCV as OHLCVType } from '../../../types/dashboard'

interface TradeViewProps {
  symbol: string
  timeframe: any // Replace with proper Timeframe type if available
  candles: OHLCVType[]
  trailStops: any
  signals: any
  currentPrice: number
  activePosition: any
  account: any
  positions: any[]
  orders: any[]
  currentTrailStop: number | null
  currentATR: number | null
  lastSignal: any
  connected: boolean
  loading: boolean
  iterationsToday: number
  addLog: (message: string, level?: 'info' | 'warning' | 'error' | 'success') => void
}

type SidePanelTab = 'account' | 'trade' | 'positions' | 'orders' | 'bot' | 'data'

const DEFAULT_INDICATORS: IndicatorState = {
  atrStop: true,
  signals: true,
  volume: true,
  srLines: true,
  ema9: false,
  ema21: false,
  vwap: false,
  rsi: false,
  macd: false,
  bollinger: false,
}

export function TradeView({
  symbol,
  timeframe,
  candles,
  trailStops,
  signals,
  currentPrice,
  activePosition,
  account,
  positions,
  orders,
  currentTrailStop,
  currentATR,
  lastSignal,
  connected,
  loading,
  iterationsToday,
  addLog
}: TradeViewProps) {
  const [indicators, setIndicators] = useState<IndicatorState>(DEFAULT_INDICATORS)
  const [hoveredCandle, setHoveredCandle] = useState<OHLCV | null>(null)
  const [sideTab, setSideTab] = useState<SidePanelTab>('account')

  const handleIndicatorToggle = (key: keyof IndicatorState) => {
    setIndicators((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const lastCandle = candles.length > 0 ? candles[candles.length - 1] : null

  const SIDE_TABS: Array<{ key: SidePanelTab; label: string }> = [
    { key: 'account', label: 'Account' },
    { key: 'trade', label: 'Trade' },
    { key: 'positions', label: 'Positions' },
    { key: 'orders', label: 'Orders' },
    { key: 'bot', label: 'Bot' },
    { key: 'data', label: 'Data' },
  ]

  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
      {/* CHART AREA */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* OHLC Data Bar */}
        <OHLCBar candle={lastCandle} hoveredCandle={hoveredCandle} />

        {/* Indicator Toolbar */}
        <IndicatorToolbar indicators={indicators} onChange={handleIndicatorToggle} />

        {/* Chart */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          <CandlestickChart
            candles={candles}
            trailStops={trailStops}
            signals={signals}
            indicators={indicators}
            currentPrice={currentPrice}
            entryPrice={activePosition ? parseFloat(activePosition.avg_entry_price) : undefined}
            onCrosshairMove={setHoveredCandle}
          />
        </div>

        {/* Volume Chart */}
        <VolumeChart candles={candles} visible={indicators.volume} />
      </div>

      {/* SIDE PANEL */}
      <div style={{
        width: '280px',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid var(--border)',
        background: 'var(--bg-secondary)',
        overflow: 'hidden',
      }}>
        {/* Side Panel Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          {SIDE_TABS.map(({ key, label }) => (
            <button
              key={key}
              id={`side-tab-${key}`}
              onClick={() => setSideTab(key)}
              style={{
                flex: 1, padding: '8px 2px', border: 'none', cursor: 'pointer',
                background: sideTab === key ? 'var(--bg-tertiary)' : 'transparent',
                color: sideTab === key ? 'var(--text-primary)' : 'var(--text-muted)',
                fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
                borderBottom: sideTab === key ? '2px solid var(--blue)' : '2px solid transparent',
                letterSpacing: '0.04em',
              }}
            >{label}</button>
          ))}
        </div>

        {/* Side Panel Content */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {sideTab === 'account' && <AccountOverview account={account} loading={loading} />}
          {sideTab === 'trade' && (
            <ActiveTrade
              position={activePosition}
              currentPrice={currentPrice}
              trailStop={currentTrailStop ?? 0}
              lastSignal={lastSignal?.type ?? ''}
            />
          )}
          {sideTab === 'positions' && <Positions positions={positions} />}
          {sideTab === 'orders' && <OrderPanel orders={orders} />}
          {sideTab === 'bot' && (
            <BotStatus
              symbol={symbol}
              timeframe={timeframe}
              atrPeriod={10}
              sensitivity={1.0}
              currentATR={currentATR ?? 0}
              currentTrailStop={currentTrailStop ?? 0}
              lastSignal={lastSignal?.type ?? ''}
              iterationsToday={iterationsToday}
              connected={connected}
            />
          )}
          {sideTab === 'data' && <SeedStatus />}
        </div>
      </div>
    </div>
  )
}
