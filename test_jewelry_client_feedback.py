import sqlite3
import sys
import types

import pytest


core_db = types.ModuleType("beirut_pos.core.db")
core_db.get_conn = lambda: None
original_core_db = sys.modules.get("beirut_pos.core.db")
sys.modules["beirut_pos.core.db"] = core_db
from beirut_pos.apps.jewelry.services import db, reports
if original_core_db is None:
    del sys.modules["beirut_pos.core.db"]
else:
    sys.modules["beirut_pos.core.db"] = original_core_db


def _keep_open(connection):
    class ConnectionProxy:
        def __getattr__(self, name):
            if name == "close":
                return lambda: None
            return getattr(connection, name)
    return ConnectionProxy()


def test_product_cost_schema_guard_defaults_legacy_rows_to_zero():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE jw_products(id INTEGER PRIMARY KEY, price REAL NOT NULL)")
    conn.execute("INSERT INTO jw_products VALUES (1, 500)")
    db._ensure_column(conn.cursor(), "jw_products", "cost", "REAL NOT NULL DEFAULT 0")
    assert conn.execute("SELECT cost, price FROM jw_products").fetchone() == (0.0, 500.0)


def test_product_cost_and_selling_price_persist_independently(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE jw_products(id INTEGER PRIMARY KEY AUTOINCREMENT,
      name_ar TEXT, name_en TEXT, sku TEXT UNIQUE, barcode TEXT, barcode_type TEXT,
      price REAL, cost REAL DEFAULT 0, qty_on_hand REAL, min_qty REAL, category TEXT,
      handmade_flag INTEGER, stone_type TEXT, color TEXT)""")
    monkeypatch.setattr(db, "get_conn", lambda: _keep_open(conn))
    product_id = db.save_product(None, "خاتم", "Ring", "R1", "123", "", 500,
                                 2, 0, "Rings", False, "", "", cost=300)
    db.save_product(product_id, "خاتم", "Ring", "R1", "123", "", 500,
                    2, 0, "Rings", False, "", "", cost=350)
    assert conn.execute("SELECT cost, price FROM jw_products WHERE id=?", (product_id,)).fetchone() == (350, 500)


def _wage_connection():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE jw_workers(id INTEGER PRIMARY KEY, name TEXT, phone TEXT, role TEXT,
          default_wage REAL, wage_type TEXT, notes TEXT, active INTEGER);
        INSERT INTO jw_workers VALUES (1, 'Worker', '', '', 3000, 'monthly', '', 1);
        CREATE TABLE jw_purchases(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, category TEXT,
          vendor TEXT, description TEXT, amount REAL, payment_method TEXT, notes TEXT,
          linked_material_id INTEGER, material_qty REAL, worker_id INTEGER, wage_period TEXT,
          created_at TEXT, movement_type TEXT DEFAULT 'wage_payment',
          applied_amount REAL DEFAULT 0, remaining_amount REAL DEFAULT 0, gross_amount REAL DEFAULT 0);
        ALTER TABLE jw_purchases ADD COLUMN apply_to_month TEXT;
    """)
    return conn


def test_wage_advances_and_deductions_reduce_next_payment_oldest_first(monkeypatch):
    conn = _wage_connection()
    monkeypatch.setattr(db, "get_conn", lambda: _keep_open(conn))
    db.create_wage_movement(worker_id=1, movement_type="advance", date="2026-01-01", amount=500)
    db.create_wage_movement(worker_id=1, movement_type="deduction", date="2026-01-02", amount=200)
    result = db.create_wage_movement(worker_id=1, movement_type="wage_payment", date="2026-01-31", amount=3000)
    assert result["net_payable"] == 2300
    assert conn.execute("SELECT movement_type, applied_amount, remaining_amount FROM jw_purchases ORDER BY id").fetchall()[:2] == [
        ("advance", 500.0, 0.0), ("deduction", 200.0, 0.0)]


def test_wage_balance_carries_forward_without_deleting_history(monkeypatch):
    conn = _wage_connection()
    monkeypatch.setattr(db, "get_conn", lambda: _keep_open(conn))
    advance = db.create_wage_movement(worker_id=1, movement_type="advance", date="2026-01-01", amount=1500)
    assert db.create_wage_movement(worker_id=1, movement_type="wage_payment", date="2026-01-02", amount=1000)["net_payable"] == 0
    assert conn.execute("SELECT remaining_amount FROM jw_purchases WHERE id=?", (advance["id"],)).fetchone()[0] == 500
    assert db.create_wage_movement(worker_id=1, movement_type="wage_payment", date="2026-02-01", amount=1000)["net_payable"] == 500
    assert conn.execute("SELECT COUNT(*), remaining_amount FROM jw_purchases WHERE id=?", (advance["id"],)).fetchone() == (1, 0.0)


def test_attach_customer_changes_no_financial_or_stock_data(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
      CREATE TABLE jw_customers(phone TEXT PRIMARY KEY, name TEXT, email TEXT, address TEXT, notes TEXT, created_at TEXT);
      INSERT INTO jw_customers VALUES ('22', 'Customer B', '', '', '', 'now');
      CREATE TABLE jw_invoices(invoice_no TEXT, customer_id TEXT, customer_name TEXT, customer_phone TEXT, total REAL);
      INSERT INTO jw_invoices VALUES ('INV-1', NULL, '', '', 500);
      CREATE TABLE jw_products(id INTEGER, qty_on_hand REAL);
      INSERT INTO jw_products VALUES (1, 7);
    """)
    monkeypatch.setattr(db, "get_conn", lambda: _keep_open(conn))
    db.attach_customer_to_invoice("INV-1", "22")
    assert conn.execute("SELECT customer_id, customer_name, customer_phone, total FROM jw_invoices").fetchone() == ("22", "Customer B", "22", 500.0)
    assert conn.execute("SELECT qty_on_hand FROM jw_products").fetchone()[0] == 7


def test_latest_material_purchase_cost(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE jw_purchases(id INTEGER, date TEXT, category TEXT, linked_material_id INTEGER, material_qty REAL, amount REAL, created_at TEXT)")
    conn.executemany("INSERT INTO jw_purchases VALUES (?, ?, 'Material Purchase', 2, ?, ?, ?)", [
        (1, "2026-01-01", 2.5, 1000, "2026-01-01T09:00:00"),
        (2, "2026-02-01", 2.5, 1125, "2026-02-01T09:00:00")])
    monkeypatch.setattr(db, "get_conn", lambda: _keep_open(conn))
    assert db.latest_material_purchase_unit_cost(2) == 450


def _return_connection(returned=0):
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
      CREATE TABLE jw_invoices(id INTEGER PRIMARY KEY, invoice_no TEXT, txn_type TEXT,
        payment_status TEXT, customer_id TEXT, customer_name TEXT, customer_phone TEXT);
      INSERT INTO jw_invoices VALUES (1, 'INV-5', 'sale', 'PAID', NULL, '', '');
      CREATE TABLE jw_invoice_items(id INTEGER PRIMARY KEY, invoice_id INTEGER, product_id INTEGER,
        product_name TEXT, product_code TEXT, qty REAL, unit_price REAL,
        item_type TEXT DEFAULT 'product', material_id INTEGER, unit TEXT DEFAULT '');
      INSERT INTO jw_invoice_items VALUES (10, 1, 7, 'Ring', 'R-7', 5, 100, 'product', NULL, 'pcs');
      CREATE TABLE jw_invoice_item_returns(source_invoice_item_id INTEGER, qty_returned REAL);
    """)
    if returned:
        conn.execute("INSERT INTO jw_invoice_item_returns VALUES (10, ?)", (returned,))
    conn.commit()
    return conn


@pytest.mark.parametrize(("returned", "remaining"), [(0, 5), (2, 3)])
def test_remaining_return_quantity_reuses_recorded_returns(monkeypatch, returned, remaining):
    conn = _return_connection(returned)
    monkeypatch.setattr(db, "get_conn", lambda: _keep_open(conn))
    items = db.fetch_source_invoice_items_with_remaining_returnable_qty("INV-5")
    assert items[0].remaining_qty == remaining


def test_return_above_remaining_is_blocked(monkeypatch):
    conn = _return_connection(2)
    monkeypatch.setattr(db, "get_conn", lambda: _keep_open(conn))
    monkeypatch.setattr(db, "get_config_value", lambda *_args: "original_sold_price")
    with pytest.raises(ValueError, match="remaining quantity"):
        db.create_return_invoice_from_source(
            "INV-5", "Cashier", "Return",
            [{"source_invoice_item_id": 10, "qty": 4}],
        )


def test_expense_report_excludes_deduction_and_does_not_double_count_advance(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
      CREATE TABLE jw_workers(id INTEGER PRIMARY KEY, name TEXT);
      INSERT INTO jw_workers VALUES (1, 'Worker');
      CREATE TABLE jw_materials(id INTEGER, name_en TEXT, name_ar TEXT);
      CREATE TABLE jw_purchases(id INTEGER PRIMARY KEY, date TEXT, category TEXT, vendor TEXT,
        description TEXT, amount REAL, payment_method TEXT, worker_id INTEGER, wage_period TEXT,
        linked_material_id INTEGER, material_qty REAL, movement_type TEXT);
      INSERT INTO jw_purchases VALUES
        (1, '2026-01-01', 'Worker Wage', '', '', 500, '', 1, '', NULL, NULL, 'advance'),
        (2, '2026-01-31', 'Worker Wage', '', '', 2500, '', 1, 'monthly', NULL, NULL, 'wage_payment'),
        (3, '2026-01-15', 'Worker Wage', '', '', 200, '', 1, '', NULL, NULL, 'deduction');
    """)
    monkeypatch.setattr(reports, "get_conn", lambda: _keep_open(conn))
    data = reports.expense_report_data("2026-01-01", "2026-01-31")
    assert data["total_expenses"] == 3000
    assert sum(row.total_paid for row in data["worker_wages"]) == 3000
    assert all(row.amount != 200 for row in data["purchases"])
