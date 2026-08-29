"""Inventory Tracking derivation (SDD 5.10).

``on_hand`` is the tracked stock level. Per shift date, GET /inventory reports:

    closing = on_hand + received_today - sold_today
    status  = "low" when closing <= reorder_level else "ok"

``received_today`` sums that day's ``restock_entry`` rows; ``sold_today`` sums the
oil quantities across that day's ``daily_sales_entry`` rows (live preview - the
real stock decrement is applied at Daily Trial Balance finalization).
"""

from __future__ import annotations

import json
import sqlite3

from svr_backend.calc.daily_sales_entry import OIL_KEYS


def _sold_today(conn: sqlite3.Connection, shift_date: str) -> dict[str, float]:
    sold = {k: 0.0 for k in OIL_KEYS}
    for row in conn.execute(
        "SELECT payload FROM daily_sales_entry WHERE shift_date = ?", (shift_date,)
    ):
        payload = json.loads(row["payload"] or "{}")
        for i, oil in enumerate(payload.get("oils") or []):
            if i >= len(OIL_KEYS):
                break
            qty = oil.get("qty")
            try:
                sold[OIL_KEYS[i]] += float(qty) if qty not in (None, "", " ") else 0.0
            except (TypeError, ValueError):
                pass
    return sold


def _received_today(conn: sqlite3.Connection, on_date: str) -> dict[str, float]:
    rows = conn.execute(
        "SELECT item_key, COALESCE(SUM(quantity), 0) q FROM restock_entry "
        "WHERE restock_date = ? GROUP BY item_key",
        (on_date,),
    ).fetchall()
    return {r["item_key"]: r["q"] for r in rows}


def stock_levels(conn: sqlite3.Connection, as_of: str) -> list[dict]:
    sold = _sold_today(conn, as_of)
    received = _received_today(conn, as_of)
    out = []
    for item in conn.execute("SELECT * FROM inventory_item ORDER BY item_key"):
        key = item["item_key"]
        rcv = round(received.get(key, 0.0), 4)
        sld = round(sold.get(key, 0.0), 4)
        closing = round(item["on_hand"] + rcv - sld, 4)
        out.append(
            {
                "item_key": key,
                "item_label": item["item_label"],
                "unit": item["unit"],
                "opening_stock": item["on_hand"],
                "received_today": rcv,
                "sold_today": sld,
                "closing_stock": closing,
                "reorder_level": item["reorder_level"],
                "status": "low" if closing <= item["reorder_level"] else "ok",
            }
        )
    return out


def on_hand_map(conn: sqlite3.Connection) -> dict[str, float]:
    """Current tracked stock per oil key - used as the Daily Sales Entry opening."""
    return {
        r["item_key"]: r["on_hand"]
        for r in conn.execute("SELECT item_key, on_hand FROM inventory_item")
    }
