import sqlite3
import sys
import types

import pytest


fake_core_db = types.ModuleType("beirut_pos.core.db")
fake_core_db.get_conn = lambda: None
sys.modules.setdefault("beirut_pos.core.db", fake_core_db)

from beirut_pos.apps.jewelry.services import db


@pytest.fixture
def design_db(tmp_path, monkeypatch):
    path = tmp_path / "design.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE jw_products(
              id INTEGER PRIMARY KEY AUTOINCREMENT, name_ar TEXT NOT NULL,
              name_en TEXT NOT NULL, sku TEXT NOT NULL UNIQUE, barcode TEXT,
              barcode_type TEXT, price REAL NOT NULL, qty_on_hand REAL NOT NULL,
              min_qty REAL NOT NULL, category TEXT, handmade_flag INTEGER NOT NULL,
              stone_type TEXT, color TEXT);
            CREATE TABLE jw_materials(id INTEGER PRIMARY KEY);
            CREATE TABLE jw_boms(id INTEGER PRIMARY KEY AUTOINCREMENT,
              product_id INTEGER NOT NULL REFERENCES jw_products(id),
              name TEXT NOT NULL, active INTEGER NOT NULL,
              labor_cost REAL NOT NULL DEFAULT 0,
              packaging_cost REAL NOT NULL DEFAULT 0,
              other_cost REAL NOT NULL DEFAULT 0);
            CREATE TABLE jw_bom_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,
              bom_id INTEGER NOT NULL REFERENCES jw_boms(id),
              material_id INTEGER NOT NULL REFERENCES jw_materials(id),
              qty_required REAL NOT NULL);
            CREATE TABLE jw_production_orders(id INTEGER PRIMARY KEY);
            CREATE TABLE jw_production_consumption(id INTEGER PRIMARY KEY);
            INSERT INTO jw_materials VALUES (10), (11);
            """
        )
    monkeypatch.setattr(db, "get_conn", lambda: sqlite3.connect(path))
    return path


def query(path, sql):
    with sqlite3.connect(path) as conn:
        return conn.execute(sql).fetchall()


def test_create_saves_product_and_bom_without_inventory_activity(design_db):
    product_id, bom_id = db.save_product_design(
        product_id=None, bom_id=None, name_ar="خاتم", name_en="Ring",
        sku="R-1", barcode="100", price=50, design_name="Summer Ring",
        active=True, lines=[(10, 2.5), (11, 1)],
    )

    assert query(design_db, "SELECT id, qty_on_hand FROM jw_products") == [(product_id, 0.0)]
    assert query(design_db, "SELECT id, product_id, name, active FROM jw_boms") == [
        (bom_id, product_id, "Summer Ring", 1)
    ]
    assert query(design_db, "SELECT material_id, qty_required FROM jw_bom_lines ORDER BY id") == [(10, 2.5), (11, 1.0)]
    assert query(design_db, "SELECT count(*) FROM jw_production_orders") == [(0,)]
    assert query(design_db, "SELECT count(*) FROM jw_production_consumption") == [(0,)]


def test_update_preserves_inventory_and_unrelated_product_attributes(design_db):
    with sqlite3.connect(design_db) as conn:
        cursor = conn.execute(
            """INSERT INTO jw_products VALUES
               (NULL, 'قديم', 'Old', 'OLD', 'old-code', 'EAN13', 20, 7, 3,
                'Limited', 0, 'Ruby', 'Red')"""
        )
        product_id = cursor.lastrowid
        cursor = conn.execute(
            "INSERT INTO jw_boms(product_id, name, active) VALUES(?, 'Old design', 1)",
            (product_id,),
        )
        bom_id = cursor.lastrowid
        conn.execute("INSERT INTO jw_bom_lines VALUES(NULL, ?, 10, 4)", (bom_id,))

    db.save_product_design(
        product_id=product_id, bom_id=bom_id, name_ar="جديد", name_en="New",
        sku="NEW", barcode="new-code", price=99, design_name="New design",
        active=False, lines=[(11, 3)],
    )

    assert query(design_db, "SELECT qty_on_hand, min_qty, category, handmade_flag, stone_type, color, barcode_type FROM jw_products") == [(7.0, 3.0, "Limited", 0, "Ruby", "Red", "EAN13")]
    assert query(design_db, "SELECT name, active FROM jw_boms") == [("New design", 0)]
    assert query(design_db, "SELECT material_id, qty_required FROM jw_bom_lines") == [(11, 3.0)]


def test_line_failure_rolls_back_new_product_and_design(design_db):
    with sqlite3.connect(design_db) as conn:
        conn.execute(
            """CREATE TRIGGER reject_line BEFORE INSERT ON jw_bom_lines
               BEGIN SELECT RAISE(FAIL, 'forced line failure'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced line failure"):
        db.save_product_design(
            product_id=None, bom_id=None, name_ar="فاشل", name_en="Failed",
            sku="FAIL", barcode="", price=1, design_name="Partial",
            active=True, lines=[(10, 1)],
        )

    assert query(design_db, "SELECT count(*) FROM jw_products") == [(0,)]
    assert query(design_db, "SELECT count(*) FROM jw_boms") == [(0,)]
    assert query(design_db, "SELECT count(*) FROM jw_bom_lines") == [(0,)]


def test_duplicate_saves_costs_without_modifying_source_design(design_db):
    source_product, source_bom = db.save_product_design(
        product_id=None, bom_id=None, name_ar="أصل", name_en="Original",
        sku="ORIGINAL", barcode="", price=100, design_name="Original design",
        active=True, lines=[(10, 1)], labor_cost=4, packaging_cost=2, other_cost=1,
    )

    copy_product, copy_bom = db.save_product_design(
        product_id=None, bom_id=None, name_ar="نسخة", name_en="Copy",
        sku="ORIGINAL-COPY", barcode="", price=100, design_name="Original design - Copy",
        active=True, lines=[(10, 1)], labor_cost=4, packaging_cost=2, other_cost=1,
    )

    assert (copy_product, copy_bom) != (source_product, source_bom)
    assert query(design_db, "SELECT name, labor_cost, packaging_cost, other_cost FROM jw_boms ORDER BY id") == [
        ("Original design", 4.0, 2.0, 1.0),
        ("Original design - Copy", 4.0, 2.0, 1.0),
    ]


def test_blank_design_barcode_is_generated_then_preserved_on_edit(design_db):
    product_id, bom_id = db.save_product_design(
        product_id=None, bom_id=None, name_ar="سوار", name_en="Bracelet",
        sku="B-1", barcode="", price=25, design_name="Bracelet design",
        active=True, lines=[(10, 1)],
    )
    generated = f"P{product_id:010d}"
    assert query(design_db, "SELECT barcode FROM jw_products") == [(generated,)]

    db.save_product_design(
        product_id=product_id, bom_id=bom_id, name_ar="سوار", name_en="Bracelet",
        sku="B-1", barcode="", price=30, design_name="Updated design",
        active=True, lines=[(11, 2)],
    )
    assert query(design_db, "SELECT barcode FROM jw_products") == [(generated,)]


def test_blank_sku_is_generated_once_and_preserved_on_edit(design_db):
    product_id, bom_id = db.save_product_design(
        product_id=None, bom_id=None, name_ar="سوار", name_en="Bracelet",
        sku="", barcode="", price=25, design_name="Bracelet design",
        active=True, lines=[(10, 1)],
    )
    generated = f"SKU{product_id:010d}"
    assert query(design_db, "SELECT sku FROM jw_products") == [(generated,)]

    db.save_product_design(
        product_id=product_id, bom_id=bom_id, name_ar="سوار", name_en="Bracelet",
        sku=generated, barcode="", price=30, design_name="Updated design",
        active=True, lines=[(11, 2)],
    )
    assert query(design_db, "SELECT sku FROM jw_products") == [(generated,)]
