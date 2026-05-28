import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

const ALPACA_API_KEY = process.env.ALPACA_API_KEY || "";
const ALPACA_API_SECRET = process.env.ALPACA_API_SECRET || "";

const JSON_HEADERS = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Admin-API-Key",
};

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

export default async (req: Request, _context: Context) => {
  // CORS Preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: JSON_HEADERS });
  }

  // Admin Key Authorization
  const adminKey = process.env.ADMIN_API_KEY;
  const requestKey = req.headers.get("X-Admin-API-Key");

  if (adminKey && requestKey !== adminKey) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: JSON_HEADERS,
    });
  }

  const symbols = ['SPY','IWM','QQQ','NVDA','TSLA','AAPL','MSFT','META','GOOGL'];

  try {
    // 1. Fetch Latest Prices from Alpaca
    let alpacaPrices: Record<string, { price: number; timestamp: string }> = {};
    try {
      const symbolsStr = symbols.join(",");
      const alpacaRes = await fetch(
        `https://data.alpaca.markets/v2/stocks/bars/latest?symbols=${symbolsStr}&feed=sip`,
        {
          headers: {
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
            "Content-Type": "application/json",
          },
        }
      );

      if (alpacaRes.ok) {
        const data = await alpacaRes.json();
        const bars = data.bars || {};
        for (const sym of symbols) {
          if (bars[sym]) {
            alpacaPrices[sym] = {
              price: parseFloat(bars[sym].c || "0"),
              timestamp: bars[sym].t,
            };
          }
        }
      } else {
        console.error("Alpaca latest bars returned non-ok status:", alpacaRes.status);
      }
    } catch (e) {
      console.error("Alpaca fetch in get-equities-monitor failed:", e);
    }

    // 2. Fetch Bar Data Freshness from Supabase
    // We query counts and last_bar for '1Min' and '15Min' timeframes
    const statsPromises = symbols.flatMap((symbol) =>
      ["1Min", "15Min"].map(async (timeframe) => {
        try {
          const { count, data, error } = await supabase
            .from("ohlcv_bars")
            .select("ts", { count: "exact" })
            .eq("symbol", symbol)
            .eq("timeframe", timeframe)
            .order("ts", { ascending: false })
            .limit(1);

          if (error) throw error;

          return {
            symbol,
            timeframe,
            bar_count: count || 0,
            last_bar: data && data.length > 0 ? data[0].ts : null,
          };
        } catch (err) {
          console.error(`Error querying ohlcv_bars for ${symbol} ${timeframe}:`, err);
          return {
            symbol,
            timeframe,
            bar_count: 0,
            last_bar: null,
          };
        }
      })
    );

    const statsResults = await Promise.all(statsPromises);

    return new Response(
      JSON.stringify({
        prices: alpacaPrices,
        stats: statsResults,
        last_updated: new Date().toISOString(),
      }),
      { status: 200, headers: JSON_HEADERS }
    );
  } catch (err: any) {
    console.error("get-equities-monitor failed:", err);
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: JSON_HEADERS,
    });
  }
};
