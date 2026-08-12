#!/bin/sh
set -eu

refresh() {
  echo "[traderoff] refreshing Tushare data at $(date -Iseconds)"
  python3 /app/notebooks/update_fear_greed_tushare.py
  python3 /app/notebooks/update_market_environment_tushare.py
}

refresh
node /app/web/server.js &
NODE_PID=$!

# Recheck every five minutes; the Python time gate prevents pre-21:00 updates.
while kill -0 "$NODE_PID" 2>/dev/null; do
  sleep 300
  if ! kill -0 "$NODE_PID" 2>/dev/null; then break; fi
  refresh || echo "[traderoff] refresh failed; keeping the last successful dataset"
done
wait "$NODE_PID"
