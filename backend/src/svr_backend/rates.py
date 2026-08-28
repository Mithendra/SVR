"""Rate Master lookups shared by the Rate Master API and the Daily Sales Entry
snapshot. Buy vs Sell matters: Daily Sales Entry gas rows lock the **Sell** rate
(SDD 9 row 3); Trial Balance Stock Value uses the **Buy** rate (SDD 9 row 6).
"""

from __future__ import annotations

import sqlite3
from datetime import date


def latest_effective_rates(
    conn: sqlite3.Connection, as_of: date | str | None = None
) -> dict[str, sqlite3.Row]:
    """Newest ``rate_master`` row per ``item_key`` with ``effective_date <= as_of``.

    ``as_of`` defaults to today. Returned rows expose ``buy_rate`` and ``sell_rate``.
    """
    if isinstance(as_of, date):
        as_of_str = as_of.isoformat()
    else:
        as_of_str = as_of or date.today().isoformat()
    rows = conn.execute(
        """
        SELECT r.*
        FROM rate_master r
        JOIN (
            SELECT item_key, MAX(effective_date) AS max_eff
            FROM rate_master
            WHERE effective_date <= ?
            GROUP BY item_key
        ) latest
          ON latest.item_key = r.item_key AND latest.max_eff = r.effective_date
        """,
        (as_of_str,),
    ).fetchall()
    return {row["item_key"]: row for row in rows}
