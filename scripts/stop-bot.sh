#!/bin/bash
# Stop scripts for DA bots

TARGET=$1

if [ -z "$TARGET" ]; then
  echo "Usage: $0 {crypto|trading|hermes|all}"
  exit 1
fi

case $TARGET in
  crypto)
    echo "Stopping da-crypto.service..."
    sudo systemctl stop da-crypto.service
    ;;
  trading)
    echo "Stopping da-trading.service..."
    sudo systemctl stop da-trading.service
    ;;
  hermes)
    echo "Stopping da-hermes.service..."
    sudo systemctl stop da-hermes.service
    ;;
  all)
    echo "Stopping all DA bot services..."
    sudo systemctl stop da-crypto.service da-trading.service da-hermes.service
    ;;
  *)
    echo "Unknown target: $TARGET"
    echo "Usage: $0 {crypto|trading|hermes|all}"
    exit 1
    ;;
esac

echo "Done."
