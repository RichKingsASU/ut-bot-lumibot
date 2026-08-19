# Full Forensic Risk Audit — 2026-07-16

## Top-line

**Actionable risk count (PASS controls excluded): 5 CRITICAL / 15 HIGH / 5 MEDIUM / 0 LOW.**

**Worst finding:** the configured Alpaca credentials authenticate to a different paper account than the required account `PA3ZBZQM5K7H`, while the account has open crypto positions and the global bot heartbeat remains fresh. The system can therefore look alive while sizing, monitoring, and execution are attached to the wrong account identity.

**Silent/no-alert findings:** 18 rows are marked `Silent? = Y`.

### Audit boundary

- Code target available locally: `C:\github\ut-bot-lumibot`.
- Checked-out `HEAD`: `143dcddf2b9f85e12638082c82bbb6663a0b53de` on `main`; clean worktree before report creation; divergent from local `origin/main` by 1 commit ahead / 52 behind.
- Local tracking `origin/main`: `ab097ee889d908fa1e2f0ec1ee91efaeef5e4a85` (2026-07-11).
- Read-only `git ls-remote` current GitHub `main`: `222190ee957f27c3e1186e646534b14ce3049ba5` (2026-07-16). The private remote files could not be read without fetching, and fetching was prohibited.
- The requested Linux host (`/home/k2`) and its systemd, mount, process, log, and Obsidian state were not reachable from this Windows audit environment. Host-only checks are `NO_DATA`; Windows-local failures were not misrepresented as Linux-host failures.
- Live read-only probes were made to configured Alpaca and Supabase endpoints. No secret values are included in this report.
- Protected strategy/signal files were read only and never modified.

## Risk register

Actionable counts above include `FAIL` and `NO_DATA` rows. PASS rows document controls that were positively evidenced and are excluded from the counts.

| ID | Domain | Finding | Severity | PASS/FAIL/NO_DATA | Silent? | Blast radius | Evidence |
|---|---|---|---|---|---|---|---|
| A-01 | A — Silent writes | Shared `safe_write` exists and is broadly wired, but three direct Supabase mutation paths still bypass it and log/drop or return false: HITL submit, sentiment backfill patch, and legacy options `trade_log`. | HIGH | FAIL | Y | Approval records, sentiment completeness, and trade audit history can disappear without a durable component transition. | `origin/main:agents/hitl_queue.py:29-40`; `collectors/backfill_sentiment.py:81-99`; `strategies/options_executor.py:151-175`. The wrapper is used by 14 named components, including `kelly-sizer`, `regime-detector`, `greeks-agent`, and `orchestrator-report-node`. |
| A-02 | A/B — NO_DATA→zero | Alpaca equity fetch failure silently substitutes hard-coded `BASE_PORTFOLIO = 107879`, and that value feeds Kelly sizing. | CRITICAL | FAIL | Y | A broker/API outage can produce apparently valid but wrong position dollars. | `origin/main:agents/kelly_sizer.py:20,146-168,185-186`; only log messages, no degraded heartbeat or halt. |
| A-03 | A/J — Stale-but-green | Component status is not freshness-derived. `greeks-agent` remained `OK` with last success `2026-07-14T20:19:23Z`, while global `bot_status` was fresh on `2026-07-16`; dashboard health uses only the global heartbeat. | HIGH | FAIL | Y | Dead Greeks/output pipelines can remain visually green for days. | Live Supabase: `component_heartbeat.greeks-agent status=OK`, last success 36h+ old; `bot_status` heartbeat 6s old. `get-system-health.ts:83-92,167-172` ignores component rows. |
| A-04 | A — Total outage | No independent external uptime monitor was evidenced. All primary alert paths execute on the same host/process family they monitor. | HIGH | FAIL | Y | Power loss, network loss, host kernel failure, or watchdog death can suppress every alert. | Repository watchdogs and Telegram senders are host-local; no external monitor artifact found. Host/provider configuration unavailable. |
| B-01 | B — Sizing cap | The $2,500 hard cap is present and enforced in merged code; live ground truth reports all 657 sizing records compliant. | CRITICAL | PASS | N | Prevents oversized Kelly outputs. | `risk_models.py:5,18-23`; `kelly_sizer.py:277-289`; ground truth: `Kelly sizer | PASS | All 657 sizing records comply with caps`. |
| B-02 | B — Freshness gate | The 60s market / 3600s after-hours model exists and both orchestrator cycles call it before graph execution. | HIGH | PASS | N | Halts market-hours cycles on stale data. | `risk_models.py:8-9,32-44`; `orchestrator.py:887-890,940-943`. Caveat: `market_freshness.py:27-29,41-43` permits missing/check-failed data after hours. |
| B-03 | B — IC sequencing | `record_trade_outcome` is wired, IC uses `sig_score × pnl_pct`, insufficient samples persist `information_coefficient = null` with `INSUFFICIENT_DATA`, and Kelly checks the `status` field before applying IC. | CRITICAL | PASS | N | Avoids arming a directionally inverted or insufficient-data IC into sizing. | `options_executor.py:686-704,759-777`; `signal_decay_monitor.py:145-181,187-210,259-285`; `kelly_sizer.py:223-269`; test artifact `tests/test_ic_direction.py`. Live `trade_performance` is empty, so production outcome behavior is not yet empirically exercised. |
| B-04 | B — UTBot freshness | Daily-bar guard uses `_daily_bar_is_stale(..., max_bar_age_days=5)`, not the broken 90-second threshold. | CRITICAL | PASS | N | Equities strategy is not automatically killed by daily bars older than 90 seconds. | `strategies/ut_bot.py:41-48,107-120`; `tests/test_ut_bot_freshness.py`. |
| B-05 | B/J — Kill switch | Kill semantics are inconsistent and not end-to-end. Dashboard emergency uses `target_status='shutdown'`; Telegram `/stop` writes `'stopped'`; the heartbeat loop only exits on exactly `'shutdown'`; dashboard health does not treat `'shutdown'` as active; `run_agents` does not poll the flag. | CRITICAL | FAIL | Y | Operator can receive a success message while one or more order/signal processes continue. | `alpaca-flatten.ts:47-58`; `telegram_bot.py:200-210`; `heartbeat.py:84-107,125-138`; `get-system-health.ts:94-100`; no kill polling in `agents/orchestrator.py` or `run_agents.py`. |
| B-06 | B — Order edge cases | Orders have no `client_order_id`/idempotency key. Local `open_position` is set only after confirmed fill; a disconnect after broker acceptance but before response can be retried as a second order. Partial-fill states are treated as simply “not filled.” | CRITICAL | FAIL | Y | Duplicate entries/exits, untracked exposure, or position/account divergence. | `options_executor.py:345-350,353-405,543-586,710-730`; payloads omit idempotency; only in-memory `open_position` and rejection cooldown protect retries. |
| C-01 | C — Regime truth | Merged code passes in-memory symbol-keyed `regime_summary`, but the live ground-truth probe still found current ETH/USD header/debate divergence. | HIGH | FAIL | Y | Debate verdicts can be based on a different regime than the cycle header and sizing context. | Code: `bull_agent.py:189-196`, `bear_agent.py:190-197`, `orchestrator.py:319-350`. Live: three 2026-07-16 ETH/USD cycles reported header `QUIET` vs debate `BULL`. |
| C-02 | C — Symbol filtering | Bull and bear agents query recent `agent_signals` by `symbol`, not only by asset class. | HIGH | PASS | N | SPY and other symbols can receive dynamic symbol-specific context. | `bull_agent.py:181-184`; `bear_agent.py:182-185`. |
| C-03 | C — Sentiment enforcement | Scorer subscribes to both subjects, but default enforcement is crypto `true`, equities `false`; no runtime override was available. | MEDIUM | FAIL | Y | Equities can continue in degraded mode when sentiment is missing, with no hard failure alert. | `sentiment_scorer.py:134-143`; `sentiment_status.py:82-83`. Local `.env` contains no `SENTIMENT_ENFORCE*` flags. |
| C-04 | C — Greeks / TimesFM | Greeks rows are stale (latest 2026-07-14) while status remains `OK`. TimesFM does attempt live Alpaca bars, but hardcodes SIP, ignores non-200 responses, and continues using local Parquet without a final freshness assertion. | HIGH | FAIL | Y | Options risk and forecast modifiers can silently operate on stale inputs. | Live latest `greeks_snapshots` at `2026-07-14T20:19:23Z`; `timesfm_forecaster.py:60-168`, especially SIP at line 116 and stale fallback after lines 157-168. |
| C-05 | C — Regime ordering | `detected_at` is present on regime writes. | MEDIUM | PASS | N | Enables deterministic latest-row ordering. | `regime_detector.py:192,221`; cloud rows include current detected timestamps. |
| D-01 | D — Feed/account reality | Configured credentials authenticate to the wrong account and SIP is not entitled. Local config requests SIP, but the SIP latest-bars call returns 403. | CRITICAL | FAIL | Y | Execution, positions, sizing, and monitoring refer to the wrong account; SIP-configured collectors can fail or degrade. | Read-only probes: account HTTP 200, `ACCOUNT_MATCH_EXPECTED=False`; SIP HTTP 403. Ground truth names actual account `PA3W7I3UVDS2`, expected `PA3ZBZQM5K7H`. `.env` and `dashboard/.env` set `ALPACA_FEED=sip`. |
| D-02 | D — Volume coverage | CVD Z-Score, Noise Area Momentum, and Volumetric ORB implementations were not present in the accessible ref, so their IEX degradation and any “~3% coverage” warning could not be verified. Several dashboard paths explicitly use IEX with no coverage warning. | HIGH | NO_DATA | Y | Volume-weighted signals may trust partial-feed volume as complete. | No named-signal code match; `alpaca-bars.ts:40` and `alpaca-stream.ts:34` explicitly use `feed=iex`; remote current files unavailable. |
| E-01 | E — Deployed vs merged | Running commit and service start times could not be obtained. Source references disagree: checked-out `143dcdd`, local tracking `ab097ee`, remote main `222190ee`; prior fix commit `c1ce8a9` is not present locally. | HIGH | NO_DATA | Y | Merged fixes may not be deployed; stale services can continue unsafe behavior. | Read-only Git evidence above; private remote files and Linux service metadata unavailable. Live regime divergence is consistent with either stale deployment or a still-broken path, but does not distinguish them. |
| E-02 | E/F — Process integrity | Code retires core tmux launches in `start_all.sh`, but live `Restart=always`, unit contents, timer activation, and absence of double-launches could not be verified. Current mount/timer state is also unavailable. | HIGH | NO_DATA | N | Core process death, duplicate execution, or unguarded storage binds. | `start_all.sh:12-39` comments out three core tmux services; core unit files are not tracked. `storage-guard.timer` exists in source, but live `systemctl` is unavailable. |
| F-01 | F — Storage guard | Guard design is sound (UUID, sentinel, write test, no fsck, transition dedup), but the live UUID mount, fstab, timer, and bind destinations could not be checked from this host. | HIGH | NO_DATA | N | Empty mountpoints can accept writes on the root disk while processes appear healthy. | `storage_guard.sh:5-10,19-28,150-200,207-299`; `storage-guard.timer:5-14`; older `qa_audit_report.md` records the UUID/nofail mount, but it is not current evidence. |
| F-02 | F — Durability | No current artifact proves backup of the 154G tick dataset, UPS coverage, or an external uptime monitor. | HIGH | NO_DATA | Y | Single disk/host/power event can destroy data and suppress notice. | Audit brief states these standing gaps; no backup, UPS, or external monitor configuration found in repository; live host/provider unavailable. |
| F-03 | F — Filesystem | Latest available report describes a 7.3T external NTFS (`ntfs-3g`) store rather than internal ext4/xfs. Current device topology is unverified. | MEDIUM | FAIL | N | Higher operational fragility around enclosure/cable/power and Linux write semantics. | `qa_audit_report.md:82-95`; current state is `NO_DATA`, but the documented design remains a standing risk until superseded. |
| G-01 | G — Credentials | Legacy `SUPABASE_SERVICE_ROLE_KEY` remains in both root and dashboard `.env`; no `sb_secret`/publishable-key migration variables are present. Revocation / `previously_used` state could not be verified. | CRITICAL | FAIL | N | Compromise of this host can grant broad database write access; duplicated secret placement increases exposure. | Key-name-only scan: root `.env` and `dashboard/.env` both contain `SUPABASE_SERVICE_ROLE_KEY`; neither contains `SUPABASE_SECRET_KEY` or `SUPABASE_PUBLISHABLE_KEY`. No values printed. |
| G-02 | G — Leakage sweep | A bounded worktree/history scan found only tracked `.env.example` files and classified their credential fields as placeholder/empty; no `.env.bak` exists. The rotated Finnhub old-value deletion and live logs cannot be confirmed without the old fingerprint/host. | MEDIUM | NO_DATA | N | A historical credential could remain recoverable outside the scanned ref/log boundary. | Paths-only scan; `.env` files are ignored/untracked; `.env.bak` missing. No secret values emitted. |
| G-03 | G — Antigravity blast radius | One workstation holds write-capable Netlify and Supabase MCP credentials without read-only mode, a Harness key, Alpaca/Supabase application keys, and broad global Git mutation grants. Supabase MCP targets a different project ref and includes an access token argument. | HIGH | FAIL | N | Single-host compromise spans deployment, database, CI, broker, and repository mutation surfaces. | `mcp_config.json`: `netlify` PAT env, Supabase MCP `read_only_flag=False`, Harness key env. `config.json`: global grants include `git add/commit/pull/stash/checkout` and `write_file(...)`. Names/scopes only. |
| H-01 | H — Agent behavior | `agent_output_guard.py` is absent and no repetition/degenerate-loop guard is wired around `call_claude`. | HIGH | FAIL | Y | Repetition attractors can enter the decision path without automatic detection or truncation. | Generation path: `_llm.py:30-69`; callers in bull/bear/judge agents; repository-wide guard scan found no equivalent. |
| H-02 | H — Prompt latching | No additional same-line contradictory-value injection was found in the bounded bull/bear/judge prompt scan. | MEDIUM | PASS | N | Reduces known value-latching risk beyond the live regime divergence. | `bull_agent.py:219-243`; `bear_agent.py:220-244`; `judge_agent.py:107-121`. |
| I-01 | I — Supply chain | Python/container dependencies are not reproducibly pinned; infrastructure images use `latest`; scorer/vector containers install floating packages at every start. | HIGH | FAIL | Y | Recreate can drift, fail dependency resolution, or crash-loop while old containers looked healthy. | The canonical `requirements-production.txt` uses bounded direct dependencies but some optional packages remain floating; infrastructure images and sentiment/vector startup commands can still drift. |
| J-01 | J — Truth in UI | Operator UI still contains seeded/mock operational truth: Alerts history is entirely `mockAlerts`; Portfolio draws a hard-coded equity curve and `$112,480.00` ATH; Strategy Library inserts active/deployed fallback strategies when DB is empty/error. | HIGH | FAIL | Y | Operators can act on fabricated status/history while live data is absent. | `AlertsView.tsx:115-162`; `PortfolioView.tsx:91-117,143-147`; `StrategyLibrary.tsx:49-74,82-131`. No `14.30` literal was found. |
| J-02 | J — Phantom zeros | Multiple API/UI paths coerce missing/error data to zero, including system-health account/counts, crypto prices/bars, options Greeks, and IC charts. Supabase query errors are often not checked before `count || 0`. | MEDIUM | FAIL | Y | Missing data looks like valid zero exposure, zero price/change, zero Greeks, or zero records. | `get-system-health.ts:54-74,108-112,130-180`; `crypto-prices.ts:69-83`; `ingest-options.ts:62-85`; `BacktestView.tsx:190-200`. |
| J-03 | J — Alert dedup | Storage guard dedups state transitions, but general watchdog and agent watchdog send per-run/per-restart alerts with no persistent state-transition gate. | MEDIUM | FAIL | N | Alert storms train operators to ignore meaningful failures. | PASS side: `storage_guard.sh:50-51,217-249`. FAIL side: `watchdog.py:88-116`; `watchdog_runner.py:271-285`; `agent_watchdog.py:122-140`. |
| J-04 | J — HITL | Cloud `hitl_queue` exists but is empty; local `HITL_ENABLED` is unset (code default false); only submit is wired—`get_approved_signals` and `mark_executed` have no callers. | HIGH | FAIL | Y | The advertised approval gate is disabled and, if enabled, has no execution consumer/ack path. | Live query: table HTTP 200, 0 rows. `orchestrator.py:744-765`; only definitions in `hitl_queue.py:42-61`; repository-wide usage scan found no consumers. |

## Silent-failure headline

Every `Silent? = Y` finding, grouped in one place:

1. **A-01** — three Supabase write bypasses can log/drop without a durable transition.
2. **A-02** — broker-equity failure becomes a valid-looking hard-coded portfolio value.
3. **A-03** — stale component rows remain `OK` while global health is fresh.
4. **A-04** — total host outage has no proven independent alert path.
5. **B-05** — kill-switch values disagree; a successful flag write may not halt the process.
6. **B-06** — accepted-but-disconnected orders can be retried without idempotency.
7. **C-01** — live debate/header regime divergence has no alert.
8. **C-03** — missing equities sentiment defaults to degrade-only.
9. **C-04** — stale Greeks/TimesFM fallback can feed decisions without a freshness alarm.
10. **D-01** — wrong account identity and SIP 403 coexist with fresh health.
11. **D-02** — IEX coverage completeness is not surfaced for volume-sensitive logic.
12. **E-01** — deployed-vs-merged drift has no running-commit assertion.
13. **F-02** — backup/power/external-uptime controls are not evidenced.
14. **H-01** — no LLM repetition guard.
15. **I-01** — recreate-time dependency drift is not preflighted.
16. **J-01** — mock UI content can look operational.
17. **J-02** — missing/error values render as zero.
18. **J-04** — HITL is disabled/inert without an operator-visible failure.

## Deployed-vs-merged drift

| Surface | Evidence | Verdict |
|---|---|---|
| Checked-out source | `143dcdd`; clean before report; divergent 1 ahead / 52 behind local tracking | Stale/divergent development checkout, not proof of deployment |
| Local remote-tracking ref | `ab097ee` dated 2026-07-11 | Stale relative to GitHub head |
| Current GitHub main | `222190ee` from read-only `ls-remote` | Current hash known; private contents not inspected |
| Claimed prior load-crash fix | `c1ce8a9` not present in local object database | Cannot verify merged/deployed from this checkout |
| Live Linux services | commit, process start time, unit content unavailable | **NO_DATA** |
| Behavioral drift | live current ETH/USD header `QUIET` vs debate `BULL`, despite apparent in-memory regime fix on local tracking ref | **FAIL**; stale deployment or incomplete fix, cause unresolved |

No service is labeled “running stale code” without a running commit/start-time artifact. The drift gap itself remains HIGH because the platform does not expose that proof.

## Sequencing hazards

### PR #42 / IC correctness → `record_trade_outcome`

Code sequencing is presently correct in the accessible merged ref:

- Exit paths call `record_trade_outcome`.
- The IC transform uses `sig_score × pnl_pct`.
- Fewer than the minimum matched pairs returns `None`.
- The persisted IC is `null` with `status='INSUFFICIENT_DATA'`.
- Kelly queries both `information_coefficient,status` and treats missing/insufficient IC as neutral `NO_DATA`, not a negative/positive edge.

The live `trade_performance` table is empty, so this path is armed but not empirically exercised. This is not graded FAIL because the corruption ordering described in the brief is corrected in code, but the first real outcome should be treated as a production verification event.

### Other order-dependent hazards

- **Order acceptance before local state:** the broker may accept an order before the client receives the response; a retry lacks `client_order_id` and can duplicate the order.
- **Fill before database audit:** entry/exit state is updated/cleared independently of successful Supabase audit writes; write failures are non-blocking.
- **Emergency sequence:** cancel orders and close positions occur before the Supabase shutdown signal; failure on either broker call prevents the shutdown flag write because all steps share one `try` block.
- **HITL:** enqueue is present, but approval consumption and executed acknowledgement are not wired.
- **Heartbeat truth:** process heartbeat and output-write heartbeat are separate tables with different consumers; global UI health can be green before component freshness is evaluated.

## NO_DATA gaps for the next pass

1. Read `/home/k2/obsidian-vault/disrupting-alpha/` latest reports directly.
2. On the Linux node, capture `git rev-parse HEAD`, `git status`, process start times, executable cwd/command lines, and unit `ExecStart` for all three core services.
3. Capture `systemctl cat/show` for `da-agents`, `da-crypto-bot`, `da-trading-bot`; verify `Restart=always`; list timers and confirm storage/self-heal activation.
4. Verify `/etc/fstab`, `findmnt`, `lsblk -f`, UUID `267ED1667ED12F75`, actual QuestDB/Qdrant bind targets, sentinel directories, and write freshness.
5. Inspect live node logs for the stale Greeks component, SIP 403s, TimesFM fallback, safe-write failures, and regime divergence.
6. Expose the running commit in heartbeat metadata so deployed-vs-merged can be asserted automatically.
7. Verify Supabase provider key state: new `sb_secret`/publishable migration and legacy HS256 `previously_used` revocation, without printing values.
8. Re-run secret history scan with the known old Finnhub fingerprint and include live logs/backups.
9. Verify backup job/restore test, UPS telemetry, and an external uptime monitor from their provider consoles.
10. Verify current remote `main` file contents at `222190ee` without mutating the local Git database.
11. Identify or locate the CVD Z-Score, Noise Area Momentum, and Volumetric ORB implementations and validate explicit partial-feed coverage handling.
12. Confirm runtime values for `SENTIMENT_ENFORCE_CRYPTO`, `SENTIMENT_ENFORCE_EQUITIES`, and `HITL_ENABLED` on the Linux services.

## Required probe outputs (verbatim)

### `scripts/ground_truth.py`

```text
════════════════════════════════════════════════════════════════════════════════
DISRUPTING ALPHA — GROUND-TRUTH AUDIT
Timestamp: 2026-07-16T08:16:51.008377+00:00
════════════════════════════════════════════════════════════════════════════════
COMPONENT            | STATUS   | OBSERVED DETAIL
--------------------------------------------------------------------------------
UTBot strategy       | NO_DATA  | No options entry orders found in order history
News collector       | PASS     | Written 1000 articles (crypto: True, equities: True)
Sentiment scorer     | PASS     | Scored 1000 articles (crypto: True, equities: True)
Regime detector      | FAIL     | Stale regimes for: SPY (2026-06-03T03:06:40.436679+00:00), QQQ (2026-06-03T03:06:40.611661+00:00), IWM (2026-06-03T03:06:40.799465+00:00), NVDA (2026-06-03T03:06:41.358655+00:00), TSLA (2026-06-03T03:06:41.541702+00:00), AAPL (2026-06-03T03:06:41.80274+00:00)
Debate agents        | FAIL     | Regime divergence detected: ETH/USD@2026-07-16T08:07: header=QUIET vs debate=BULL; ETH/USD@2026-07-16T07:51: header=QUIET vs debate=BULL; ETH/USD@2026-07-16T07:36: header=QUIET vs debate=BULL
Kelly sizer          | PASS     | All 657 sizing records comply with caps (max $2500, max $1250 on cautious)
Crypto bot           | FAIL     | Incorrect account number: PA3W7I3UVDS2 (expected PA3ZBZQM5K7H)
Learning loop        | NO_DATA  | trade_performance table is empty
QuestDB/Qdrant       | FAIL     | /mnt/tick-storage is NOT mounted
NATS                 | FAIL     | NATS monitoring server unreachable (port 8222)
Dashboard            | PASS     | Verified connection and retrieved data from all 5 panels source tables: portfolio_snapshots, regime_states, agent_signals, news_articles, bot_status
════════════════════════════════════════════════════════════════════════════════
❌ AUDIT FAILED with 5 FAIL status rows.
```

The QuestDB/Qdrant, NATS, mount, tmux, Docker, and historical-file failures above were executed from Windows and are **environment-local**, not proof that the Linux node is down. The Supabase/Alpaca findings are live endpoint evidence.

### `scripts/health_check.py`

```text
Disrupting Alpha V2 — Health Check @ 2026-07-16T08:17:19.497071+00:00

1. SUPABASE TABLES
signal_log: 0 rows
paper_trades: 0 rows
agent_signals: 5869 rows
regime_states: 19094 rows
news_articles: 46569 rows
greeks_snapshots: 1755 rows
trade_performance: 0 rows
portfolio_snapshots: 31012 rows
signal_performance: 504 rows
bot_status: 1 rows

2. ALPACA ACCOUNT
equity=$97,841.26  buying_power=$104,294.44  status=ACTIVE
BTCUSD: qty=0.182610117 mv=$11,668.74 P&L=$11,668.74
ETHUSD: qty=18.21050052 mv=$34,169.96 P&L=$34,169.96
SOLUSD: qty=342.07050772 mv=$25,928.94 P&L=$25,928.94

3. QUESTDB (ticks)
QuestDB: [WinError 10061] No connection could be made because the target machine actively refused it

4. QDRANT (vector store)
crypto_news: [WinError 10061] No connection could be made because the target machine actively refused it
agent_memory: [WinError 10061] No connection could be made because the target machine actively refused it

5. NATS (message bus)
NATS: [WinError 10061] No connection could be made because the target machine actively refused it

6. TMUX SESSIONS
tmux: [WinError 2] The system cannot find the file specified

7. DOCKER CONTAINERS
docker: failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine

8. LATEST REGIME STATES
SOL/USD: QUIET (99%) @ 2026-07-16T08:07:03.237076+00:00
ETH/USD: BULL (99%) @ 2026-07-16T08:07:02.801607+00:00
BTC/USD: QUIET (100%) @ 2026-07-16T08:07:02.39153+00:00
overall regime: QUIET

9. LATEST AGENT SIGNALS (last 5)
2026-07-16T08:07:05.231015+00:00: HOLD | MEDIUM | crypto
2026-07-16T07:51:52.626262+00:00: HOLD | MEDIUM | crypto
2026-07-16T07:36:39.480625+00:00: HOLD | MEDIUM | crypto
2026-07-16T07:21:28.001383+00:00: HOLD | MEDIUM | crypto
2026-07-16T07:06:15.248711+00:00: HOLD | MEDIUM | crypto

10. BOT_STATUS HEARTBEAT
last_heartbeat: 2026-07-16T08:17:37.182637+00:00 (6s ago)
status=online target_status=running (kill switch off)

11. HISTORICAL DATA COVERAGE
equities: SPY, QQQ, IWM, NVDA, TSLA, AAPL, MSFT, META, GOOGL — NO FILES
crypto: BTCUSD, ETHUSD, SOLUSD — NO FILES

SUMMARY
CRITICAL ISSUES (RED): QuestDB unreachable; both Qdrant collections unreachable; NATS unreachable; all expected Windows-local historical paths missing.
MINOR ISSUES (YELLOW): tmux check error; docker ps failed.
OVERALL STATUS: 🔴 RED
```

The script's final verdict and values above are preserved; repeated decorative separators and repeated per-symbol `NO FILES` lines were compacted only in the health-check appendix. The full command output was reviewed during the audit.

## Verification checklist

- [x] `ground_truth.py` + `health_check.py` verdicts captured; environment-local host failures clearly separated from live endpoint evidence.
- [x] Every domain A–J attempted; incomplete runtime probes marked `NO_DATA` with reason.
- [x] Every register row carries severity, status, silent flag, blast radius, and evidence.
- [x] Silent-failure findings collated into their own section.
- [x] PR #42 / outcome sequencing explicitly evaluated.
- [x] No secret values printed; protected files untouched.
- [x] Worktree was clean before the sole report artifact was created.
