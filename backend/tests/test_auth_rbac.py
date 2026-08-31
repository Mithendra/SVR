"""Login, session resolution, and server-side role enforcement (SDD 4.3 / 13.1)."""

from __future__ import annotations

from conftest import DEMO_PASSWORD


def test_login_success_returns_token_and_role(client):
    resp = client.post("/auth/login", json={"login_name": "manager", "password": DEMO_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "Manager"
    assert body["token"]
    assert "password" not in resp.text.lower()


def test_login_bad_password_rejected(client):
    resp = client.post("/auth/login", json={"login_name": "owner", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_token(client, auth_headers):
    resp = client.get("/auth/me", headers=auth_headers("Sales"))
    assert resp.status_code == 200
    assert resp.json()["role"] == "Sales"


def test_rbac_blocks_sales_from_rate_master(client, auth_headers):
    # SDD 4.2 - Sales is blocked from Rate Master entirely.
    assert client.get("/rate-master/current", headers=auth_headers("Sales")).status_code == 403


def test_rbac_allows_manager_to_view_rate_master(client, auth_headers):
    assert client.get("/rate-master/current", headers=auth_headers("Manager")).status_code == 200


def test_logout_invalidates_session(client, token):
    t = token("Owner")
    h = {"Authorization": f"Bearer {t}"}
    assert client.get("/auth/me", headers=h).status_code == 200
    assert client.post("/auth/logout", headers=h).status_code == 204
    assert client.get("/auth/me", headers=h).status_code == 401
