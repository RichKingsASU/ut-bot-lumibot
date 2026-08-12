#!/bin/bash
# Copies updated unit files to /etc/systemd/system/ and reloads systemd.
#
# GUARDED: the units in systemd/ do NOT match what runs on k2. Running this
# script unmodified would take production down. See docs/SECRETS.md.
#
#   systemd/ units          live on k2
#   --------------          ----------
#   da-trading.service      da-trading-bot.service
#   da-crypto.service       da-crypto-bot.service
#   da-agents.service       da-agents.service        <- NAME COLLISION
#   da-watchdog.service     da-watchdog.service      <- NAME COLLISION
#   da-hermes.service       (not installed)
#
# Two independent problems:
#
#   1. Name collisions. da-agents and da-watchdog would be OVERWRITTEN with the
#      versions in this directory. The non-colliding names would install as
#      ADDITIONAL units -- so da-trading.service would run a second trading bot
#      alongside da-trading-bot.service, both against the same account.
#
#   2. Secret backend mismatch. Every unit in systemd/ launches via
#      `doppler run --token ${DOPPLER_TOKEN} --project disrupting-alpha
#      --config prd`, and gates on ConditionFileNotEmpty=/etc/systemd/system/
#      da-doppler.conf. The live units read EnvironmentFile=.../.env directly
#      and do not use Doppler at all. k2 has the Doppler CLI installed but
#      unconfigured and not logged in.
#
# Before removing this guard, reconcile systemd/*.service with the units
# actually running (`systemctl cat da-trading-bot` etc.) and decide which
# secret backend k2 should use. Do not do it while the market is open.

set -euo pipefail

cat >&2 <<'GUARD'
REFUSING TO RUN.

The unit files in systemd/ do not match the units running on this host, and
installing them would overwrite da-agents and da-watchdog while adding a
duplicate trading bot under a different name.

Compare before proceeding:
    systemctl cat da-trading-bot da-crypto-bot da-agents da-watchdog
    grep -l doppler systemd/*.service

See docs/SECRETS.md for the current secret-management split.

To install a single reconciled unit deliberately:
    sudo cp systemd/<unit>.service /etc/systemd/system/<live-name>.service
    sudo systemctl daemon-reload
    sudo systemctl restart <live-name>
GUARD
exit 1
