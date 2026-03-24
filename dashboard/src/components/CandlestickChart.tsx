import React, { useEffect, useRef, useState, useCallback } from 'react'
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type LineData,
  type Time,
} from 'lightweight-charts'
import type { OHLCV, Signal, IndicatorState } from '../types/dashboard'

interface CandlestickChartProps {
  candles: OHLCV[]
  trailStops: number[]
  signals: Signal[]
  indicators: IndicatorState
  currentPrice: number
  entryPrice?: number
  onCrosshairMove?: (candle: OHLCV | null) => void
}

function calcEMA(data: number[], period: number): number[] {
  const result: number[] = new Array(data.length).fill(NaN)
  const k = 2 / (period + 1)
  let ema = data[0]
  result[0] = ema
  for (let i = 1; i < data.length; i++) {
    ema = data[i] * k + ema * (1 - k)
    result[i] = ema
  }
  return result
}

function calcVWAP(candles: OHLCV[]): number[] {
  let cumVP = 0
  let cumV = 0
  return candles.map((c) => {
    const tp = (c.high + c.low + c.close) / 3
    cumVP += tp * c.volume
    cumV += c.volume
    return cumV > 0 ? cumVP / cumV : tp
  })
}

function calcBB(data: number[], period = 20, mult = 2): { upper: number[]; lower: number[]; mid: number[] } {
  const upper: number[] = []
  const lower: number[] = []
  const mid: number[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { upper.push(NaN); lower.push(NaN); mid.push(NaN); continue }
    const slice = data.slice(i - period + 1, i + 1)
    const mean = slice.reduce((a, b) => a + b, 0) / period
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period
    const std = Math.sqrt(variance)
    mid.push(mean)
    upper.push(mean + mult * std)
    lower.push(mean - mult * std)
  }
  return { upper, lower, mid }
}

function findSRLevels(candles: OHLCV[], lookback = 10): number[] {
  const levels: number[] = []
  for (let i = lookback; i < candles.length - lookback; i++) {
    const hi = candles.slice(i - lookback, i + lookback).reduce((a, c) => Math.max(a, c.high), -Infinity)
    const lo = candles.slice(i - lookback, i + lookback).reduce((a, c) => Math.min(a, c.low), Infinity)
    if (candles[i].high === hi) levels.push(hi)
    if (candles[i].low === lo) levels.push(lo)
  }
  // Deduplicate close levels
  const sorted = [...new Set(levels.map((l) => Math.round(l * 100) / 100))].sort((a, b) => a - b)
  const deduped: number[] = []
  for (const l of sorted) {
    if (deduped.length === 0 || Math.abs(l - deduped[deduped.length - 1]) > 0.5) {
      deduped.push(l)
    }
  }
  return deduped.slice(-8)
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  candles, trailStops, signals, indicators,
  currentPrice, entryPrice, onCrosshairMove,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const trailSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ema9Ref = useRef<ISeriesApi<'Line'> | null>(null)
  const ema21Ref = useRef<ISeriesApi<'Line'> | null>(null)
  const vwapRef = useRef<ISeriesApi<'Line'> | null>(null)
  const bbUpperRef = useRef<ISeriesApi<'Line'> | null>(null)
  const bbLowerRef = useRef<ISeriesApi<'Line'> | null>(null)
  const entryLineRef = useRef<ISeriesApi<'Line'> | null>(null)
  const srLineRefs = useRef<ISeriesApi<'Line'>[]>([])

  // Init chart
  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: '#0d1117' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: '#21262d' },
        horzLines: { color: '#21262d' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: '#30363d',
        textColor: '#8b949e',
      },
      timeScale: {
        borderColor: '#30363d',
        timeVisible: true,
        secondsVisible: false,
      },
    })
    chartRef.current = chart

    // Candles
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#3fb950',
      downColor: '#f85149',
      borderUpColor: '#3fb950',
      borderDownColor: '#f85149',
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
    })
    candleSeriesRef.current = candleSeries

    // ATR Trail Stop line
    const trailSeries = chart.addLineSeries({
      color: '#58a6ff',
      lineWidth: 2,
      lineStyle: 0,
      priceLineVisible: true,
      lastValueVisible: true,
      title: 'ATR Stop',
    })
    trailSeriesRef.current = trailSeries

    // EMA 9
    ema9Ref.current = chart.addLineSeries({ color: '#e6edf3', lineWidth: 1, lineStyle: 0, title: 'EMA9', lastValueVisible: false, priceLineVisible: false })
    // EMA 21
    ema21Ref.current = chart.addLineSeries({ color: '#f0883e', lineWidth: 1, lineStyle: 0, title: 'EMA21', lastValueVisible: false, priceLineVisible: false })
    // VWAP
    vwapRef.current = chart.addLineSeries({ color: '#6e40c9', lineWidth: 1, lineStyle: 1, title: 'VWAP', lastValueVisible: false, priceLineVisible: false })
    // Bollinger Bands
    bbUpperRef.current = chart.addLineSeries({ color: '#58a6ff', lineWidth: 1, lineStyle: 2, lastValueVisible: false, priceLineVisible: false })
    bbLowerRef.current = chart.addLineSeries({ color: '#58a6ff', lineWidth: 1, lineStyle: 2, lastValueVisible: false, priceLineVisible: false })
    // Entry price line
    entryLineRef.current = chart.addLineSeries({ color: '#3fb950', lineWidth: 1, lineStyle: 1, title: 'Entry', lastValueVisible: true, priceLineVisible: false })

    // Crosshair
    chart.subscribeCrosshairMove((param) => {
      if (onCrosshairMove) {
        if (param.time && param.seriesData.has(candleSeries)) {
          const d = param.seriesData.get(candleSeries) as CandlestickData
          if (d) {
            const match = candles.find((c) => c.time === (param.time as number))
            onCrosshairMove(match ?? null)
          }
        } else {
          onCrosshairMove(null)
        }
      }
    })

    // Resize
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [])

  // Update data
  useEffect(() => {
    if (!candleSeriesRef.current || !trailSeriesRef.current || candles.length === 0) return

    const candleData: CandlestickData[] = candles.map((c) => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    candleSeriesRef.current.setData(candleData)

    // Trail stop data
    const trailData: LineData[] = candles
      .map((c, i) => trailStops[i] > 0 ? { time: c.time as Time, value: trailStops[i] } : null)
      .filter(Boolean) as LineData[]
    trailSeriesRef.current.setData(trailData)
    trailSeriesRef.current.applyOptions({ visible: indicators.atrStop })

    // Signal markers
    if (indicators.signals && signals.length > 0) {
      const markers = signals.map((s) => ({
        time: s.time as Time,
        position: s.type === 'BUY' ? 'belowBar' : 'aboveBar',
        color: s.type === 'BUY' ? '#3fb950' : '#f85149',
        shape: s.type === 'BUY' ? 'arrowUp' : 'arrowDown',
        text: s.type,
        size: 1.5,
      }))
      candleSeriesRef.current.setMarkers(markers as Parameters<typeof candleSeriesRef.current.setMarkers>[0])
    } else {
      candleSeriesRef.current.setMarkers([])
    }

    // EMAs
    const closes = candles.map((c) => c.close)
    const ema9 = calcEMA(closes, 9)
    const ema21 = calcEMA(closes, 21)
    const ema9Data: LineData[] = candles.map((c, i) => ({ time: c.time as Time, value: ema9[i] })).filter((d) => !isNaN(d.value))
    const ema21Data: LineData[] = candles.map((c, i) => ({ time: c.time as Time, value: ema21[i] })).filter((d) => !isNaN(d.value))
    ema9Ref.current?.setData(ema9Data)
    ema9Ref.current?.applyOptions({ visible: indicators.ema9 })
    ema21Ref.current?.setData(ema21Data)
    ema21Ref.current?.applyOptions({ visible: indicators.ema21 })

    // VWAP
    const vwapData = calcVWAP(candles)
    vwapRef.current?.setData(candles.map((c, i) => ({ time: c.time as Time, value: vwapData[i] })))
    vwapRef.current?.applyOptions({ visible: indicators.vwap })

    // Bollinger Bands
    const bb = calcBB(closes)
    bbUpperRef.current?.setData(candles.map((c, i) => ({ time: c.time as Time, value: bb.upper[i] })).filter((d) => !isNaN(d.value)))
    bbLowerRef.current?.setData(candles.map((c, i) => ({ time: c.time as Time, value: bb.lower[i] })).filter((d) => !isNaN(d.value)))
    bbUpperRef.current?.applyOptions({ visible: indicators.bollinger })
    bbLowerRef.current?.applyOptions({ visible: indicators.bollinger })

    // S/R Lines
    const srLevels = findSRLevels(candles)
    // Remove old SR lines
    // (We'll use a simplified approach — set as price lines on the candle series)
    // Clear existing SR lineData
    srLineRefs.current.forEach((s) => chartRef.current?.removeSeries(s))
    srLineRefs.current = []
    if (indicators.srLines) {
      srLevels.forEach((level) => {
        const sr = chartRef.current?.addLineSeries({
          color: '#e3b341',
          lineWidth: 1,
          lineStyle: 1,
          lastValueVisible: false,
          priceLineVisible: false,
        })
        if (sr) {
          sr.setData(candles.map((c) => ({ time: c.time as Time, value: level })))
          srLineRefs.current.push(sr)
        }
      })
    }

    // Entry price line
    if (entryPrice && entryPrice > 0) {
      entryLineRef.current?.setData(candles.map((c) => ({ time: c.time as Time, value: entryPrice })))
      entryLineRef.current?.applyOptions({ visible: true })
    } else {
      entryLineRef.current?.applyOptions({ visible: false })
    }

    chartRef.current?.timeScale().fitContent()
  }, [candles, trailStops, signals, indicators, entryPrice])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', position: 'relative' }}
    />
  )
}
