"""Pytest fixtures: force the file market-data backend and set test env for all tests."""

import os
import sys
from pathlib import Path

# Must be set before importing web.app.config.
os.environ.setdefault("MARKET_DATA_BACKEND", "file")
os.environ.setdefault("TRADEROFF_TEST", "1")

# Isolate the users sqlite per test run.
_web_root = Path(__file__).resolve().parents[1]
os.environ.setdefault("USERS_DB", str(_web_root / "data" / "users.test.sqlite"))

# Ensure the project root is importable (web.app package).
_ROOT = _web_root.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
