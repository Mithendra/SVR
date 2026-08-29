"""Reports (SDD 5.28). Yearly Sales Report - a financial-year (Apr 1 - Mar 31)
summary. Revenue / salaries / operational expenses are computed live from the
transactional tables; stock-value COGS and IOCL commission are stored per FY
(they come from Daily Trial Balance, not built yet). Manager + Owner; the manual
figures are Owner-editable.

Not tax advice - the report carries an explicit disclaimer for the station's CA.
"""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal

router = APIRouter(prefix="/reports", tags=["reports"])

DISCLAIMER = (
    "Summary for reference only - not tax advice. Verify every figure against the "
    "source records and route the return through the station's Chartered Accountant."
)


class YearlyManualIn(BaseModel):
    cogs_opening: float | None = Field(default=None, ge=0)
    cogs_purchases: float | None = Field(default=None, ge=0)
    cogs_closing: float | None = Field(default=None, ge=0)
    hs_commission: float | None = Field(default=None, ge=0)
    ms_commission: float | None = Field(default=None, ge=0)
    notes: str | None = None


def _fy_bounds(fy_start_year: int) -> tuple[str, str]:
    return f"{fy_start_year}-04-01", f"{fy_start_year + 1}-03-31"


def _live_figures(conn: sqlite3.Connection, start: str, end: str) -> dict:
    hs = ms = oil = 0.0
    months: dict[str, dict] = {}
    for row in conn.execute(
        "SELECT shift_date, result FROM daily_sales_entry "
        "WHERE shift_date >= ? AND shift_date <= ?",
        (start, end),
    ):
        r = json.loads(row["result"] or "{}")
        row_hs = (r.get("hs") or {}).get("amount") or 0.0
        row_ms = (r.get("ms") or {}).get("amount") or 0.0
        row_oil = r.get("oil_total") or 0.0
        hs += row_hs
        ms += row_ms
        oil += row_oil
        m = row["shift_date"][:7]
        b = months.setdefault(m, {"month": m, "fuel_sales": 0.0, "oil_sales": 0.0})
        b["fuel_sales"] += row_hs + row_ms
        b["oil_sales"] += row_oil

    salaries = conn.execute(
        "SELECT COALESCE(SUM(net_total), 0) s FROM payroll_run "
        "WHERE pay_date >= ? AND pay_date <= ?",
        (start, end),
    ).fetchone()["s"]

    opex_rows = conn.execute(
        """
        SELECT c.name AS category, COALESCE(SUM(e.amount), 0) AS total
        FROM monthly_expense e JOIN expense_category c ON c.id = e.category_id
        WHERE c.kind = 'operational' AND e.expense_date >= ? AND e.expense_date <= ?
        GROUP BY c.id
        ORDER BY c.name
        """,
        (start, end),
    ).fetchall()
    opex = [{"category": r["category"], "total": round(r["total"], 4)} for r in opex_rows]
    opex_total = round(sum(r["total"] for r in opex), 4)

    return {
        "hs_sales": round(hs, 4),
        "ms_sales": round(ms, 4),
        "oil_sales": round(oil, 4),
        "fuel_sales_total": round(hs + ms, 4),
        "total_revenue": round(hs + ms + oil, 4),
        "salaries_total": round(salaries, 4),
        "operational_expenses": opex,
        "operational_expenses_total": opex_total,
        "by_month": [months[k] for k in sorted(months)],
    }


@router.get("/yearly/{fy_start_year}")
def yearly_report(
    fy_start_year: int,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    start, end = _fy_bounds(fy_start_year)
    live = _live_figures(conn, start, end)

    m = conn.execute(
        "SELECT * FROM yearly_report WHERE fy_start_year = ?", (fy_start_year,)
    ).fetchone()
    manual = {
        "cogs_opening": m["cogs_opening"] if m else 0.0,
        "cogs_purchases": m["cogs_purchases"] if m else 0.0,
        "cogs_closing": m["cogs_closing"] if m else 0.0,
        "hs_commission": m["hs_commission"] if m else 0.0,
        "ms_commission": m["ms_commission"] if m else 0.0,
        "notes": m["notes"] if m else None,
    }

    cogs = round(manual["cogs_opening"] + manual["cogs_purchases"] - manual["cogs_closing"], 4)
    gross_profit = round(live["total_revenue"] - cogs, 4)
    total_commission = round(manual["hs_commission"] + manual["ms_commission"], 4)
    total_operating_costs = round(live["salaries_total"] + live["operational_expenses_total"], 4)
    net_profit = round(gross_profit + total_commission - total_operating_costs, 4)

    return {
        "fy_start_year": fy_start_year,
        "fy_label": f"FY {fy_start_year}-{str(fy_start_year + 1)[-2:]}",
        "period": {"start": start, "end": end},
        "live": live,
        "manual": manual,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "total_commission": total_commission,
        "total_operating_costs": total_operating_costs,
        "net_profit": net_profit,
        "disclaimer": DISCLAIMER,
    }


@router.put("/yearly/{fy_start_year}")
def set_yearly_manual(
    fy_start_year: int,
    body: YearlyManualIn,
    principal: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    existing = conn.execute(
        "SELECT * FROM yearly_report WHERE fy_start_year = ?", (fy_start_year,)
    ).fetchone()

    def pick(field: str, default: float | str | None):
        v = getattr(body, field)
        if v is not None:
            return v
        return existing[field] if existing else default

    values = {
        "cogs_opening": pick("cogs_opening", 0.0),
        "cogs_purchases": pick("cogs_purchases", 0.0),
        "cogs_closing": pick("cogs_closing", 0.0),
        "hs_commission": pick("hs_commission", 0.0),
        "ms_commission": pick("ms_commission", 0.0),
        "notes": pick("notes", None),
    }
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO yearly_report
                (fy_start_year, cogs_opening, cogs_purchases, cogs_closing,
                 hs_commission, ms_commission, notes, last_updated_by)
            VALUES (:fy, :cogs_opening, :cogs_purchases, :cogs_closing,
                    :hs_commission, :ms_commission, :notes, :by)
            ON CONFLICT(fy_start_year) DO UPDATE SET
                cogs_opening = excluded.cogs_opening,
                cogs_purchases = excluded.cogs_purchases,
                cogs_closing = excluded.cogs_closing,
                hs_commission = excluded.hs_commission,
                ms_commission = excluded.ms_commission,
                notes = excluded.notes,
                last_updated_by = excluded.last_updated_by,
                last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            {"fy": fy_start_year, "by": principal.login_name, **values},
        )
        record_write(
            conn, table="yearly_report", record_id=fy_start_year, action="update",
            actor=principal.login_name, new=values,
        )
    return yearly_report(fy_start_year, principal, conn)
