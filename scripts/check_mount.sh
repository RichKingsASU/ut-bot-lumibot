#!/bin/bash
MOUNT=/mnt/tick-storage
if ! mountpoint -q "$MOUNT"; then
  echo "ERROR: $MOUNT is not mounted. Refusing to start (would write to root disk)."
  echo "Fix: power on the drive, then run: sudo mount -a"
  exit 1
fi
echo "OK: $MOUNT is mounted."
