import { Config, Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";
import fetch from "node-fetch";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const alpacaKey = process.env.ALPACA_API_KEY!;
const alpacaSecret = process.env.ALPACA_API_SECRET!;
const alpacaFeed = process.env.ALPACA_FEED || 'iex';

const supabase = createClient(supabaseUrl, supabaseServiceKey);

export default async (req: Request, context: Context) => {
  console.log("[INGEST] Starting bar ingestion...");

  // 1. Check Alpaca clock
  const clockRes = await fetch("https://paper-api.alpaca.markets/v2/clock", {
    headers: {
      "APCA-API-KEY-ID": alpacaKey,
      "APCA-API-SECRET-KEY": alpacaSecret
    }
  });
  const clock = await clockRes.json() as { is_open: boolean };

  if (!clock.is_open) {
    console.log("[INGEST] Market closed, skipping.");
    return new Response(JSON.stringify({ status: "skipped", reason: "market_closed" }), { status: 200 });
  }

  const symbols = (process.env.INGEST_SYMBOLS || "IWM,SPY,QQQ").split(",");
  const timeframes = (process.env.INGEST_TIMEFRAMES || "1m,5m,15m").split(",");
  console.log(`[INGEST] Symbols: ${symbols}, Timeframes: ${timeframes}, Feed: ${alpacaFeed}`);
  let totalSaved = 0;

  for (const symbol of symbols) {
    for (const timeframe of timeframes) {
      try {
        // a. Query Supabase for most recent ts
        const { data: lastBars } = await supabase
          .from("ohlcv_bars")
          .select("ts")
          .eq("symbol", symbol)
          .eq("timeframe", timeframe)
          .order("ts", { ascending: false })
          .limit(1);

        let start = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // Default last 5 mins
        if (lastBars && lastBars.length > 0) {
          start = new Date(new Date(lastBars[0].ts).getTime() + 1000).toISOString();
        }
        
        console.log(`[INGEST] Fetching ${symbol} ${timeframe} starting from ${start}...`);

        // b. Fetch bars from Alpaca
        const alpacaTimeframe = timeframe === '1m' ? '1Min' : 
                               timeframe === '5m' ? '5Min' : 
                               timeframe === '15m' ? '15Min' : timeframe;
        
        const baseUrl = 'https://data.alpaca.markets';
        const url = `${baseUrl}/v2/stocks/${symbol}/bars?timeframe=${alpacaTimeframe}&start=${start}&feed=${alpacaFeed}&limit=100`;
        const barsRes = await fetch(url, {

            headers: {
              "APCA-API-KEY-ID": alpacaKey,
              "APCA-API-SECRET-KEY": alpacaSecret
            }
          }
        );

        if (!barsRes.ok) {
          const errText = await barsRes.text();
          console.error(`[INGEST] Alpaca Error ${barsRes.status} for ${symbol}: ${errText}`);
          continue;
        }

        const barsData = await barsRes.json() as { bars: any[] };
        const bars = barsData.bars || [];
        console.log(`[INGEST] Received ${bars.length} bars for ${symbol} ${timeframe}`);


        if (bars.length > 0) {
          // c. Upsert into ohlcv_bars
          const rows = bars.map((b: any) => ({
            symbol,
            timeframe,
            ts: b.t,
            open: b.o,
            high: b.h,
            low: b.l,
            close: b.c,
            volume: b.v,
            vwap: b.vw,
            trade_count: b.n,
            feed: alpacaFeed
          }));

          const { error: upsertError } = await supabase
            .from("ohlcv_bars")
            .upsert(rows, { onConflict: 'symbol,timeframe,ts' });

          if (upsertError) {
            console.error(`[INGEST] Error saving ${symbol} ${timeframe}:`, upsertError);
          } else {
            totalSaved += rows.length;
            console.log(`[INGEST] ${symbol} ${timeframe}: ${rows.length} bars saved, latest ${rows[rows.length - 1].ts}`);
          }
        }
      } catch (err) {
        console.error(`[INGEST] Failed ${symbol} ${timeframe}:`, err);
      }
    }
  }

  return new Response(JSON.stringify({ saved: totalSaved, symbols, ts: new Date().toISOString() }), { status: 200 });
};

export const config: Config = {
  schedule: "* 13-20 * * 1-5"
};
