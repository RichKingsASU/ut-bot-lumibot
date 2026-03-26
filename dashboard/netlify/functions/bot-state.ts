import { Context } from "@netlify/functions";

/**
 * Bot State API — returns the bot's last signal direction and underlying price.
 * Reads from Supabase bot_signals table (latest row) + Alpaca latest trade.
 */

const ALPACA_DATA_URL = process.env.ALPACA_DATA_URL || "https://data.alpaca.markets";
const ALPACA_API_KEY = process.env.ALPACA_API_KEY || "";
const ALPACA_API_SECRET = process.env.ALPACA_API_SECRET || "";

const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

const JSON_HEADERS = { "Content-Type": "application/json", "Cache-Control": "no-store" };

export default async (req: Request, _context: Context) => {
  try {
    // Fetch last signal from Supabase
    let lastSignal = "FLAT";
    try {
      const res = await fetch(
        `${SUPABASE_URL}/rest/v1/bot_signals?select=signal_type&order=ts.desc&limit=1`,
        {
          headers: {
            apikey: SUPABASE_KEY,
            Authorization: `Bearer ${SUPABASE_KEY}`,
          },
        }
      );
      if (res.ok) {
        const rows = await res.json();
        if (rows.length > 0) {
          const sig = rows[0].signal_type?.toUpperCase();
          if (sig === "BUY" || sig === "LONG") lastSignal = "LONG";
          else if (sig === "SELL" || sig === "SHORT") lastSignal = "SHORT";
        }
      }
    } catch {
      // Supabase unavailable — default to FLAT
    }

    // Fetch underlying price
    let underlyingPrice: number | null = null;
    try {
      const res = await fetch(`${ALPACA_DATA_URL}/v2/stocks/SPY/trades/latest`, {
        headers: {
          "APCA-API-KEY-ID": ALPACA_API_KEY,
          "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
        },
      });
      if (res.ok) {
        const data = await res.json();
        underlyingPrice = data?.trade?.p ?? null;
      }
    } catch {
      // Alpaca unavailable
    }

    return new Response(
      JSON.stringify({
        last_signal: lastSignal,
        underlying_price: underlyingPrice,
      }),
      { status: 200, headers: JSON_HEADERS }
    );
  } catch (err: any) {
    return new Response(
      JSON.stringify({ last_signal: "FLAT", underlying_price: null, error: err.message }),
      { status: 200, headers: JSON_HEADERS }
    );
  }
};
