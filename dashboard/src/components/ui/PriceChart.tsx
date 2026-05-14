import { useEffect, useRef } from 'react';
import { createChart, ColorType, type IChartApi, type CandlestickData, type UTCTimestamp } from 'lightweight-charts';

export interface PriceChartBar {
  time: number | string;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface PriceChartProps {
  bars: PriceChartBar[];
  symbol: string;
  height?: number;
}

export function PriceChart({ bars, symbol, height = 320 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      width: containerRef.current.clientWidth,
      height,
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    if (bars.length > 0) {
      const data = bars.map<CandlestickData>((b) => ({
        time: (typeof b.time === 'number' ? b.time : b.time) as UTCTimestamp,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }));
      candleSeries.setData(data);
      chart.timeScale().fitContent();
    }

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [bars, height]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {bars.length === 0 && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#6b7280',
            fontSize: 13,
            zIndex: 1,
          }}
        >
          No bar data available for {symbol}
        </div>
      )}
      <div ref={containerRef} style={{ width: '100%', height }} />
    </div>
  );
}
