"""Daily Sales Summary (SDD 5.23-5.25 / 10).

Access (SDD 4.2): Sales may submit/verify *their own pump's* data; Manager and
Owner have full access. Upload to Daily Trial Balance is blocked until BOTH pumps
are verified - the check that a scanned/OCR'd entry was reviewed by a human before
it counts (SDD ADR-5).

Combined totals are derived (svr_backend/summary.build_summary), never stored.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, get_principal, require
from svr_backend.core.session import Principal
from svr_backend.summary import build_summary

router = APIRouter(prefix="/daily-sales-summary", tags=["daily-sales-summary"])

TABLE = "daily_sales_summary"


class SummaryUpdate(BaseModel):
    off_salesman: str | None = None
    road_salesman: str | None = None
    off_verified: bool | None = None
    road_verified: bool | None = None
    off_verified_note: str | None = None
    road_verified_note: str | None = None


def _touches_side(body: SummaryUpdate, side: str) -> bool:
    prefix = "off_" if side == "office" else "road_"
    fields = (f"{prefix}salesman", f"{prefix}verified", f"{prefix}verified_note")
    return any(getattr(body, f) is not None for f in fields)


@router.get("")
def list_summaries(
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    rows = conn.execute(
        f"SELECT shift_date, status, uploaded_at FROM {TABLE} ORDER BY shift_date DESC LIMIT 60"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{shift_date}")
def get_summary(
    shift_date: str,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    return build_summary(conn, shift_date)


@router.put("/{shift_date}")
def upsert_summary(
    shift_date: str,
    body: SummaryUpdate,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    current = build_summary(conn, shift_date)

    # Sales may only touch the side they submitted (SDD 4.2).
    if principal.role == "Sales":
        for side in ("office", "road"):
            if _touches_side(body, side) and current[side]["submitted_by"] != principal.login_name:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    f"Sales users can only verify their own pump's submission "
                    f"(the {side} pump was submitted by "
                    f"{current[side]['submitted_by'] or 'nobody yet'})",
                )

    off_id = current["office"]["entry_id"]
    road_id = current["road"]["entry_id"]

    # Merge body onto current state.
    def pick(field_name: str, cur_val):
        v = getattr(body, field_name)
        return cur_val if v is None else v

    off_verified = pick("off_verified", current["office"]["verified"])
    road_verified = pick("road_verified", current["road"]["verified"])
    off_salesman = pick("off_salesman", current["office"]["salesman"])
    road_salesman = pick("road_salesman", current["road"]["salesman"])
    off_note = pick("off_verified_note", current["office"]["verified_note"])
    road_note = pick("road_verified_note", current["road"]["verified_note"])

    both_verified = bool(off_verified) and bool(road_verified) and off_id and road_id
    new_status = current["status"]
    if new_status != "uploaded":
        new_status = "verified" if both_verified else "draft"

    verified_by = current["verified_by"]
    if both_verified and not verified_by:
        verified_by = principal.login_name

    with transaction(conn):
        conn.execute(
            f"""
            INSERT INTO {TABLE} (
                shift_date, off_entry_id, road_entry_id,
                off_verified, road_verified, off_verified_note, road_verified_note,
                off_salesman, road_salesman, status,
                prepared_by, verified_by, last_updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shift_date) DO UPDATE SET
                off_entry_id       = excluded.off_entry_id,
                road_entry_id      = excluded.road_entry_id,
                off_verified       = excluded.off_verified,
                road_verified      = excluded.road_verified,
                off_verified_note  = excluded.off_verified_note,
                road_verified_note = excluded.road_verified_note,
                off_salesman       = excluded.off_salesman,
                road_salesman      = excluded.road_salesman,
                status             = excluded.status,
                verified_by        = excluded.verified_by,
                last_updated_by    = excluded.last_updated_by,
                last_updated_at    = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            (
                shift_date, off_id, road_id,
                int(bool(off_verified)), int(bool(road_verified)), off_note, road_note,
                off_salesman, road_salesman, new_status,
                principal.login_name, verified_by, principal.login_name,
            ),
        )
        rid = conn.execute(
            f"SELECT id FROM {TABLE} WHERE shift_date = ?", (shift_date,)
        ).fetchone()["id"]
        record_write(
            conn, table=TABLE, record_id=rid, action="update", actor=principal.login_name,
            new={"status": new_status, "off_verified": bool(off_verified),
                 "road_verified": bool(road_verified)},
        )
    return build_summary(conn, shift_date)


@router.post("/{shift_date}/upload")
def upload_to_trial_balance(
    shift_date: str,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    summary = build_summary(conn, shift_date)
    if not summary["both_present"]:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Both the Office and Road pump submissions must exist before uploading",
        )
    if summary["status"] == "uploaded":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already uploaded")
    if not summary["both_verified"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Upload blocked: both pumps must be verified first",
        )

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    with transaction(conn):
        conn.execute(
            f"""
            UPDATE {TABLE}
            SET status = 'uploaded', uploaded_by = ?, uploaded_at = ?,
                last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE shift_date = ?
            """,
            (principal.login_name, now, principal.login_name, shift_date),
        )
        rid = conn.execute(
            f"SELECT id FROM {TABLE} WHERE shift_date = ?", (shift_date,)
        ).fetchone()["id"]
        record_write(
            conn, table=TABLE, record_id=rid, action="update", actor=principal.login_name,
            old={"status": summary["status"]},
            new={"status": "uploaded", "grand_total": summary["combined"]["grand_total"]},
        )
    # NOTE: writing the combined figures into Daily Trial Balance Section 2 happens
    # when that module lands - this endpoint sets the gate + records the transition.
    return build_summary(conn, shift_date)
