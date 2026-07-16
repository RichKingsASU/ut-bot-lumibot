TASK: Test the UT Bot signal in its native habitat — IWM options — using the
existing options backtest harness (PR #44 lineage), under the same evidentiary
standards recently established: strict real data, honest per-asset costs, gross vs
net, and the harness's own go/no-go gate: NET EXPECTANCY PER TRADE AFTER SPREAD
COSTS. The daily-SPY-equity version of this signal was just proven edgeless
(docs/hmm_signal_diagnosis.md); the open question is whether the signal earns its
keep on the instrument it was designed for.

BRANCH: create and work on `research/iwm-options-habitat`. Do not commit to main.

ESTABLISHED CONTEXT:
- run_options_backtest.py + backtests/ harness exist (merged PR #44, SHA a6a882a):
  IWM, UT Bot ATR signals, parameter sweep across DTE / strike modes / timeframes.
- The provenance layer is live: load_underlying returns SourcedData; strict mode
  raises on missing real data. DO NOT weaken it.
- Cost model refactor: fee_pct keyword-only, FEE_PER_SIDE per asset class. Options
  costs are NOT a per-side percentage fee — spread crossing dominates. Read how the
  harness currently models spread/commission BEFORE running anything, and report it.
- Known accepted deviation in calculate_ut_signals (2-branch) — sweep as-is.

DO, IN ORDER:
1. AUDIT THE HARNESS FIRST (report before running): (a) where does it source IWM
   underlying bars, and is that path provenance-stamped real data? If IWM minute/daily
   parquet is missing from /mnt/tick-storage/historical/equities/IWM/, seed it via
   scripts/seed_historical.py (daily via yfinance for depth; minute via alpaca if
   creds present — report actual coverage obtained). (b) How are option prices
   generated — real chains or a pricing model (Black-Scholes off underlying + IV
   assumption)? State this explicitly in every output: MODELED option prices are a
   provenance class of their own — label results data_provenance=real_underlying_
   modeled_options if that's what the harness does. Do not present modeled-option
   results as market-data results. (c) What spread-cost assumption does the gate use,
   and is it realistic for IWM options (penny-wide ATM front-month vs wider back
   months)? Justify or fix the assumption with a written note.
2. Run the harness's existing parameter sweep (DTE x strike mode x timeframe) with
   UT Bot signals on the maximum real IWM history available. Flat sizing; no HMM
   (it's been dropped from sizing — see diagnosis doc).
3. Apply the go/no-go gate per cell: net expectancy per trade after spread. Same
   overfit guard as Track 1: report median cell vs best cell; flag islands.
4. Output: printed table + backtests/results/iwm_options_habitat.json + a decision
   memo at docs/iwm_habitat_findings.md with a clear GO / NO-GO / INSUFFICIENT-DATA
   verdict and the reasoning. If the data can't support a verdict (e.g. only ~2 yrs
   of usable intraday history), SAY SO — insufficient evidence is a valid finding.
5. PERSIST: one row per cell to the same Supabase `backtest_results` table
   (coordinate schema with Track 1's migration if both run; use IF NOT EXISTS).
   service_role via existing env config only.
6. GIT: commit scripts changed, results, memo, any seed manifests, on the branch;
   push to origin.

GUARDRAILS: no execution-logic changes; no synthetic underlying data ever; if the
harness's option-pricing model has a look-ahead (e.g. IV taken from the exit date),
flag it and STOP for my decision rather than shipping a flattering number. The gate
is the gate — do not move it to manufacture a GO.

ACCEPTANCE: harness audit written BEFORE results; provenance class of option prices
stated on every output; gate verdict delivered with median-vs-best honesty check;
branch pushed; Supabase rows written.
