import { Config, Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";
import fetch from "node-fetch";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const alpacaKey = process.env.ALPACA_API_KEY!;
const alpacaSecret = process.env.ALPACA_API_SECRET!;

const supabase = createClient(supabaseUrl, supabaseServiceKey);

export default async (req: Request, context: Context) => {
  console.log("[OPTIONS] Starting options snapshot...");

  // 1. Check Alpaca clock
  const clockRes = await fetch("https://paper-api.alpaca.markets/v2/clock", {
    headers: {
      "APCA-API-KEY-ID": alpacaKey,
      "APCA-API-SECRET-KEY": alpacaSecret
    }
  });
  const clock = await clockRes.json() as { is_open: boolean };

  if (!clock.is_open) {
    console.log("[OPTIONS] Market closed, skipping.");
    return new Response(JSON.stringify({ status: "skipped", reason: "market_closed" }), { status: 200 });
  }

  const symbols = (process.env.OPTIONS_SYMBOLS || "IWM,SPY").split(",");
  const optionsFeed = process.env.OPTIONS_FEED || 'indicative';
  const today = new Date();
  const fortyFiveDaysLater = new Date(today.getTime() + 45 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  const todayStr = today.toISOString().split('T')[0];

  let totalSnapshotted = 0;

  for (const symbol of symbols) {
    try {
      // 2. Fetch options snapshot from Alpaca
      const res = await fetch(
        `https://data.alpaca.markets/v2/options/snapshots/${symbol}?feed=${optionsFeed}&expiration_date_gte=${todayStr}&expiration_date_lte=${fortyFiveDaysLater}`,

        {
          headers: {
            "APCA-API-KEY-ID": alpacaKey,
            "APCA-API-SECRET-KEY": alpacaSecret
          }
        }
      );

      if (res.status === 429) {
        console.warn(`[OPTIONS] Rate limited for ${symbol}, retrying in 1s...`);
        await new Promise(r => setTimeout(r, 1000));
        continue;
      }

      const data = await res.json() as { snapshots: any };
      const snapshots = data.snapshots || {};
      const contracts = Object.values(snapshots);

      if (contracts.length > 0) {
        const rows = contracts.map((c: any) => {
          const bid = c.latest_quote?.bp || 0;
          const ask = c.latest_quote?.ap || 0;
          const mid = (bid + ask) / 2;
          
          return {
            ts: new Date().toISOString(),
            underlying: symbol,
            symbol: c.contract_symbol,
            expiration: c.expiration_date,
            strike: c.strike_price,
            option_type: c.option_type === 'call' ? 'C' : 'P',
            dte: Math.ceil((new Date(c.expiration_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
            bid,
            ask,
            mid,
            last: c.latest_trade?.p || 0,
            volume: c.latest_trade?.v || 0,
            open_interest: c.open_interest || 0,
            iv: c.implied_volatility || 0,
            delta: c.greeks?.delta || 0,
            gamma: c.greeks?.gamma || 0,
            theta: c.greeks?.theta || 0,
            vega: c.greeks?.vega || 0,
            underlying_price: c.underlying_price || 0,
            feed: 'indicative'
          };
        });

        // Batch insert into options_chain
        const { error } = await supabase
          .from("options_chain")
          .insert(rows);

        if (error) {
          console.error(`[OPTIONS] Error saving ${symbol}:`, error);
        } else {
          totalSnapshotted += rows.length;
          console.log(`[OPTIONS] ${symbol}: ${rows.length} contracts snapshotted`);
        }
      }
    } catch (err) {
      console.error(`[OPTIONS] Failed ${symbol}:`, err);
    }
  }

  return new Response(JSON.stringify({ snapshotted: totalSnapshotted, symbols, ts: new Date().toISOString() }), { status: 200 });
};

export const config: Config = {
  schedule: "*/5 13-20 * * 1-5"
};
