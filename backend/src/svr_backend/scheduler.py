"""Scheduler Service core (SDD 7.7 / 2.3).

Runs the 23:59 Asia/Kolkata carry-forward job and a daily SQLite backup. Kept
separate from the Backend Service so a scheduler crash cannot take down interactive
data entry mid-shift (SDD ADR-2).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from svr_backend.carry_forward import catch_up_on_startup, run_carry_forward
from svr_backend.core.config import get_settings
from svr_backend.core.db import connect

log = logging.getLogger("svr.scheduler")


def carry_forward_job() -> dict:
    """Roll today's Current Readings into tomorrow's Last Shift Readings."""
    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.scheduler_timezone)).date().isoformat()
    conn = connect()
    try:
        summary = run_carry_forward(conn, today)
    finally:
        conn.close()
    log.info("carry_forward_job ran for %s: %s", today, summary)
    return summary


def startup_catch_up() -> list[dict]:
    conn = connect()
    try:
        results = catch_up_on_startup(conn)
    finally:
        conn.close()
    if results:
        log.info("catch_up_on_startup replayed %d missed date(s)", len(results))
    return results


def backup_job() -> Path | None:
    settings = get_settings()
    db_path = settings.resolved_db_path()
    if not db_path.exists():
        return None
    backup_dir = settings.data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo(settings.scheduler_timezone)).strftime("%Y%m%d")
    dest = backup_dir / f"svr-{stamp}.sqlite"
    conn = connect(db_path)
    try:
        # sqlite online backup - consistent even with the Backend Service writing.
        import sqlite3

        with sqlite3.connect(dest) as target:
            conn.backup(target)
    finally:
        conn.close()
    log.info("backup_job wrote %s", dest)
    return dest


def build_scheduler():
    """Return a configured (not started) APScheduler BackgroundScheduler."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    settings = get_settings()
    tz = ZoneInfo(settings.scheduler_timezone)
    sched = BackgroundScheduler(timezone=tz)
    sched.add_job(
        carry_forward_job,
        CronTrigger(
            hour=settings.carry_forward_hour, minute=settings.carry_forward_minute, timezone=tz
        ),
        id="carry_forward",
        replace_existing=True,
    )
    sched.add_job(
        backup_job,
        CronTrigger(hour=0, minute=15, timezone=tz),
        id="daily_backup",
        replace_existing=True,
    )
    return sched
