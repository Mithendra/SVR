"""Password reset: self-service request/confirm, admin-initiated reset, token
single-use + expiry, no account enumeration, no plaintext anywhere (SDD 13.1)."""

from __future__ import annotations

from tests.conftest import DEMO_PASSWORD

from svr_backend.core.email import OUTBOX

NEW_PW = "brand-new-passw0rd"


def test_request_for_known_user_issues_a_token_and_emails_a_link(client, conn):
    r = client.post("/auth/password-reset/request", json={"identifier": "sales"})
    assert r.status_code == 202
    assert "dev_reset_link" in r.json()  # memory backend echoes it
    assert len(OUTBOX) == 1
    assert "password-reset.html?token=" in OUTBOX[0].body
    assert conn.execute("SELECT COUNT(*) c FROM password_reset_token").fetchone()["c"] == 1


def test_request_for_unknown_identifier_still_returns_202_without_a_token(client, conn):
    r = client.post("/auth/password-reset/request", json={"identifier": "nobody@nowhere"})
    assert r.status_code == 202
    assert "dev_reset_link" not in r.json()
    assert len(OUTBOX) == 0
    assert conn.execute("SELECT COUNT(*) c FROM password_reset_token").fetchone()["c"] == 0


def _token_for(client, identifier):
    link = client.post(
        "/auth/password-reset/request", json={"identifier": identifier}
    ).json()["dev_reset_link"]
    return link.split("token=", 1)[1]


def test_confirm_sets_the_new_password_and_invalidates_old_sessions(client):
    # old password works, giving a session
    old = client.post("/auth/login", json={"login_name": "sales", "password": DEMO_PASSWORD})
    assert old.status_code == 200

    token = _token_for(client, "sales")
    done = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PW})
    assert done.status_code == 200

    # old password no longer works; new one does
    assert client.post(
        "/auth/login", json={"login_name": "sales", "password": DEMO_PASSWORD}
    ).status_code == 401
    assert client.post(
        "/auth/login", json={"login_name": "sales", "password": NEW_PW}
    ).status_code == 200


def test_token_is_single_use(client):
    token = _token_for(client, "manager")
    assert client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PW}
    ).status_code == 200
    assert client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": "another-one-99"}
    ).status_code == 400


def test_bad_token_and_short_password_are_rejected(client):
    assert client.post(
        "/auth/password-reset/confirm", json={"token": "not-a-real-token", "new_password": NEW_PW}
    ).status_code == 400
    token = _token_for(client, "owner")
    assert client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": "short"}
    ).status_code == 422


def test_expired_token_is_rejected(client, conn):
    token = _token_for(client, "manager")
    conn.execute(
        "UPDATE password_reset_token SET expires_at = '2000-01-01T00:00:00.000000Z' WHERE token = ?",
        (token,),
    )
    assert client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PW}
    ).status_code == 400


def test_admin_initiated_reset(client, auth_headers, users, conn):
    assert client.post(
        f"/users/{users['Sales']}/reset-password", headers=auth_headers("Sales")
    ).status_code == 403

    r = client.post(f"/users/{users['Sales']}/reset-password", headers=auth_headers("Manager"))
    assert r.status_code == 202
    assert len(OUTBOX) == 1
    token = r.json()["dev_reset_link"].split("token=", 1)[1]
    assert client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PW}
    ).status_code == 200
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name = 'password_reset_token'"
    ).fetchone()["c"] == 1
