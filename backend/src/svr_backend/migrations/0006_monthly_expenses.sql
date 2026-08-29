-- 0006_monthly_expenses.sql - Monthly Expenses (SDD 5.15 / 5.18 / 5.19 / 5.39).
-- Payroll + operational expense ledger with an extensible category list and
-- date-range / category filtered reporting. This is the monthly rollup account -
-- not a fourth independent entry point (Employee Master's Payroll Run computes the
-- per-employee pay; a row here records that run's total).

CREATE TABLE expense_category (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('payroll', 'operational')),
    is_active  INTEGER NOT NULL DEFAULT 1,
    UNIQUE (name, kind)
);

INSERT INTO expense_category (name, kind) VALUES
    ('Bi-weekly Salary', 'payroll'),
    ('Salary Advances',  'payroll'),
    ('Power Bill',       'operational'),
    ('Rent',             'operational'),
    ('Maintenance',      'operational'),
    ('Supplies',         'operational'),
    ('Misc',             'operational');

CREATE TABLE monthly_expense (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_date    TEXT NOT NULL,
    category_id     INTEGER NOT NULL REFERENCES expense_category (id),
    amount          REAL NOT NULL,
    description     TEXT,
    created_by      TEXT NOT NULL,
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_monthly_expense_date ON monthly_expense (expense_date);
CREATE INDEX idx_monthly_expense_category ON monthly_expense (category_id, expense_date);
