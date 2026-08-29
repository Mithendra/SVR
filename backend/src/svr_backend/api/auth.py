"""Authentication endpoints (SDD 13.1), including the self-service password-reset
flow: request a single-use emailed link, then set a new password with the token.
The password value is never displayed, stored, or transmitted - only its argon2
hash is persisted.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from svr_backend.core.config import get_settings
from svr_backend.core.email import echo_link_in_response
from svr_backend.core.rbac import _token_from_headers, get_db, get_principal
from svr_backend.core.security import hash_password
from svr_backend.core.session import Principal
from svr_backend.core.session import login as do_login
from svr_backend.core.session import logout as do_logout
from svr_backend.reset import consume_token, issue_token, reset_link, send_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    login_name: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str
    full_name: str


class MeResponse(BaseModel):
    user_id: int
    login_name: str
    full_name: str
    role: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, conn: sqlite3.Connection = Depends(get_db)) -> LoginResponse:
    token = do_login(conn, body.login_name, body.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login name or password",
        )
    principal = conn.execute(
        "SELECT role, full_name FROM users WHERE login_name = ?", (body.login_name,)
    ).fetchone()
    return LoginResponse(token=token, role=principal["role"], full_name=principal["full_name"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: str | None = Depends(_token_from_headers),
    conn: sqlite3.Connection = Depends(get_db),
    _: Principal = Depends(get_principal),
) -> None:
    if token:
        do_logout(conn, token)


@router.get("/me", response_model=MeResponse)
def me(principal: Principal = Depends(get_principal)) -> MeResponse:
    return MeResponse(
        user_id=principal.user_id,
        login_name=principal.login_name,
        full_name=principal.full_name,
        role=principal.role,
    )


class ResetRequest(BaseModel):
    identifier: str  # login name or email


class ResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=1)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def password_reset_request(
    body: ResetRequest, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Always returns 202 (no account enumeration). Emails a link only if the
    identifier matches an active account. Dev email backends echo the link back."""
    ident = body.identifier.strip()
    row = conn.execute(
        "SELECT id, email, status FROM users WHERE login_name = ? OR email = ?",
        (ident, ident),
    ).fetchone()
    out: dict = {"detail": "If that account exists, a reset link has been emailed."}
    if row is not None and row["status"] == "Active":
        conn.execute("BEGIN")
        try:
            token = issue_token(conn, row["id"])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        send_reset_email(row["email"], token, admin_initiated=False)
        if echo_link_in_response():
            out["dev_reset_link"] = reset_link(token)
    return out


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
def password_reset_confirm(
    body: ResetConfirm, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    if len(body.new_password) < get_settings().min_password_length:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Password must be at least {get_settings().min_password_length} characters",
        )
    conn.execute("BEGIN")
    try:
        user_id = consume_token(conn, body.token)
        if user_id is None:
            conn.execute("ROLLBACK")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset link")
        conn.execute(
            "UPDATE users SET password_hash = ?, last_updated_by = 'password-reset', "
            "last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (hash_password(body.new_password), user_id),
        )
        # Any existing sessions for this user are now stale.
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("COMMIT")
    except HTTPException:
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"detail": "Password updated. You can now sign in with the new password."}
