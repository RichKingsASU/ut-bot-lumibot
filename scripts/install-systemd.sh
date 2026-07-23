#!/bin/bash
# Copies updated unit files to /etc/systemd/system/
# and reloads systemd
set -e
for unit in da-crypto da-trading da-agents \
  da-watchdog da-hermes; do
  sudo cp systemd/${unit}.service /etc/systemd/system/
  echo "Installed ${unit}.service"
done

sudo cp systemd/da-doppler.conf /etc/systemd/system/
echo "Installed da-doppler.conf"
sudo chmod 600 /etc/systemd/system/da-doppler.conf

sudo systemctl daemon-reload
echo "systemd reloaded"
echo "Run: sudo systemctl restart da-crypto da-trading da-agents da-watchdog"
