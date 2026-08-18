#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
NOTEBOOK_DIR="$ROOT/notebooks"
DATA_DIR="${FEAR_GREED_DATA_DIR:-$ROOT/data}"
PYTHON="${PYTHON:-python3}"

export FEAR_GREED_DATA_DIR="$DATA_DIR"
echo "[traderoff] market refresh started at $(date -Iseconds)"
# Fear & Greed is updated incrementally (append only new trading days) to keep
# memory usage safe on the small production instance; fall back to the full
# rebuild only if no history exists yet.
"$PYTHON" "$NOTEBOOK_DIR/update_fear_greed_incremental.py"
"$PYTHON" "$NOTEBOOK_DIR/update_market_environment_tushare.py"
"$PYTHON" "$NOTEBOOK_DIR/update_market_style_tushare.py"
"$PYTHON" "$NOTEBOOK_DIR/update_industry_price_tushare.py"
"$PYTHON" "$NOTEBOOK_DIR/update_market_volume_tushare.py"
"$PYTHON" "$NOTEBOOK_DIR/update_market_volatility_tushare.py"
"$PYTHON" "$NOTEBOOK_DIR/update_market_turnover_tushare.py"
"$PYTHON" "$NOTEBOOK_DIR/update_market_breadth_tushare.py"
"$PYTHON" "$NOTEBOOK_DIR/update_factor_exposure_tushare.py"
"$PYTHON" "$NOTEBOOK_DIR/sync_market_data.py" --data-dir "$DATA_DIR"
echo "[traderoff] market refresh completed at $(date -Iseconds)"
