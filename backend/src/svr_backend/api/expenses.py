"""Monthly Expenses (SDD 5.15 / 5.18 / 5.19 / 5.39). Manager + Owner (Sales has
no access). Adding a category is Owner-only (a policy knob).

Reporting: GET /expenses filters by inclusive date range + category/kind and
returns payroll / operational / grand totals; GET /expenses/summary groups by
category with per-kind subtotals.
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

router = APIRouter(prefix="/expenses", tags=["expenses"])


class CategoryIn(BaseModel):
    name: str = Field(min_length=1)
    kind: str = Field(pattern="^(payroll|operational)$")


class ExpenseIn(BaseModel):
    expense_date: str | None = None
    category_id: int
    amount: float = Field(gt=0)
    description: str | None = None


class ExpenseUpdate(BaseModel):
    expense_date: str | None = None
    category_id: int | None = None
    amount: float | None = Field(default=None, gt=0)
    description: str | None = None


def _range_clause(start: str | None, end: str | None) -> tuple[str, list]:
    clauses, params = [], []
    if start:
        clauses.append("e.expense_date >= ?")
        params.append(start)
    if end:
        clauses.append("e.expense_date <= ?")
        params.append(end)
    return (" AND ".join(clauses), params)


@router.get("/categories")
def list_categories(
    active_only: bool = True,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    sql = "SELECT id, name, kind, is_active FROM expense_category"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY kind, name"
    return [dict(r) for r in conn.execute(sql)]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def add_category(
    body: CategoryIn,
    principal: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    existing = conn.execute(
        "SELECT id FROM expense_category WHERE name = ? AND kind = ?", (body.name, body.kind)
    ).fetchone()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Category already exists")
    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO expense_category (name, kind) VALUES (?, ?)", (body.name, body.kind)
        )
        record_write(
            conn, table="expense_category", record_id=cur.lastrowid, action="create",
            actor=principal.login_name, new={"name": body.name, "kind": body.kind},
        )
    return {"id": cur.lastrowid, "name": body.name, "kind": body.kind, "is_active": 1}


@router.get("")
def list_expenses(
    start: str | None = None,
    end: str | None = None,
    category_id: int | None = None,
    kind: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    where, params = _range_clause(start, end)
    clauses = [where] if where else []
    if category_id is not None:
        clauses.append("e.category_id = ?")
        params.append(category_id)
    if kind is not None:
        clauses.append("c.kind = ?")
        params.append(kind)
    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""

    rows = conn.execute(
        f"""
        SELECT e.id, e.expense_date, e.amount, e.description,
               c.id AS category_id, c.name AS category, c.kind
        FROM monthly_expense e JOIN expense_category c ON c.id = e.category_id
        {where_sql}
        ORDER BY e.expense_date DESC, e.id DESC
        """,
        params,
    ).fetchall()
    items = [dict(r) for r in rows]
    payroll_total = round(sum(i["amount"] for i in items if i["kind"] == "payroll"), 4)
    operational_total = round(sum(i["amount"] for i in items if i["kind"] == "operational"), 4)
    return {
        "items": items,
        "count": len(items),
        "payroll_total": payroll_total,
        "operational_total": operational_total,
        "grand_total": round(payroll_total + operational_total, 4),
    }


@router.get("/summary")
def expense_summary(
    start: str | None = None,
    end: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    where, params = _range_clause(start, end)
    where_sql = f" WHERE {where}" if where else ""
    rows = conn.execute(
        f"""
        SELECT c.name AS category, c.kind, COALESCE(SUM(e.amount), 0) AS total
        FROM monthly_expense e JOIN expense_category c ON c.id = e.category_id
        {where_sql}
        GROUP BY c.id
        ORDER BY c.kind, c.name
        """,
        params,
    ).fetchall()
    by_category = [
        {"category": r["category"], "kind": r["kind"], "total": round(r["total"], 4)} for r in rows
    ]
    payroll = round(sum(r["total"] for r in by_category if r["kind"] == "payroll"), 4)
    operational = round(sum(r["total"] for r in by_category if r["kind"] == "operational"), 4)
    return {
        "by_category": by_category,
        "payroll_subtotal": payroll,
        "operational_subtotal": operational,
        "grand_total": round(payroll + operational, 4),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def add_expense(
    body: ExpenseIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    cat = conn.execute(
        "SELECT id FROM expense_category WHERE id = ?", (body.category_id,)
    ).fetchone()
    if cat is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category_id")
    when = body.expense_date or date.today().isoformat()
    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO monthly_expense
                (expense_date, category_id, amount, description, created_by, last_updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (when, body.category_id, body.amount, body.description, principal.login_name,
             principal.login_name),
        )
        record_write(
            conn, table="monthly_expense", record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"expense_date": when, "category_id": body.category_id, "amount": body.amount},
        )
    return {"id": cur.lastrowid, "expense_date": when, "category_id": body.category_id,
            "amount": body.amount}


@router.put("/{expense_id}")
def update_expense(
    expense_id: int,
    body: ExpenseUpdate,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute(
        "SELECT * FROM monthly_expense WHERE id = ?", (expense_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    updates = {
        k: v for k, v in {
            "expense_date": body.expense_date,
            "category_id": body.category_id,
            "amount": body.amount,
            "description": body.description,
        }.items() if v is not None
    }
    if not updates:
        return dict(row)
    set_sql = ", ".join(f"{k} = ?" for k in updates)
    with transaction(conn):
        conn.execute(
            f"UPDATE monthly_expense SET {set_sql}, last_updated_by = ?, "
            f"last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            (*updates.values(), principal.login_name, expense_id),
        )
        record_write(
            conn, table="monthly_expense", record_id=expense_id, action="update",
            actor=principal.login_name, old={k: row[k] for k in updates}, new=updates,
        )
    updated = conn.execute("SELECT * FROM monthly_expense WHERE id = ?", (expense_id,)).fetchone()
    return dict(updated)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute("SELECT * FROM monthly_expense WHERE id = ?", (expense_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    with transaction(conn):
        conn.execute("DELETE FROM monthly_expense WHERE id = ?", (expense_id,))
        record_write(
            conn, table="monthly_expense", record_id=expense_id, action="delete",
            actor=principal.login_name,
            old={"expense_date": row["expense_date"], "amount": row["amount"]},
        )
