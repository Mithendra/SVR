"""Audit trail (SDD 13.4) - one ``audit_log`` row per write, everywhere, no exceptions.

``record_write`` is called inside the same transaction as the write it describes, so
an entry and its audit row commit or roll back together.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

Action = Literal["create", "update", "delete"]


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str, sort_keys=True)


def record_write(
    conn: sqlite3.Connection,
    *,
    table: str,
    record_id: str | int,
    action: Action,
    actor: str,
    old: dict | None = None,
    new: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (table_name, record_id, action, actor, old_value, new_value)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (table, str(record_id), action, actor, _dump(old), _dump(new)),
    )
