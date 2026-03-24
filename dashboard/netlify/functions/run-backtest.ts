import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

const supabase = createClient(supabaseUrl, supabaseServiceKey);

interface Bar {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export default async (req: Request, context: Context) => {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  const { symbol, timeframe, date_start, date_end, atr_period = 10, sensitivity = 1.0, initial_capital = 100000 } = await req.json();

  console.log(`[BACKTEST] Running for ${symbol} ${timeframe} from ${date_start} to ${date_end}...`);

  // 1. Fetch bars from Supabase
  const { data: bars, error } = await supabase
    .from("ohlcv_bars")
    .select("ts, open, high, low, close, volume")
    .eq("symbol", symbol)
    .eq("timeframe", timeframe)
    .gte("ts", date_start)
    .lte("ts", date_end)
    .order("ts", { ascending: true });

  if (error || !bars || bars.length === 0) {
    return new Response(JSON.stringify({ error: "No data found for backtest" }), { status: 400 });
  }

  // 2. UT Bot Strategy Logic (Ported from Python)
  const df = bars.map((b: any) => ({
    ...b,
    tr: 0,
    atr: 0,
    trail_stop: 0,
    signal: 0
  }));

  // Calculate ATR
  for (let i = 0; i < df.length; i++) {
    const high = parseFloat(df[i].high);
    const low = parseFloat(df[i].low);
    const close = parseFloat(df[i].close);
    const prevClose = i > 0 ? parseFloat(df[i-1].close) : close;

    const tr1 = high - low;
    const tr2 = Math.abs(high - prevClose);
    const tr3 = Math.abs(low - prevClose);
    df[i].tr = Math.max(tr1, tr2, tr3);
  }

  // Simple moving average for ATR (or EWM if desired)
  for (let i = atr_period - 1; i < df.length; i++) {
    let sum = 0;
    for (let j = 0; j < atr_period; j++) {
      sum += df[i - j].tr;
    }
    df[i].atr = sum / atr_period;
  }

  // Calculate Trailing Stop
  for (let i = 1; i < df.length; i++) {
    const close = parseFloat(df[i].close);
    const prevClose = parseFloat(df[i-1].close);
    const prevTrailStop = df[i-1].trail_stop;
    const loss = sensitivity * df[i].atr;

    if (close > prevTrailStop && prevClose > prevTrailStop) {
      df[i].trail_stop = Math.max(prevTrailStop, close - loss);
    } else if (close < prevTrailStop && prevClose < prevTrailStop) {
      df[i].trail_stop = Math.min(prevTrailStop, close + loss);
    } else if (close > prevTrailStop) {
      df[i].trail_stop = close - loss;
    } else {
      df[i].trail_stop = close + loss;
    }

    // Signal logic
    const prevTs = df[i-1].trail_stop;
    if (close > df[i].trail_stop && prevClose <= prevTs) {
      df[i].signal = 1; // BUY
    } else if (close < df[i].trail_stop && prevClose >= prevTs) {
      df[i].signal = -1; // SELL
    }
  }

  // 3. Backtest Simulation
  let capital = initial_capital;
  let shares = 0;
  let trades = [];
  let equityCurve = [];

  for (let i = 0; i < df.length; i++) {
    const price = parseFloat(df[i].close);
    
    if (df[i].signal === 1 && shares === 0) {
      // Buy
      shares = Math.floor(capital / price);
      capital -= shares * price;
      trades.push({ type: 'buy', price, ts: df[i].ts });
    } else if (df[i].signal === -1 && shares > 0) {
      // Sell
      capital += shares * price;
      trades.push({ type: 'sell', price, ts: df[i].ts });
      shares = 0;
    }
    
    const currentEquity = capital + (shares * price);
    equityCurve.push(currentEquity);
  }

  // Close final position if any
  if (shares > 0) {
    capital += shares * parseFloat(df[df.length - 1].close);
    trades.push({ type: 'sell', price: parseFloat(df[df.length - 1].close), ts: df[df.length - 1].ts, note: 'final_close' });
    shares = 0;
  }

  // 4. Calculate Metrics
  const finalValue = capital;
  const totalReturnPct = ((finalValue - initial_capital) / initial_capital) * 100;
  
  let maxDrawdown = 0;
  let peak = initial_capital;
  for (const eq of equityCurve) {
    if (eq > peak) peak = eq;
    const dd = (peak - eq) / peak;
    if (dd > maxDrawdown) maxDrawdown = dd;
  }

  const tradeResults = [];
  for (let i = 0; i < trades.length; i += 2) {
    if (trades[i+1]) {
      const profit = (trades[i+1].price - trades[i].price) * (initial_capital / trades[i].price); // approx
      tradeResults.push(profit);
    }
  }

  const winCount = tradeResults.filter(p => p > 0).length;
  const lossCount = tradeResults.filter(p => p <= 0).length;
  const avgWin = winCount > 0 ? tradeResults.filter(p => p > 0).reduce((a, b) => a + b, 0) / winCount : 0;
  const avgLoss = lossCount > 0 ? tradeResults.filter(p => p <= 0).reduce((a, b) => a + b, 0) / lossCount : 0;
  const profitFactor = Math.abs(avgLoss) > 0 ? (winCount * avgWin) / (lossCount * Math.abs(avgLoss)) : winCount > 0 ? 100 : 0;

  const result = {
    strategy: "UT Bot Preview",
    symbol,
    timeframe,
    data_source: "Supabase",
    date_start,
    date_end,
    atr_period,
    sensitivity,
    initial_capital,
    final_value: finalValue,
    total_return_pct: totalReturnPct,
    max_drawdown_pct: maxDrawdown * 100,
    sharpe_ratio: 0, // Placeholder
    total_trades: tradeResults.length,
    winning_trades: winCount,
    losing_trades: lossCount,
    win_rate_pct: tradeResults.length > 0 ? (winCount / tradeResults.length) * 100 : 0,
    avg_win: avgWin,
    avg_loss: avgLoss,
    profit_factor: profitFactor,
    params: { atr_period, sensitivity }
  };

  // 5. Store in Supabase
  await supabase.from("backtest_results").insert([result]);

  return new Response(JSON.stringify(result), { status: 200 });
};
