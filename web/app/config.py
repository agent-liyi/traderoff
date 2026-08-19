"""Environment-driven configuration, equivalent to the Node server.js constants.

Keeps the same env var names and defaults as the original Node backend so
deployment/compose files do not need to change.
"""

from __future__ import annotations

import os
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1]          # web/
REPO_ROOT = WEB_ROOT.parent                              # project root
STATIC_ROOT = WEB_ROOT / "static"
DATA_DIR_DEFAULT = REPO_ROOT / "data"

# --- market data file paths (file backend only) ---
DATA_PATH = os.getenv("FEAR_GREED_DATA", str(DATA_DIR_DEFAULT / "fear_greed_runtime.json"))
MARKET_ENVIRONMENT_PATH = os.getenv("MARKET_ENVIRONMENT_DATA", str(DATA_DIR_DEFAULT / "market_environment_runtime.json"))
MARKET_STYLE_PATH = os.getenv("MARKET_STYLE_DATA", str(DATA_DIR_DEFAULT / "market_style_runtime.json"))
INDUSTRY_PRICE_PATH = os.getenv("INDUSTRY_PRICE_DATA", str(DATA_DIR_DEFAULT / "industry_price_runtime.json"))
MARKET_VOLUME_PATH = os.getenv("MARKET_VOLUME_DATA", str(DATA_DIR_DEFAULT / "market_volume_runtime.json"))
MARKET_VOLATILITY_PATH = os.getenv("MARKET_VOLATILITY_DATA", str(DATA_DIR_DEFAULT / "market_volatility_runtime.json"))
MARKET_TURNOVER_PATH = os.getenv("MARKET_TURNOVER_DATA", str(DATA_DIR_DEFAULT / "market_turnover_runtime.json"))
MARKET_BREADTH_PATH = os.getenv("MARKET_BREADTH_DATA", str(DATA_DIR_DEFAULT / "market_breadth_runtime.json"))
FACTOR_EXPOSURE_PATH = os.getenv("FACTOR_EXPOSURE_DATA", str(DATA_DIR_DEFAULT / "factor_exposure_runtime.json"))

USERS_DB = os.getenv("USERS_DB", str(WEB_ROOT / "data" / "users.sqlite"))
PORT = int(os.getenv("PORT", "8788"))

# --- market data backend ---
# Original: MARKET_DATA_BACKEND || (NODE_ENV === 'test' ? 'file' : 'postgres')
MARKET_DATA_BACKEND = os.getenv("MARKET_DATA_BACKEND")
if not MARKET_DATA_BACKEND:
    MARKET_DATA_BACKEND = "file" if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TRADEROFF_TEST") else "postgres"
MARKET_DATABASE_URL = os.getenv("MARKET_DATABASE_URL") or os.getenv("DATABASE_URL") or ""

# Map dataset name -> runtime JSON file path (file backend)
DATASET_FILES = {
    "market-environment": MARKET_ENVIRONMENT_PATH,
    "market-style": MARKET_STYLE_PATH,
    "industry-price": INDUSTRY_PRICE_PATH,
    "market-volume": MARKET_VOLUME_PATH,
    "market-volatility": MARKET_VOLATILITY_PATH,
    "market-turnover": MARKET_TURNOVER_PATH,
    "market-breadth": MARKET_BREADTH_PATH,
    "factor-exposure": FACTOR_EXPOSURE_PATH,
}
