# Disrupting Alpha — systemd supervision units

These units keep the trading stack **continuously running and auto-restarting**
on the `/home/k2` edge host. They exist because the root cause of the equity
bot producing **zero signals** was never a code bug — the signal logic is
correct (see `docs/signal_zero_diagnosis.md`). The real cause was **uptime**:
the bot was alive only ~5 scattered days and, by chance, was never online during
one of the ~10 trailing-stop crossover days/year (the last was 2026-06-15).

The existing watchdog (`scripts/watchdog.py`) only **alerts** — it runs
`systemctl is-active da-trading-bot` and sends a Telegram message if a service
is dead. It relies on systemd's own `Restart=` policy to actually bring the
service back. If the unit lacks `Restart=always`, a crashed bot **stays dead**
(this is consistent with the QA audit's "trading layer down ~3 days"). It was
also launched from a **tmux session** — a single point of failure that dies with
the tmux server (QA audit finding P0-14).

## Units

| Unit | Runs | Purpose |
|------|------|---------|
| `da-trading-bot.service` | `main.py` | UT Bot options trading bot (equities) |
| `da-agents.service` | `run_agents.py` | Agent orchestration pipeline |
| `da-crypto-bot.service` | `run_crypto_bot.py` | Crypto trading bot |
| `da-watchdog.service` | `run_agent_watchdog.py` | Self-healing watchdog (off tmux) |

All four use:
- `Restart=always`, `RestartSec=10–15` — restart on any exit.
- `StartLimitIntervalSec=0` — **never give up** on a crash loop. Uptime is the
  whole point; `da-watchdog` will Telegram-alert a human if the bot flaps, so a
  crash loop is noisy, not silent. (This is the deliberate opposite of systemd's
  default start-rate limiting, which is what let the bot stay silently dead.)
- `EnvironmentFile=/home/k2/ut-bot-lumibot/.env` — load credentials/config.
- `User=k2` — run as the app user, not root (unlike `storage-guard.service`,
  which needs root for mounts/docker).

## Install (on the host, as root)

```bash
cd /home/k2/ut-bot-lumibot
git pull                       # get these unit files
sudo bash scripts/systemd/install_da_services.sh
```

The script copies the units to `/etc/systemd/system/`, runs `daemon-reload`, and
`enable --now`s each. It is idempotent — re-run it after editing a unit.

## Verify

```bash
systemctl status da-trading-bot da-agents da-crypto-bot da-watchdog
journalctl -u da-trading-bot -f          # follow logs
systemctl is-active da-trading-bot        # what watchdog CHECK 3 runs
```

## Important caveats

1. **`.env` format.** systemd's `EnvironmentFile` is **not** a shell — it reads
   plain `KEY=value` lines and does **not** honor `export` or perform expansion.
   If `.env` has `export FOO=bar`, systemd loads the key as `export FOO`. The
   installer warns if it detects `export` lines; convert them to `KEY=value`.
2. **User/paths.** Units assume user `k2`, repo at `/home/k2/ut-bot-lumibot`, and
   venv at `venv/bin/python`. Edit the units if your host differs, then re-run
   the installer.
3. **`start_all.sh` already expects these.** It comments the tmux launches for
   `trading-bot`/`crypto-bot`/`agents` with "Core services managed by systemd
   now" — these units provide the referenced `da-*` services. Also move the
   `watchdog` tmux launch (line ~38) to `da-watchdog.service` and drop it from
   `start_all.sh`.
4. **This fixes uptime, not strategy behavior.** Once the bot stays up
   continuously it will catch the ~4%-of-days crossover events it currently
   misses. No change to signal logic or params is involved.
