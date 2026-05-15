import sqlite3

from beirut_pos.apps.jewelry.services import reports as jewelry_reports


def _setup_conn():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE jw_invoices (
            id INTEGER PRIMARY KEY,
            datetime TEXT,
            txn_type TEXT,
            subtotal REAL,
            discount REAL,
            total REAL
        )"""
    )
    cur.execute(
        """CREATE TABLE jw_purchases (
            id INTEGER PRIMARY KEY,
            date TEXT,
            category TEXT,
            vendor TEXT,
            description TEXT,
            amount REAL,
            payment_method TEXT,
            worker_id INTEGER,
            linked_material_id INTEGER,
            material_qty REAL,
            wage_period TEXT
        )"""
    )
    cur.execute("CREATE TABLE jw_workers (id INTEGER PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE jw_materials (id INTEGER PRIMARY KEY, name_en TEXT, name_ar TEXT)")
    return conn


def test_cash_profit_includes_purchases_bills_and_wages(monkeypatch):
    conn = _setup_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO jw_invoices(id, datetime, txn_type, subtotal, discount, total) VALUES (1, '2026-01-10T10:00:00', 'sale', 1000, 0, 1000)"
    )
    cur.execute(
        "INSERT INTO jw_purchases(date, category, vendor, description, amount, payment_method) VALUES ('2026-01-10', 'Electricity Bill', 'Utility', 'January bill', 100, 'cash')"
    )
    cur.execute("INSERT INTO jw_workers(id, name) VALUES (1, 'Worker A')")
    cur.execute(
        "INSERT INTO jw_purchases(date, category, vendor, description, amount, payment_method, worker_id, wage_period) VALUES ('2026-01-10', 'Worker Wage', '', 'Daily wage', 200, 'cash', 1, 'daily')"
    )
    conn.commit()
    monkeypatch.setattr(jewelry_reports, "get_conn", lambda: conn)

    sales = jewelry_reports.sales_aggregate("2026-01-10T00:00:00", "2026-01-10T23:59:59")
    returns = jewelry_reports.returns_aggregate("2026-01-10T00:00:00", "2026-01-10T23:59:59")
    expenses = jewelry_reports.expense_report_data("2026-01-10T00:00:00", "2026-01-10T23:59:59")

    net_revenue = sales.net_sales - returns.return_total
    net_cash_profit = net_revenue - expenses["total_expenses"]
    assert net_cash_profit == 700

    cur.execute("INSERT INTO jw_materials(id, name_en, name_ar) VALUES (7, 'Silver', 'فضة')")
    cur.execute(
        "INSERT INTO jw_purchases(date, category, vendor, description, amount, payment_method, linked_material_id, material_qty) VALUES ('2026-01-10', 'Material Purchase', 'Metal Supplier', 'Silver stock', 300, 'cash', 7, 30)"
    )
    conn.commit()

    expenses_after_purchase = jewelry_reports.expense_report_data("2026-01-10T00:00:00", "2026-01-10T23:59:59")
    net_cash_profit_after_purchase = net_revenue - expenses_after_purchase["total_expenses"]

    assert net_cash_profit_after_purchase == 400
    assert expenses_after_purchase["material_expenses"] == 300
