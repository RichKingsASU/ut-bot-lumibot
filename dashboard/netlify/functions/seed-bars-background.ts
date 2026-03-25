import { Config } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";
import fetch from "node-fetch";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const alpacaKey = process.env.ALPACA_API_KEY!;
const alpacaSecret = process.env.ALPACA_API_SECRET!;
const alpacaFeed = process.env.ALPACA_FEED || 'sip';

const supabase = createClient(supabaseUrl, supabaseServiceKey);

export default async (req: Request) => {
  const startTime = Date.now();
  let body: any = {};
  try {
    const text = await req.text();
    if (text) body = JSON.parse(text);
  } catch (e) {
    console.error("Error parsing request body:", e);
  }

  const symbol = body.symbol || "IWM";
  const timeframe = body.timeframe || "15Min";
  const days = body.days || 730;

  console.log(`[SEED-BARS] Starting seed for ${symbol} ${timeframe} (${days} days)`);

  // 1. Insert seed_jobs row
  const { data: job, error: jobError } = await supabase
    .from("seed_jobs")
    .insert({
      job_type: "bars",
      symbol,
      timeframe,
      status: "running",
      metadata: { requested_days: days }
    })
    .select()
    .single();

  if (jobError) {
    console.error("[SEED-BARS] Job tracking error:", jobError);
    return new Response(JSON.stringify({ error: "Failed to create seed job" }), { status: 500 });
  }

  const jobId = job.id;

  try {
    // 2. Calculate start date
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);
    let startStr = startDate.toISOString();
    
    let nextToken: string | null = null;
    let totalRows = 0;
    const batchSize = 1000;
    let currentBatch: any[] = [];

    // 3. Paginate through Alpaca SIP bars
    do {
      const url = new URL(`https://data.alpaca.markets/v2/stocks/${symbol}/bars`);
      url.searchParams.append("timeframe", timeframe);
      url.searchParams.append("start", startStr);
      url.searchParams.append("feed", alpacaFeed);
      url.searchParams.append("adjustment", "all");
      url.searchParams.append("limit", "10000");
      if (nextToken) url.searchParams.append("page_token", nextToken);

      const res = await fetch(url.toString(), {
        headers: {
          "APCA-API-KEY-ID": alpacaKey,
          "APCA-API-SECRET-KEY": alpacaSecret
        }
      });

      if (res.status === 429) {
        console.warn("[SEED-BARS] Rate limited, waiting 1s...");
        await new Promise(r => setTimeout(r, 1000));
        continue;
      }

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Alpaca API Error (${res.status}): ${errText}`);
      }

      const data = await res.json() as { bars: any[], next_page_token: string | null };
      const bars = data.bars || [];
      nextToken = data.next_page_token;

      for (const bar of bars) {
        currentBatch.push({
          symbol,
          timeframe,
          ts: bar.t,
          open: bar.o,
          high: bar.h,
          low: bar.l,
          close: bar.c,
          volume: bar.v,
          vwap: bar.vw,
          trade_count: bar.n,
          feed: alpacaFeed
        });

        if (currentBatch.length >= batchSize) {
          const { error: upsertError } = await supabase
            .from("ohlcv_bars")
            .upsert(currentBatch, { onConflict: "symbol,timeframe,ts" });

          if (upsertError) console.error("[SEED-BARS] Upsert error:", upsertError);
          
          totalRows += currentBatch.length;
          currentBatch = [];

          // Update progress every 5000 rows
          if (totalRows % 5000 === 0) {
            await supabase
              .from("seed_jobs")
              .update({ rows_written: totalRows })
              .eq("id", jobId);
          }
        }
      }

      // Check timeout (12 min mark)
      if (Date.now() - startTime > 12 * 60 * 1000) {
        console.warn("[SEED-BARS] Time limit approaching, saving checkpoint.");
        if (currentBatch.length > 0) {
            await supabase.from("ohlcv_bars").upsert(currentBatch, { onConflict: "symbol,timeframe,ts" });
            totalRows += currentBatch.length;
        }
        await supabase.from("seed_jobs").update({
            status: "partial",
            rows_written: totalRows,
            metadata: { ...job.metadata, last_ts: bars[bars.length - 1]?.t, next_token: nextToken }
        }).eq("id", jobId);
        return new Response(JSON.stringify({ status: "partial", totalRows, nextToken }), { status: 200 });
      }

    } while (nextToken);

    // Final batch
    if (currentBatch.length > 0) {
      const { error: upsertError } = await supabase
        .from("ohlcv_bars")
        .upsert(currentBatch, { onConflict: "symbol,timeframe,ts" });
      if (upsertError) console.error("[SEED-BARS] Final batch upsert error:", upsertError);
      totalRows += currentBatch.length;
    }

    // 4. Update completion
    await supabase
      .from("seed_jobs")
      .update({
        status: "completed",
        completed_at: new Date().toISOString(),
        rows_written: totalRows,
        date_from: startStr.split('T')[0],
        date_to: new Date().toISOString().split('T')[0]
      })
      .eq("id", jobId);

    console.log(`[SEED-BARS] Finished seeding ${symbol} ${timeframe}. Total rows: ${totalRows}`);
    return new Response(JSON.stringify({
      total_rows: totalRows,
      symbol,
      timeframe,
      duration_ms: Date.now() - startTime
    }), { status: 200 });

  } catch (err: any) {
    console.error("[SEED-BARS] Critical Failure:", err);
    await supabase
      .from("seed_jobs")
      .update({
        status: "failed",
        error_msg: err.message,
        completed_at: new Date().toISOString()
      })
      .eq("id", jobId);
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
};
