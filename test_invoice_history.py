import sqlite3
import sys
import types


# The jewelry DB service only needs this symbol from the application's
# SQLAlchemy-backed core module; isolate these sqlite query tests from that
# optional application dependency.
core_db = types.ModuleType("beirut_pos.core.db")
core_db.get_conn = lambda: None
original_core_db = sys.modules.get("beirut_pos.core.db")
sys.modules["beirut_pos.core.db"] = core_db

from beirut_pos.apps.jewelry.services import db

if original_core_db is None:
    del sys.modules["beirut_pos.core.db"]
else:
    sys.modules["beirut_pos.core.db"] = original_core_db


def _history_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE jw_statuses (id INTEGER PRIMARY KEY, name_ar TEXT, name_en TEXT);
        CREATE TABLE jw_invoices (
            id INTEGER PRIMARY KEY,
            invoice_no TEXT,
            datetime TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            total REAL,
            paid_total REAL,
            remaining_total REAL,
            payment_due_date TEXT,
            payment_status TEXT,
            payment_order_status_id INTEGER,
            order_source TEXT,
            website_order_ref TEXT,
            txn_type TEXT
        );
        CREATE TABLE jw_invoice_items (invoice_id INTEGER, product_id INTEGER);
        """
    )
    conn.executemany(
        """INSERT INTO jw_invoices
           (id, invoice_no, datetime, total, paid_total, remaining_total,
            payment_status, txn_type)
           VALUES (?, ?, ?, 100, ?, ?, ?, 'sale')""",
        [
            (1, "INV-PAID", "2024-01-01T10:00:00", 100, 0, "PAID"),
            (2, "INV-PARTIAL", "2025-01-01T10:00:00", 50, 50, "PARTIAL"),
            (3, "INV-UNPAID", "2026-01-01T10:00:00", 0, 100, "UNPAID"),
        ],
    )
    return conn


def test_invoice_history_all_status_does_not_filter_existing_invoices(monkeypatch):
    conn = _history_connection()
    monkeypatch.setattr(db, "get_conn", lambda: conn)

    rows = db.list_invoice_history(status_filter="ALL")

    assert [row.invoice_no for row in rows] == [
        "INV-UNPAID",
        "INV-PARTIAL",
        "INV-PAID",
    ]


def test_invoice_history_default_remains_unpaid_and_partial(monkeypatch):
    conn = _history_connection()
    monkeypatch.setattr(db, "get_conn", lambda: conn)

    rows = db.list_invoice_history()

    assert [row.invoice_no for row in rows] == ["INV-UNPAID", "INV-PARTIAL"]
