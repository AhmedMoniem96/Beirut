import sqlite3

from beirut_pos.apps.jewelry.services import db as jewelry_db


def _setup_conn():
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE jw_invoices (
               id INTEGER PRIMARY KEY, invoice_no TEXT, txn_type TEXT, payment_status TEXT,
               customer_name TEXT, datetime TEXT, payment_method TEXT, total REAL
           )"""
    )
    cur.execute("CREATE TABLE jw_invoice_items (id INTEGER PRIMARY KEY, invoice_id INTEGER, product_id INTEGER, product_name TEXT, product_code TEXT, qty REAL, unit_price REAL)")
    cur.execute("CREATE TABLE jw_invoice_item_returns (id INTEGER PRIMARY KEY, source_invoice_item_id INTEGER, qty_returned REAL)")
    return conn


def test_load_existing_paid_invoice_items(monkeypatch):
    conn = _setup_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO jw_invoices(id, invoice_no, txn_type, payment_status) VALUES (1,'JINV-00003','sale','PAID')")
    cur.execute("INSERT INTO jw_invoice_items(id, invoice_id, product_id, product_name, product_code, qty, unit_price) VALUES (10,1,7,'Ring','R-7',2,860)")
    conn.commit()
    monkeypatch.setattr(jewelry_db, 'get_conn', lambda: conn)

    items = jewelry_db.fetch_source_invoice_items_with_remaining_returnable_qty('JINV-00003')
    assert len(items) == 1
    assert items[0].remaining_qty == 2.0


def test_missing_invoice_number(monkeypatch):
    conn = _setup_conn()
    monkeypatch.setattr(jewelry_db, 'get_conn', lambda: conn)
    assert jewelry_db.fetch_source_invoice_items_with_remaining_returnable_qty('JINV-40404') == []


def test_invoice_with_no_returnable_quantity(monkeypatch):
    conn = _setup_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO jw_invoices(id, invoice_no, txn_type, payment_status) VALUES (1,'JINV-00003','sale','PAID')")
    cur.execute("INSERT INTO jw_invoice_items(id, invoice_id, product_id, product_name, product_code, qty, unit_price) VALUES (10,1,7,'Ring','R-7',2,860)")
    cur.execute("INSERT INTO jw_invoice_item_returns(source_invoice_item_id, qty_returned) VALUES (10,2)")
    conn.commit()
    monkeypatch.setattr(jewelry_db, 'get_conn', lambda: conn)

    assert jewelry_db.fetch_source_invoice_items_with_remaining_returnable_qty('JINV-00003') == []


def test_invoice_already_returned(monkeypatch):
    conn = _setup_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO jw_invoices(id, invoice_no, txn_type, payment_status) VALUES (1,'JINV-00003','sale','PAID')")
    cur.execute("INSERT INTO jw_invoice_items(id, invoice_id, product_id, product_name, product_code, qty, unit_price) VALUES (10,1,7,'Ring','R-7',1,860)")
    cur.execute("INSERT INTO jw_invoice_item_returns(source_invoice_item_id, qty_returned) VALUES (10,1)")
    conn.commit()
    monkeypatch.setattr(jewelry_db, 'get_conn', lambda: conn)

    assert jewelry_db.fetch_source_invoice_items_with_remaining_returnable_qty('JINV-00003') == []


def test_fetch_return_source_invoice_metadata(monkeypatch):
    conn = _setup_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO jw_invoices(
               id, invoice_no, txn_type, payment_status, customer_name, datetime, payment_method, total
           ) VALUES (1, 'JINV-00003', 'sale', 'PAID', 'Maya', '2026-08-01T10:30:00', 'Cash', 1720)"""
    )
    conn.commit()
    monkeypatch.setattr(jewelry_db, 'get_conn', lambda: conn)

    invoice = jewelry_db.fetch_return_source_invoice('JINV-00003')

    assert invoice is not None
    assert invoice.customer_name == 'Maya'
    assert invoice.payment_method == 'Cash'
    assert invoice.total == 1720.0
