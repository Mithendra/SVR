"""Credit / Remittance Master (SDD 5.17). Manager + Owner only (SDD 4.2).

Section 1 (New Credit) and Section 2 (Remittance) both write ``credit_transaction``
rows; Section 3 (Creditor Balance Summary) groups them by ``creditor_name`` -
``outstanding = total_credit - total_remitted``, pending (largest outstanding)
first.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal

router = APIRouter(prefix="/credit-master", tags=["credit-master"])

TABLE = "credit_transaction"


class CreditIn(BaseModel):
    creditor_name: str = Field(min_length=1)
    phone: str | None = None
    fuel_type: str | None = None
    ltrs: float | None = Field(default=None, gt=0)
    rate: float | None = Field(default=None, gt=0)
    amount: float | None = Field(default=None, gt=0)
    txn_date: str | None = None
    given_by: str | None = None
    note: str | None = None


class RemittanceIn(BaseModel):
    creditor_name: str = Field(min_length=1)
    amount: float = Field(gt=0)
    txn_date: str | None = None
    source: str | None = None
    pump_sales_man: str | None = None
    note: str | None = None


def _row(r: sqlite3.Row) -> dict:
    return {k: r[k] for k in r.keys()}


@router.get("/transactions")
def list_transactions(
    creditor: str | None = None,
    kind: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    clauses, params = [], []
    if creditor:
        clauses.append("creditor_name = ?")
        params.append(creditor)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM {TABLE}{where} ORDER BY txn_date DESC, id DESC", params
    ).fetchall()
    return [_row(r) for r in rows]


@router.get("/summary")
def creditor_summary(
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT
            creditor_name,
            (SELECT phone FROM {TABLE} t2
             WHERE t2.creditor_name = t.creditor_name AND t2.phone IS NOT NULL
             ORDER BY id DESC LIMIT 1) AS phone,
            COALESCE(SUM(CASE WHEN kind = 'credit' THEN amount END), 0)     AS total_credit,
            COALESCE(SUM(CASE WHEN kind = 'remittance' THEN amount END), 0) AS total_remitted
        FROM {TABLE} t
        GROUP BY creditor_name
        ORDER BY (total_credit - total_remitted) DESC, creditor_name
        """
    ).fetchall()
    out = []
    for r in rows:
        outstanding = round(r["total_credit"] - r["total_remitted"], 4)
        out.append(
            {
                "creditor_name": r["creditor_name"],
                "phone": r["phone"],
                "total_credit": round(r["total_credit"], 4),
                "total_remitted": round(r["total_remitted"], 4),
                "outstanding": outstanding,
            }
        )
    return out


@router.post("/credit", status_code=status.HTTP_201_CREATED)
def add_credit(
    body: CreditIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    if body.ltrs is not None and body.rate is not None:
        amount = round(body.ltrs * body.rate, 4)
    elif body.amount is not None:
        amount = body.amount
    else:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Provide either (ltrs and rate) or an explicit amount",
        )
    when = body.txn_date or date.today().isoformat()
    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {TABLE}
                (kind, creditor_name, phone, fuel_type, ltrs, rate, amount, txn_date,
                 pump_sales_man, note, created_by, last_updated_by)
            VALUES ('credit', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.creditor_name, body.phone, body.fuel_type, body.ltrs, body.rate,
                amount, when, body.given_by, body.note, principal.login_name,
                principal.login_name,
            ),
        )
        record_write(
            conn, table=TABLE, record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"kind": "credit", "creditor_name": body.creditor_name, "amount": amount},
        )
    return _row(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.post("/remittance", status_code=status.HTTP_201_CREATED)
def add_remittance(
    body: RemittanceIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    when = body.txn_date or date.today().isoformat()
    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {TABLE}
                (kind, creditor_name, amount, txn_date, source, pump_sales_man, note,
                 created_by, last_updated_by)
            VALUES ('remittance', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.creditor_name, body.amount, when, body.source, body.pump_sales_man,
                body.note, principal.login_name, principal.login_name,
            ),
        )
        record_write(
            conn, table=TABLE, record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"kind": "remittance", "creditor_name": body.creditor_name, "amount": body.amount},
        )
    return _row(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.delete("/transactions/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    txn_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (txn_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    with transaction(conn):
        conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (txn_id,))
        record_write(
            conn, table=TABLE, record_id=txn_id, action="delete",
            actor=principal.login_name,
            old={
                "kind": row["kind"],
                "creditor_name": row["creditor_name"],
                "amount": row["amount"],
            },
        )
