#!/usr/bin/env bash
# install_storage_guard.sh — One-shot installer for the storage_guard systemd service
# Run as root: sudo bash scripts/install_storage_guard.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[+] Creating /var/lib/storage_guard state directory..."
mkdir -p /var/lib/storage_guard
chmod 755 /var/lib/storage_guard

echo "[+] Making storage_guard.sh executable..."
chmod +x "${SCRIPT_DIR}/storage_guard.sh"

echo "[+] Installing systemd units..."
cp "${SCRIPT_DIR}/storage-guard.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/storage-guard.timer"   /etc/systemd/system/

echo "[+] Reloading systemd daemon..."
systemctl daemon-reload

echo "[+] Enabling and starting timer..."
systemctl enable storage-guard.timer
systemctl start  storage-guard.timer

echo "[+] Running one immediate dry-run to confirm healthy state..."
systemctl start storage-guard.service
sleep 2
systemctl status storage-guard.service --no-pager -n 5

echo ""
echo "=== INSTALLED SUCCESSFULLY ==="
echo "Timer schedule:"
systemctl list-timers storage-guard.timer --no-pager
echo ""
echo "Test alert (optional): sudo bash scripts/storage_guard.sh --test-alert"
echo "View logs: journalctl -u storage-guard.service -f"
echo "View state: cat /var/lib/storage_guard/state"
echo "View log file: tail -f /var/log/storage_guard.log"
