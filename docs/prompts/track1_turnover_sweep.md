TASK: Parameter sweep to reduce the UT Bot signal's turnover on daily SPY and measure
whether lower trade count moves gross return toward/past zero. This is RESEARCH on a
signal already proven edgeless at current params — the question is whether the edge
was being destroyed by overtrading or never existed at any parameterization.

BRANCH: create and work on `research/turnover-sweep`. Do not commit to main.

ESTABLISHED CONTEXT (do not re-derive; see docs/hmm_signal_diagnosis.md):
- Strict real-parquet SPY 2000-2026 (6,671 daily bars) loads cleanly.
- Current UT Bot params produce 645 trades, gross -28.6%, net -37.3% at the correct
  1bp/side equity fee, 12.1% total fee drag, corr(pos, fwd ret) = -0.0385, win rate
  35.5%, avg win +2.4% / avg loss -1.4%.
- calculate_ut_signals has a KNOWN, ACCEPTED deviation from published UT Bot (2-branch
  vs 4-branch; documented). DO NOT fix or alter it — sweep the existing implementation.
- simulate_portfolio and the cost model are validated (buy-and-hold reproduces +436.8%).
  fee_pct is keyword-only; equity_etf = 0.0001/side.

DO:
1. Read the signal implementation to identify its actual tunable parameters (ATR
   period, ATR multiplier / sensitivity, and any smoothing). List them with current
   values before sweeping.
2. Build scripts/sweep_utbot_turnover.py: grid sweep over ATR period (e.g. 10, 14,
   21, 30, 50) x multiplier (e.g. 1, 2, 3, 4, 6) — adjust ranges to what the code's
   params actually are. For each cell run the STRICT full-window SPY backtest with
   the validated engine and 1bp fee, using flat 100% sizing (isolate the signal;
   no vol targeting in this sweep).
3. For each cell record: trades, gross return, net return, Sharpe, maxDD, fee-drag %,
   win rate, expectancy/trade, avg hold. Also record buy-and-hold once as benchmark.
4. Output: a ranked table (by net Sharpe) printed + saved to
   backtests/results/utbot_turnover_sweep.json AND a markdown summary at
   docs/turnover_sweep_findings.md answering ONE question honestly: does ANY cell
   show positive net expectancy per trade, or does the edge not exist at any
   parameterization? Guard against the obvious trap: with ~25 cells, the best cell
   will look better by luck alone — report the median cell alongside the best, and
   flag if the best cell is an island (neighbors much worse = overfit artifact,
   not signal).
5. PERSIST: write one row per sweep cell to Supabase table `backtest_results`
   (create via migration if absent: run_id, strategy, symbol, timeframe, params
   jsonb, gross_return, net_return, sharpe, max_drawdown, trades, fee_drag_pct,
   data_provenance, created_at). Use env-configured service_role credentials that
   the repo's existing safe_write/Supabase client already uses — never hardcode keys.
6. GIT: commit the sweep script, results JSON, findings doc, and any migration on
   the branch; push to origin. Open no PR — I'll review the branch.

GUARDRAILS: no changes to calculate_ut_signals, simulate_portfolio, or cost model.
Strict mode only — if SyntheticDataError fires, STOP and report, don't work around.
Every result row and JSON carries data_provenance=real_parquet.

ACCEPTANCE: sweep completes on real data; ranked table exists in JSON + Supabase +
markdown; the median-vs-best overfit check is reported; branch pushed. SUCCESS IS AN
HONEST ANSWER, including "no parameterization has edge" — do not torture the grid
until something looks good.
