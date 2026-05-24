import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

const supabase = createClient(supabaseUrl, supabaseKey);

export default async (req: Request, context: Context) => {
  // Simple API Key Authorization
  const adminKey = process.env.ADMIN_API_KEY;
  const requestKey = req.headers.get("X-Admin-API-Key");

  if (adminKey && requestKey !== adminKey) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    // 1. Get latest greeks snapshot for each symbol
    const { data: symbolsData, error: symbolsError } = await supabase.rpc(
      'get_latest_greeks_snapshots'
    );
    
    let greeksResult;
    
    // If RPC doesn't exist, use raw query
    if (symbolsError && symbolsError.code === '42883') {
      // Postgres DISTINCT ON workaround using a subquery/view or direct SQL via postgres
      // Since we are limited in Supabase JS client to do DISTINCT ON directly easily without RPC,
      // we'll fetch all ordered and filter in JS if needed, or better, fetch latest snapshots.
      // Assuming a reasonable number of rows, we can fetch recent and dedupe.
      const { data: rawData, error: rawError } = await supabase
        .from('greeks_snapshots')
        .select('symbol, delta, gamma, theta, vega, iv_rank, rvol, trade_mode, snapshot_at, underlying_price, strike, option_type')
        .order('snapshot_at', { ascending: false })
        .limit(1000);
        
      if (rawError) throw rawError;
      
      const latestMap = new Map();
      if (rawData) {
          for (const row of rawData) {
              if (!latestMap.has(row.symbol)) {
                  latestMap.set(row.symbol, row);
              }
          }
      }
      greeksResult = Array.from(latestMap.values());
    } else if (symbolsError) {
      throw symbolsError;
    } else {
      greeksResult = symbolsData;
    }

    const symbolsMap: Record<string, any> = {};
    for (const row of (greeksResult || [])) {
        symbolsMap[row.symbol] = row;
    }

    // 2. Query circuit breaker events (gamma > 0.05 in last 24h)
    const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const { data: eventsData, error: eventsError } = await supabase
      .from('greeks_snapshots')
      .select('symbol, gamma, trade_mode, snapshot_at')
      .gt('gamma', 0.05)
      .gt('snapshot_at', twentyFourHoursAgo)
      .order('snapshot_at', { ascending: false })
      .limit(10);

    if (eventsError) throw eventsError;

    // Check if market is currently open (simple check for now)
    const now = new Date();
    const day = now.getUTCDay();
    const hours = now.getUTCHours();
    const mins = now.getUTCMinutes();
    const marketOpen = day >= 1 && day <= 5 && 
                      ((hours > 13 || (hours === 13 && mins >= 30)) && 
                       (hours < 20));

    return new Response(JSON.stringify({
      symbols: symbolsMap,
      high_gamma_events: eventsData || [],
      last_updated: new Date().toISOString(),
      market_open: marketOpen
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  } catch (err: any) {
    console.error("[GET_GREEKS] Error:", err);
    return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }
};
