import sqlite3

from beirut_pos.apps.jewelry.services import reports
from beirut_pos.apps.jewelry.services import db
from beirut_pos.apps.jewelry.services import auth


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


def test_completed_batch_history_is_unchanged_after_design_edits(tmp_path, monkeypatch):
    path = tmp_path / "snapshots.sqlite"
    monkeypatch.setattr(db, "get_conn", lambda: sqlite3.connect(path))
    monkeypatch.setattr(reports, "get_conn", lambda: sqlite3.connect(path))
    monkeypatch.setattr(auth, "get_conn", lambda: sqlite3.connect(path))
    db.init_jewelry_db()

    with sqlite3.connect(path) as conn:
        conn.execute(
            """INSERT INTO jw_products
               (id, name_ar, name_en, sku, barcode, barcode_type, price,
                qty_on_hand, min_qty, category, handmade_flag, stone_type, color)
               VALUES (1, 'خاتم', 'Ring', 'R1', '', 'CODE128', 100, 0, 0, '', 1, '', '')"""
        )
        conn.execute(
            """INSERT INTO jw_materials
               (id, name_ar, name_en, code, qty_on_hand, unit, min_qty, cost_per_unit)
               VALUES (1, 'ذهب', 'Gold', 'G1', 100, 'g', 0, 10)"""
        )
        conn.execute(
            """INSERT INTO jw_boms
               (id, product_id, name, active, labor_cost, packaging_cost, other_cost)
               VALUES (1, 1, 'Ring design', 1, 5, 2, 3)"""
        )
        conn.execute(
            "INSERT INTO jw_bom_lines(id, bom_id, material_id, qty_required) VALUES (1, 1, 1, 2)"
        )

    result = db.produce_from_bom(1, 2)
    before = reports.production_history("2000", "2999", "all", None)[0]

    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE jw_bom_lines SET qty_required = 9 WHERE id = 1")
        conn.execute("UPDATE jw_materials SET cost_per_unit = 70 WHERE id = 1")
        conn.execute("UPDATE jw_products SET price = 250 WHERE id = 1")
        conn.execute(
            "UPDATE jw_boms SET labor_cost = 30, packaging_cost = 40, other_cost = 50 WHERE id = 1"
        )

    after = reports.production_history("2000", "2999", "all", None)[0]
    assert after == before
    assert (after.material_cost, after.extra_cost, after.total_cost) == (40, 20, 60)
    assert (after.selling_price, after.profit, after.margin_pct) == (200, 140, 70)
    with sqlite3.connect(path) as conn:
        detail = conn.execute(
            """SELECT qty_consumed, cost_at_time
               FROM jw_production_consumption WHERE production_order_id = ?""",
            (result["production_order_id"],),
        ).fetchone()
    assert detail == (4, 10)
