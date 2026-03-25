import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const alpacaKey = process.env.ALPACA_API_KEY!;
const alpacaSecret = process.env.ALPACA_API_SECRET!;
const alpacaFeed = process.env.ALPACA_FEED || 'iex';

const supabase = createClient(supabaseUrl, supabaseServiceKey);

export default async (req: Request, context: Context) => {
  if (req.method !== "POST" && req.method !== "GET") { // Allow GET for Netlify Dashboard "Run now"
    return new Response("Method Not Allowed", { status: 405 });
  }

  const body = req.method === "POST" ? await req.json() : {};
  const symbol = body.symbol || "IWM";
  const timeframe = body.timeframe || "15m";
  const days = body.days || 30;

  console.log(`[BACKFILL] Starting backfill for ${symbol} ${timeframe} (${days} days)...`);

  const start = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
  let nextPageToken: string | null = "";
  let totalSaved = 0;

  while (nextPageToken !== null) {
    const alpacaTimeframe = timeframe === '1m' ? '1Min' : 
                          timeframe === '5m' ? '5Min' : 
                          timeframe === '15m' ? '15Min' : timeframe;
                          
    const baseUrl = "https://data.alpaca.markets";
    let url = `${baseUrl}/v2/stocks/${symbol}/bars?timeframe=${alpacaTimeframe}&start=${start}&feed=${alpacaFeed}&limit=10000`;
    if (nextPageToken) {
      url += `&page_token=${nextPageToken}`;
    }

    const barsRes = await fetch(url, {
      headers: {
        "APCA-API-KEY-ID": alpacaKey,
        "APCA-API-SECRET-KEY": alpacaSecret
      }
    });

    if (!barsRes.ok) {
        const errText = await barsRes.text();
        console.error(`[BACKFILL] Alpaca Error ${barsRes.status} for ${symbol}: ${errText}`);
        break;
    }


    const data = await barsRes.json() as { bars: any[], next_page_token: string | null };
    const bars = data.bars || [];
    nextPageToken = data.next_page_token;

    if (bars.length > 0) {
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

      // Batch insert in chunks of 500
      for (let i = 0; i < rows.length; i += 500) {
        const chunk = rows.slice(i, i + 500);
        const { error } = await supabase
          .from("ohlcv_bars")
          .upsert(chunk, { onConflict: 'symbol,timeframe,ts' });

        if (error) {
          console.error(`[BACKFILL] Error saving chunk:`, error);
        } else {
          totalSaved += chunk.length;
          console.log(`[BACKFILL] ${symbol} ${timeframe}: ${totalSaved} bars saved so far...`);
        }
      }
    } else {
      break;
    }
  }

  console.log(`[BACKFILL] Completed: ${totalSaved} bars saved.`);
  return new Response(JSON.stringify({ total_bars: totalSaved, symbol, timeframe, start }), { status: 200 });
};
