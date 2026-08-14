#!/bin/sh
set -eu

# Website availability must not depend on a full Tushare refresh. The separate
# market-updater service runs the transactional refresh after 21:00 Shanghai time.
exec node /app/web/server.js
