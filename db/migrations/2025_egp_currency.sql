-- Currency migration introducing LE decimal columns and purchases table.
-- This script is provided for reference; SQLite will patch columns at runtime.
ALTER TABLE products ADD COLUMN price_le NUMERIC(12,2);
UPDATE products SET price_le = price_cents / 100.0 WHERE price_le IS NULL;

ALTER TABLE product_options ADD COLUMN price_delta_le NUMERIC(12,2);
UPDATE product_options SET price_delta_le = price_delta_cents / 100.0 WHERE price_delta_le IS NULL;

ALTER TABLE order_items ADD COLUMN price_le NUMERIC(12,2);
UPDATE order_items SET price_le = price_cents / 100.0 WHERE price_le IS NULL;

ALTER TABLE payments ADD COLUMN amount_le NUMERIC(12,2);
UPDATE payments SET amount_le = amount_cents / 100.0 WHERE amount_le IS NULL;

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    supplier TEXT,
    description TEXT NOT NULL,
    payment_method TEXT CHECK(payment_method IN ('cash','card','transfer')),
    amount_le NUMERIC(12,2) NOT NULL,
    attachment_path TEXT,
    linked_order_id INTEGER,
    deleted_at TEXT,
    deleted_by TEXT,
    delete_reason TEXT
);
