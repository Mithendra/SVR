"""User helpers - login-name derivation (SDD 13.1: first initial + last name,
editable on collision) and safe row -> dict projection that never exposes the
password hash or TOTP secret.
"""

from __future__ import annotations

import re
import sqlite3


def derive_login_name(full_name: str) -> str:
    tokens = [t for t in re.split(r"\s+", (full_name or "").strip()) if t]
    if not tokens:
        return "user"
    first_initial = re.sub(r"[^a-z0-9]", "", tokens[0][:1].lower())
    last = re.sub(r"[^a-z0-9]", "", tokens[-1].lower())
    base = (first_initial + last) or "user"
    return base


def unique_login_name(conn: sqlite3.Connection, base: str, *, exclude_id: int | None = None) -> str:
    candidate = base
    n = 1
    while True:
        row = conn.execute(
            "SELECT id FROM users WHERE login_name = ?", (candidate,)
        ).fetchone()
        if row is None or row["id"] == exclude_id:
            return candidate
        n += 1
        candidate = f"{base}{n}"


PUBLIC_COLUMNS = (
    "id",
    "login_name",
    "full_name",
    "email",
    "cell_phone",
    "role",
    "status",
    "totp_enabled",
    "last_updated_by",
    "last_updated_at",
    "created_at",
)


def public_user(row: sqlite3.Row) -> dict:
    d = {c: row[c] for c in PUBLIC_COLUMNS}
    d["totp_enabled"] = bool(d["totp_enabled"])
    d["has_password"] = row["password_hash"] is not None
    return d


def count_active_owners(conn: sqlite3.Connection, *, exclude_id: int | None = None) -> int:
    rows = conn.execute(
        "SELECT id FROM users WHERE role = 'Owner' AND status = 'Active'"
    ).fetchall()
    return sum(1 for r in rows if r["id"] != exclude_id)
