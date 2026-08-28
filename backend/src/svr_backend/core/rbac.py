"""FastAPI dependencies for DB access and role enforcement.

RBAC is defense-in-depth (SDD 4.3): the UI hides what a role cannot reach, and
independently every write endpoint re-checks the session's role here, server-side.
The role -> module matrix is SDD 4.2.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, status

from svr_backend.core.db import connect
from svr_backend.core.session import Principal, resolve

ROLES = ("Sales", "Manager", "Owner")


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _token_from_headers(
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return x_session_token


def get_principal(
    token: str | None = Depends(_token_from_headers),
    conn: sqlite3.Connection = Depends(get_db),
) -> Principal:
    principal = resolve(conn, token)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require(*allowed_roles: str):
    """Dependency factory: allow only the given roles, else 403."""
    unknown = set(allowed_roles) - set(ROLES)
    if unknown:
        raise ValueError(f"Unknown role(s): {sorted(unknown)}")

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{principal.role}' is not permitted to perform this action",
            )
        return principal

    return _dep
