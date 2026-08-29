"""Rate Master: 3-tier access and append-only versioning (SDD 4.2 / 19 item 7)."""

from __future__ import annotations


def test_only_owner_can_update_rates(client, auth_headers):
    body = [{"item_key": "HS", "sell_rate": 106.0}]
    assert client.put("/rate-master/", json=body, headers=auth_headers("Sales")).status_code == 403
    assert client.put("/rate-master/", json=body, headers=auth_headers("Manager")).status_code == 403
    assert client.put("/rate-master/", json=body, headers=auth_headers("Owner")).status_code == 200


def test_update_appends_new_effective_row_and_audits(client, auth_headers, conn):
    before = conn.execute("SELECT COUNT(*) c FROM rate_master WHERE item_key = 'HS'").fetchone()["c"]
    resp = client.put(
        "/rate-master/",
        json=[{"item_key": "HS", "sell_rate": 108.5, "buy_rate": 104.0}],
        headers=auth_headers("Owner"),
    )
    assert resp.status_code == 200
    after = conn.execute("SELECT COUNT(*) c FROM rate_master WHERE item_key = 'HS'").fetchone()["c"]
    assert after == before + 1  # appended, not mutated

    current = {r["item_key"]: r for r in resp.json()}
    assert current["HS"]["sell_rate"] == 108.5

    audit = conn.execute(
        "SELECT * FROM audit_log WHERE table_name = 'rate_master' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert audit["action"] == "create"
    assert audit["actor"] == "owner"


def test_current_rates_returns_latest_per_item(client, auth_headers):
    client.put(
        "/rate-master/",
        json=[{"item_key": "MS", "sell_rate": 120.0}],
        headers=auth_headers("Owner"),
    )
    rows = client.get("/rate-master/current", headers=auth_headers("Owner")).json()
    ms = next(r for r in rows if r["item_key"] == "MS")
    assert ms["sell_rate"] == 120.0


def test_history_shows_prior_rate_and_is_manager_visible(client, auth_headers):
    assert client.get("/rate-master/history", headers=auth_headers("Sales")).status_code == 403

    seed_hs = next(
        r for r in client.get("/rate-master/current", headers=auth_headers("Owner")).json()
        if r["item_key"] == "HS"
    )["sell_rate"]

    client.put(
        "/rate-master/",
        json=[{"item_key": "HS", "sell_rate": 109.0, "effective_date": "2026-09-01"}],
        headers=auth_headers("Owner"),
    )

    hist = client.get("/rate-master/history", headers=auth_headers("Manager")).json()
    newest_hs = next(r for r in hist if r["item_key"] == "HS")
    assert newest_hs["sell_rate"] == 109.0
    assert newest_hs["prev_sell_rate"] == seed_hs
    assert newest_hs["effective_date"] == "2026-09-01"
