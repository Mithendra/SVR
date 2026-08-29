-- 0009_yearly_report.sql - Yearly Sales Report (SDD 5.28). Financial-year
-- (Apr 1 - Mar 31) tax-oriented summary. Revenue, salaries and operational
-- expenses are computed live from Daily Sales Entry / Payroll Run / Monthly
-- Expenses; the figures that depend on Daily Trial Balance (which is not built
-- yet) - stock-value COGS and IOCL commission - are stored here per FY.

CREATE TABLE yearly_report (
    fy_start_year   INTEGER PRIMARY KEY,       -- 2026 => FY 2026-27 (Apr 2026 - Mar 2027)
    cogs_opening    REAL NOT NULL DEFAULT 0,   -- Opening Stock Value (Apr 1), at Buy Rate
    cogs_purchases  REAL NOT NULL DEFAULT 0,   -- Purchases during the year, at Buy Rate
    cogs_closing    REAL NOT NULL DEFAULT 0,   -- Closing Stock Value (Mar 31), at Buy Rate
    hs_commission   REAL NOT NULL DEFAULT 0,
    ms_commission   REAL NOT NULL DEFAULT 0,
    notes           TEXT,
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
