/**
 * Sharpe ratio — annualized, excess return over risk-free rate.
 * @param periodReturns  Array of per-period returns as decimals (e.g. 0.012 for 1.2%)
 * @param periodsPerYear 252 for daily, 252*6.5 for hourly, 252*6.5*4 for 15-min bars
 * @param riskFreeRate   Annual risk-free rate as decimal (e.g. 0.053 for 5.3%)
 */
export function sharpeRatio(
  periodReturns: number[],
  periodsPerYear = 252,
  riskFreeRate = 0.053
): number | null {
  if (periodReturns.length < 2) return null;
  const rfPerPeriod = riskFreeRate / periodsPerYear;
  const excess = periodReturns.map((r) => r - rfPerPeriod);
  const mean = excess.reduce((a, b) => a + b, 0) / excess.length;
  const variance =
    excess.reduce((a, b) => a + (b - mean) ** 2, 0) / (excess.length - 1);
  const std = Math.sqrt(variance);
  if (std === 0) return null;
  return (mean / std) * Math.sqrt(periodsPerYear);
}

/** Format Sharpe for display — 2 decimal places, em dash if null */
export function formatSharpe(value: number | null): string {
  if (value === null) return '—';
  return value.toFixed(2);
}
