import { Config, Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const alpacaKey = process.env.ALPACA_API_KEY!;
const alpacaSecret = process.env.ALPACA_API_SECRET!;
const alpacaOptionFeed = process.env.ALPACA_OPTION_FEED || 'opra';

const supabase = createClient(supabaseUrl, supabaseServiceKey);

export default async (req: Request, context: Context) => {
    console.log("[OPTIONS-INGEST] Starting options chain snapshot...");

    try {
        // 1. Check Alpaca clock
        const clockRes = await fetch("https://api.alpaca.markets/v2/clock", {
            headers: { "APCA-API-KEY-ID": alpacaKey, "APCA-API-SECRET-KEY": alpacaSecret }
        });
        const clock = await clockRes.json() as { is_open: boolean };

        if (!clock.is_open) {
            console.log("[OPTIONS-INGEST] Market closed, skipping.");
            return new Response(JSON.stringify({ status: "skipped", reason: "market_closed" }), { status: 200 });
        }

        const snapshotTs = new Date().toISOString();
        const underlyingSymbols = (process.env.OPTIONS_SYMBOLS || "IWM,SPY").split(",");
        const dteMax = parseInt(process.env.OPTIONS_DTE_MAX || "60");
        const today = new Date().toISOString().split('T')[0];
        const maxDate = new Date();
        maxDate.setDate(maxDate.getDate() + dteMax);
        const maxDateStr = maxDate.toISOString().split('T')[0];

        let grandTotalRows = 0;

        for (const underlying of underlyingSymbols) {
            console.log(`[OPTIONS-INGEST] Processing ${underlying}...`);
            
            // 2. Fetch underlying price
            const uRes = await fetch(`https://data.alpaca.markets/v2/stocks/${underlying}/snapshot?feed=sip`, {
                headers: { "APCA-API-KEY-ID": alpacaKey, "APCA-API-SECRET-KEY": alpacaSecret }
            });
            const uData = await uRes.json() as any;
            const underlyingPrice = uData.latestTrade?.p || uData.latestQuote?.bp;

            // 3. Fetch active contracts/snapshots via chain endpoint
            let snapshots: any[] = [];
            let nextToken: string | null = null;
            do {
                const chainUrl = new URL(`https://data.alpaca.markets/v2/options/chain/${underlying}`);
                chainUrl.searchParams.append("feed", alpacaOptionFeed);
                chainUrl.searchParams.append("expiration_date_gte", today);
                chainUrl.searchParams.append("expiration_date_lte", maxDateStr);
                chainUrl.searchParams.append("limit", "1000");
                if (nextToken) chainUrl.searchParams.append("page_token", nextToken);

                const sRes = await fetch(chainUrl.toString(), {
                    headers: { "APCA-API-KEY-ID": alpacaKey, "APCA-API-SECRET-KEY": alpacaSecret }
                });
                if (!sRes.ok) throw new Error(`Alpaca Chain Error for ${underlying}: ${await sRes.text()}`);
                const sData = await sRes.json() as { snapshots: any[], next_page_token: string | null };
                snapshots = snapshots.concat(sData.snapshots || []);
                nextToken = sData.next_page_token;
            } while (nextToken);

            // 4. Transform snapshots into DB rows
            const rows: any[] = [];
            let withGreeks = 0;
            let dte0 = 0;

            for (const snap of snapshots) {
                // Parse symbol metadata from symbol string (e.g. IWM250321C00248000)
                // contract_symbol: IWM 250321 C 00248000
                const matches = snap.symbol.match(/^([A-Z]+)(\d{6})([CP])(\d{8})$/);
                if (!matches) continue;

                const symbol = matches[1];
                const expStr = matches[2]; // YYMMDD
                const type = matches[3];
                const strikeInt = parseInt(matches[4]);
                const strike = strikeInt / 1000;
                
                const expYear = "20" + expStr.substring(0, 2);
                const expMonth = expStr.substring(2, 4);
                const expDay = expStr.substring(4, 6);
                const expirationDate = `${expYear}-${expMonth}-${expDay}`;

                const expDate = new Date(expirationDate);
                const dte = Math.ceil((expDate.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
                if (dte === 0) dte0++;

                const bid = snap.latestQuote?.bp;
                const ask = snap.latestQuote?.ap;
                const mid = (bid && ask) ? (bid + ask) / 2 : null;
                const spread = (bid && ask) ? ask - bid : null;
                const spreadPct = (spread && mid) ? (spread / mid) * 100 : null;

                const intrinsic = type === 'C' 
                    ? Math.max(0, underlyingPrice - strike)
                    : Math.max(0, strike - underlyingPrice);
                const extrinsic = mid ? Math.max(0, mid - intrinsic) : null;
                const moneyness = type === 'C' ? underlyingPrice / strike : strike / underlyingPrice;

                if (snap.greeks) withGreeks++;

                rows.push({
                    snapshot_ts: snapshotTs,
                    contract_symbol: snap.symbol,
                    underlying: symbol,
                    expiration_date: expirationDate,
                    strike_price: strike,
                    option_type: type,
                    dte,
                    moneyness,
                    intrinsic_value: intrinsic,
                    extrinsic_value: extrinsic,
                    underlying_price: underlyingPrice,
                    last_trade_price: snap.latestTrade?.p,
                    last_trade_size: snap.latestTrade?.s,
                    last_trade_ts: snap.latestTrade?.t,
                    last_trade_exchange: snap.latestTrade?.x,
                    last_trade_condition: snap.latestTrade?.c,
                    bid_price: bid,
                    bid_size: snap.latestQuote?.bs,
                    bid_exchange: snap.latestQuote?.bx,
                    ask_price: ask,
                    ask_size: snap.latestQuote?.as,
                    ask_exchange: snap.latestQuote?.ax,
                    quote_ts: snap.latestQuote?.t,
                    quote_condition: snap.latestQuote?.c,
                    mid_price: mid,
                    bid_ask_spread: spread,
                    bid_ask_spread_pct: spreadPct,
                    implied_volatility: snap.impliedVolatility,
                    delta: snap.greeks?.delta,
                    gamma: snap.greeks?.gamma,
                    theta: snap.greeks?.theta,
                    vega: snap.greeks?.vega,
                    rho: snap.greeks?.rho,
                    has_greeks: !!snap.greeks,
                    has_trade: !!snap.latestTrade,
                    has_quote: !!snap.latestQuote,
                    feed: alpacaOptionFeed
                });
            }

            // 5. Batch insert
            for (let i = 0; i < rows.length; i += 200) {
                const batch = rows.slice(i, i + 200);
                const { error: insertError } = await supabase.from("options_chain").insert(batch);
                if (insertError) console.error(`[OPTIONS-INGEST] Error inserting ${underlying} batch:`, insertError);
            }

            grandTotalRows += rows.length;

            // 6. Log summary row
            await supabase.from("seed_jobs").insert({
               job_type: 'options_snapshot',
               symbol: underlying,
               status: 'completed',
               rows_written: rows.length,
               metadata: { with_greeks: withGreeks, nulls_0dte: dte0, snapshot_ts: snapshotTs }
            });
            
            console.log(`[OPTIONS-INGEST] ${underlying}: ${rows.length} contracts, ${withGreeks} w/ greeks, ${dte0} 0DTE`);
        }

        return new Response(JSON.stringify({ 
            status: "success", 
            total_rows: grandTotalRows, 
            snapshot_ts: snapshotTs 
        }), { status: 200 });

    } catch (err: any) {
        console.error("[OPTIONS-INGEST] Critical Failure:", err);
        return new Response(JSON.stringify({ error: err.message }), { status: 500 });
    }
};

export const config: Config = {
    schedule: "*/5 13-20 * * 1-5"
};
