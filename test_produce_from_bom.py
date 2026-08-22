import sqlite3
import sys
import types

import pytest

# Keep these focused service tests independent of SQLAlchemy initialization.
fake_core_db = types.ModuleType("beirut_pos.core.db")
fake_core_db.get_conn = lambda: None
sys.modules.setdefault("beirut_pos.core.db", fake_core_db)

from beirut_pos.apps.jewelry.services import db


@pytest.fixture
def production_db(tmp_path, monkeypatch):
    path = tmp_path / "production.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE jw_products(id INTEGER PRIMARY KEY, name_ar TEXT NOT NULL,
          name_en TEXT NOT NULL, qty_on_hand REAL NOT NULL);
        CREATE TABLE jw_materials(id INTEGER PRIMARY KEY, name_ar TEXT NOT NULL,
          name_en TEXT NOT NULL, unit TEXT, qty_on_hand REAL NOT NULL,
          cost_per_unit REAL NOT NULL);
        CREATE TABLE jw_boms(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL,
          name TEXT NOT NULL);
        CREATE TABLE jw_bom_lines(id INTEGER PRIMARY KEY, bom_id INTEGER NOT NULL,
          material_id INTEGER NOT NULL, qty_required REAL NOT NULL);
        CREATE TABLE jw_production_orders(id INTEGER PRIMARY KEY AUTOINCREMENT,
          order_no TEXT NOT NULL UNIQUE, datetime TEXT NOT NULL, status TEXT NOT NULL,
          product_id INTEGER NOT NULL, qty_to_produce REAL NOT NULL,
          qty_produced REAL NOT NULL, labor_cost REAL NOT NULL,
          overhead_cost REAL NOT NULL, notes TEXT, bom_id INTEGER);
        CREATE TABLE jw_production_consumption(id INTEGER PRIMARY KEY AUTOINCREMENT,
          production_order_id INTEGER NOT NULL, material_id INTEGER NOT NULL,
          qty_consumed REAL NOT NULL, cost_at_time REAL NOT NULL);
        INSERT INTO jw_products VALUES (1, 'خاتم', 'Ring', 2);
        INSERT INTO jw_materials VALUES (10, 'ذهب', 'Gold', 'g', 100, 12.5);
        INSERT INTO jw_materials VALUES (11, 'حجر', 'Stone', 'pc', 20, 3);
        INSERT INTO jw_boms VALUES (20, 1, 'Ring BOM');
        INSERT INTO jw_bom_lines VALUES (30, 20, 10, 2.5);
        INSERT INTO jw_bom_lines VALUES (31, 20, 11, 1);
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "get_conn", lambda: sqlite3.connect(path))
    return path


def rows(path, sql):
    with sqlite3.connect(path) as conn:
        return conn.execute(sql).fetchall()


def test_produces_multiple_materials_with_multiplied_quantities(production_db):
    result = db.produce_from_bom(20, 4, labor_cost=7, overhead_cost=2)

    assert result["success"] is True
    assert result["status"] == "done"
    assert rows(production_db, "SELECT qty_on_hand FROM jw_materials ORDER BY id") == [(90.0,), (16.0,)]
    assert rows(production_db, "SELECT qty_consumed FROM jw_production_consumption ORDER BY material_id") == [(10.0,), (4.0,)]
    assert rows(production_db, "SELECT qty_on_hand FROM jw_products") == [(6.0,)]


def test_shortage_returns_details_without_mutations(production_db):
    result = db.produce_from_bom(20, 30)

    assert result["success"] is False
    assert result["shortages"] == [{
        "material_name": "Stone", "material_name_ar": "حجر",
        "material_name_en": "Stone", "unit": "pc", "required": 30.0,
        "available": 20.0, "missing": 10.0,
    }]
    assert rows(production_db, "SELECT qty_on_hand FROM jw_materials ORDER BY id") == [(100.0,), (20.0,)]
    assert rows(production_db, "SELECT COUNT(*) FROM jw_production_orders") == [(0,)]


@pytest.mark.parametrize("bom_id, quantity", [(999, 1), (20, 0), (20, -1)])
def test_rejects_missing_bom_and_non_positive_quantity(production_db, bom_id, quantity):
    with pytest.raises(ValueError):
        db.produce_from_bom(bom_id, quantity)


def test_rejects_missing_product_and_lines(production_db):
    with sqlite3.connect(production_db) as conn:
        conn.execute("INSERT INTO jw_boms VALUES (21, 999, 'Missing product')")
        conn.execute("INSERT INTO jw_boms VALUES (22, 1, 'No lines')")
    with pytest.raises(ValueError, match="product"):
        db.produce_from_bom(21, 1)
    with pytest.raises(ValueError, match="lines"):
        db.produce_from_bom(22, 1)


def test_mid_operation_failure_rolls_back_everything(production_db):
    with sqlite3.connect(production_db) as conn:
        conn.execute("""CREATE TRIGGER fail_second_consumption BEFORE INSERT ON
          jw_production_consumption WHEN NEW.material_id = 11
          BEGIN SELECT RAISE(FAIL, 'injected failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        db.produce_from_bom(20, 2)
    assert rows(production_db, "SELECT qty_on_hand FROM jw_materials ORDER BY id") == [(100.0,), (20.0,)]
    assert rows(production_db, "SELECT COUNT(*) FROM jw_production_orders") == [(0,)]


def test_consumption_keeps_historical_cost_snapshot(production_db):
    result = db.produce_from_bom(20, 1)
    with sqlite3.connect(production_db) as conn:
        conn.execute("UPDATE jw_materials SET cost_per_unit = 99 WHERE id = 10")
    assert rows(production_db, f"SELECT cost_at_time FROM jw_production_consumption WHERE production_order_id={result['production_order_id']} ORDER BY material_id") == [(12.5,), (3.0,)]


def test_repeated_invocations_create_independent_completed_orders(production_db):
    first = db.produce_from_bom(20, 1)
    second = db.produce_from_bom(20, 2)
    assert first["production_order_id"] != second["production_order_id"]
    assert rows(production_db, "SELECT status, qty_produced FROM jw_production_orders ORDER BY id") == [("done", 1.0), ("done", 2.0)]
    assert rows(production_db, "SELECT qty_on_hand FROM jw_products") == [(5.0,)]
