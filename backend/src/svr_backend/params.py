"""Read versioned business-rule constants from ``system_parameter`` (SDD ADR-3)."""

from __future__ import annotations

import sqlite3
from datetime import date


def get_param(
    conn: sqlite3.Connection, name: str, default: float, as_of: str | None = None
) -> float:
    as_of = as_of or date.today().isoformat()
    row = conn.execute(
        "SELECT value FROM system_parameter WHERE name = ? AND effective_date <= ? "
        "ORDER BY effective_date DESC, id DESC LIMIT 1",
        (name, as_of),
    ).fetchone()
    return float(row["value"]) if row is not None else default
