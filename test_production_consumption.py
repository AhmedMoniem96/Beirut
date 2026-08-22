import sqlite3

from beirut_pos.apps.jewelry.services import db


def test_list_production_consumption_returns_recorded_cost_and_material_names(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE jw_materials (id INTEGER PRIMARY KEY, name_ar TEXT, name_en TEXT)"
    )
    conn.execute(
        """CREATE TABLE jw_production_consumption (
            id INTEGER PRIMARY KEY,
            production_order_id INTEGER,
            material_id INTEGER,
            qty_consumed REAL,
            cost_at_time REAL
        )"""
    )
    conn.execute("INSERT INTO jw_materials VALUES (1, 'ذهب', 'Gold')")
    conn.execute("INSERT INTO jw_materials VALUES (2, 'فضة', 'Silver')")
    conn.execute("INSERT INTO jw_production_consumption VALUES (1, 10, 1, 2.5, 30)")
    conn.execute("INSERT INTO jw_production_consumption VALUES (2, 11, 2, 4, 8)")
    conn.commit()
    monkeypatch.setattr(db, "get_conn", lambda: conn)

    rows = db.list_production_consumption(10)

    assert len(rows) == 1
    assert rows[0].material_name_ar == "ذهب"
    assert rows[0].material_name_en == "Gold"
    assert rows[0].qty_consumed == 2.5
    assert rows[0].cost_at_time == 30
