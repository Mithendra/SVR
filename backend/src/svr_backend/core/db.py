"""SQLite access.

The Backend Service is the *only* process that opens the database file for writes
(SDD 2.3). Connections here enable foreign keys and WAL so the Scheduler Service can
read concurrently without blocking interactive writes.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from svr_backend.core.config import get_settings


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else get_settings().resolved_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: sync endpoints run in Starlette's threadpool, and the
    # scheduler/backup path shares a connection across an APScheduler worker. Writes
    # are still serialized by SQLite; explicit BEGIN/COMMIT + busy_timeout below.
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Wrap a unit of work. Commits on success, rolls back on any exception."""
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
