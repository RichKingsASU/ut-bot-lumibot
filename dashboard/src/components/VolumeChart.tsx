import React, { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type Time,
} from 'lightweight-charts'
import type { OHLCV } from '../types/dashboard'

interface VolumeChartProps {
  candles: OHLCV[]
  visible: boolean
}

export const VolumeChart: React.FC<VolumeChartProps> = ({ candles, visible }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: '#0d1117' },
        textColor: '#8b949e',
      },
      grid: { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#30363d', textColor: '#8b949e' },
      timeScale: { borderColor: '#30363d', timeVisible: true, secondsVisible: false },
      handleScroll: false,
      handleScale: false,
    })
    chartRef.current = chart

    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })

    const volData = candles.map((c) => ({
      time: c.time as Time,
      value: c.volume,
      color: c.close >= c.open ? '#3fb95066' : '#f8514966',
    }))
    volSeries.setData(volData)
    chart.timeScale().fitContent()

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    })
    ro.observe(containerRef.current)
    return () => { ro.disconnect(); chart.remove() }
  }, [candles])

  if (!visible) return null

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '80px', flexShrink: 0, borderTop: '1px solid var(--border)' }}
    />
  )
}
