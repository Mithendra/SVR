"""Password-reset token issue / consume + the reset email (SDD 13.1)."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from svr_backend.core.config import get_settings
from svr_backend.core.email import send_email

_ISO = "%Y-%m-%dT%H:%M:%S.%fZ"


def issue_token(conn: sqlite3.Connection, user_id: int, *, created_by: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(minutes=get_settings().reset_token_ttl_minutes)
    conn.execute(
        "INSERT INTO password_reset_token (token, user_id, expires_at, created_by) "
        "VALUES (?, ?, ?, ?)",
        (token, user_id, expires.strftime(_ISO), created_by),
    )
    return token


def consume_token(conn: sqlite3.Connection, token: str) -> int | None:
    """Return the user_id for a valid, unused, unexpired token and mark it used."""
    row = conn.execute(
        "SELECT user_id, expires_at, used_at FROM password_reset_token WHERE token = ?",
        (token,),
    ).fetchone()
    if row is None or row["used_at"] is not None:
        return None
    try:
        expires = datetime.strptime(row["expires_at"], _ISO).replace(tzinfo=UTC)
    except ValueError:
        return None
    if expires < datetime.now(UTC):
        return None
    conn.execute(
        "UPDATE password_reset_token SET used_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
        "WHERE token = ?",
        (token,),
    )
    return row["user_id"]


def reset_link(token: str) -> str:
    base = get_settings().app_base_url.rstrip("/")
    return f"{base}/password-reset.html?token={token}"


def send_reset_email(to: str, token: str, *, admin_initiated: bool) -> None:
    link = reset_link(token)
    who = "An administrator has requested a password reset for your account." if admin_initiated \
        else "You (or someone) requested a password reset for your account."
    body = (
        f"{who}\n\n"
        f"Open this single-use link to set a new password (valid for "
        f"{get_settings().reset_token_ttl_minutes} minutes):\n\n{link}\n\n"
        "If you did not expect this, you can ignore this email - the link does nothing "
        "until it is used, and your current password is unchanged."
    )
    send_email(to, "SVR IOCL Station - password reset", body)
