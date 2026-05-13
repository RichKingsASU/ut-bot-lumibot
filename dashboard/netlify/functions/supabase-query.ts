import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

const supabase = createClient(supabaseUrl, supabaseKey);

export default async (req: Request, context: Context) => {
  // ── [SECURITY FIX] Simple API Key Authorization ──────────────────────
  const adminKey = process.env.ADMIN_API_KEY;
  const requestKey = req.headers.get("X-Admin-API-Key");

  if (adminKey && requestKey !== adminKey) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const url = new URL(req.url);
  const type = url.searchParams.get("type");
  const symbol = url.searchParams.get("symbol");
  const timeframe = url.searchParams.get("timeframe") || "1m";
  const limit = parseInt(url.searchParams.get("limit") || "100");
  const underlying = url.searchParams.get("underlying");

  try {
    if (type === "bars") {
      if (!symbol) return new Response("Missing symbol", { status: 400 });
      const { data, error } = await supabase
        .from("ohlcv_bars")
        .select("*")
        .eq("symbol", symbol)
        .eq("timeframe", timeframe)
        .order("ts", { ascending: false })
        .limit(limit);

      if (error) throw error;
      return new Response(JSON.stringify(data.reverse()), { status: 200 });
    }

    if (type === "signals") {
      if (!symbol) return new Response("Missing symbol", { status: 400 });
      const { data, error } = await supabase
        .from("bot_signals")
        .select("*")
        .eq("symbol", symbol)
        .order("ts", { ascending: false })
        .limit(limit);

      if (error) throw error;
      return new Response(JSON.stringify(data), { status: 200 });
    }

    if (type === "inventory") {
      const { data: bars, error: barsError } = await supabase
        .from("data_inventory")
        .select("*");
      
      const { data: options, error: optionsError } = await supabase
        .from("options_inventory")
        .select("*");

      if (barsError) throw barsError;
      if (optionsError) throw optionsError;

      return new Response(JSON.stringify({ bars, options }), { status: 200 });
    }

    if (type === "options") {
      if (!underlying) return new Response("Missing underlying", { status: 400 });
      const dteMax = parseInt(url.searchParams.get("dte_max") || "45");
      
      // Get latest snapshot timestamp
      const { data: latestTsData } = await supabase
        .from("options_chain")
        .select("ts")
        .eq("underlying", underlying)
        .order("ts", { ascending: false })
        .limit(1);
      
      if (!latestTsData || latestTsData.length === 0) {
        return new Response(JSON.stringify([]), { status: 200 });
      }

      const { data, error } = await supabase
        .from("options_chain")
        .select("*")
        .eq("underlying", underlying)
        .eq("ts", latestTsData[0].ts)
        .lte("dte", dteMax)
        .order("strike", { ascending: true });

      if (error) throw error;
      return new Response(JSON.stringify(data), { status: 200 });
    }

    return new Response("Invalid type", { status: 400 });
  } catch (err: any) {
    console.error("[QUERY] Error:", err);
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
};
