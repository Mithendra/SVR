-- 0008_payment_receipt.sql - Payment Receipt (SDD 5.20 / 5.30). The only
-- per-transaction artifact in the system: a customer-facing fuel-sale receipt.
-- English-only (confirmed). Usable at point of sale by Sales, Manager, Owner;
-- deletion is Manager/Owner only.

CREATE TABLE payment_receipt (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no    TEXT UNIQUE,                -- 'SVR-000123', assigned after insert
    receipt_date  TEXT NOT NULL,
    receipt_time  TEXT,
    pump_serial   TEXT,
    attendant     TEXT,
    vehicle_no    TEXT,
    fuel_type     TEXT NOT NULL,              -- 'Diesel' / 'Petrol'
    liters        REAL NOT NULL,
    rate          REAL NOT NULL,
    total         REAL NOT NULL,              -- liters * rate
    payment_mode  TEXT NOT NULL CHECK (payment_mode IN ('Cash', 'Card', 'UPI', 'Credit')),
    ref_no        TEXT,
    card_last4    TEXT,
    created_by    TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_receipt_date ON payment_receipt (receipt_date);
