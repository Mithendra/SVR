"""Apply numbered ``NNNN_*.sql`` migrations in order, once each.

Usage: ``svr-migrate`` (see cli.py). Idempotent - re-running applies only files not
yet recorded in ``schema_migrations``.
"""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path

_MIGRATIONS_PACKAGE = "svr_backend.migrations"


def _ensure_bookkeeping(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )
        """
    )


def _discover() -> list[tuple[str, str]]:
    files = []
    for entry in resources.files(_MIGRATIONS_PACKAGE).iterdir():
        name = entry.name
        if name.endswith(".sql"):
            files.append((name, entry.read_text(encoding="utf-8")))
    files.sort(key=lambda pair: pair[0])
    return files


def applied_versions(conn: sqlite3.Connection) -> set[str]:
    _ensure_bookkeeping(conn)
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply all pending migrations. Returns the list of versions applied this call."""
    _ensure_bookkeeping(conn)
    done = applied_versions(conn)
    newly_applied: list[str] = []
    for version, sql in _discover():
        if version in done:
            continue
        # executescript() commits any pending transaction first, so the BEGIN/COMMIT
        # must live inside the script itself for the file + its version row to be
        # applied atomically. Migration filenames never contain quotes.
        record = f"INSERT INTO schema_migrations (version) VALUES ('{version}');"
        script = f"BEGIN;\n{sql}\n;\n{record}\nCOMMIT;"
        try:
            conn.executescript(script)
        except Exception:
            conn.executescript("ROLLBACK;")
            raise
        newly_applied.append(version)
    return newly_applied


def migrate_path(db_path: Path | str) -> list[str]:
    from svr_backend.core.db import connect

    conn = connect(db_path)
    try:
        return migrate(conn)
    finally:
        conn.close()
