"""Shared fixtures: a migrated temp DB, a TestClient wired to it, and role logins."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from svr_backend.app import create_app
from svr_backend.core import rbac
from svr_backend.core.db import connect
from svr_backend.core.security import hash_password
from svr_backend.migrations.runner import migrate

DEMO_PASSWORD = "test-pass-1234"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.sqlite"


@pytest.fixture
def conn(db_path) -> sqlite3.Connection:
    c = connect(db_path)
    migrate(c)
    try:
        yield c
    finally:
        c.close()


@pytest.fixture
def users(conn) -> dict[str, int]:
    """One user per role. login_name == role lowercased."""
    pw = hash_password(DEMO_PASSWORD)
    ids: dict[str, int] = {}
    for role in ("Sales", "Manager", "Owner"):
        cur = conn.execute(
            """
            INSERT INTO users (login_name, full_name, email, role, password_hash, last_updated_by)
            VALUES (?, ?, ?, ?, ?, 'test')
            """,
            (role.lower(), f"{role} User", f"{role.lower()}@test.local", role, pw),
        )
        ids[role] = cur.lastrowid
    return ids


@pytest.fixture
def client(conn, users) -> TestClient:
    app = create_app()

    def _get_db():
        yield conn

    app.dependency_overrides[rbac.get_db] = _get_db
    return TestClient(app)


@pytest.fixture
def token(client):
    """Callable: token('Sales') -> a bearer token for that role."""

    def _login(role: str) -> str:
        resp = client.post(
            "/auth/login", json={"login_name": role.lower(), "password": DEMO_PASSWORD}
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["token"]

    return _login


@pytest.fixture
def auth_headers(token):
    def _headers(role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token(role)}"}

    return _headers
