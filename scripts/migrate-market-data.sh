#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export FEAR_GREED_DATA_DIR="${FEAR_GREED_DATA_DIR:-$ROOT/data}"
exec python3 "$ROOT/notebooks/sync_market_data.py" --data-dir "$FEAR_GREED_DATA_DIR"
