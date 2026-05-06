import sqlite3

from beirut_pos.apps.jewelry.services import reports


def test_production_history_cost_profit(monkeypatch):
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE jw_products (id INTEGER PRIMARY KEY, name_en TEXT, name_ar TEXT, price REAL)")
    cur.execute(
        "CREATE TABLE jw_production_orders (id INTEGER PRIMARY KEY, order_no TEXT, datetime TEXT, status TEXT, product_id INTEGER, qty_to_produce REAL, qty_produced REAL, labor_cost REAL, overhead_cost REAL)"
    )
    cur.execute(
        "CREATE TABLE jw_production_consumption (id INTEGER PRIMARY KEY, production_order_id INTEGER, material_id INTEGER, qty_consumed REAL, cost_at_time REAL)"
    )

    cur.execute("INSERT INTO jw_products VALUES (1, 'Ring', 'خاتم', 100)")
    cur.execute(
        "INSERT INTO jw_production_orders VALUES (1, 'PO-1', '2026-05-01T10:00:00', 'done', 1, 2, 2, 15, 5)"
    )
    cur.execute("INSERT INTO jw_production_consumption VALUES (1, 1, 1, 3, 10)")
    conn.commit()

    monkeypatch.setattr(reports, "get_conn", lambda: conn)

    rows = reports.production_history("2026-05-01T00:00:00", "2026-05-02T23:59:59", "all", None)
    assert len(rows) == 1
    row = rows[0]
    assert row.material_cost == 30
    assert row.extra_cost == 20
    assert row.total_cost == 50
    assert row.selling_price == 200
    assert row.profit == 150
    assert row.margin_pct == 75
