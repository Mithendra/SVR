-- 0004_inventory.sql - Inventory Tracking (SDD 5.10, BRD 33/35). Five oil SKUs,
-- name-identical to the Daily Sales Entry / Rate Master keys so the cross-module
-- lookups line up.
--
-- on_hand is the tracked "Opening Stock". It is moved only by Restock Entry (+qty)
-- and Owner correction. The Sold decrement happens when Daily Trial Balance is
-- finalized (that module is not built yet) - until then GET /inventory shows
-- Sold (Today) as a live preview summed from that day's Daily Sales Entry rows.

CREATE TABLE inventory_item (
    item_key        TEXT PRIMARY KEY,          -- 'oil1'..'oil5'
    item_label      TEXT NOT NULL,
    unit            TEXT NOT NULL DEFAULT 'unit',
    on_hand         REAL NOT NULL DEFAULT 0,
    reorder_level   REAL NOT NULL DEFAULT 0,
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO inventory_item (item_key, item_label, unit, on_hand, reorder_level) VALUES
    ('oil1', '2T/1.20 ML Total#',         'pcs',   40,  12),
    ('oil2', '2T/2.40 ML Total#',         'pcs',   30,  10),
    ('oil3', 'Acid Water Total 1 Lts',    'ltr',   60,  20),
    ('oil4', 'Acid Water Total 5 Lts',    'pcs',   18,   6),
    ('oil5', '20/40 Engine Total in Lts', 'ltr',  120,  40);

CREATE TABLE restock_entry (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    restock_date  TEXT NOT NULL,
    item_key      TEXT NOT NULL REFERENCES inventory_item (item_key),
    quantity      REAL NOT NULL,
    supplier_ref  TEXT,
    received_by   TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_restock_date ON restock_entry (restock_date);
CREATE INDEX idx_restock_item ON restock_entry (item_key, restock_date);
