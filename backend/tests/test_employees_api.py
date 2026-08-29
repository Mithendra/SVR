"""Employee Master + Payroll Run: field encryption at rest + masking, RBAC,
payroll gross/net math, audit (SDD 5.16 / 5.19 / 13.3)."""

from __future__ import annotations


def _emp(client, headers, **over):
    body = {
        "name": "Suresh Babu",
        "designation": "Attendant",
        "daily_wage": 600,
        "bank_name": "Indian Bank",
        "account_number": "123456789012",
        "ifsc": "IDIB000P123",
        "bank_branch": "Ponnur Main",
    }
    body.update(over)
    return client.post("/employees", json=body, headers=headers)


def test_sales_has_no_access(client, auth_headers):
    assert client.get("/employees", headers=auth_headers("Sales")).status_code == 403
    assert _emp(client, auth_headers("Sales")).status_code == 403


def test_bank_fields_encrypted_at_rest_and_masked_in_list(client, auth_headers, conn):
    created = _emp(client, auth_headers("Manager")).json()
    # detail view (single GET / create response) reveals in full
    assert created["account_number"] == "123456789012"
    assert created["ifsc"] == "IDIB000P123"

    # stored ciphertext is NOT the plaintext
    row = conn.execute("SELECT * FROM employee WHERE id = ?", (created["id"],)).fetchone()
    assert row["account_number_enc"] not in (None, "123456789012")
    assert "123456789012" not in row["account_number_enc"]

    # list view masks
    listed = client.get("/employees", headers=auth_headers("Manager")).json()
    e = next(x for x in listed if x["id"] == created["id"])
    assert e["account_number"].endswith("9012")
    assert e["account_number"] != "123456789012"

    # audit never carries the sensitive value
    audit = conn.execute(
        "SELECT new_value FROM audit_log WHERE table_name='employee' AND action='create'"
    ).fetchone()["new_value"]
    assert "123456789012" not in audit


def test_get_single_employee_decrypts(client, auth_headers):
    eid = _emp(client, auth_headers("Owner")).json()["id"]
    full = client.get(f"/employees/{eid}", headers=auth_headers("Owner")).json()
    assert full["ifsc"] == "IDIB000P123"
    assert full["bank_branch"] == "Ponnur Main"


def test_update_reencrypts_and_audit_stays_clean(client, auth_headers, conn):
    eid = _emp(client, auth_headers("Manager")).json()["id"]
    upd = client.put(
        f"/employees/{eid}",
        json={"account_number": "999888777666", "daily_wage": 650},
        headers=auth_headers("Manager"),
    ).json()
    assert upd["account_number"] == "999888777666"
    assert upd["daily_wage"] == 650
    row = conn.execute("SELECT new_value FROM audit_log WHERE table_name='employee' AND action='update'").fetchone()
    assert "999888777666" not in row["new_value"]


def test_payroll_run_computes_gross_and_net(client, auth_headers, conn):
    h = auth_headers("Manager")
    a = _emp(client, h, name="A One", daily_wage=500).json()["id"]
    b = _emp(client, h, name="B Two", daily_wage=700).json()["id"]

    run = client.post(
        "/payroll-runs",
        json={
            "period_start": "2026-08-01",
            "period_end": "2026-08-14",
            "pay_date": "2026-08-15",
            "lines": [
                {"employee_id": a, "days_worked": 12},
                {"employee_id": b, "days_worked": 12, "advance_deduction": 1000},
            ],
        },
        headers=h,
    ).json()

    assert run["gross_total"] == 12 * 500 + 12 * 700  # 14400
    assert run["net_total"] == 14400 - 1000  # 13400
    line_b = next(x for x in run["lines"] if x["employee_name"] == "B Two")
    assert line_b["gross_salary"] == 8400
    assert line_b["net_pay"] == 7400

    got = client.get(f"/payroll-runs/{run['id']}", headers=h).json()
    assert len(got["lines"]) == 2
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE table_name='payroll_run'"
    ).fetchone()["c"] == 1


def test_payroll_run_rejects_unknown_employee(client, auth_headers):
    r = client.post(
        "/payroll-runs",
        json={"period_start": "2026-08-01", "period_end": "2026-08-14",
              "lines": [{"employee_id": 99999, "days_worked": 10}]},
        headers=auth_headers("Owner"),
    )
    assert r.status_code == 422
