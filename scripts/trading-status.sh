#!/bin/bash
if [ -f /tmp/trading-disabled ]; then
    echo "STATUS: DISABLED"
    exit 1
else
    echo "STATUS: ENABLED"
    exit 0
fi
