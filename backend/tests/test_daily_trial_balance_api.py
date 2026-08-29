"""Daily Trial Balance: Section 1 formulas (SDD 9 r1), Section 3 pull from Daily
Sales Summary, Section 6/7 stock value + total, finalize lock, RBAC (SDD 5.8 / 9)."""

from __future__ import annotations

DATE = "2026-10-05"


def _seed_summary(client, auth_headers):
    """Two pump submissions -> combined HS consumption 50 L, MS consumption 20 L."""
    h = auth_headers("Sales")
    client.post("/daily-sales-entry", json={
        "pump_serial": "12BC4523V-OFF", "shift_date": DATE,
        "hs": {"current": "30"}, "ms": {"current": "15"},
    }, headers=h)
    client.post("/daily-sales-entry", json={
        "pump_serial": "11CC2012V-RDF", "shift_date": DATE,
        "hs": {"current": "20"}, "ms": {"current": "5"},
    }, headers=auth_headers("Manager"))


def test_sales_has_no_access(client, auth_headers):
    assert client.get(f"/daily-trial-balance/{DATE}", headers=auth_headers("Sales")).status_code == 403


def test_section1_formulas_and_section3_pull(client, auth_headers):
    _seed_summary(client, auth_headers)
    r = client.put(
        f"/daily-trial-balance/{DATE}",
        json={"s1_hs_yesterday": 100, "s1_hs_current": 60},
        headers=auth_headers("Manager"),
    )
    assert r.status_code == 200
    view = r.json()
    assert view["pulled"]["s3_source"] == "daily_sales_summary"
    assert view["pulled"]["s3_hs_consumption"] == 50

    hs = view["computed"]["section1"]["hs"]
    assert hs["diff"] == 40           # 100 - 60
    assert hs["consumption"] == 50    # pulled from Section 3
    assert hs["computer_pump_diff"] == 10   # 50 - 40
    assert hs["benefit_loss"] == 90         # 50 + 40
    assert hs["deduct_testing"] == 40       # 50 - 10 (system_parameter)
    assert hs["stock_ltrs"] == -10          # diff - consumption
    # Section 6 stock amount = stock_ltrs x Buy Rate HS (seeded 101.50)
    assert hs["stock_amount"] == -1015.0


def test_section7_total_uses_cash_book_value_plus_stock_value(client, auth_headers):
    _seed_summary(client, auth_headers)
    view = client.put(
        f"/daily-trial-balance/{DATE}",
        json={
            "s1_hs_yesterday": 100, "s1_hs_current": 60,
            "s1_ms_yesterday": 200, "s1_ms_current": 190,
            "s54_cash_book_value": 500000,
        },
        headers=auth_headers("Owner"),
    ).json()
    s6 = view["computed"]["section6"]
    s7 = view["computed"]["section7"]
    assert s7["7_1_cash_book_value"] == 500000
    assert s7["7_2_stock_value"] == s6["total"]
    assert s7["7_3_total"] == round(500000 + s6["total"], 4)


def test_section3_unavailable_without_a_summary(client, auth_headers):
    view = client.get("/daily-trial-balance/2099-01-01", headers=auth_headers("Manager")).json()
    assert view["pulled"]["s3_source"] == "unavailable"
    assert view["computed"]["section1"]["hs"]["consumption"] is None


def test_finalize_locks_further_edits(client, auth_headers, conn):
    _seed_summary(client, auth_headers)
    client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_yesterday": 100, "s1_hs_current": 60},
               headers=auth_headers("Manager"))

    fin = client.post(f"/daily-trial-balance/{DATE}/finalize", headers=auth_headers("Manager"))
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"

    assert client.put(f"/daily-trial-balance/{DATE}", json={"s1_hs_current": 61},
                      headers=auth_headers("Owner")).status_code == 409
    assert client.post(f"/daily-trial-balance/{DATE}/finalize",
                       headers=auth_headers("Owner")).status_code == 409

    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='daily_trial_balance'"
    ).fetchone()["c"] >= 2


def test_manual_blob_round_trips(client, auth_headers):
    view = client.put(
        f"/daily-trial-balance/{DATE}",
        json={"manual": {"section4": {"4_16_total": 123456}, "section8": {"note": "call owner"}}},
        headers=auth_headers("Manager"),
    ).json()
    assert view["manual"]["section4"]["4_16_total"] == 123456
    assert view["manual"]["section8"]["note"] == "call owner"
