#!/usr/bin/env bash
#
# Install/refresh the Disrupting Alpha systemd units that keep the trading
# stack continuously supervised (Restart=always). Run ON THE HOST as root:
#
#     sudo bash scripts/systemd/install_da_services.sh
#
# Idempotent: re-running copies the latest unit files and reloads systemd.
set -euo pipefail

REPO_DIR="/home/k2/ut-bot-lumibot"
UNIT_SRC="${REPO_DIR}/scripts/systemd"
UNIT_DST="/etc/systemd/system"
SERVICES=(da-trading-bot da-agents da-crypto-bot da-watchdog)

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: must run as root (use sudo)." >&2
  exit 1
fi

# ── Preflight ────────────────────────────────────────────────────────────────
if [[ ! -f "${REPO_DIR}/.env" ]]; then
  echo "ERROR: ${REPO_DIR}/.env not found — units require it (EnvironmentFile)." >&2
  exit 1
fi
if [[ ! -x "${REPO_DIR}/venv/bin/python" ]]; then
  echo "ERROR: ${REPO_DIR}/venv/bin/python not found — create the venv first." >&2
  exit 1
fi

# systemd's EnvironmentFile parser is NOT a shell: it reads plain KEY=value
# lines and does not honor `export` or unquoted values with spaces. Warn if the
# .env uses `export`, which would be loaded literally as part of the key.
if grep -qE '^\s*export\s' "${REPO_DIR}/.env"; then
  echo "WARNING: ${REPO_DIR}/.env contains 'export' lines. systemd EnvironmentFile" >&2
  echo "         does not strip 'export'; convert those lines to plain KEY=value." >&2
fi

# ── Install ──────────────────────────────────────────────────────────────────
for svc in "${SERVICES[@]}"; do
  src="${UNIT_SRC}/${svc}.service"
  [[ -f "${src}" ]] || { echo "ERROR: missing unit ${src}" >&2; exit 1; }
  echo "Installing ${svc}.service ..."
  install -m 0644 "${src}" "${UNIT_DST}/${svc}.service"
done

systemctl daemon-reload

for svc in "${SERVICES[@]}"; do
  systemctl enable --now "${svc}.service"
done

echo
echo "Done. Current status:"
for svc in "${SERVICES[@]}"; do
  printf '  %-16s %s\n' "${svc}" "$(systemctl is-active "${svc}.service" 2>/dev/null || true)"
done
echo
echo "Logs:    journalctl -u da-trading-bot -f"
echo "Restart: sudo systemctl restart da-trading-bot"
