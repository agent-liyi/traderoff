"""Scheduled market-data refresh inside the FastAPI process.

Runs the existing notebooks pipeline (refresh-market-data.sh) on weekdays at
21:10 Asia/Shanghai via APScheduler, replacing the standalone market-updater
container. The actual heavy computation is executed in a subprocess so a slow /
memory-heavy run can neither block the event loop nor crash the web worker.
"""

from __future__ import annotations

import logging
import os
import subprocess
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_REFRESH_SCRIPT = os.getenv("REFRESH_MARKET_DATA_SH", "/app/refresh-market-data.sh")
_TZ = ZoneInfo("Asia/Shanghai")

_scheduler: AsyncIOScheduler | None = None


def run_refresh() -> None:
    """Execute the full market-data refresh pipeline in a subprocess."""
    logger.info("[refresher] starting market-data refresh")
    try:
        result = subprocess.run(
            [_REFRESH_SCRIPT],
            env=dict(os.environ),
            timeout=2700,  # 45 min cap; keeps the job from stacking on a 1.9GiB box
        )
        logger.info("[refresher] refresh completed rc=%s", result.returncode)
        if result.returncode != 0:
            logger.error("[refresher] refresh exited non-zero (data keeps last full run)")
    except Exception:  # noqa: BLE001
        logger.exception("[refresher] refresh failed")


def start_scheduler() -> AsyncIOScheduler:
    """Build and start an APScheduler that refreshes weekdays at 21:10."""
    global _scheduler
    scheduler = AsyncIOScheduler(timezone=_TZ)
    # Weekdays 21:10 Asia/Shanghai (matches the former schedule-market-refresh.sh).
    scheduler.add_job(
        run_refresh,
        CronTrigger(day_of_week="mon-fri", hour=21, minute=10, timezone=_TZ),
        id="market_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("[refresher] APScheduler started: weekdays 21:10 Asia/Shanghai")
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
