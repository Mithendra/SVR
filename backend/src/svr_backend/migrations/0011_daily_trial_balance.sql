-- 0011_daily_trial_balance.sql - Daily Trial Balance (SDD 5.8 / 9). The most
-- formula-dense module. One row per calendar date.
--
-- SCOPE OF THIS SLICE: Sections 1 (IOCL Computer vs Pump), 3 (Day Sales Report -
-- pulled read-only from Daily Sales Summary), 6 (Stock Value) and 7 (Trial Balance
-- total) are modelled with the SDD Section 9 formulas. Sections 2, 4, 5, 8, 9, 10,
-- 11 are captured as a free-form `manual_json` blob pending SDD ADR-1 (whether
-- their fields are manual columns or computed rollups from Credit Master /
-- Monthly Expenses / Payroll Run). See docs/ ADR-1.

CREATE TABLE daily_trial_balance (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_date         TEXT NOT NULL UNIQUE,

    -- Section 1 manual inputs (the regulatory IOCL flow-computer readings).
    s1_hs_yesterday    REAL,
    s1_hs_current      REAL,
    s1_ms_yesterday    REAL,
    s1_ms_current      REAL,

    -- Section 5.4 / 7.1 manual: "Today's Actual Reported SVR Cash / Book Value".
    s54_cash_book_value REAL,

    manual_json        TEXT NOT NULL DEFAULT '{}',   -- deferred sections 2/4/5/8/9/10/11
    result_json        TEXT NOT NULL DEFAULT '{}',   -- cached calc-engine output

    status             TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'finalized')),
    finalized_by       TEXT,
    finalized_at       TEXT,
    last_updated_by    TEXT,
    last_updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_dtb_status ON daily_trial_balance (status);
