import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

const ALPACA_API_KEY = process.env.ALPACA_API_KEY || "";
const ALPACA_API_SECRET = process.env.ALPACA_API_SECRET || "";
const ALPACA_BASE_URL = process.env.ALPACA_BASE_URL || "https://paper-api.alpaca.markets";

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

  try {
    // 1. Fetch Alpaca Account
    let account = { equity: 0, buying_power: 0, portfolio_value: 0, daytrade_count: 0 };
    try {
      const alpacaRes = await fetch(`${ALPACA_BASE_URL}/v2/account`, {
        headers: {
          "APCA-API-KEY-ID": ALPACA_API_KEY,
          "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
          "Content-Type": "application/json",
        },
      });
      if (alpacaRes.ok) {
        const data = await alpacaRes.json();
        account = {
          equity: parseFloat(data.equity || "0"),
          buying_power: parseFloat(data.buying_power || "0"),
          portfolio_value: parseFloat(data.portfolio_value || "0"),
          daytrade_count: parseInt(data.daytrade_count || data.day_trade_count || "0", 10),
        };
      }
    } catch (e) {
      console.error("Alpaca fetch failed:", e);
    }

    // 2. Fetch Heartbeat & Pipeline
    const { data: botStatus } = await supabase
      .from("bot_status")
      .select("*")
      .eq("id", 1)
      .maybeSingle();

    let heartbeat_at: string | null = null;
    let heartbeat_age_seconds = 999999;
    let is_healthy = false;

    if (botStatus && botStatus.last_heartbeat) {
      heartbeat_at = botStatus.last_heartbeat;
      const hbTime = new Date(botStatus.last_heartbeat).getTime();
      heartbeat_age_seconds = Math.max(0, Math.floor((Date.now() - hbTime) / 1000));
      is_healthy = heartbeat_age_seconds < 120;
    }

    // 3. Fetch Kill Switch Active
    const { data: settings } = await supabase
      .from("user_settings")
      .select("trading_enabled")
      .eq("id", 1)
      .maybeSingle();

    const kill_switch_active = settings ? !settings.trading_enabled : false;

    // 4. Fetch Regime States (limit 18)
    const { data: regimesData } = await supabase
      .from("regime_states")
      .select("symbol, regime, probability:regime_probability, detected_at")
      .order("detected_at", { ascending: false })
      .limit(18);

    const regimes = (regimesData || []).map((r: any) => ({
      symbol: r.symbol,
      regime: (r.regime || "QUIET").toUpperCase(),
      probability: r.probability ? parseFloat(r.probability) : 0,
      detected_at: r.detected_at,
    }));

    // 5. Fetch Agent Signals (limit 5)
    const { data: signalsData } = await supabase
      .from("agent_signals")
      .select("symbol, action, confidence, asset_class, created_at")
      .order("created_at", { ascending: false })
      .limit(5);

    const signals = (signalsData || []).map((s: any) => ({
      symbol: s.symbol,
      action: s.action || "HOLD",
      confidence: s.confidence != null ? parseFloat(s.confidence) : 0.5,
      asset_class: s.asset_class || "equity",
      created_at: s.created_at,
    }));

    // 6. Fetch counts
    const { count: signals_total } = await supabase
      .from("agent_signals")
      .select("*", { count: "exact", head: true });

    const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const { count: news_24h } = await supabase
      .from("news_articles")
      .select("*", { count: "exact", head: true })
      .gt("created_at", twentyFourHoursAgo);

    const { count: regime_states_count } = await supabase
      .from("regime_states")
      .select("*", { count: "exact", head: true });

    const { count: snapshots_count } = await supabase
      .from("portfolio_snapshots")
      .select("*", { count: "exact", head: true });

    // 7. Fetch positions (latest row from portfolio_snapshots)
    const { data: latestSnapshot } = await supabase
      .from("portfolio_snapshots")
      .select("*")
      .order("snapshot_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    // Fallback if Alpaca keys failed
    if (account.equity === 0 && latestSnapshot) {
      account.equity = parseFloat(latestSnapshot.equity || "0");
      account.buying_power = parseFloat(latestSnapshot.buying_power || "0");
      account.portfolio_value = parseFloat(latestSnapshot.portfolio_value || latestSnapshot.equity || "0");
    }

    return new Response(
      JSON.stringify({
        account,
        pipeline: {
          heartbeat_at,
          heartbeat_age_seconds,
          kill_switch_active,
          is_healthy,
        },
        regimes,
        signals,
        counts: {
          signals_total: signals_total || 0,
          news_24h: news_24h || 0,
          regime_states: regime_states_count || 0,
          snapshots: snapshots_count || 0,
        },
        positions: latestSnapshot || null,
      }),
      { status: 200, headers: JSON_HEADERS }
    );
  } catch (err: any) {
    console.error("System health check failed:", err);
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: JSON_HEADERS,
    });
  }
};
