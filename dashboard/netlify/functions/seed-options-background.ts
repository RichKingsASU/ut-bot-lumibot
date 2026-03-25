import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const alpacaKey = process.env.ALPACA_API_KEY!;
const alpacaSecret = process.env.ALPACA_API_SECRET!;
const alpacaOptionFeed = process.env.ALPACA_OPTION_FEED || 'opra';

const supabase = createClient(supabaseUrl, supabaseServiceKey);

export default async (req: Request) => {
    const startTime = Date.now();
    let body: any = {};
    try {
        const text = await req.text();
        if (text) body = JSON.parse(text);
    } catch (e) {}

    const underlying = body.underlying || "IWM";
    const dteMax = body.dte_max || 60;

    console.log(`[SEED-OPTIONS] Starting seed for ${underlying} (DTE max: ${dteMax})`);

    // 1. Insert seed job
    const { data: job, error: jobError } = await supabase
        .from("seed_jobs")
        .insert({
            job_type: "options_seed",
            symbol: underlying,
            status: "running"
        })
        .select().single();

    if (jobError) return new Response(JSON.stringify({ error: jobError.message }), { status: 500 });
    const jobId = job.id;

    try {
        const today = new Date().toISOString().split('T')[0];
        const maxDate = new Date();
        maxDate.setDate(maxDate.getDate() + dteMax);
        const maxDateStr = maxDate.toISOString().split('T')[0];

        // 2. Fetch active contracts metadata
        console.log(`[SEED-OPTIONS] Fetching contracts for ${underlying}...`);
        let contracts: any[] = [];
        let nextContractToken: string | null = null;
        do {
            const contractUrl = new URL("https://api.alpaca.markets/v2/options/contracts");
            contractUrl.searchParams.append("underlying_symbol", underlying);
            contractUrl.searchParams.append("expiration_date_gte", today);
            contractUrl.searchParams.append("expiration_date_lte", maxDateStr);
            contractUrl.searchParams.append("status", "active");
            contractUrl.searchParams.append("limit", "1000");
            if (nextContractToken) contractUrl.searchParams.append("page_token", nextContractToken);

            const cRes = await fetch(contractUrl.toString(), {
                headers: { "APCA-API-KEY-ID": alpacaKey, "APCA-API-SECRET-KEY": alpacaSecret }
            });
            if (!cRes.ok) throw new Error(`Alpaca Contracts Error: ${await cRes.text()}`);
            const cData = await cRes.json() as { option_contracts: any[], next_page_token: string | null };
            contracts = contracts.concat(cData.option_contracts || []);
            nextContractToken = cData.next_page_token;
        } while (nextContractToken);

        console.log(`[SEED-OPTIONS] Found ${contracts.length} active contracts.`);

        // 3. Fetch snapshots using the chain endpoint
        console.log(`[SEED-OPTIONS] Fetching snapshots for ${underlying} chain...`);
        let snapshots: any[] = [];
        let nextSnapToken: string | null = null;
        do {
            const chainUrl = new URL(`https://data.alpaca.markets/v2/options/chain/${underlying}`);
            chainUrl.searchParams.append("feed", alpacaOptionFeed);
            chainUrl.searchParams.append("expiration_date_gte", today);
            chainUrl.searchParams.append("expiration_date_lte", maxDateStr);
            chainUrl.searchParams.append("limit", "1000");
            if (nextSnapToken) chainUrl.searchParams.append("page_token", nextSnapToken);

            const sRes = await fetch(chainUrl.toString(), {
                headers: { "APCA-API-KEY-ID": alpacaKey, "APCA-API-SECRET-KEY": alpacaSecret }
            });
            if (!sRes.ok) throw new Error(`Alpaca Chain Error: ${await sRes.text()}`);
            const sData = await sRes.json() as { snapshots: any[], next_page_token: string | null };
            snapshots = snapshots.concat(sData.snapshots || []);
            nextSnapToken = sData.next_page_token;
        } while (nextSnapToken);

        // 4. Fetch underlying snapshot for current price
        const uRes = await fetch(`https://data.alpaca.markets/v2/stocks/${underlying}/snapshot?feed=sip`, {
            headers: { "APCA-API-KEY-ID": alpacaKey, "APCA-API-SECRET-KEY": alpacaSecret }
        });
        const uData = await uRes.json() as any;
        const underlyingPrice = uData.latestTrade?.p || uData.latestQuote?.bp;

        // 5. Build final records
        const snapshotTs = new Date().toISOString();
        const rows: any[] = [];
        let withGreeks = 0;
        let dte0 = 0;

        // Create a map for quick contract metadata lookup
        const contractMap = new Map(contracts.map(c => [c.symbol, c]));

        for (const snap of snapshots) {
            const contract = contractMap.get(snap.symbol);
            if (!contract) continue;

            const expDate = new Date(contract.expiration_date);
            const dte = Math.ceil((expDate.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
            if (dte === 0) dte0++;

            const bid = snap.latestQuote?.bp;
            const ask = snap.latestQuote?.ap;
            const mid = (bid && ask) ? (bid + ask) / 2 : null;
            const spread = (bid && ask) ? ask - bid : null;
            const spreadPct = (spread && mid) ? (spread / mid) * 100 : null;

            const optionType = contract.type === 'call' ? 'C' : 'P';
            const strike = parseFloat(contract.strike_price);
            
            const intrinsic = optionType === 'C' 
                ? Math.max(0, underlyingPrice - strike)
                : Math.max(0, strike - underlyingPrice);
            const extrinsic = mid ? Math.max(0, mid - intrinsic) : null;
            const moneyness = optionType === 'C' ? underlyingPrice / strike : strike / underlyingPrice;

            if (snap.greeks) withGreeks++;

            rows.push({
                snapshot_ts: snapshotTs,
                contract_symbol: snap.symbol,
                underlying,
                expiration_date: contract.expiration_date,
                strike_price: strike,
                option_type: optionType,
                contract_style: contract.style,
                contract_size: contract.size || 100,
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
                open_interest: contract.open_interest,
                open_interest_date: contract.open_interest_date,
                prev_close_price: contract.close_price,
                prev_close_date: contract.close_price_date,
                has_greeks: !!snap.greeks,
                has_trade: !!snap.latestTrade,
                has_quote: !!snap.latestQuote,
                feed: alpacaOptionFeed
            });
        }

        // 6. Batch insert into Supabase
        const totalRows = rows.length;
        for (let i = 0; i < rows.length; i += 200) {
            const batch = rows.slice(i, i + 200);
            const { error: insertError } = await supabase.from("options_chain").insert(batch);
            if (insertError) console.error("[SEED-OPTIONS] Insert Batch Error:", insertError);
        }

        // 7. Complete job record
        await supabase.from("seed_jobs").update({
            status: "completed",
            completed_at: new Date().toISOString(),
            rows_written: totalRows,
            metadata: { with_greeks: withGreeks, nulls_0dte: dte0 }
        }).eq("id", jobId);

        return new Response(JSON.stringify({ 
            contracts_seeded: totalRows, 
            with_greeks: withGreeks, 
            nulls_0dte: dte0,
            duration_ms: Date.now() - startTime 
        }), { status: 200 });

    } catch (err: any) {
        console.error("[SEED-OPTIONS] Failure:", err);
        await supabase.from("seed_jobs").update({
            status: "failed",
            error_msg: err.message,
            completed_at: new Date().toISOString()
        }).eq("id", jobId);
        return new Response(JSON.stringify({ error: err.message }), { status: 500 });
    }
};
