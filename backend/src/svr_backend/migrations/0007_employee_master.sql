-- 0007_employee_master.sql - Employee Master + Payroll Run (SDD 5.16 / 5.18 / 5.19).
-- Manager + Owner only (holds sensitive bank data). account_number / ifsc /
-- bank_branch are stored as Fernet ciphertext (SDD 13.3), decrypted only on the
-- single-employee read; list views mask them.

CREATE TABLE employee (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL,
    designation        TEXT,
    daily_wage         REAL NOT NULL DEFAULT 0,
    bank_name          TEXT,
    account_number_enc TEXT,          -- Fernet ciphertext
    ifsc_enc           TEXT,          -- Fernet ciphertext
    bank_branch_enc    TEXT,          -- Fernet ciphertext
    status             TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    last_updated_by    TEXT,
    last_updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_employee_status ON employee (status);

CREATE TABLE payroll_run (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start  TEXT NOT NULL,
    period_end    TEXT NOT NULL,
    pay_date      TEXT NOT NULL,
    gross_total   REAL NOT NULL DEFAULT 0,
    advance_total REAL NOT NULL DEFAULT 0,
    net_total     REAL NOT NULL DEFAULT 0,
    created_by    TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_payroll_run_pay_date ON payroll_run (pay_date);

CREATE TABLE payroll_run_line (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            INTEGER NOT NULL REFERENCES payroll_run (id) ON DELETE CASCADE,
    employee_id       INTEGER NOT NULL REFERENCES employee (id),
    employee_name     TEXT NOT NULL,     -- snapshot at run time
    days_worked       REAL NOT NULL,
    daily_wage        REAL NOT NULL,     -- snapshot
    gross_salary      REAL NOT NULL,
    advance_deduction REAL NOT NULL DEFAULT 0,
    net_pay           REAL NOT NULL
);
CREATE INDEX idx_payroll_line_run ON payroll_run_line (run_id);
