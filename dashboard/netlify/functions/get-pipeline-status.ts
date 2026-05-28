import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

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
    // 1. Fetch last cycle run time and info
    const { data: latestSignalData } = await supabase
      .from("agent_signals")
      .select("created_at, asset_class, reasoning")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    let ran_at: string | null = null;
    let cycle_age_seconds = 999999;
    let asset_class_last = "equity";

    if (latestSignalData) {
      ran_at = latestSignalData.created_at;
      if (ran_at) {
        cycle_age_seconds = Math.max(0, Math.floor((Date.now() - new Date(ran_at).getTime()) / 1000));
      }
      asset_class_last = latestSignalData.asset_class || "equity";
    }

    // 2. Fetch Crypto Signals (limit 5)
    const { data: cryptoData } = await supabase
      .from("agent_signals")
      .select("symbol, action, confidence, reasoning, created_at")
      .eq("asset_class", "crypto")
      .order("created_at", { ascending: false })
      .limit(5);

    const crypto_signals = (cryptoData || []).map((s: any) => ({
      symbol: s.symbol,
      action: s.action || "HOLD",
      confidence: s.confidence != null ? parseFloat(s.confidence) : 0.5,
      reasoning: s.reasoning || "",
      created_at: s.created_at,
    }));

    // 3. Fetch Equity Signals (limit 5)
    const { data: equityData } = await supabase
      .from("agent_signals")
      .select("symbol, action, confidence, reasoning, created_at")
      .eq("asset_class", "equity")
      .order("created_at", { ascending: false })
      .limit(5);

    const equity_signals = (equityData || []).map((s: any) => ({
      symbol: s.symbol,
      action: s.action || "HOLD",
      confidence: s.confidence != null ? parseFloat(s.confidence) : 0.5,
      reasoning: s.reasoning || "",
      created_at: s.created_at,
    }));

    // 4. Fetch Regime Summary (limit 10)
    const { data: regimesData } = await supabase
      .from("regime_states")
      .select("symbol, regime, probability, detected_at")
      .order("detected_at", { ascending: false })
      .limit(10);

    const regime_summary = (regimesData || []).map((r: any) => ({
      symbol: r.symbol,
      regime: (r.regime || "QUIET").toUpperCase(),
      regime_probability: r.probability ? parseFloat(r.probability) : 0,
      detected_at: r.detected_at,
    }));

    // 5. Parse Debate from latest signal's reasoning
    let debate = {
      bull_score: null as number | null,
      bear_score: null as number | null,
      verdict: null as string | null,
      confidence: null as number | null,
    };

    if (latestSignalData && latestSignalData.reasoning) {
      try {
        const parsed = JSON.parse(latestSignalData.reasoning);
        debate.bull_score = parsed.bull_score !== undefined ? parsed.bull_score : (parsed.bull !== undefined ? parsed.bull : null);
        debate.bear_score = parsed.bear_score !== undefined ? parsed.bear_score : (parsed.bear !== undefined ? parsed.bear : null);
        debate.verdict = parsed.verdict || parsed.decision || null;
        debate.confidence = parsed.confidence !== undefined ? parsed.confidence : (parsed.score !== undefined ? parsed.score : null);

        // Normalize confidence if it's 0-1
        if (debate.confidence !== null && debate.confidence <= 1.0 && debate.confidence > 0) {
          debate.confidence = Math.round(debate.confidence * 100);
        }
        if (debate.bull_score !== null && debate.bull_score <= 1.0 && debate.bull_score > 0) {
          debate.bull_score = Math.round(debate.bull_score * 100);
        }
        if (debate.bear_score !== null && debate.bear_score <= 1.0 && debate.bear_score > 0) {
          debate.bear_score = Math.round(debate.bear_score * 100);
        }
      } catch (e) {
        // Reasoning is text, not JSON - debate fields remain null
      }
    }

    return new Response(
      JSON.stringify({
        last_cycle: {
          ran_at,
          cycle_age_seconds,
          asset_class_last,
        },
        crypto_signals,
        equity_signals,
        regime_summary,
        debate,
      }),
      { status: 200, headers: JSON_HEADERS }
    );
  } catch (err: any) {
    console.error("Pipeline status check failed:", err);
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: JSON_HEADERS,
    });
  }
};
