-- 0001_init.sql - foundation schema (SDD 8.2, subset needed for the Daily Sales
-- Entry vertical slice). Every mutable business figure lives in a table, not code
-- (SDD ADR-3); every table carries last_updated_by/at and is mirrored into audit_log
-- on write (SDD 13.4).

-- ---------------------------------------------------------------------------
-- users - system accounts. role in {Sales, Manager, Owner} (SDD 4.1).
-- login_name auto-derived (first initial + last name), editable on collision.
-- password_hash: argon2; never plaintext, never returned by any endpoint.
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    login_name       TEXT NOT NULL UNIQUE,
    full_name        TEXT NOT NULL,
    email            TEXT NOT NULL,
    cell_phone       TEXT,                      -- personal data; encrypt at rest in prod (SDD 13.3)
    role             TEXT NOT NULL CHECK (role IN ('Sales', 'Manager', 'Owner')),
    password_hash    TEXT,                      -- NULL until the user sets one via reset link
    status           TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Disabled')),
    totp_enabled     INTEGER NOT NULL DEFAULT 0,
    totp_secret      TEXT,                      -- server-side only; never displayed after setup
    last_updated_by  TEXT,
    last_updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_users_role ON users (role);

-- ---------------------------------------------------------------------------
-- sessions - issued on login, checked on every request (SDD 13.1).
-- ---------------------------------------------------------------------------
CREATE TABLE sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at  TEXT NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions (user_id);

-- ---------------------------------------------------------------------------
-- system_parameter - versioned business-rule constants (SDD ADR-3). The next
-- correction is a data change an Owner makes, not a code deployment.
-- ---------------------------------------------------------------------------
CREATE TABLE system_parameter (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    value            REAL NOT NULL,
    effective_date   TEXT NOT NULL,
    updated_by       TEXT,
    last_updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_system_parameter_lookup ON system_parameter (name, effective_date);

-- Seeds (SDD 9.1 / 19). testing_density_deduction: final value 10, per fuel,
-- always (SDD 9 row 1). trial_balance_alert_threshold: +/-Rs100 (SDD 9 row 8).
INSERT INTO system_parameter (name, value, effective_date, updated_by) VALUES
    ('testing_density_deduction',      10,  '2026-08-28', 'seed'),
    ('trial_balance_alert_threshold',  100, '2026-08-01', 'seed');

-- ---------------------------------------------------------------------------
-- rate_master - Buy/Sell rate per fuel (HS/MS) and per oil SKU, versioned by
-- effective_date (SDD 8.2). Daily Sales Entry gas rows read SELL rate only
-- (SDD 9 row 3); Trial Balance Stock Value reads BUY rate (SDD 9 row 6).
-- ---------------------------------------------------------------------------
CREATE TABLE rate_master (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key         TEXT NOT NULL,   -- 'HS','MS','oil1'..'oil5'
    item_label       TEXT NOT NULL,
    buy_rate         REAL,            -- NULL for oil SKUs (no buy/sell split, SDD session log 49)
    sell_rate        REAL NOT NULL,
    effective_date   TEXT NOT NULL,
    updated_by       TEXT,
    last_updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_rate_master_lookup ON rate_master (item_key, effective_date);

-- Seed rates - figures used throughout the BRD/SDD worked examples.
INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, effective_date, updated_by) VALUES
    ('HS',   'Diesel (HS)',                 101.50, 105.36, '2026-08-11', 'seed'),
    ('MS',   'Petrol (MS)',                 112.30, 117.70, '2026-08-11', 'seed'),
    ('oil1', '2T/1.20 ML Total#',           NULL,    62.00, '2026-08-11', 'seed'),
    ('oil2', '2T/2.40 ML Total#',           NULL,   118.00, '2026-08-11', 'seed'),
    ('oil3', 'Acid Water Total 1 Lts',      NULL,    30.00, '2026-08-11', 'seed'),
    ('oil4', 'Acid Water Total 5 Lts',      NULL,   130.00, '2026-08-11', 'seed'),
    ('oil5', '20/40 Engine Total in Lts',   NULL,   280.00, '2026-08-11', 'seed');

-- ---------------------------------------------------------------------------
-- user_preference - per-user theme / language (SDD 8.2). scope kept simple
-- (per-user) pending the global-vs-per-form decision (SDD 19 item 5).
-- ---------------------------------------------------------------------------
CREATE TABLE user_preference (
    user_id          INTEGER PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    theme_accent     TEXT NOT NULL DEFAULT 'orange' CHECK (theme_accent IN ('orange', 'blue', 'red')),
    language         TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'te')),
    last_updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ---------------------------------------------------------------------------
-- audit_log - one row per write anywhere in the system (SDD 13.4). Client
-- called this non-negotiable.
-- ---------------------------------------------------------------------------
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name  TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    actor       TEXT NOT NULL,
    old_value   TEXT,   -- JSON snapshot, NULL on create
    new_value   TEXT,   -- JSON snapshot, NULL on delete
    ts          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_audit_log_record ON audit_log (table_name, record_id);
CREATE INDEX idx_audit_log_ts ON audit_log (ts);

-- ---------------------------------------------------------------------------
-- scheduler_run - bookkeeping for the 23:59 IST carry-forward job so
-- catch-up-on-startup can tell whether a night was missed (SDD 7.7).
-- ---------------------------------------------------------------------------
CREATE TABLE scheduler_run (
    job_name        TEXT NOT NULL,
    for_date        TEXT NOT NULL,   -- the shift_date whose readings were carried forward
    ran_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (job_name, for_date)
);
