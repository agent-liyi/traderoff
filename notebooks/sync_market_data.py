#!/usr/bin/env python3
"""Import all generated market outputs and Tushare cache files into PostgreSQL."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from market_database import sync_data_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("FEAR_GREED_DATA_DIR", "/workspace/data")))
    parser.add_argument("--skip-raw", action="store_true", help="Only import website runtime outputs")
    args = parser.parse_args()
    result = sync_data_dir(args.data_dir, include_raw=not args.skip_raw)
    print(
        f"PostgreSQL sync complete: run={result['run_id']} snapshots={result['snapshots']} "
        f"raw_added={result['raw_added']} raw_unchanged={result['raw_skipped']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
