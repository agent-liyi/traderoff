#!/bin/sh
set -eu

next_target() {
  day=$(date +%F)
  weekday=$(date +%u)
  if [ "$weekday" -gt 5 ]; then
    day=$(date -d "$day +$((8 - weekday)) days" +%F)
  fi
  target=$(date -d "$day 21:10:00" +%s)
  now=$(date +%s)
  if [ "$target" -le "$now" ]; then
    day=$(date -d "$day +1 day" +%F)
    weekday=$(date -d "$day" +%u)
    if [ "$weekday" -gt 5 ]; then
      day=$(date -d "$day +$((8 - weekday)) days" +%F)
    fi
    target=$(date -d "$day 21:10:00" +%s)
  fi
  printf '%s\n' "$target"
}

while true; do
  target=$(next_target)
  now=$(date +%s)
  delay=$((target - now))
  echo "[traderoff] next market refresh at $(date -d "@$target" -Iseconds)"
  sleep "$delay"
  /app/refresh-market-data.sh || echo "[traderoff] market refresh failed; database keeps the last complete run"
  sleep 60
done
