TASK: READ-ONLY forensic audit of what the live/paper trading fleet is ACTUALLY
running on, in light of new findings. Recent rigorous backtesting (docs/
hmm_signal_diagnosis.md in ut-bot-lumibot) established: (1) the UT Bot daily signal
has no edge on SPY (corr -0.0385, expectancy ~0); (2) the HMM regime detector's
semantic labels are ANTI-predictive (BULL precedes the worst forward returns) and
its vol estimate is a redundant copy of 20d realized vol (corr 0.906) — it has been
dropped from backtest sizing; (3) a 10bp global fee assumption was masking true
economics. The question this audit answers: HOW MUCH OF THE RUNNING FLEET DEPENDS
ON THE THINGS JUST FALSIFIED?

MODE: READ-ONLY. Change nothing. No commits to code. The only artifact you produce
is the audit report (committed on branch `audit/fleet-signal-dependencies`).

SCOPE: the execution stack described in this repo and its deployment — run_agents.py,
run_crypto_bot.py, main.py, agents/ (regime_detector, kelly sizer, signal agents,
timesfm_forecaster, pairs_trader, greeks_calculator), the HITL queue writers, the
SignalDecayMonitor, and the Telegram alerting path. If parts live in another repo
or only on the host, enumerate what you can see and EXPLICITLY LIST what you cannot.

PRODUCE docs/fleet_signal_audit.md answering, with file:line evidence per claim:
1. SIGNAL INVENTORY: every signal the fleet can act on (symbol, timeframe, signal
   logic, which agent). For each: is it the same UT Bot implementation just proven
   edgeless, a variant, or something independent?
2. HMM DEPENDENCY MAP: every consumer of regime_states / the regime detector. For
   each consumer: what does it DO with the label (sizing? gating? display-only?),
   and is it exposed to the anti-predictive BULL/BEAR problem? Note especially the
   KellySizer's regime input.
3. COST ASSUMPTIONS: what fee/spread assumptions does the LIVE sizing/execution
   path carry? Is the 10bp-style global constant present anywhere in live code?
4. DECISION AUTHORITY: for each signal, can it reach a live order without HITL
   approval? (Map the hitl_queue path vs any direct-execution paths.)
5. RISK RANKING: rank findings by "damage if this runs as-is on paper->live",
   with a one-line recommended action each (e.g. "disable regime input to sizer",
   "leave: display-only"). Recommendations only — implement nothing.
6. STALENESS CHECK: cross-reference against the SignalDecayMonitor — is the live
   IC monitoring even wired to the signals actually trading, and would it catch
   the edgeless-signal condition the backtest found? (Recall its known weakness:
   30-trade Spearman windows are statistically thin.)

PERSIST: commit ONLY docs/fleet_signal_audit.md on the audit branch; push. Also
insert one summary row to Supabase table `system_audits` (create via migration if
absent: audit_id, scope, findings_count, critical_count, report_path, created_at)
— this is the single allowed write, via existing service_role env config.

GUARDRAILS: touch no agent code, no configs, no schedules. If you find something
alarming (e.g. a signal path that bypasses HITL), REPORT it prominently — do not
hot-fix it. Uncertainty must be labeled uncertainty; do not fill gaps between
repos with plausible guesses.

ACCEPTANCE: audit doc with file:line evidence for every claim; explicit list of
what was out of view; risk-ranked recommendations; branch pushed; audit row in
Supabase.
