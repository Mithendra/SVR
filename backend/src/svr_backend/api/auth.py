"""Authentication endpoints (SDD 13.1). Password-reset / admin-reset flows are
email-driven and deferred to a later phase; stubs return 501 so the shape is fixed.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from svr_backend.core.rbac import _token_from_headers, get_db, get_principal
from svr_backend.core.session import Principal
from svr_backend.core.session import login as do_login
from svr_backend.core.session import logout as do_logout

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


@router.post("/password-reset/request", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def password_reset_request() -> None:
    """Self-service reset link by email - deferred (email integration, SDD 7.6)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Email integration not yet implemented")
