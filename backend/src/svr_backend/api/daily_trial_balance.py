"""Daily Trial Balance API (SDD 5.8 / 9). Manager + Owner only (Sales has no
access, SDD 4.2). One row per date.

Sections 1/6/7 are computed by the calc engine; Section 3 is pulled read-only from
Daily Sales Summary; Sections 2/4/5/8/9/10/11 are stored as a free-form manual
blob pending SDD ADR-1. Every write recomputes and audits.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from svr_backend.calc.daily_trial_balance import (
    Section1Input,
    TrialBalanceInput,
    compute,
)
from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.params import get_param
from svr_backend.rates import latest_effective_rates
from svr_backend.summary import build_summary

router = APIRouter(prefix="/daily-trial-balance", tags=["daily-trial-balance"])

TABLE = "daily_trial_balance"


class TrialBalanceUpsert(BaseModel):
    s1_hs_yesterday: float | None = None
    s1_hs_current: float | None = None
    s1_ms_yesterday: float | None = None
    s1_ms_current: float | None = None
    s54_cash_book_value: float | None = None
    manual: dict = {}


def _context(conn: sqlite3.Connection, shift_date: str, row: sqlite3.Row | None) -> dict:
    """Pull Section 3 consumption (Daily Sales Summary), Buy rates, testing deduction."""
    summary = build_summary(conn, shift_date)
    s3_hs = summary["combined"]["hs_liters"]["combined"] if summary["both_present"] else None
    s3_ms = summary["combined"]["ms_liters"]["combined"] if summary["both_present"] else None

    rates = latest_effective_rates(conn, shift_date)
    buy_hs = rates["HS"]["buy_rate"] if "HS" in rates else None
    buy_ms = rates["MS"]["buy_rate"] if "MS" in rates else None
    testing = get_param(conn, "testing_density_deduction", 10.0, as_of=shift_date)

    data = TrialBalanceInput(
        s1=Section1Input(
            hs_yesterday=row["s1_hs_yesterday"] if row else None,
            hs_current=row["s1_hs_current"] if row else None,
            ms_yesterday=row["s1_ms_yesterday"] if row else None,
            ms_current=row["s1_ms_current"] if row else None,
        ),
        s3_hs_consumption=s3_hs,
        s3_ms_consumption=s3_ms,
        buy_rate_hs=buy_hs,
        buy_rate_ms=buy_ms,
        testing_deduction=testing,
        cash_book_value=row["s54_cash_book_value"] if row else None,
    )
    return {
        "data": data,
        "s3_source": "daily_sales_summary" if summary["both_present"] else "unavailable",
        "s3_hs_consumption": s3_hs,
        "s3_ms_consumption": s3_ms,
        "buy_rate_hs": buy_hs,
        "buy_rate_ms": buy_ms,
        "testing_deduction": testing,
        "summary_status": summary["status"],
    }


def _view(conn: sqlite3.Connection, shift_date: str) -> dict:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE shift_date = ?", (shift_date,)).fetchone()
    ctx = _context(conn, shift_date, row)
    result = compute(ctx["data"]).to_dict()
    return {
        "shift_date": shift_date,
        "status": row["status"] if row else "draft",
        "inputs": {
            "s1_hs_yesterday": row["s1_hs_yesterday"] if row else None,
            "s1_hs_current": row["s1_hs_current"] if row else None,
            "s1_ms_yesterday": row["s1_ms_yesterday"] if row else None,
            "s1_ms_current": row["s1_ms_current"] if row else None,
            "s54_cash_book_value": row["s54_cash_book_value"] if row else None,
        },
        "manual": json.loads(row["manual_json"]) if row else {},
        "pulled": {
            "s3_source": ctx["s3_source"],
            "s3_hs_consumption": ctx["s3_hs_consumption"],
            "s3_ms_consumption": ctx["s3_ms_consumption"],
            "buy_rate_hs": ctx["buy_rate_hs"],
            "buy_rate_ms": ctx["buy_rate_ms"],
            "testing_deduction": ctx["testing_deduction"],
        },
        "computed": result,
        "finalized_by": row["finalized_by"] if row else None,
        "finalized_at": row["finalized_at"] if row else None,
        "adr1_note": (
            "Sections 2/4/5/8/9/10/11 are captured in `manual` pending SDD ADR-1 "
            "(manual columns vs computed rollups)."
        ),
    }


@router.get("/{shift_date}")
def get_trial_balance(
    shift_date: str,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return _view(conn, shift_date)


@router.put("/{shift_date}")
def upsert_trial_balance(
    shift_date: str,
    body: TrialBalanceUpsert,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    existing = conn.execute(
        f"SELECT * FROM {TABLE} WHERE shift_date = ?", (shift_date,)
    ).fetchone()
    if existing and existing["status"] == "finalized":
        raise HTTPException(status.HTTP_409_CONFLICT, "This date's Trial Balance is finalized")

    def pick(field_name: str, col: str):
        v = getattr(body, field_name)
        if v is not None:
            return v
        return existing[col] if existing else None

    values = {
        "s1_hs_yesterday": pick("s1_hs_yesterday", "s1_hs_yesterday"),
        "s1_hs_current": pick("s1_hs_current", "s1_hs_current"),
        "s1_ms_yesterday": pick("s1_ms_yesterday", "s1_ms_yesterday"),
        "s1_ms_current": pick("s1_ms_current", "s1_ms_current"),
        "s54_cash_book_value": pick("s54_cash_book_value", "s54_cash_book_value"),
    }
    manual = json.loads(existing["manual_json"]) if existing else {}
    manual.update(body.manual or {})

    # recompute with the merged inputs so result_json is always current.
    # _context indexes the row by column name; a plain dict with all five keys works.
    ctx = _context(conn, shift_date, dict(values))
    result = compute(ctx["data"]).to_dict()

    with transaction(conn):
        conn.execute(
            f"""
            INSERT INTO {TABLE} (
                shift_date, s1_hs_yesterday, s1_hs_current, s1_ms_yesterday, s1_ms_current,
                s54_cash_book_value, manual_json, result_json, last_updated_by
            ) VALUES (:d, :s1hy, :s1hc, :s1my, :s1mc, :cash, :manual, :result, :by)
            ON CONFLICT(shift_date) DO UPDATE SET
                s1_hs_yesterday = :s1hy, s1_hs_current = :s1hc,
                s1_ms_yesterday = :s1my, s1_ms_current = :s1mc,
                s54_cash_book_value = :cash, manual_json = :manual, result_json = :result,
                last_updated_by = :by,
                last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            {
                "d": shift_date,
                "s1hy": values["s1_hs_yesterday"], "s1hc": values["s1_hs_current"],
                "s1my": values["s1_ms_yesterday"], "s1mc": values["s1_ms_current"],
                "cash": values["s54_cash_book_value"],
                "manual": json.dumps(manual), "result": json.dumps(result),
                "by": principal.login_name,
            },
        )
        rid = conn.execute(
            f"SELECT id FROM {TABLE} WHERE shift_date = ?", (shift_date,)
        ).fetchone()["id"]
        record_write(
            conn, table=TABLE, record_id=rid, action="update", actor=principal.login_name,
            new={"shift_date": shift_date, "s7_3_total": result["section7"]["7_3_total"]},
        )
    return _view(conn, shift_date)


@router.post("/{shift_date}/finalize")
def finalize_trial_balance(
    shift_date: str,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE shift_date = ?", (shift_date,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No Trial Balance for this date yet")
    if row["status"] == "finalized":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already finalized")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with transaction(conn):
        conn.execute(
            f"UPDATE {TABLE} SET status = 'finalized', finalized_by = ?, finalized_at = ?, "
            f"last_updated_by = ? WHERE shift_date = ?",
            (principal.login_name, now, principal.login_name, shift_date),
        )
        record_write(
            conn, table=TABLE, record_id=row["id"], action="update", actor=principal.login_name,
            old={"status": "draft"}, new={"status": "finalized"},
        )
    # NOTE: finalizing is where Section 9's historical ledger row and the Inventory
    # stock decrement would be written - deferred with the remaining sections.
    return _view(conn, shift_date)
