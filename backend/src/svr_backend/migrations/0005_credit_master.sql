-- 0005_credit_master.sql - Credit / Remittance Master (SDD 5.17). Supersedes the
-- two retired forms (New Credit Entry, Record Repayment). One table for both the
-- credit-given and the remittance-received events; the Creditor Balance Summary is
-- a GROUP BY over creditor_name (partial repayments are the norm - SDD 19 item 10).

CREATE TABLE credit_transaction (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL CHECK (kind IN ('credit', 'remittance')),
    creditor_name   TEXT NOT NULL,
    phone           TEXT,
    fuel_type       TEXT,                 -- credit only: 'Diesel' / 'Petrol' / free text
    ltrs            REAL,                  -- credit only
    rate            REAL,                  -- credit only
    amount          REAL NOT NULL,         -- credit: ltrs*rate (or entered); remittance: payment
    txn_date        TEXT NOT NULL,
    source          TEXT,                  -- remittance only: where the repayment was captured
    pump_sales_man  TEXT,                  -- given-by (credit) / involved (remittance)
    note            TEXT,
    created_by      TEXT NOT NULL,
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_credit_txn_name ON credit_transaction (creditor_name);
CREATE INDEX idx_credit_txn_kind_date ON credit_transaction (kind, txn_date);
