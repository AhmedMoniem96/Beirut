import sqlite3
import sys
import types

fake_core_db = types.ModuleType("beirut_pos.core.db")
fake_core_db.get_conn = lambda: None
sys.modules.setdefault("beirut_pos.core.db", fake_core_db)
from beirut_pos.apps.jewelry.services import reports


def _database(tmp_path, monkeypatch):
    path = tmp_path / "reports.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """CREATE TABLE jw_invoices (
                   id INTEGER PRIMARY KEY, invoice_no TEXT, datetime TEXT, txn_type TEXT,
                   customer_name TEXT, order_source TEXT, website_order_ref TEXT,
                   delivery_enabled INTEGER, delivery_company_id INTEGER, delivery_status_id INTEGER,
                   delivery_fee REAL, subtotal REAL, discount REAL, total REAL,
                   payment_method TEXT, payment_status TEXT);
               CREATE TABLE jw_delivery_companies (id INTEGER PRIMARY KEY, name TEXT);
               CREATE TABLE jw_statuses (
                   id INTEGER PRIMARY KEY, status_group TEXT, name_ar TEXT, name_en TEXT);
               INSERT INTO jw_delivery_companies VALUES (1, 'In-house Delivery');
               INSERT INTO jw_delivery_companies VALUES (2, 'Courier');
               INSERT INTO jw_statuses VALUES (1, 'DELIVERY', 'قيد الانتظار', 'Pending');
               INSERT INTO jw_invoices VALUES
                 (1, 'POS-1', '2026-08-28T09:00:00', 'sale', 'POS Customer', 'in_store', '',
                  0, 2, 1, 99, 600, 0, 600, 'Cash', 'Paid'),
                 (2, 'WEB-1', '2026-08-28T10:00:00', 'sale', 'Web Customer', 'website', 'WEB-00123',
                  0, NULL, NULL, 0, 400, 0, 400, 'Card', 'Paid'),
                 (3, 'POS-2', '2026-08-28T11:00:00', 'sale', 'Delivery Customer', 'in_store', '',
                  1, 1, 1, 70, 600, 0, 600, 'Cash', 'Paid'),
                 (4, 'WEB-2', '2026-08-28T12:00:00', 'sale', 'Both Customer', 'instagram', 'WEB-00999',
                  1, 2, 1, 25, 225, 0, 225, 'Card', 'Paid');"""
        )
    monkeypatch.setattr(reports, "get_conn", lambda: sqlite3.connect(path))
    return "2026-08-28T00:00:00", "2026-08-28T23:59:59"


def test_invoice_report_preserves_source_delivery_and_saved_total(tmp_path, monkeypatch):
    start, end = _database(tmp_path, monkeypatch)
    rows = {row.invoice_no: row for row in reports.invoice_report_rows(start, end)}

    assert rows["POS-1"].order_source == "in_store"
    assert not rows["POS-1"].delivery_enabled
    assert rows["POS-1"].delivery_company == ""
    assert rows["POS-1"].delivery_status_en == ""
    assert rows["POS-1"].delivery_fee == 0
    assert rows["WEB-1"].website_order_ref == "WEB-00123"
    assert rows["POS-2"].delivery_company == "In-house Delivery"
    assert rows["POS-2"].delivery_status_ar == "قيد الانتظار"
    assert rows["WEB-2"].order_source == "instagram"
    assert rows["WEB-2"].delivery_enabled
    # The persisted grand total is reported unchanged; the fee is only a breakdown.
    assert rows["POS-2"].total == 600
    assert rows["POS-2"].delivery_fee == 70


def test_invoice_report_source_delivery_and_company_filters(tmp_path, monkeypatch):
    start, end = _database(tmp_path, monkeypatch)
    assert {r.invoice_no for r in reports.invoice_report_rows(start, end, order_source="branch")} == {"POS-1", "POS-2"}
    assert {r.invoice_no for r in reports.invoice_report_rows(start, end, order_source="website")} == {"WEB-1", "WEB-2"}
    assert {r.invoice_no for r in reports.invoice_report_rows(start, end, delivery=True)} == {"POS-2", "WEB-2"}
    assert {r.invoice_no for r in reports.invoice_report_rows(start, end, delivery=False)} == {"POS-1", "WEB-1"}
    assert [r.invoice_no for r in reports.invoice_report_rows(start, end, delivery_company_id=1)] == ["POS-2"]


def test_delivery_kpi_is_separate_from_sales_total(tmp_path, monkeypatch):
    start, end = _database(tmp_path, monkeypatch)
    metrics = reports.sales_channel_metrics(start, end)
    sales = reports.sales_aggregate(start, end)
    assert metrics.delivery_orders == 2
    assert metrics.delivery_fees_total == 95
    assert metrics.website_orders == 2
    assert metrics.branch_orders == 2
    assert sales.net_sales == 1825  # Includes each saved invoice total exactly once.
