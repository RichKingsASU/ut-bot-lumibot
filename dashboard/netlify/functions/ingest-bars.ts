import { Config, Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";
import fetch from "node-fetch";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const alpacaKey = process.env.ALPACA_API_KEY!;
const alpacaSecret = process.env.ALPACA_API_SECRET!;
const alpacaFeed = process.env.ALPACA_FEED || 'sip';

const supabase = createClient(supabaseUrl, supabaseServiceKey);

export default async (req: Request, context: Context) => {
  console.log("[INGEST] Starting bar ingestion...");

  try {
    // 1. Check Alpaca clock
    const clockRes = await fetch("https://api.alpaca.markets/v2/clock", {
      headers: {
        "APCA-API-KEY-ID": alpacaKey,
        "APCA-API-SECRET-KEY": alpacaSecret
      }
    });
    const clock = await clockRes.json() as { is_open: boolean, timestamp: string };

    if (!clock.is_open) {
      console.log("[INGEST] Market closed, skipping.");
      return new Response(JSON.stringify({ status: "skipped", reason: "market_closed" }), { status: 200 });
    }

    const symbols = (process.env.SEED_SYMBOLS || "IWM,SPY,QQQ").split(",");
    const timeframes = ['1Min', '5Min', '15Min'];
    
    // Check if it's 4:05pm EST (20:05 UTC)
    const now = new Date(clock.timestamp);
    const isEOD = now.getUTCHours() === 20 && now.getUTCMinutes() >= 5 && now.getUTCMinutes() <= 10;
    if (isEOD) timeframes.push('1Day');

    let totalSaved = 0;

    for (const symbol of symbols) {
      for (const timeframe of timeframes) {
        // a. Query Supabase for last ts
        const { data: lastBars } = await supabase
          .from("ohlcv_bars")
          .select("ts")
          .eq("symbol", symbol)
          .eq("timeframe", timeframe)
          .order("ts", { ascending: false })
          .limit(1);

        let start = new Date(Date.now() - 30 * 60 * 1000).toISOString(); // Default last 30 mins
        if (lastBars && lastBars.length > 0) {
          start = lastBars[0].ts;
        }

        // b. Fetch last 3 bars from Alpaca SIP
        const url = `https://data.alpaca.markets/v2/stocks/${symbol}/bars?timeframe=${timeframe}&start=${start}&feed=${alpacaFeed}&limit=3`;
        const barsRes = await fetch(url, {
          headers: {
            "APCA-API-KEY-ID": alpacaKey,
            "APCA-API-SECRET-KEY": alpacaSecret
          }
        });

        if (!barsRes.ok) {
          console.error(`[INGEST] Alpaca Error ${barsRes.status} for ${symbol} ${timeframe}`);
          continue;
        }

        const barsData = await barsRes.json() as { bars: any[] };
        const bars = barsData.bars || [];

        if (bars.length > 0) {
          // c. Upsert all returned bars
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

          if (!upsertError) {
            totalSaved += rows.length;
          }
        }
      }
    }

    return new Response(JSON.stringify({ saved: totalSaved, ts: new Date().toISOString() }), { status: 200 });

  } catch (err: any) {
    console.error("[INGEST] Failure:", err);
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
};

export const config: Config = {
  schedule: "* 13-20 * * 1-5"
};
