#!/bin/sh
set -eu

# Website availability must not depend on a full Tushare refresh. The separate
# market-updater service runs the transactional refresh after 21:00 Shanghai time.
exec python3 -m uvicorn web.app.main:app --host 0.0.0.0 --port "${PORT:-8788}" --workers 1
